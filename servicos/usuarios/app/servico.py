"""Regras de usuários. Quase igual ao monólito, só que agora outro serviço
não chama mais essas funções direto: ele chama a rota GET /usuarios/{id}."""
from sqlalchemy.orm import Session

from app import repositorio, senhas
from app.esquemas import UsuarioCriar
from app.modelos import Usuario
from comum.erros import NaoEncontrado, RegraDeNegocio


def criar(db: Session, dados: UsuarioCriar) -> Usuario:
    email = dados.email.lower()
    if repositorio.buscar_por_email(db, email):
        raise RegraDeNegocio("Já existe um usuário com este e-mail.")
    usuario = Usuario(nome=dados.nome, email=email, perfil=dados.perfil, senha_hash=senhas.gerar_hash(dados.senha))
    return repositorio.salvar(db, usuario)


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return repositorio.buscar_por_email(db, email.lower())


def obter(db: Session, usuario_id: int) -> Usuario:
    usuario = repositorio.buscar_por_id(db, usuario_id)
    if usuario is None:
        raise NaoEncontrado(f"Usuário {usuario_id} não encontrado.")
    return usuario


def listar(db: Session, perfil: str | None = None) -> list[Usuario]:
    return repositorio.listar(db, perfil)
