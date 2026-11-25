"""Chamadas HTTP para os outros serviços.

No monólito era só `usuarios.obter_tecnico(db, id)`. Agora tem a rede no meio,
então três cuidados:
1. timeout: se o outro serviço travar, a gente desiste em poucos segundos;
2. repassar o token do usuário (cabeçalho Authorization), porque o outro serviço
   também confere o login;
3. "disjuntor" (circuit breaker): depois de algumas falhas seguidas, paro de tentar
   por um tempo e já respondo 503 na hora, sem ficar esperando o timeout toda vez.
"""
import logging
import os
import threading
import time

import httpx

from comum.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel

log = logging.getLogger("chamados")

USUARIOS_URL = os.getenv("USUARIOS_URL", "http://usuarios:8000")
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://inventario:8000")
TIMEOUT = httpx.Timeout(float(os.getenv("TIMEOUT_SEGUNDOS", "3")), connect=2.0)

_http = httpx.Client(timeout=TIMEOUT)


class Disjuntor:
    def __init__(self, nome: str, falhas_para_abrir: int = 3, segundos_aberto: int = 15):
        self.nome = nome
        self.falhas_para_abrir = falhas_para_abrir
        self.segundos_aberto = segundos_aberto
        self.falhas = 0
        self.aberto_ate = 0.0
        self._trava = threading.Lock()

    def pode_tentar(self) -> bool:
        return time.monotonic() >= self.aberto_ate

    def deu_certo(self):
        with self._trava:
            self.falhas = 0

    def deu_errado(self):
        with self._trava:
            self.falhas += 1
            if self.falhas >= self.falhas_para_abrir:
                self.aberto_ate = time.monotonic() + self.segundos_aberto
                log.warning("disjuntor de %s ABERTO por %ss", self.nome, self.segundos_aberto)

    def estado(self) -> str:
        return "aberto" if not self.pode_tentar() else "fechado"


disjuntores = {"Usuários": Disjuntor("Usuários"), "Inventário": Disjuntor("Inventário")}


def _get(servico: str, url: str, token: str) -> dict | None:
    """GET no outro serviço. Devolve o JSON, None se for 404, ou lança ServicoIndisponivel."""
    disjuntor = disjuntores[servico]
    fora = ServicoIndisponivel(f"O serviço de {servico} está fora do ar. Tente de novo em instantes.")
    if not disjuntor.pode_tentar():
        raise fora
    try:
        r = _http.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as erro:  # timeout, conexão recusada, DNS...
        log.warning("falha ao chamar %s: %s", servico, erro.__class__.__name__)
        disjuntor.deu_errado()
        raise fora
    if r.status_code >= 500:
        disjuntor.deu_errado()
        raise fora
    disjuntor.deu_certo()
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        # 401/403 aqui seria configuração errada (ex.: segredos diferentes)
        log.error("%s respondeu %s", servico, r.status_code)
        raise ServicoIndisponivel(f"Não foi possível consultar o serviço de {servico}.")
    return r.json()


def conferir_ativo(ativo_id: int, token: str) -> dict:
    ativo = _get("Inventário", f"{INVENTARIO_URL}/ativos/{ativo_id}", token)
    if ativo is None:
        raise NaoEncontrado(f"Ativo {ativo_id} não encontrado.")
    return ativo


def conferir_tecnico(usuario_id: int, token: str) -> dict:
    usuario = _get("Usuários", f"{USUARIOS_URL}/usuarios/{usuario_id}", token)
    if usuario is None:
        raise NaoEncontrado(f"Usuário {usuario_id} não encontrado.")
    if usuario.get("perfil") != "tecnico":
        raise RegraDeNegocio(f"Usuário {usuario_id} não é técnico.")
    return usuario
