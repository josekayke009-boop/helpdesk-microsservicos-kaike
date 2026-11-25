from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app import limite, senhas, servico
from app.banco import get_db
from app.esquemas import Perfil, UsuarioCriar, UsuarioPublico, UsuarioSaida
from app.modelos import Usuario
from comum import tokens
from comum.autenticacao import NAO_AUTENTICADO, exigir_perfil, usuario_atual
from comum.tokens import UsuarioDoToken

# ---------------- login (/auth) ----------------
# o login ficou aqui porque é este serviço que guarda as senhas

auth = APIRouter(prefix="/auth", tags=["Autenticação"])


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    senha: str = Field(min_length=1, max_length=128)


class TokenSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em: datetime
    usuario: UsuarioSaida


def ip_do_cliente(request: Request) -> str:
    # quem fala com a gente é o gateway, então o IP real vem no X-Forwarded-For
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "-"


@auth.post("/login", response_model=TokenSaida)
def login(dados: Login, request: Request, db: Session = Depends(get_db)):
    email = dados.email.lower()
    chave = f"{email}|{ip_do_cliente(request)}"
    if limite.bloqueado(chave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Tente de novo em alguns minutos.")

    usuario = servico.buscar_por_email(db, email)
    # confere a senha mesmo se o e-mail não existir, pro tempo de resposta não entregar nada
    senha_ok = senhas.conferir(dados.senha, usuario.senha_hash if usuario else senhas.HASH_FALSO)
    if not usuario or not senha_ok or not usuario.ativo:
        limite.registrar_falha(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos.")

    limite.limpar(chave)
    # o nome e o perfil vão dentro do token, assim os outros serviços não precisam
    # vir aqui perguntar quem é o usuário a cada requisição
    token, expira = tokens.criar(usuario.id, usuario.perfil, usuario.nome)
    return TokenSaida(access_token=token, expira_em=expira, usuario=UsuarioSaida.model_validate(usuario))


@auth.get("/eu", response_model=UsuarioSaida)
def quem_sou_eu(eu: UsuarioDoToken = Depends(usuario_atual), db: Session = Depends(get_db)):
    # aqui eu confiro no banco também: se o usuário foi desativado, não passa
    usuario = db.get(Usuario, eu.id)
    if usuario is None or not usuario.ativo:
        raise NAO_AUTENTICADO
    return usuario


# ---------------- usuários (/usuarios) ----------------

usuarios = APIRouter(prefix="/usuarios", tags=["Usuários"])


@usuarios.post("", response_model=UsuarioSaida, status_code=201, dependencies=[Depends(exigir_perfil("admin"))])
def criar_usuario(dados: UsuarioCriar, db: Session = Depends(get_db)):
    return servico.criar(db, dados)


@usuarios.get("", response_model=list[UsuarioPublico], dependencies=[Depends(usuario_atual)])
def listar_usuarios(perfil: Perfil | None = None, db: Session = Depends(get_db)):
    return servico.listar(db, perfil)


# essa é a rota que o serviço de Chamados chama pra conferir o técnico
@usuarios.get("/{usuario_id}", response_model=UsuarioPublico, dependencies=[Depends(usuario_atual)])
def obter_usuario(usuario_id: int, db: Session = Depends(get_db)):
    return servico.obter(db, usuario_id)
