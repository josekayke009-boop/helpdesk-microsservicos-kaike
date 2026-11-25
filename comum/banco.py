"""Conexão com o banco de cada serviço.

Cada serviço tem o SEU MySQL (bd-usuarios, bd-inventario, bd-chamados, bd-notificacoes).
O endereço vem das variáveis BD_HOST / BD_NOME / BD_USUARIO, e a senha vem de um
arquivo (BD_SENHA_ARQUIVO) que é gerado no primeiro `docker compose up`, então
nenhuma senha fica escrita no código.

Sem BD_HOST (rodando os testes ou na minha máquina) usa SQLite, só pra facilitar.
"""
import logging
import os
import time
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from comum.config import ler_segredo

log = logging.getLogger("helpdesk")


def url_do_banco(padrao: str) -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.getenv("BD_HOST"):
        senha = quote(ler_segredo("BD_SENHA"), safe="")
        return (f"mysql+pymysql://{os.getenv('BD_USUARIO', 'helpdesk')}:{senha}"
                f"@{os.environ['BD_HOST']}:3306/{os.getenv('BD_NOME', 'helpdesk')}?charset=utf8mb4")
    return padrao


def criar_sessoes(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        # pre_ping/recycle: o MySQL derruba conexão parada, isso evita erro "MySQL server has gone away"
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=280)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def get_db():
        # abre uma sessão por requisição e fecha no final
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    return engine, Sessao, get_db


def criar_tabelas(base, engine, tentativas: int = 20) -> None:
    """Cria as tabelas. Tenta de novo algumas vezes porque o MySQL demora pra subir."""
    for n in range(1, tentativas + 1):
        try:
            base.metadata.create_all(engine)
            return
        except OperationalError:
            if n == tentativas:
                raise
            log.warning("banco ainda não respondeu (tentativa %s), esperando...", n)
            time.sleep(3)
