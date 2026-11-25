"""Serviço de Chamados: abrir, atribuir, mudar status, comentar e painel."""
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import clientes, eventos, servico
from app.banco import Base, SessionLocal, engine, get_db
from app.esquemas import (
    Atribuicao, ChamadoCriar, ChamadoSaida, ComentarioCriar, ComentarioSaida, MudancaStatus, Painel, Status,
)
from app.modelos import Chamado
from comum.aplicacao import criar_app
from comum.autenticacao import usuario_atual
from comum.banco import criar_tabelas
from comum.tokens import UsuarioDoToken


def dados_exemplo(db):
    # aqui não dá pra chamar os outros serviços (não tem token no início),
    # então uso os ids que eu sei que os outros criam: ana=2, bruno=3, carla=4 / PAT-0001=1, PAT-0002=2
    if db.query(Chamado).first():
        return
    agora = datetime.now()
    exemplos = [("Computador não liga", "Apertei o botão e nada acontece.", "alta", 2, 1),
                ("Impressora atolando papel", "Atola a cada 3 folhas.", "media", 3, 2),
                ("Acesso ao sistema de RH", "Preciso de acesso para a nova estagiária.", "baixa", 3, None)]
    for titulo, desc, prio, solicitante, ativo in exemplos:
        c = Chamado(titulo=titulo, descricao=desc, prioridade=prio, solicitante_id=solicitante, ativo_id=ativo,
                    status="aberto", criado_em=agora, prazo_sla=servico.calcular_prazo(prio, agora))
        db.add(c)
        db.flush()
        eventos.registrar(db, "ChamadoAberto", solicitante, f"Seu chamado #{c.id} foi aberto. Prazo: {c.prazo_sla:%d/%m %H:%M}.")
        if c.id == 1:  # o primeiro já vai atribuído pra Carla, igual no monólito
            c.tecnico_id, c.status = 4, "em_atendimento"
            eventos.registrar(db, "ChamadoAtribuido", 4, f"O chamado #{c.id} foi atribuído a você.")
    db.commit()


@asynccontextmanager
async def ciclo_de_vida(app):
    criar_tabelas(Base, engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            dados_exemplo(db)
    parar = eventos.iniciar_publicador(SessionLocal)
    yield
    if parar:
        parar.set()


def saude_extra():
    # aparece no /saude: dá pra ver se o Inventário/Usuários estão dando problema
    return {"disjuntores": {nome: d.estado() for nome, d in clientes.disjuntores.items()},
            "eventos_pendentes": eventos.quantos_pendentes(SessionLocal)}


app = criar_app("chamados", "HelpDesk · Serviço de Chamados", ciclo_de_vida, saude_extra)
rotas = APIRouter(prefix="/chamados", tags=["Chamados"])


@rotas.post("", response_model=ChamadoSaida, status_code=201)
def abrir_chamado(dados: ChamadoCriar, usuario: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.abrir(db, dados, usuario)


@rotas.get("", response_model=list[ChamadoSaida])
def listar_chamados(status: Status | None = None, tecnico_id: int | None = None,
                    usuario: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.listar(db, usuario, status, tecnico_id)


@rotas.get("/painel", response_model=Painel)
def painel(usuario: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.painel(db, usuario)


@rotas.get("/{chamado_id}", response_model=ChamadoSaida)
def obter_chamado(chamado_id: int, usuario: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.obter(db, chamado_id, usuario)


@rotas.patch("/{chamado_id}/atribuir", response_model=ChamadoSaida)
def atribuir_chamado(chamado_id: int, dados: Atribuicao, usuario: UsuarioDoToken = Depends(usuario_atual),
                     db: Session = Depends(get_db)):
    return servico.atribuir(db, chamado_id, dados.tecnico_id, usuario)


@rotas.patch("/{chamado_id}/status", response_model=ChamadoSaida)
def mudar_status(chamado_id: int, dados: MudancaStatus, usuario: UsuarioDoToken = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    return servico.mudar_status(db, chamado_id, dados.status, usuario)


@rotas.post("/{chamado_id}/comentarios", response_model=ComentarioSaida, status_code=201)
def comentar(chamado_id: int, dados: ComentarioCriar, usuario: UsuarioDoToken = Depends(usuario_atual),
             db: Session = Depends(get_db)):
    return servico.comentar(db, chamado_id, dados, usuario)


app.include_router(rotas)
