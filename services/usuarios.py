"""Usuários do sistema, criados pela página Admin.

Não há envio de e-mail: o Admin cria a pessoa, o sistema mostra uma senha provisória **uma
única vez** na tela, e quem recebe é obrigado a trocar no primeiro acesso.
"""

from sqlalchemy import insert, select, update

from services import modelo
from services.db import conexao
from services.seguranca import ErroDeValidacao, exige_admin, hash_senha, senha_provisoria


def listar(sessao) -> list[dict]:
    exige_admin(sessao)
    with conexao() as con:
        linhas = con.execute(
            select(
                modelo.usuario.c.id,
                modelo.usuario.c.email,
                modelo.usuario.c.nome_exibicao,
                modelo.usuario.c.papel,
                modelo.usuario.c.ativo,
                modelo.usuario.c.ultimo_login,
                modelo.usuario.c.deve_trocar_senha,
            ).order_by(modelo.usuario.c.nome_exibicao)
        )
        return [dict(linha) for linha in linhas.mappings()]


def criar(sessao, email: str, nome_exibicao: str, papel: str) -> str:
    """Cria o usuário e devolve a senha provisória, para o Admin anotar e entregar."""
    exige_admin(sessao)
    return _criar(email, nome_exibicao, papel, criado_por=sessao.usuario_id)


def _criar(email: str, nome_exibicao: str, papel: str, criado_por: str | None = None) -> str:
    """Criação propriamente dita. Usada pela página Admin e pelos scripts de instalação."""
    email = (email or "").strip().lower()
    if "@" not in email:
        raise ErroDeValidacao("Escreva um e-mail válido.")
    if not (nome_exibicao or "").strip():
        raise ErroDeValidacao("Escreva o nome da pessoa.")
    if papel not in modelo.PAPEIS:
        raise ErroDeValidacao("Escolha o perfil de acesso.")

    senha = senha_provisoria()
    with conexao() as con:
        if con.execute(
            select(modelo.usuario.c.id).where(modelo.usuario.c.email == email)
        ).scalar():
            raise ErroDeValidacao("Já existe usuário com esse e-mail.")
        con.execute(
            insert(modelo.usuario).values(
                id=modelo.novo_id(),
                email=email,
                nome_exibicao=nome_exibicao.strip(),
                senha_hash=hash_senha(senha),
                papel=papel,
                deve_trocar_senha=True,
                created_by=criado_por,
            )
        )
    return senha


def mudar_papel(sessao, usuario_id: str, papel: str) -> None:
    exige_admin(sessao)
    if papel not in modelo.PAPEIS:
        raise ErroDeValidacao("Perfil de acesso inválido.")
    if usuario_id == sessao.usuario_id and papel != "admin":
        raise ErroDeValidacao("Você não pode tirar o seu próprio acesso de administrador.")
    _atualizar(usuario_id, papel=papel)


def definir_ativo(sessao, usuario_id: str, ativo: bool) -> None:
    exige_admin(sessao)
    if usuario_id == sessao.usuario_id and not ativo:
        raise ErroDeValidacao("Você não pode desativar o seu próprio acesso.")
    _atualizar(usuario_id, ativo=ativo)


def redefinir_senha(sessao, usuario_id: str) -> str:
    """Gera nova senha provisória, mostrada uma única vez."""
    exige_admin(sessao)
    senha = senha_provisoria()
    _atualizar(usuario_id, senha_hash=hash_senha(senha), deve_trocar_senha=True)
    return senha


def _atualizar(usuario_id: str, **campos) -> None:
    with conexao() as con:
        con.execute(
            update(modelo.usuario).where(modelo.usuario.c.id == usuario_id).values(**campos)
        )
