import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import clientes
from app.banco import Base, get_db
from app.main import app
from comum import tokens

# "mundo de mentira": o que os serviços de Usuários e Inventário teriam
USUARIOS = {1: "admin", 2: "solicitante", 3: "solicitante", 4: "tecnico"}
ATIVOS = {1: "PAT-0001"}


class OutrosServicos:
    """Faz o papel de Usuários e Inventário nos testes. Dá pra "derrubar" cada um."""

    def __init__(self):
        self.fora = set()
        self.chamadas = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.chamadas.append(request)
        host = request.url.host
        if host in self.fora:
            raise httpx.ConnectError("serviço fora", request=request)
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401)
        _, recurso, numero = request.url.path.split("/")
        numero = int(numero)
        if recurso == "usuarios" and numero in USUARIOS:
            return httpx.Response(200, json={"id": numero, "nome": "X", "perfil": USUARIOS[numero]})
        if recurso == "ativos" and numero in ATIVOS:
            return httpx.Response(200, json={"id": numero, "patrimonio": ATIVOS[numero]})
        return httpx.Response(404, json={"detail": "não encontrado"})


@pytest.fixture
def outros(monkeypatch):
    falso = OutrosServicos()
    monkeypatch.setattr(clientes, "_http", httpx.Client(transport=httpx.MockTransport(falso)))
    monkeypatch.setattr(clientes, "USUARIOS_URL", "http://usuarios")
    monkeypatch.setattr(clientes, "INVENTARIO_URL", "http://inventario")
    for d in clientes.disjuntores.values():
        d.falhas, d.aberto_ate = 0, 0.0
    return falso


@pytest.fixture
def sessao(monkeypatch):
    monkeypatch.setenv("DADOS_EXEMPLO", "0")
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
def cliente(sessao, outros):
    with TestClient(app) as c:
        yield c


def cabecalho(uid):
    token, _ = tokens.criar(uid, USUARIOS[uid], "Teste")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def h():
    return {"admin": cabecalho(1), "ana": cabecalho(2), "bruno": cabecalho(3), "carla": cabecalho(4)}
