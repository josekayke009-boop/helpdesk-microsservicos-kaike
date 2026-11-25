"""Configurações comuns, lidas das variáveis de ambiente.

O segredo do JWT nunca fica no código. Ele vem de:
1. a variável JWT_SEGREDO (por exemplo, do arquivo .env), ou
2. o arquivo indicado em JWT_SEGREDO_ARQUIVO (gerado no primeiro `docker compose up`
   pelo contêiner `segredos` e montado só nos serviços que precisam dele).
"""
import logging
import os
import secrets
from pathlib import Path

log = logging.getLogger("helpdesk")


def ler_segredo(nome: str) -> str:
    """Lê um segredo da variável `nome` ou do arquivo indicado em `nome_ARQUIVO`."""
    valor = os.getenv(nome) or ""
    arquivo = os.getenv(f"{nome}_ARQUIVO")
    if not valor and arquivo and Path(arquivo).is_file():
        valor = Path(arquivo).read_text().strip()
    return valor


JWT_SEGREDO = ler_segredo("JWT_SEGREDO")
if len(JWT_SEGREDO) < 32:
    if os.getenv("EXIGIR_SEGREDO", "0") == "1":
        # No Docker os serviços PRECISAM do mesmo segredo: sem ele, melhor nem subir.
        raise RuntimeError("JWT_SEGREDO ausente ou com menos de 32 caracteres.")
    if JWT_SEGREDO:
        log.warning("JWT_SEGREDO tem menos de 32 caracteres; usando um segredo aleatório.")
    JWT_SEGREDO = secrets.token_urlsafe(48)  # só para testes e desenvolvimento

JWT_ALGORITMO = "HS256"
JWT_EMISSOR = "helpdesk-ti"
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "60"))

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = os.getenv("DOCS", "1") == "1"
REDIS_URL = os.getenv("REDIS_URL", "")
