"""API Gateway: o único ponto de entrada (porta 8000).

Ele não tem regra de negócio nenhuma. Só faz 3 coisas:
1. entrega a tela (index.html, app.js, estilo.css), então a tela continua no mesmo endereço;
2. olha o começo da rota e repassa pro serviço certo (tabela ROTAS abaixo);
3. /saude: pergunta pra cada serviço se ele está de pé e mostra tudo junto.

Quem confere o token são os próprios serviços (cada um confere o seu).
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from comum.seguranca_http import CabecalhosDeSeguranca

logging.basicConfig(level=logging.INFO, format="%(asctime)s [gateway] %(levelname)s %(message)s")
log = logging.getLogger("gateway")

WEB = Path(os.getenv("WEB_DIR", Path(__file__).parent.parent / "web"))

SERVICOS = {
    "usuarios": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
    "inventario": os.getenv("INVENTARIO_URL", "http://inventario:8000"),
    "chamados": os.getenv("CHAMADOS_URL", "http://chamados:8000"),
    "notificacoes": os.getenv("NOTIFICACOES_URL", "http://notificacoes:8000"),
}
NOMES = {"usuarios": "Usuários", "inventario": "Inventário", "chamados": "Chamados", "notificacoes": "Notificações"}

# primeiro pedaço da URL -> serviço
ROTAS = {
    "auth": "usuarios",
    "usuarios": "usuarios",
    "ativos": "inventario",
    "chamados": "chamados",
    "notificacoes": "notificacoes",
}

# cabeçalhos que eu repasso (o resto eu descarto, tipo cookie, host...)
REPASSA_IDA = ("authorization", "content-type", "accept")
REPASSA_VOLTA = ("content-type", "www-authenticate", "retry-after")

http: httpx.AsyncClient | None = None


@asynccontextmanager
async def ciclo_de_vida(app):
    global http
    # 10s: o Chamados pode demorar até ~3s esperando outro serviço, então dou folga
    http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=2.0))
    yield
    await http.aclose()


app = FastAPI(title="HelpDesk TI · API Gateway", version="3.0.0", lifespan=ciclo_de_vida,
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CabecalhosDeSeguranca)


# ---------- tela ----------

@app.get("/", include_in_schema=False)
def tela_inicial():
    return FileResponse(WEB / "index.html")


@app.get("/app.js", include_in_schema=False)
def script():
    return FileResponse(WEB / "app.js", media_type="text/javascript")


@app.get("/estilo.css", include_in_schema=False)
def estilo():
    return FileResponse(WEB / "estilo.css", media_type="text/css")


# ---------- saúde de todo mundo ----------

async def _saude_de(nome: str, url: str) -> tuple[str, dict]:
    try:
        r = await http.get(f"{url}/saude", timeout=1.5)
        if r.status_code != 200:
            return nome, {"status": "com problema"}
        detalhes = r.json()
        detalhes.pop("servico", None)
        detalhes["status"] = "no ar"
        return nome, detalhes
    except (httpx.HTTPError, ValueError):
        return nome, {"status": "fora do ar"}


@app.get("/saude")
async def saude():
    resultados = await asyncio.gather(*[_saude_de(n, u) for n, u in SERVICOS.items()])
    servicos = dict(resultados)
    tudo_ok = all(s["status"] == "no ar" for s in servicos.values())
    return {"gateway": "ok", "tudo_no_ar": tudo_ok, "servicos": servicos}


# ---------- repasse pros serviços ----------

@app.api_route("/{caminho:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def repassar(caminho: str, request: Request):
    servico = ROTAS.get(caminho.split("/")[0])
    if servico is None:
        return JSONResponse(status_code=404, content={"detail": "Rota não encontrada."})

    cabecalhos = {k: v for k, v in request.headers.items() if k.lower() in REPASSA_IDA}
    cabecalhos["x-forwarded-for"] = request.client.host if request.client else "-"
    url = f"{SERVICOS[servico]}/{caminho}"
    try:
        r = await http.request(request.method, url, params=request.query_params,
                               content=await request.body(), headers=cabecalhos)
    except httpx.HTTPError as erro:
        log.warning("%s fora do ar (%s)", servico, erro.__class__.__name__)
        return JSONResponse(status_code=503, headers={"Retry-After": "10"},
                            content={"detail": f"O serviço de {NOMES[servico]} está fora do ar no momento."})

    volta = {k: v for k, v in r.headers.items() if k.lower() in REPASSA_VOLTA}
    return Response(content=r.content, status_code=r.status_code, headers=volta)
