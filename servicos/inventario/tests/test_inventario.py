import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.banco import Base, get_db
from app.main import app
from comum import tokens


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("DADOS_EXEMPLO", "0")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste():
        with Sessao() as db:
            yield db

    app.dependency_overrides[get_db] = db_de_teste
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(perfil, uid=1):
    # aqui não tem serviço de usuários, então gero o token direto (mesmo segredo)
    token, _ = tokens.criar(uid, perfil, "Teste")
    return {"Authorization": f"Bearer {token}"}


ATIVO = {"patrimonio": "PAT-1", "tipo": "computador", "descricao": "Desktop", "setor": "TI"}


def test_sem_token_da_401(cliente):
    assert cliente.get("/ativos").status_code == 401
    assert cliente.get("/ativos/1").status_code == 401


def test_token_invalido_da_401(cliente):
    assert cliente.get("/ativos", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_tecnico_cadastra_e_filtra(cliente):
    h = login("tecnico")
    assert cliente.post("/ativos", headers=h, json=ATIVO).status_code == 201
    cliente.post("/ativos", headers=h, json={**ATIVO, "patrimonio": "PAT-2", "setor": "RH"})
    assert len(cliente.get("/ativos", params={"setor": "RH"}, headers=h).json()) == 1


def test_solicitante_nao_cadastra(cliente):
    assert cliente.post("/ativos", headers=login("solicitante"), json=ATIVO).status_code == 403


def test_patrimonio_repetido(cliente):
    h = login("admin")
    cliente.post("/ativos", headers=h, json=ATIVO)
    assert cliente.post("/ativos", headers=h, json=ATIVO).status_code == 422


def test_campo_extra_recusado(cliente):
    assert cliente.post("/ativos", headers=login("admin"), json={**ATIVO, "id": 50}).status_code == 422


def test_obter_ativo(cliente):
    h = login("tecnico")
    aid = cliente.post("/ativos", headers=h, json=ATIVO).json()["id"]
    assert cliente.get(f"/ativos/{aid}", headers=login("solicitante", 2)).json()["patrimonio"] == "PAT-1"
    assert cliente.get("/ativos/999", headers=h).status_code == 404
