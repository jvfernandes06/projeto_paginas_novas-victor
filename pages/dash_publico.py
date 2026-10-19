"""Dashboard: público atendido."""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Público atendido")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    cartoes = indicadores.cartoes(sessao, periodo.inicio, periodo.fim, programa_id)
    ui.cabecalho_dashboard(periodo, cartoes["registros"])

    colunas = st.columns(3)
    ui.cartao(colunas[0], "Pessoas únicas atendidas", cartoes["pessoas_unicas"])
    ui.cartao(colunas[1], "Gestantes atendidas", cartoes["gestantes"])
    ui.cartao(colunas[2], "Participações", cartoes["participacoes"])
    st.caption(
        "Gestantes atendidas conta as pessoas marcadas como gestantes no cadastro que "
        "participaram de alguma atividade no período."
    )

    st.divider()

    esquerda, direita = st.columns(2)
    with esquerda:
        graficos.barras(
            indicadores.pessoas_por_faixa(sessao, periodo.inicio, periodo.fim, programa_id),
            "faixa_etaria",
            "pessoas",
            "Pessoas únicas por faixa etária",
            "Quantas pessoas diferentes de cada idade foram atendidas no período.",
        )
    with direita:
        graficos.barras(
            indicadores.pessoas_por_genero(sessao, periodo.inicio, periodo.fim, programa_id),
            "genero",
            "pessoas",
            "Pessoas únicas por gênero",
            "Como a pessoa se identifica, conforme informado no cadastro.",
            horizontal=True,
        )

    graficos.barras(
        indicadores.pessoas_por_perfil(sessao, periodo.inicio, periodo.fim, programa_id),
        "perfil",
        "pessoas",
        "Pessoas únicas por perfil",
        "Uma pessoa pode ter mais de um perfil, por exemplo adolescente e TEA, então ela "
        "aparece em cada barra que lhe corresponde.",
        horizontal=True,
    )

    graficos.barras(
        indicadores.novos_cadastros_por_mes(sessao, periodo.inicio, periodo.fim, programa_id),
        "mes",
        "pessoas",
        "Novos cadastros por mês",
        "Pessoas que tiveram o primeiro contato com a ONG em cada mês do período.",
    )


painel()
