"""Teste rápido de ponta a ponta, passando pelo gateway (com o docker compose rodando).

    python3 infra/testar_fluxo.py

Só usa biblioteca padrão, não precisa instalar nada.
"""
import json
import time
import urllib.error
import urllib.request

GATEWAY = "http://localhost:8000"


def req(metodo, caminho, token=None, corpo=None):
    cab = {"Content-Type": "application/json"}
    if token:
        cab["Authorization"] = "Bearer " + token
    r = urllib.request.Request(GATEWAY + caminho, method=metodo, headers=cab,
                               data=json.dumps(corpo).encode() if corpo else None)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read() or b"null")


def login(email):
    return req("POST", "/auth/login", corpo={"email": email, "senha": "Helpdesk2026"})[1]["access_token"]


carla, ana = login("carla@empresa.com"), login("ana@empresa.com")
print("usuarios / ativos / chamados:", len(req("GET", "/usuarios", carla)[1]),
      len(req("GET", "/ativos", carla)[1]), len(req("GET", "/chamados", carla)[1]))

status, chamado = req("POST", "/chamados", carla, {"titulo": "Sem internet", "descricao": "cabo ok",
                                                   "prioridade": "alta", "ativo_id": 1})
print("abrir:", status)
cid = chamado["id"]
print("atribuir:", req("PATCH", f"/chamados/{cid}/atribuir", carla, {"tecnico_id": 4})[1]["status"])
print("resolver:", req("PATCH", f"/chamados/{cid}/status", carla, {"status": "resolvido"})[1]["status"])
print("fechar:", req("PATCH", f"/chamados/{cid}/status", carla, {"status": "fechado"})[1]["status"])

time.sleep(3)  # dá tempo do evento passar pelo Redis
print("notificações da Carla:", [n["tipo"] for n in req("GET", "/notificacoes", carla)[1]])
print("sem token:", req("GET", "/chamados")[0], "| Ana vendo chamado do Bruno (#2):", req("GET", "/chamados/2", ana)[0])
print("saúde:", {k: v["status"] for k, v in req("GET", "/saude")[1]["servicos"].items()})
