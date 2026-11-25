"""Publica os eventos dos chamados no Redis (bônus do desafio).

Fluxo: servico.py grava o evento na tabela eventos_pendentes -> esta thread pega os
pendentes a cada segundo -> manda pro stream "helpdesk:eventos" no Redis -> marca como
publicado. O serviço de Notificações lê desse stream.
"""
import logging
import threading
import time
from datetime import datetime

import redis
from sqlalchemy import func, select

from app.modelos import EventoPendente
from comum.config import REDIS_URL

STREAM = "helpdesk:eventos"
log = logging.getLogger("chamados")


def registrar(db, tipo: str, destinatario_id: int, mensagem: str) -> None:
    # sem commit aqui de propósito: vai junto com o commit do chamado
    db.add(EventoPendente(tipo=tipo, destinatario_id=destinatario_id, mensagem=mensagem,
                          criado_em=datetime.now(), publicado=False))


def quantos_pendentes(Sessao) -> int:
    try:
        with Sessao() as db:
            return db.scalar(select(func.count()).where(EventoPendente.publicado.is_(False))) or 0
    except Exception:
        return -1


def publicar_pendentes(db, r: redis.Redis) -> int:
    pendentes = db.scalars(select(EventoPendente).where(EventoPendente.publicado.is_(False))
                           .order_by(EventoPendente.id).limit(50)).all()
    for ev in pendentes:
        r.xadd(STREAM, {"evento_id": ev.id, "tipo": ev.tipo, "destinatario_id": ev.destinatario_id,
                        "mensagem": ev.mensagem, "criado_em": ev.criado_em.isoformat()})
        ev.publicado = True
        db.commit()  # commit um por um: se cair no meio, no máximo repete um evento
    return len(pendentes)


def iniciar_publicador(Sessao) -> threading.Event | None:
    if not REDIS_URL:
        log.info("sem REDIS_URL, eventos ficam só na tabela")
        return None
    parar = threading.Event()
    r = redis.Redis.from_url(REDIS_URL, socket_timeout=2, socket_connect_timeout=2)

    def loop():
        while not parar.is_set():
            try:
                with Sessao() as db:
                    n = publicar_pendentes(db, r)
                if n:
                    log.info("%s evento(s) publicados no Redis", n)
                parar.wait(1)
            except Exception as erro:  # Redis fora, banco fora... tenta de novo depois
                log.warning("não deu pra publicar eventos agora (%s), tentando em 5s", erro.__class__.__name__)
                parar.wait(5)

    threading.Thread(target=loop, name="publicador", daemon=True).start()
    return parar
