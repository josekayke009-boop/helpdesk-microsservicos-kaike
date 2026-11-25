"""Limite de tentativas de login.

No monólito isso ficava num dicionário em memória. O problema: se eu subir 2 cópias
do serviço de usuários, cada uma teria a sua contagem e o bloqueio não funcionaria.
Então agora a contagem fica no Redis (compartilhado). Se o Redis cair, volto a
contar em memória pra não derrubar o login.
"""
import logging
import os
import time
from collections import defaultdict
from threading import Lock

import redis

from comum.config import REDIS_URL

MAX_FALHAS = int(os.getenv("LOGIN_MAX_FALHAS", "5"))
JANELA = int(os.getenv("LOGIN_JANELA_SEGUNDOS", "300"))

log = logging.getLogger("usuarios")
_redis = redis.Redis.from_url(REDIS_URL, socket_timeout=1, socket_connect_timeout=1) if REDIS_URL else None

# plano B em memória
_falhas: dict[str, list[float]] = defaultdict(list)
_trava = Lock()


def _recentes(chave: str) -> list[float]:
    agora = time.monotonic()
    _falhas[chave] = [t for t in _falhas[chave] if agora - t < JANELA]
    return _falhas[chave]


def bloqueado(chave: str) -> bool:
    if _redis is not None:
        try:
            return int(_redis.get(f"login:{chave}") or 0) >= MAX_FALHAS
        except redis.RedisError:
            log.warning("Redis fora, usando contagem em memória")
    with _trava:
        return len(_recentes(chave)) >= MAX_FALHAS


def registrar_falha(chave: str) -> None:
    if _redis is not None:
        try:
            n = _redis.incr(f"login:{chave}")
            if n == 1:
                _redis.expire(f"login:{chave}", JANELA)
            return
        except redis.RedisError:
            pass
    with _trava:
        _recentes(chave).append(time.monotonic())


def limpar(chave: str) -> None:
    if _redis is not None:
        try:
            _redis.delete(f"login:{chave}")
        except redis.RedisError:
            pass
    with _trava:
        _falhas.pop(chave, None)


def limpar_tudo() -> None:  # usado nos testes
    with _trava:
        _falhas.clear()
