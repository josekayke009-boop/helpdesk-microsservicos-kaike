"""Serviço de Usuários: cadastro de usuários e login (é quem emite o token)."""
import os
from contextlib import asynccontextmanager

from app import servico
from app.banco import Base, SessionLocal, engine
from comum.banco import criar_tabelas
from app.esquemas import UsuarioCriar
from app.rotas import auth, usuarios
from comum.aplicacao import criar_app


def dados_exemplo(db):
    # mesmas contas do monólito. A ordem importa: os outros serviços usam esses ids
    # nos dados de exemplo deles (ana=2, bruno=3, carla=4)
    if servico.listar(db):
        return
    senha = os.getenv("SENHA_EXEMPLO", "Helpdesk2026")
    for nome, email, perfil in [("Admin TI", "admin@empresa.com", "admin"), ("Ana Souza", "ana@empresa.com", "solicitante"),
                                ("Bruno Lima", "bruno@empresa.com", "solicitante"), ("Carla Dias", "carla@empresa.com", "tecnico"),
                                ("Diego Rocha", "diego@empresa.com", "tecnico")]:
        servico.criar(db, UsuarioCriar(nome=nome, email=email, perfil=perfil, senha=senha))


@asynccontextmanager
async def ciclo_de_vida(app):
    criar_tabelas(Base, engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            dados_exemplo(db)
    yield


app = criar_app("usuarios", "HelpDesk · Serviço de Usuários", ciclo_de_vida)
app.include_router(auth)
app.include_router(usuarios)
