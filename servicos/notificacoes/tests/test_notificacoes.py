import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.consumidor import processar
from app.main import app
from app.modelos import Base, get_db
from comum import tokens


@pytest.fixture
def sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste():
        with Sessao() as db:
            yield db

    app.dependency_overrides[get_db] = db_de_teste
    yield Sessao
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(sessao):
    with TestClient(app) as c:
        yield c


def evento(eid, para, tipo="ChamadoAberto"):
    # do jeito que chega do Redis (tudo string)
    return {"evento_id": str(eid), "tipo": tipo, "destinatario_id": str(para),
            "mensagem": f"aviso {eid}", "criado_em": "2026-11-25T10:00:00"}


def login(uid):
    token, _ = tokens.criar(uid, "solicitante", "Teste")
    return {"Authorization": f"Bearer {token}"}


def test_evento_vira_notificacao(cliente, sessao):
    with sessao() as db:
        assert processar(db, evento(1, para=2)) is True
    lista = cliente.get("/notificacoes", headers=login(2)).json()
    assert lista[0]["tipo"] == "ChamadoAberto" and lista[0]["mensagem"] == "aviso 1"


def test_evento_repetido_nao_duplica(cliente, sessao):
    with sessao() as db:
        processar(db, evento(7, para=2))
        assert processar(db, evento(7, para=2)) is False
    assert len(cliente.get("/notificacoes", headers=login(2)).json()) == 1


def test_cada_um_ve_so_as_suas(cliente, sessao):
    with sessao() as db:
        processar(db, evento(1, para=2))
        processar(db, evento(2, para=3, tipo="ChamadoResolvido"))
    assert [n["tipo"] for n in cliente.get("/notificacoes", headers=login(3)).json()] == ["ChamadoResolvido"]


def test_sem_token_da_401(cliente):
    assert cliente.get("/notificacoes").status_code == 401
