"""Criação e validação dos tokens JWT.

Só o serviço de Usuários *cria* tokens (ele é o dono do login). Todos os serviços
*conferem* o token: assinatura, emissor, validade e campos obrigatórios.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt

from comum.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO, TOKEN_MINUTOS

PERFIS = ("solicitante", "tecnico", "admin")


class TokenInvalido(Exception):
    pass


@dataclass(frozen=True)
class UsuarioDoToken:
    """Quem está logado, segundo o token (sem consultar o banco de Usuários)."""
    id: int
    perfil: str
    nome: str
    token: str = field(repr=False)  # repassado no cabeçalho Authorization ao chamar outro serviço


def criar(usuario_id: int, perfil: str, nome: str) -> tuple[str, datetime]:
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=TOKEN_MINUTOS)
    dados = {"sub": str(usuario_id), "perfil": perfil, "nome": nome, "iat": agora, "exp": expira, "iss": JWT_EMISSOR}
    return jwt.encode(dados, JWT_SEGREDO, algorithm=JWT_ALGORITMO), expira


def ler(token: str) -> UsuarioDoToken:
    """Devolve quem está logado, ou lança TokenInvalido."""
    try:
        dados = jwt.decode(
            token, JWT_SEGREDO, algorithms=[JWT_ALGORITMO], issuer=JWT_EMISSOR,
            options={"require": ["exp", "iat", "sub", "iss", "perfil"]},
        )
        if dados["perfil"] not in PERFIS:
            raise TokenInvalido()
        return UsuarioDoToken(id=int(dados["sub"]), perfil=dados["perfil"], nome=str(dados.get("nome", "")), token=token)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as erro:
        raise TokenInvalido() from erro
