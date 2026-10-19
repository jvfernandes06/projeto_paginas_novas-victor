"""Administração: usuários, listas do sistema e trilha de auditoria. Só Admin."""

import streamlit as st

import ui
from services import auth, dominios, restrito, usuarios
from services.modelo import PAPEIS
from services.seguranca import NOMES_DOS_PAPEIS, ErroDeValidacao

sessao = auth.exigir_papel("admin")
ui.definir_layout("wide")

ui.titulo("Administração")

aba_usuarios, aba_listas, aba_auditoria = st.tabs(["Usuários", "Listas do sistema", "Auditoria"])

# --- Usuários ------------------------------------------------------------------------------
with aba_usuarios:
    senha_nova = st.session_state.pop("senha_gerada", None)
    if senha_nova:
        st.warning(
            f"Senha provisória de **{senha_nova['email']}**: "
            f"**{senha_nova['senha']}**\n\n"
            "Anote agora e entregue em mãos. Ela não será mostrada de novo. "
            "A pessoa vai trocar a senha no primeiro acesso."
        )

    with st.expander("Criar usuário"):
        with st.form("criar_usuario"):
            email = st.text_input("E-mail")
            nome = st.text_input("Nome")
            papel = st.selectbox("Perfil de acesso", PAPEIS, format_func=NOMES_DOS_PAPEIS.get)
            if st.form_submit_button("Criar", type="primary"):
                try:
                    senha = usuarios.criar(sessao, email, nome, papel)
                except ErroDeValidacao as erro:
                    ui.erro(str(erro))
                else:
                    st.session_state["senha_gerada"] = {"email": email, "senha": senha}
                    st.rerun()

    for pessoa in usuarios.listar(sessao):
        colunas = st.columns([3, 2, 2, 2])
        situacao = "ativo" if pessoa["ativo"] else "desativado"
        colunas[0].markdown(
            f"**{pessoa['nome_exibicao']}**  \n{pessoa['email']} · {situacao}"
        )
        novo_papel = colunas[1].selectbox(
            "Perfil",
            PAPEIS,
            index=PAPEIS.index(pessoa["papel"]),
            format_func=NOMES_DOS_PAPEIS.get,
            key=f"papel_{pessoa['id']}",
            label_visibility="collapsed",
        )
        if novo_papel != pessoa["papel"]:
            try:
                usuarios.mudar_papel(sessao, pessoa["id"], novo_papel)
            except ErroDeValidacao as erro:
                ui.erro(str(erro))
            else:
                st.rerun()

        if colunas[2].button(
            "Desativar" if pessoa["ativo"] else "Reativar",
            key=f"ativo_{pessoa['id']}",
            use_container_width=True,
        ):
            try:
                usuarios.definir_ativo(sessao, pessoa["id"], not pessoa["ativo"])
            except ErroDeValidacao as erro:
                ui.erro(str(erro))
            else:
                st.rerun()

        if colunas[3].button("Nova senha", key=f"senha_{pessoa['id']}", use_container_width=True):
            senha = usuarios.redefinir_senha(sessao, pessoa["id"])
            st.session_state["senha_gerada"] = {"email": pessoa["email"], "senha": senha}
            st.rerun()

# --- Listas do sistema ---------------------------------------------------------------------
with aba_listas:
    st.caption(
        "Estas listas alimentam todos os formulários. Item desativado deixa de aparecer nos "
        "formulários, mas continua valendo no histórico já registrado."
    )
    nome_lista = st.selectbox(
        "Qual lista?", list(dominios.TABELAS), format_func=dominios.ROTULOS.get
    )

    with st.form("nova_linha"):
        colunas = st.columns([3, 2, 1])
        novo_nome = colunas[0].text_input("Nome")
        extras = {}
        if nome_lista == "local":
            extras["tipo"] = colunas[1].selectbox("Tipo", ["sede", "boate", "rua", "externo"])
        if nome_lista == "tipo_item":
            extras["unidade"] = colunas[1].text_input("Unidade", value="unidade")
        if nome_lista == "funcao_equipe":
            extras["conta_voluntariado"] = colunas[1].checkbox("Conta como voluntariado")
        if nome_lista == "perfil":
            extras["faixas_permitidas"] = colunas[1].text_input(
                "Faixas permitidas", help="Deixe vazio para qualquer faixa. Exemplo: ,0-5,6-11,"
            ) or None
        if colunas[2].form_submit_button("Adicionar", use_container_width=True):
            if nome_lista == "faixa_etaria":
                ui.erro(
                    "As faixas etárias não são editáveis aqui: os indicadores dependem delas."
                )
            else:
                try:
                    dominios.criar(sessao, nome_lista, nome=novo_nome, **extras)
                except ErroDeValidacao as erro:
                    ui.erro(str(erro))
                else:
                    ui.sucesso("Item adicionado")
                    st.rerun()

    for linha in dominios.listar(nome_lista, apenas_ativos=False):
        colunas = st.columns([4, 2])
        marca = "" if linha["ativo"] else " · desativado"
        colunas[0].markdown(f"**{linha['nome']}**{marca}")
        if colunas[1].button(
            "Desativar" if linha["ativo"] else "Reativar",
            key=f"lista_{linha['id']}",
            use_container_width=True,
        ):
            if linha["ativo"]:
                dominios.desativar(sessao, nome_lista, linha["id"])
            else:
                dominios.reativar(sessao, nome_lista, linha["id"])
            st.rerun()

# --- Auditoria -----------------------------------------------------------------------------
with aba_auditoria:
    st.caption(
        "Toda leitura e alteração de dado identificado fica registrada aqui, com quem fez e "
        "quando. Esta trilha não é alterada nem apagada."
    )
    registros = restrito.listar_auditoria(sessao)
    if not registros:
        st.info("Nada registrado ainda.")
    else:
        st.dataframe(registros, use_container_width=True, hide_index=True)
