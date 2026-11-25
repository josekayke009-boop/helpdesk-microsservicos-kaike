"""Serviço de Notificações (bônus): consome eventos e mostra os avisos de cada usuário."""
from contextlib import asynccontextmanager

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import consumidor
from app.esquemas import NotificacaoSaida
from app.modelos import Base, Notificacao, SessionLocal, engine, get_db
from comum.aplicacao import criar_app
from comum.autenticacao import usuario_atual
from comum.banco import criar_tabelas
from comum.tokens import UsuarioDoToken


@asynccontextmanager
async def ciclo_de_vida(app):
    criar_tabelas(Base, engine)
    parar = consumidor.iniciar(SessionLocal)
    yield
    if parar:
        parar.set()


app = criar_app("notificacoes", "HelpDesk · Serviço de Notificações", ciclo_de_vida,
                saude_extra=lambda: {"redis": consumidor.estado["conectado"], "eventos_processados": consumidor.estado["processados"]})


@app.get("/notificacoes", response_model=list[NotificacaoSaida], tags=["Notificações"])
def minhas_notificacoes(usuario: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    # cada um vê só as próprias
    return list(db.scalars(select(Notificacao).where(Notificacao.destinatario_id == usuario.id).order_by(Notificacao.id)))
