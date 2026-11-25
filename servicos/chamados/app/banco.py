from sqlalchemy.orm import DeclarativeBase

from comum.banco import criar_sessoes, url_do_banco

# banco dos chamados (contêiner bd-chamados)
engine, SessionLocal, get_db = criar_sessoes(url_do_banco("sqlite:///./chamados.db"))


class Base(DeclarativeBase):
    pass
