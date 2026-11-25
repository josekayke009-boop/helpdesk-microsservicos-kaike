from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from comum.banco import criar_sessoes, url_do_banco

# banco das notificações (contêiner bd-notificacoes)
engine, SessionLocal, get_db = criar_sessoes(url_do_banco("sqlite:///./notificacoes.db"))


class Base(DeclarativeBase):
    pass


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # id do evento lá no serviço de chamados. É unique pra não gravar o mesmo aviso
    # duas vezes se o evento chegar repetido
    evento_id: Mapped[int] = mapped_column(unique=True)
    tipo: Mapped[str] = mapped_column(String(40))
    destinatario_id: Mapped[int] = mapped_column(index=True)
    mensagem: Mapped[str] = mapped_column(String(300))
    criada_em: Mapped[datetime] = mapped_column(DateTime)
