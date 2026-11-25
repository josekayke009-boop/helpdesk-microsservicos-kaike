"""Regras dos chamados. As regras (SLA, transições, permissões) são as MESMAS do monólito.

O que mudou:
- conferir técnico e equipamento agora é chamada HTTP (clientes.py);
- notificar virou evento (eventos.py), gravado junto com o chamado;
- o usuário logado vem do token (UsuarioDoToken), não do banco de usuários.
"""
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clientes, eventos
from app.esquemas import ChamadoCriar, ComentarioCriar
from app.modelos import Chamado, Comentario
from comum.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from comum.tokens import UsuarioDoToken

# prazo pra resolver, conforme a prioridade (SLA)
HORAS_SLA = {"critica": 4, "alta": 8, "media": 24, "baixa": 72}

# de qual status pra quais status o chamado pode ir
TRANSICOES = {
    "aberto": {"em_atendimento"},
    "em_atendimento": {"resolvido"},
    "resolvido": {"fechado", "em_atendimento"},  # reabrir se o problema voltar
    "fechado": set(),
}


def eh_equipe(usuario: UsuarioDoToken) -> bool:
    return usuario.perfil in ("tecnico", "admin")


def calcular_prazo(prioridade: str, inicio: datetime) -> datetime:
    return inicio + timedelta(hours=HORAS_SLA[prioridade])


def abrir(db: Session, dados: ChamadoCriar, usuario: UsuarioDoToken) -> Chamado:
    if dados.ativo_id is not None:
        clientes.conferir_ativo(dados.ativo_id, usuario.token)   # HTTP -> Inventário

    agora = datetime.now()
    chamado = Chamado(**dados.model_dump(), solicitante_id=usuario.id, status="aberto", criado_em=agora,
                      prazo_sla=calcular_prazo(dados.prioridade, agora))
    db.add(chamado)
    db.flush()  # pra já ter o id do chamado na mensagem
    eventos.registrar(db, "ChamadoAberto", usuario.id,
                      f"Seu chamado #{chamado.id} foi aberto. Prazo: {chamado.prazo_sla:%d/%m %H:%M}.")
    db.commit()  # chamado + evento juntos
    return chamado


def obter(db: Session, chamado_id: int, usuario: UsuarioDoToken) -> Chamado:
    chamado = db.get(Chamado, chamado_id)
    # pra quem não pode ver, responde "não encontrado" (não revela que existe)
    if chamado is None or not (eh_equipe(usuario) or chamado.solicitante_id == usuario.id):
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    return chamado


def listar(db: Session, usuario: UsuarioDoToken, status: str | None = None, tecnico_id: int | None = None) -> list[Chamado]:
    consulta = select(Chamado).order_by(Chamado.id)
    if not eh_equipe(usuario):
        consulta = consulta.where(Chamado.solicitante_id == usuario.id)  # solicitante só vê os dele
    if status:
        consulta = consulta.where(Chamado.status == status)
    if tecnico_id:
        consulta = consulta.where(Chamado.tecnico_id == tecnico_id)
    return list(db.scalars(consulta))


def atribuir(db: Session, chamado_id: int, tecnico_id: int, usuario: UsuarioDoToken) -> Chamado:
    if not eh_equipe(usuario):
        raise SemPermissao("Só técnicos e administradores atribuem chamados.")
    chamado = obter(db, chamado_id, usuario)
    if chamado.status in ("resolvido", "fechado"):
        raise RegraDeNegocio("Não é possível atribuir um chamado resolvido ou fechado.")
    clientes.conferir_tecnico(tecnico_id, usuario.token)         # HTTP -> Usuários
    chamado.tecnico_id = tecnico_id
    if chamado.status == "aberto":
        chamado.status = "em_atendimento"
    eventos.registrar(db, "ChamadoAtribuido", tecnico_id, f"O chamado #{chamado.id} foi atribuído a você.")
    db.commit()
    return chamado


def mudar_status(db: Session, chamado_id: int, novo_status: str, usuario: UsuarioDoToken) -> Chamado:
    chamado = obter(db, chamado_id, usuario)
    # o solicitante só pode confirmar (fechar) ou reabrir o próprio chamado resolvido
    pode_solicitante = chamado.status == "resolvido" and novo_status in ("fechado", "em_atendimento")
    if not (eh_equipe(usuario) or pode_solicitante):
        raise SemPermissao("Você não pode mudar o status deste chamado.")
    if novo_status not in TRANSICOES[chamado.status]:
        raise RegraDeNegocio(f"Não é possível ir de '{chamado.status}' para '{novo_status}'.")
    if novo_status == "em_atendimento" and chamado.tecnico_id is None:
        raise RegraDeNegocio("Atribua um técnico antes de iniciar o atendimento.")
    chamado.status = novo_status
    if novo_status == "resolvido":
        eventos.registrar(db, "ChamadoResolvido", chamado.solicitante_id,
                          f"Seu chamado #{chamado.id} foi resolvido. Confirme se está tudo certo.")
    db.commit()
    return chamado


def comentar(db: Session, chamado_id: int, dados: ComentarioCriar, usuario: UsuarioDoToken) -> Comentario:
    chamado = obter(db, chamado_id, usuario)
    if chamado.status == "fechado":
        raise RegraDeNegocio("Chamados fechados não recebem comentários.")
    comentario = Comentario(chamado_id=chamado.id, autor_id=usuario.id, texto=dados.texto, criado_em=datetime.now())
    db.add(comentario)
    db.commit()
    return comentario


def painel(db: Session, usuario: UsuarioDoToken) -> dict:
    chamados = listar(db, usuario)
    agora = datetime.now()
    atrasados = sum(1 for c in chamados if c.status in ("aberto", "em_atendimento") and c.prazo_sla < agora)
    return {"total": len(chamados), "por_status": dict(Counter(c.status for c in chamados)), "atrasados": atrasados}
