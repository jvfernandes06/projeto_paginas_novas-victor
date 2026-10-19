"""Dashboard: equipe e voluntariado."""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Equipe e voluntariado")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    cartoes = indicadores.cartoes(sessao, periodo.inicio, periodo.fim, programa_id)
    ui.cabecalho_dashboard(periodo, cartoes["registros"])

    colunas = st.columns(2)
    ui.cartao(colunas[0], "Horas de voluntariado", cartoes["horas_voluntariado"], sufixo=" h")
    ui.cartao(colunas[1], "Atividades realizadas", cartoes["atividades"])
    st.caption(
        "Horas de voluntariado é o número de voluntários em cada atividade multiplicado pela "
        "duração dela. Quais funções contam como voluntariado é o Admin quem decide, na lista "
        "de funções da equipe."
    )

    st.divider()

    graficos.barras(
        indicadores.horas_voluntariado_por_mes(sessao, periodo.inicio, periodo.fim, programa_id),
        "mes",
        "horas",
        "Horas de voluntariado por mês",
        "Quanto trabalho voluntário sustentou as atividades em cada mês do período.",
        sufixo=" h",
    )

    graficos.barras(
        indicadores.composicao_equipe(sessao, periodo.inicio, periodo.fim, programa_id),
        "funcao",
        "media",
        "Composição média da equipe por atividade",
        "Em média, quantas pessoas de cada função estiveram presentes numa atividade do período.",
        horizontal=True,
    )


painel()
