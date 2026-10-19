"""Dashboard: território e abordagem de rua."""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Território e abordagem de rua")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    cartoes = indicadores.cartoes(sessao, periodo.inicio, periodo.fim, programa_id)
    ui.cabecalho_dashboard(periodo, cartoes["registros"])

    colunas = st.columns(2)
    ui.cartao(colunas[0], "Contatos anônimos no período", cartoes["contatos_anonimos"])
    ui.cartao(colunas[1], "Itens distribuídos", cartoes["itens"])
    st.caption(
        "Abordagem de rua e de boate é anônima por decisão de projeto: ninguém é identificado, "
        "só se registra quantas pessoas foram abordadas."
    )

    st.divider()

    graficos.barras(
        indicadores.contatos_anonimos_por_local(sessao, periodo.inicio, periodo.fim, programa_id),
        "local",
        "abordagens",
        "Contatos anônimos por local",
        "Onde a equipe encontrou mais pessoas no período.",
        horizontal=True,
    )

    graficos.linha(
        indicadores.abordagens_por_semana(sessao, periodo.inicio, periodo.fim, programa_id),
        "semana",
        "abordagens",
        "Abordagens por semana",
        "Total de abordagens por semana, para acompanhar a presença da equipe na rua.",
    )

    graficos.barras(
        indicadores.itens_por_tipo(sessao, periodo.inicio, periodo.fim, programa_id),
        "tipo_item",
        "quantidade",
        "Itens distribuídos por tipo",
        "Quanto de cada item foi entregue no período: preservativos, refeições, kits e o que "
        "mais estiver cadastrado nas listas.",
        horizontal=True,
    )


painel()
