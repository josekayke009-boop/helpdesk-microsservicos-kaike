from datetime import datetime, timedelta, timezone

import jwt

from app import limite
from comum import config
from tests.conftest import SENHA


def token_falso(sub, segredo, **extra):
    agora = datetime.now(timezone.utc)
    dados = {"sub": str(sub), "perfil": "admin", "iss": config.JWT_EMISSOR, "iat": agora,
             "exp": agora + timedelta(hours=1), **extra}
    return jwt.encode(dados, segredo, algorithm="HS256" if segredo else "none")


# ---------- login e token ----------

def test_rotas_exigem_login(cliente, contas):
    for rota in ["/usuarios", "/usuarios/1", "/auth/eu"]:
        assert cliente.get(rota).status_code == 401, rota


def test_login_devolve_token_com_perfil(cliente, contas):
    r = cliente.get("/auth/eu", headers=contas["carla"]["headers"])
    assert r.status_code == 200 and r.json()["perfil"] == "tecnico"


def test_login_com_senha_errada(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_email_inexistente_tem_a_mesma_mensagem(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ninguem@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_bloqueio_apos_varias_senhas_erradas(cliente, contas):
    for _ in range(limite.MAX_FALHAS):
        cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    assert cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA}).status_code == 429


def test_token_adulterado(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"] + "x"
    assert cliente.get("/auth/eu", headers={"Authorization": token}).status_code == 401


def test_token_com_outro_segredo(cliente, contas):
    falso = token_falso(contas["admin"]["id"], "segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_sem_assinatura(cliente, contas):
    falso = token_falso(contas["admin"]["id"], None)
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_vencido(cliente, contas):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = token_falso(contas["ana"]["id"], config.JWT_SEGREDO, iat=antigo, exp=antigo + timedelta(minutes=5))
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_senha_guardada_com_hash(sessao, contas):
    from app.modelos import Usuario
    with sessao() as db:
        u = db.query(Usuario).filter_by(email="ana@x.com").one()
        assert SENHA not in u.senha_hash and u.senha_hash.startswith("scrypt$")


# ---------- cadastro ----------

def test_admin_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Davi", "email": "davi@x.com", "perfil": "tecnico", "senha": "Forte1234"})
    assert r.status_code == 201 and "senha_hash" not in r.json()


def test_solicitante_nao_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["ana"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"})
    assert r.status_code == 403


def test_senha_fraca_e_recusada(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "abcdefgh"})
    assert r.status_code == 422


def test_email_repetido(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Ana 2", "email": "ANA@x.com", "perfil": "solicitante", "senha": "Forte1234"})
    assert r.status_code == 422


def test_obter_usuario_e_inexistente(cliente, contas):
    h = contas["ana"]["headers"]
    assert cliente.get(f"/usuarios/{contas['carla']['id']}", headers=h).json()["perfil"] == "tecnico"
    assert cliente.get("/usuarios/99", headers=h).status_code == 404


def test_lista_nao_mostra_email(cliente, contas):
    lista = cliente.get("/usuarios", headers=contas["ana"]["headers"]).json()
    assert lista and all("email" not in u for u in lista)


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/saude")
    assert r.json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff"
