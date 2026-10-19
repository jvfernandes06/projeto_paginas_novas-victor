"""Encaminhamentos: criar, filtrar por situação e atualizar em um toque.

Página restrita a Técnico e Admin. Toda leitura daqui fica registrada em auditoria.
"""

import streamlit as st

import ui
from services import auth, dominios, pessoas, restrito
from services.modelo import STATUS_ENCAMINHAMENTO
from services.seguranca import ErroDeValidacao

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("centered")

NOMES = {
    "enviado": "Enviado",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
    "sem_retorno": "Sem retorno",
}
PROXIMO = {"enviado": "em_andamento", "em_andamento": "concluido", "sem_retorno": "em_andamento"}

ui.titulo("Encaminhamentos")

with st.expander("Novo encaminhamento"):
    destinos = dominios.opcoes("destino_encaminhamento")
    with st.form("novo_encaminhamento"):
        codigo = st.text_input("Código da pessoa", placeholder="PN-00001")
        nome_destino = st.selectbox("Para onde", list(destinos))
        observacao = st.text_area("Observação (opcional)")
        if st.form_submit_button("Criar encaminhamento", use_container_width=True, type="primary"):
            pessoa = pessoas.buscar_por_codigo(sessao, codigo)
            if pessoa is None:
                ui.erro("Não encontrei esse código. Confira o número.")
            else:
                try:
                    restrito.criar_encaminhamento(
                        sessao, pessoa["id"], destinos[nome_destino], observacao or None
                    )
                except ErroDeValidacao as erro:
                    ui.erro(str(erro))
                else:
                    ui.sucesso("Encaminhamento criado")
                    st.rerun()

filtro = st.radio(
    "Mostrar",
    ["Todos"] + [NOMES[s] for s in STATUS_ENCAMINHAMENTO],
    horizontal=True,
)
status_escolhido = next((s for s, nome in NOMES.items() if nome == filtro), None)

lista = restrito.listar_encaminhamentos(sessao, status_escolhido)
st.caption(f"{len(lista)} encaminhamento(s).")

for item in lista:
    st.markdown(
        f"<div class='pn-item'><b>{item['pessoa_codigo']}</b> → {item['destino']}<br>"
        f"<span style='color:#52514e'>{NOMES[item['status']]} · "
        f"atualizado em {item['data_ultima_atualizacao'].strftime('%d/%m/%Y')}</span></div>",
        unsafe_allow_html=True,
    )
    colunas = st.columns(2)
    proximo = PROXIMO.get(item["status"])
    if proximo and colunas[0].button(
        f"Marcar como {NOMES[proximo].lower()}", key=f"proximo_{item['id']}",
        use_container_width=True,
    ):
        restrito.atualizar_status(sessao, item["id"], proximo)
        ui.sucesso("Situação atualizada")
        st.rerun()
    if item["status"] != "sem_retorno" and colunas[1].button(
        "Sem retorno", key=f"sem_retorno_{item['id']}", use_container_width=True
    ):
        restrito.atualizar_status(sessao, item["id"], "sem_retorno")
        ui.sucesso("Situação atualizada")
        st.rerun()
