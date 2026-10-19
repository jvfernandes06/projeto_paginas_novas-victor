"""Dashboard: encaminhamentos.

Os números vêm de services/restrito.py, o único módulo com acesso à tabela de encaminhamentos.
Aqui só aparecem contagens: nenhum nome, nenhum código de pessoa.
"""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Encaminhamentos")
periodo, _ = ui.filtro_periodo_e_programa({})
st.caption(
    "Encaminhamento não pertence a um programa, então nesta página o filtro de programa não "
    "se aplica."
)


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    resumo = indicadores.resumo_encaminhamentos(sessao, periodo.inicio, periodo.fim)
    ui.cabecalho_dashboard(periodo, resumo["total"])

    colunas = st.columns(3)
    ui.cartao(colunas[0], "Encaminhamentos no período", resumo["total"])
    ui.cartao(colunas[1], "Taxa de conclusão", resumo["taxa_conclusao"], sufixo="%")
    ui.cartao(colunas[2], "Parados há mais de 60 dias", resumo["parados"])
    st.caption(
        "Taxa de conclusão é o número de encaminhamentos concluídos dividido pelo total do "
        "período. Os parados são os que precisam de alguém ligando para o serviço."
    )

    st.divider()

    graficos.barras(
        indicadores.encaminhamentos_por_destino(sessao, periodo.inicio, periodo.fim),
        "destino",
        "encaminhamentos",
        "Encaminhamentos por destino",
        "Para quais serviços da rede as pessoas foram encaminhadas no período.",
        horizontal=True,
    )

    graficos.barras_empilhadas_por_status(
        indicadores.encaminhamentos_por_status(sessao, periodo.inicio, periodo.fim),
        "destino",
        "encaminhamentos",
        "Situação dos encaminhamentos por destino",
        "Cada cor é uma situação, e o número está escrito dentro de cada faixa. Serviço com "
        "muita faixa vermelha é serviço que não dá retorno.",
    )


painel()
