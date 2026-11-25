from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main

FORA = set()
PEDIDOS = []


def servicos_falsos(request: httpx.Request) -> httpx.Response:
    PEDIDOS.append(request)
    if request.url.host in FORA:
        raise httpx.ConnectError("fora", request=request)
    if request.url.path == "/saude":
        return httpx.Response(200, json={"servico": request.url.host, "status": "ok"})
    return httpx.Response(200, json={"quem_respondeu": request.url.host, "caminho": request.url.path})


@pytest.fixture
def cliente():
    FORA.clear()
    PEDIDOS.clear()
    with TestClient(main.app) as c:
        main.http = httpx.AsyncClient(transport=httpx.MockTransport(servicos_falsos))
        yield c


@pytest.mark.parametrize("rota,servico", [("/auth/login", "usuarios"), ("/usuarios/2", "usuarios"),
                                          ("/ativos", "inventario"), ("/chamados/painel", "chamados"),
                                          ("/notificacoes", "notificacoes")])
def test_cada_rota_vai_pro_servico_certo(cliente, rota, servico):
    r = cliente.get(rota)
    assert r.json() == {"quem_respondeu": servico, "caminho": rota}


def test_repassa_token_e_query(cliente):
    cliente.get("/chamados", params={"status": "aberto"}, headers={"Authorization": "Bearer abc", "Cookie": "x=1"})
    pedido = PEDIDOS[-1]
    assert pedido.headers["authorization"] == "Bearer abc"
    assert "cookie" not in pedido.headers  # não repassa o que não precisa
    assert pedido.url.params["status"] == "aberto"


def test_servico_fora_vira_503(cliente):
    FORA.add("inventario")
    r = cliente.get("/ativos")
    assert r.status_code == 503 and "Inventário" in r.json()["detail"]
    assert cliente.get("/chamados").status_code == 200  # o resto continua


def test_rota_desconhecida(cliente):
    assert cliente.get("/qualquer-coisa").status_code == 404


def test_saude_mostra_quem_esta_no_ar(cliente):
    FORA.add("notificacoes")
    r = cliente.get("/saude").json()
    assert r["servicos"]["chamados"]["status"] == "no ar"
    assert r["servicos"]["notificacoes"]["status"] == "fora do ar"
    assert r["tudo_no_ar"] is False


def test_tela_e_cabecalhos(cliente):
    r = cliente.get("/")
    assert "HelpDesk" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


def test_tela_escapa_o_html():
    js = (Path(__file__).parent.parent / "web" / "app.js").read_text(encoding="utf-8")
    assert "const esc =" in js and "onclick" not in js


def test_requisicao_grande_demais(cliente):
    r = cliente.post("/chamados", content="x" * 70000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
