from sqlalchemy.orm import DeclarativeBase

from comum.banco import criar_sessoes, url_do_banco

# banco só do serviço de usuários (no Docker é o contêiner bd-usuarios)
engine, SessionLocal, get_db = criar_sessoes(url_do_banco("sqlite:///./usuarios.db"))


class Base(DeclarativeBase):
    pass
