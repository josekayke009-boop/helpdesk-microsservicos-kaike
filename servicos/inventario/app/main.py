"""Serviço de Inventário: equipamentos de TI (computadores, impressoras...).

É o serviço mais simples, não depende de nenhum outro. Só confere o token.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app import repositorio
from app.banco import Base, SessionLocal, engine, get_db
from app.esquemas import AtivoCriar, AtivoSaida
from app.modelos import Ativo
from comum.autenticacao import exigir_perfil, usuario_atual
from comum.banco import criar_tabelas
from comum.erros import NaoEncontrado, RegraDeNegocio
from comum.aplicacao import criar_app


def dados_exemplo(db):
    if repositorio.listar(db):
        return
    # ids 1 e 2 são usados nos chamados de exemplo
    for pat, tipo, desc, setor in [("PAT-0001", "computador", "Desktop Dell OptiPlex", "Financeiro"),
                                   ("PAT-0002", "impressora", "Impressora HP LaserJet", "RH"),
                                   ("PAT-0003", "notebook", "Notebook Lenovo ThinkPad", "TI")]:
        repositorio.salvar(db, Ativo(patrimonio=pat, tipo=tipo, descricao=desc, setor=setor))


@asynccontextmanager
async def ciclo_de_vida(app):
    criar_tabelas(Base, engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            dados_exemplo(db)
    yield


app = criar_app("inventario", "HelpDesk · Serviço de Inventário", ciclo_de_vida)


@app.post("/ativos", response_model=AtivoSaida, status_code=201, tags=["Inventário"],
          dependencies=[Depends(exigir_perfil("tecnico", "admin"))])
def criar_ativo(dados: AtivoCriar, db: Session = Depends(get_db)):
    if repositorio.buscar_por_patrimonio(db, dados.patrimonio):
        raise RegraDeNegocio("Já existe um ativo com este patrimônio.")
    return repositorio.salvar(db, Ativo(**dados.model_dump()))


@app.get("/ativos", response_model=list[AtivoSaida], tags=["Inventário"], dependencies=[Depends(usuario_atual)])
def listar_ativos(setor: str | None = Query(None, max_length=80), db: Session = Depends(get_db)):
    return repositorio.listar(db, setor)


# o serviço de Chamados chama essa rota quando alguém abre chamado com equipamento
@app.get("/ativos/{ativo_id}", response_model=AtivoSaida, tags=["Inventário"], dependencies=[Depends(usuario_atual)])
def obter_ativo(ativo_id: int, db: Session = Depends(get_db)):
    ativo = repositorio.buscar_por_id(db, ativo_id)
    if ativo is None:
        raise NaoEncontrado(f"Ativo {ativo_id} não encontrado.")
    return ativo
