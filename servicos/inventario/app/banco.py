from sqlalchemy.orm import DeclarativeBase

from comum.banco import criar_sessoes, url_do_banco

# banco do inventário (contêiner bd-inventario). Ninguém mais conecta nele.
engine, SessionLocal, get_db = criar_sessoes(url_do_banco("sqlite:///./inventario.db"))


class Base(DeclarativeBase):
    pass
