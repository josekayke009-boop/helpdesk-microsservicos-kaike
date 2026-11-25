"""Erros de negócio compartilhados e a tradução de cada um para HTTP."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class NaoEncontrado(Exception):
    """O recurso pedido não existe (ou o usuário não pode vê-lo)."""


class RegraDeNegocio(Exception):
    """A operação viola uma regra do sistema."""


class SemPermissao(Exception):
    """O usuário está logado, mas não pode fazer esta operação."""


class ServicoIndisponivel(Exception):
    """Outro serviço necessário está fora do ar ou demorou demais para responder."""


def _tratador(status: int, cabecalhos: dict | None = None):
    def tratar(request: Request, erro: Exception):
        return JSONResponse(status_code=status, content={"detail": str(erro)}, headers=cabecalhos)
    return tratar


def registrar_tratadores(app: FastAPI) -> None:
    app.add_exception_handler(NaoEncontrado, _tratador(404))
    app.add_exception_handler(RegraDeNegocio, _tratador(422))
    app.add_exception_handler(SemPermissao, _tratador(403))
    app.add_exception_handler(ServicoIndisponivel, _tratador(503, {"Retry-After": "10"}))

    @app.exception_handler(IntegrityError)
    def tratar_conflito(request: Request, erro: IntegrityError):
        # Não expõe detalhes do banco na resposta
        return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})
