from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco import Base


class Chamado(Base):
    __tablename__ = "chamados"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="aberto")
    # MUDOU: antes eram ForeignKey("usuarios.id") e ForeignKey("ativos.id").
    # Agora essas tabelas estão em outros bancos, então guardo só o número.
    # Quem garante que o id existe é a chamada HTTP antes de salvar.
    solicitante_id: Mapped[int]
    tecnico_id: Mapped[int | None] = mapped_column(nullable=True)
    ativo_id: Mapped[int | None] = mapped_column(nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime)
    prazo_sla: Mapped[datetime] = mapped_column(DateTime)

    comentarios: Mapped[list["Comentario"]] = relationship(
        back_populates="chamado", order_by="Comentario.id", cascade="all, delete-orphan", lazy="selectin"
    )


class Comentario(Base):
    __tablename__ = "comentarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    # essa FK pode ficar, as duas tabelas são deste serviço
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamados.id"))
    autor_id: Mapped[int]  # era FK pra usuarios, saiu
    texto: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime)

    chamado: Mapped[Chamado] = relationship(back_populates="comentarios")


class EventoPendente(Base):
    """Caixa de saída dos eventos (padrão "outbox").

    Quando algo acontece com o chamado, eu gravo o evento AQUI, na mesma transação
    do chamado. Depois uma thread manda pro Redis. Se o Redis ou o serviço de
    notificações estiverem fora, o chamado é salvo do mesmo jeito e o evento
    fica esperando, não se perde.
    """
    __tablename__ = "eventos_pendentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))
    destinatario_id: Mapped[int]
    mensagem: Mapped[str] = mapped_column(String(300))
    criado_em: Mapped[datetime] = mapped_column(DateTime)
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
