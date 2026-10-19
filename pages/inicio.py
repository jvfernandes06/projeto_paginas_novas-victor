"""Tela de início: dois atalhos grandes, o que a pessoa registrou por último e a correção.

A correção fica aqui, junto da lista, porque é onde a pessoa percebe o erro: ela abre o
início, vê "Kidstinga, ontem, 14h" e lembra que o horário estava errado.
"""

import streamlit as st

import ui
from services import atividades, auth, dominios
from services.seguranca import ErroDeValidacao

sessao = auth.exigir_papel("admin", "tecnico", "campo")
ui.definir_layout("centered")

ui.titulo(f"Olá, {sessao.nome.split()[0]}", "O que você quer fazer agora?")

esquerda, direita = st.columns(2)
with esquerda:
    st.markdown("<div class='pn-atalho'>", unsafe_allow_html=True)
    if st.button("Registrar\natividade", use_container_width=True, type="primary"):
        st.switch_page("pages/registrar_atividade.py")
    st.markdown("</div>", unsafe_allow_html=True)
with direita:
    st.markdown("<div class='pn-atalho'>", unsafe_allow_html=True)
    if st.button("Cadastrar\npessoa", use_container_width=True):
        st.switch_page("pages/cadastrar_pessoa.py")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown("### Minhas últimas atividades registradas")

ultimas = atividades.minhas_ultimas(sessao)
if not ultimas:
    st.info("Você ainda não registrou nenhuma atividade.")
    st.stop()

tipos = dominios.opcoes("tipo_atividade")

for item in ultimas:
    pessoas = item["participantes"] or item["contagem_anonima"]
    quem = f"{pessoas} pessoa(s)" if pessoas else "sem participantes registrados"
    st.markdown(
        f"<div class='pn-item'><b>{item['programa']}</b> — "
        f"{item['data'].strftime('%d/%m/%Y')} · {item['local']}<br>"
        f"<span style='color:#52514e'>{item['tipo_atividade']} · {quem}</span></div>",
        unsafe_allow_html=True,
    )

    with st.expander("Corrigir"):
        with st.form(f"corrigir_{item['id']}"):
            dia = st.date_input("Data", value=item["data"], format="DD/MM/YYYY")
            coluna_inicio, coluna_fim = st.columns(2)
            inicio = coluna_inicio.time_input("Começou às", value=item["hora_inicio"], step=1800)
            fim = coluna_fim.time_input("Terminou às", value=item["hora_fim"], step=1800)
            nomes = list(tipos)
            tipo = st.selectbox("Tipo", nomes, index=nomes.index(item["tipo_atividade"]))
            descricao = st.text_input(
                "Descrição curta", value=item["descricao_curta"] or "", max_chars=200
            )
            salvar = st.form_submit_button("Salvar correção", use_container_width=True,
                                           type="primary")

        if salvar:
            try:
                atividades.atualizar(
                    sessao,
                    item["id"],
                    data=dia,
                    hora_inicio=inicio,
                    hora_fim=fim,
                    tipo_atividade_id=tipos[tipo],
                    descricao_curta=descricao or None,
                )
            except ErroDeValidacao as erro:
                ui.erro(str(erro))
            else:
                ui.sucesso("Correção salva")
                st.rerun()

        if sessao.papel in ("admin", "tecnico"):
            st.caption(
                "Desativar tira a atividade dos relatórios, mas não apaga nada: dá para pedir "
                "para quem cuida do sistema trazer de volta."
            )
            if st.button("Desativar atividade", key=f"desativar_{item['id']}",
                         use_container_width=True):
                atividades.desativar(sessao, item["id"])
                ui.sucesso("Atividade desativada")
                st.rerun()
        else:
            st.caption(
                "Para desativar uma atividade registrada por engano, fale com a assistente "
                "social ou a coordenação."
            )
