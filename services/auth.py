"""Entrada no sistema: login, troca de senha, logout e expiração por inatividade.

Este é o módulo que conversa com a sessão do Streamlit. As páginas não leem
`st.session_state` para saber quem está logado: elas chamam `exigir_papel(...)`.
"""

from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy import select, update

from services import config, modelo
from services.db import conexao
from services.seguranca import ErroDeValidacao, Sessao, hash_senha, senha_confere

CHAVE_SESSAO = "sessao"
CHAVE_ATIVIDADE = "ultima_interacao"
CHAVE_TROCAR_SENHA = "deve_trocar_senha"

MENSAGEM_LOGIN_INVALIDO = "E-mail ou senha incorretos."


def autenticar(email: str, senha: str) -> tuple[Sessao, bool]:
    """Confere e-mail e senha. Devolve a sessão e se a senha precisa ser trocada."""
    email = (email or "").strip().lower()
    with conexao() as con:
        usuario = con.execute(
            select(modelo.usuario).where(modelo.usuario.c.email == email)
        ).mappings().first()

        if usuario is None or not senha_confere(senha or "", usuario["senha_hash"]):
            raise ErroDeValidacao(MENSAGEM_LOGIN_INVALIDO)
        if not usuario["ativo"]:
            raise ErroDeValidacao("Este acesso está desativado. Procure a coordenação.")

        con.execute(
            update(modelo.usuario)
            .where(modelo.usuario.c.id == usuario["id"])
            .values(ultimo_login=datetime.now())
        )

    sessao = Sessao(
        usuario_id=usuario["id"],
        email=usuario["email"],
        nome=usuario["nome_exibicao"],
        papel=usuario["papel"],
    )
    return sessao, bool(usuario["deve_trocar_senha"])


def trocar_senha(sessao: Sessao, senha_atual: str, senha_nova: str, repetida: str) -> None:
    if senha_nova != repetida:
        raise ErroDeValidacao("As duas senhas digitadas não são iguais.")
    if len(senha_nova or "") < 8:
        raise ErroDeValidacao("A senha precisa ter pelo menos 8 caracteres.")

    with conexao() as con:
        guardado = con.execute(
            select(modelo.usuario.c.senha_hash).where(modelo.usuario.c.id == sessao.usuario_id)
        ).scalar()
        if not senha_confere(senha_atual or "", guardado):
            raise ErroDeValidacao("A senha atual está incorreta.")
        con.execute(
            update(modelo.usuario)
            .where(modelo.usuario.c.id == sessao.usuario_id)
            .values(senha_hash=hash_senha(senha_nova), deve_trocar_senha=False)
        )
    st.session_state[CHAVE_TROCAR_SENHA] = False


# --- Sessão do Streamlit ------------------------------------------------------------------


def entrar(sessao: Sessao, deve_trocar_senha: bool) -> None:
    st.session_state[CHAVE_SESSAO] = sessao
    st.session_state[CHAVE_TROCAR_SENHA] = deve_trocar_senha
    registrar_interacao()


def sair() -> None:
    for chave in (CHAVE_SESSAO, CHAVE_ATIVIDADE, CHAVE_TROCAR_SENHA):
        st.session_state.pop(chave, None)


def registrar_interacao() -> None:
    st.session_state[CHAVE_ATIVIDADE] = datetime.now()


def expirou() -> bool:
    ultima = st.session_state.get(CHAVE_ATIVIDADE)
    if ultima is None:
        return False
    return datetime.now() - ultima > timedelta(minutes=config.MINUTOS_INATIVIDADE)


def sessao_atual() -> Sessao | None:
    """Sessão de quem está logado, ou None. Encerra sozinha depois da inatividade."""
    sessao = st.session_state.get(CHAVE_SESSAO)
    if sessao is None:
        return None
    if expirou():
        sair()
        st.session_state["aviso_expirou"] = True
        return None
    registrar_interacao()
    return sessao


def precisa_trocar_senha() -> bool:
    return bool(st.session_state.get(CHAVE_TROCAR_SENHA))


def exigir_papel(*papeis: str) -> Sessao:
    """Primeira linha de toda página: garante login e papel, ou interrompe a página.

    O menu já esconde o que o papel não pode ver, mas esta checagem é o que protege quem
    digitar o endereço da página na mão.
    """
    sessao = sessao_atual()
    if sessao is None:
        st.warning("Faça login para continuar.")
        st.stop()
    if papeis and sessao.papel not in papeis:
        st.error("Seu perfil de acesso não permite abrir esta página.")
        st.stop()
    return sessao
