"""Dashboard: programas."""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Programas")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    atividades = indicadores.atividades_por_programa(
        sessao, periodo.inicio, periodo.fim, programa_id
    )
    registros = int(atividades["atividades"].sum()) if not atividades.empty else 0
    ui.cabecalho_dashboard(periodo, registros)

    esquerda, direita = st.columns(2)
    with esquerda:
        graficos.barras(
            atividades,
            "programa",
            "atividades",
            "Atividades por programa",
            "Quantas atividades cada programa realizou no período.",
            horizontal=True,
        )
    with direita:
        graficos.barras(
            atividades,
            "programa",
            "horas",
            "Horas de atividade por programa",
            "Soma da duração das atividades de cada programa. Está em gráfico separado de "
            "propósito: quantidade de atividades e horas são medidas diferentes, e juntá-las "
            "num só gráfico com dois eixos engana a leitura.",
            horizontal=True,
            sufixo=" h",
        )

    graficos.barras(
        indicadores.taxa_recorrencia(sessao, periodo.inicio, periodo.fim, programa_id),
        "programa",
        "taxa_pct",
        "Taxa de recorrência por programa",
        "Percentual das pessoas atendidas que voltaram 3 vezes ou mais no período. Recorrência "
        "alta indica vínculo criado; recorrência baixa pode indicar atividade de porta de entrada.",
        horizontal=True,
        sufixo="%",
    )

    st.markdown("**Resumo por programa**")
    resumo = indicadores.resumo_por_programa(sessao, periodo.inicio, periodo.fim, programa_id)
    if resumo.empty:
        st.info("Ainda não há dados para este período.")
    else:
        st.dataframe(
            resumo.rename(
                columns={
                    "programa": "Programa",
                    "atividades": "Atividades",
                    "horas": "Horas",
                    "pessoas": "Pessoas únicas",
                    "pessoas_3mais": "Pessoas com 3+ presenças",
                    "taxa_pct": "Recorrência (%)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "A mesma informação dos gráficos acima, em tabela, para conferir número por número."
        )


painel()
