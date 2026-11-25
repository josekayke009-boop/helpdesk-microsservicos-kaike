"""Lê os eventos que o serviço de Chamados publica no Redis e grava os avisos.

Uso um "consumer group" do Redis Streams: o Redis lembra até onde a gente já leu.
Então se este serviço cair, os eventos ficam guardados lá e quando ele voltar
processa tudo que perdeu. Os chamados continuam sendo abertos nesse meio tempo.
"""
import logging
import threading
from datetime import datetime

import redis
from sqlalchemy import select

from app.modelos import Notificacao
from comum.config import REDIS_URL

STREAM = "helpdesk:eventos"
GRUPO = "notificacoes"
log = logging.getLogger("notificacoes")

estado = {"conectado": False, "processados": 0}


def processar(db, campos: dict) -> bool:
    """Grava o aviso. Devolve False se esse evento já tinha sido gravado antes."""
    evento_id = int(campos["evento_id"])
    if db.scalar(select(Notificacao.id).where(Notificacao.evento_id == evento_id)):
        return False
    db.add(Notificacao(evento_id=evento_id, tipo=campos["tipo"], destinatario_id=int(campos["destinatario_id"]),
                       mensagem=campos["mensagem"], criada_em=datetime.fromisoformat(campos["criado_em"])))
    db.commit()
    # aqui seria o lugar de mandar e-mail/SMS de verdade
    log.info("aviso %s para o usuário %s", campos["tipo"], campos["destinatario_id"])
    return True


def iniciar(Sessao) -> threading.Event | None:
    if not REDIS_URL:
        log.info("sem REDIS_URL, consumidor desligado")
        return None
    parar = threading.Event()
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10, socket_connect_timeout=2)

    def loop():
        ler_desde = "0"  # primeiro pega o que ficou pendente (lido mas não confirmado)
        while not parar.is_set():
            try:
                try:
                    r.xgroup_create(STREAM, GRUPO, id="0", mkstream=True)
                except redis.ResponseError:
                    pass  # grupo já existe
                estado["conectado"] = True
                resposta = r.xreadgroup(GRUPO, "notificacoes-1", {STREAM: ler_desde}, count=20, block=5000)
                mensagens = resposta[0][1] if resposta else []
                if ler_desde == "0" and not mensagens:
                    ler_desde = ">"  # acabou o pendente, agora só os novos
                for msg_id, campos in mensagens:
                    with Sessao() as db:
                        processar(db, campos)
                    r.xack(STREAM, GRUPO, msg_id)  # só confirma depois de gravar
                    estado["processados"] += 1
            except redis.RedisError as erro:
                estado["conectado"] = False
                log.warning("Redis fora (%s), tentando de novo em 5s", erro.__class__.__name__)
                parar.wait(5)
            except Exception:
                log.exception("erro processando evento, tento de novo em 5s")
                parar.wait(5)

    threading.Thread(target=loop, name="consumidor", daemon=True).start()
    return parar
