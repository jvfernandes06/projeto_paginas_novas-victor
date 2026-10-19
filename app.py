"""Plataforma de registro de campo e impacto — Páginas Novas.

Este arquivo faz três coisas: tela de entrada, troca de senha obrigatória no primeiro acesso e
montagem do menu com **apenas** as páginas que o papel da pessoa pode abrir. Cada página
verifica o papel outra vez, porque esconder do menu não é proteção.
"""

import streamlit as st

import navegacao
import ui
from services import auth
from services.seguranca import ErroDeValidacao

st.set_page_config(
    page_title="Páginas Novas",
    page_icon=str(ui.LOGO) if ui.LOGO.exists() else ":material/volunteer_activism:",
    layout=ui.layout_atual(),
    initial_sidebar_state="collapsed",
)

ui.aplicar_css()
if ui.LOGO.exists():
    st.logo(str(ui.LOGO), size="large")


def tela_de_entrada() -> None:
    ui.definir_layout("centered")
    st.markdown("## Páginas Novas")
    st.caption("Registro de campo e relatórios de impacto")

    if st.session_state.pop("aviso_expirou", False):
        st.info("Sua sessão foi encerrada por inatividade. Entre de novo para continuar.")

    with st.form("entrar"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        enviar = st.form_submit_button("Entrar", use_container_width=True, type="primary")

    if enviar:
        try:
            sessao, trocar = auth.autenticar(email, senha)
        except ErroDeValidacao as erro:
            ui.erro(str(erro))
            return
        auth.entrar(sessao, trocar)
        st.rerun()


def tela_de_troca_de_senha(sessao) -> None:
    ui.definir_layout("centered")
    st.markdown("## Crie a sua senha")
    st.caption(
        "Você entrou com a senha provisória. Escolha agora uma senha só sua, "
        "com pelo menos 8 letras ou números."
    )

    with st.form("trocar_senha"):
        atual = st.text_input("Senha provisória", type="password")
        nova = st.text_input("Nova senha", type="password")
        repetida = st.text_input("Repita a nova senha", type="password")
        enviar = st.form_submit_button("Salvar senha", use_container_width=True, type="primary")

    if enviar:
        try:
            auth.trocar_senha(sessao, atual, nova, repetida)
        except ErroDeValidacao as erro:
            ui.erro(str(erro))
            return
        ui.sucesso("Senha trocada.")
        st.rerun()

    if st.button("Sair", use_container_width=True):
        auth.sair()
        st.rerun()


def _paginas(grupo, inicial: str | None = None) -> list[st.Page]:
    return [
        st.Page(f"pages/{arquivo}", title=titulo, icon=icone, default=(arquivo == inicial))
        for arquivo, titulo, icone in grupo
    ]


def menu_do_papel(papel: str) -> dict[str, list[st.Page]]:
    """Monta o menu a partir da tabela em navegacao.py."""
    grupos = navegacao.menu(papel)
    primeira = navegacao.paginas_do_papel(papel)[0]
    return {nome: _paginas(grupo, primeira) for nome, grupo in grupos.items()}


sessao = auth.sessao_atual()

if sessao is None:
    tela_de_entrada()
elif auth.precisa_trocar_senha():
    tela_de_troca_de_senha(sessao)
else:
    menu = st.navigation(menu_do_papel(sessao.papel))
    ui.barra_lateral(sessao)
    menu.run()
