"""Cria o FastAPI que todo serviço usa, já com os cabeçalhos de segurança,
os tratadores de erro e a rota /saude. Assim não preciso repetir isso em cada main.py."""
import logging

from fastapi import FastAPI

from comum.config import DOCS_ATIVA
from comum.erros import registrar_tratadores
from comum.seguranca_http import CabecalhosDeSeguranca


def criar_app(nome: str, titulo: str, lifespan=None, saude_extra=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format=f"%(asctime)s [{nome}] %(levelname)s %(message)s")
    app = FastAPI(
        title=titulo, version="3.0.0", lifespan=lifespan,
        docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
        openapi_url="/openapi.json" if DOCS_ATIVA else None,
    )
    app.add_middleware(CabecalhosDeSeguranca)
    registrar_tratadores(app)

    # rota de saúde: o gateway chama ela pra saber se o serviço está de pé
    @app.get("/saude", tags=["Saúde"])
    def saude():
        extra = saude_extra() if saude_extra else {}
        return {"servico": nome, "status": "ok", **extra}

    return app
