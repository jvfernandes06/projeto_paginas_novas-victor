"""Dashboard: visão geral.

Os blocos de números e gráficos ficam dentro de um fragmento que se reconsulta a cada 60
segundos (configurável). Só o fragmento recarrega: o período e o programa escolhidos ficam
onde estão, e quem registrou uma atividade no celular vê o número mudar aqui sem apertar nada.
"""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("wide")

ui.titulo("Visão geral")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    agora = indicadores.cartoes(sessao, periodo.inicio, periodo.fim, programa_id)
    antes_periodo = periodo.anterior()
    antes = indicadores.cartoes(sessao, antes_periodo.inicio, antes_periodo.fim, programa_id)

    ui.cabecalho_dashboard(periodo, agora["registros"])

    primeira = st.columns(3)
    ui.cartao(primeira[0], "Pessoas únicas atendidas", agora["pessoas_unicas"], antes["pessoas_unicas"])
    ui.cartao(primeira[1], "Participações", agora["participacoes"], antes["participacoes"])
    ui.cartao(primeira[2], "Atividades realizadas", agora["atividades"], antes["atividades"])

    segunda = st.columns(3)
    ui.cartao(
        segunda[0], "Contatos anônimos (rua)", agora["contatos_anonimos"], antes["contatos_anonimos"]
    )
    ui.cartao(segunda[1], "Itens distribuídos", agora["itens"], antes["itens"])
    ui.cartao(
        segunda[2],
        "Horas de voluntariado",
        agora["horas_voluntariado"],
        antes["horas_voluntariado"],
        sufixo=" h",
    )

    st.divider()

    graficos.linha(
        indicadores.participacoes_por_semana(sessao, periodo.inicio, periodo.fim, programa_id),
        "semana",
        "participacoes",
        "Participações por semana",
        "Cada ponto é o total de presenças registradas naquela semana. Serve para ver se o "
        "movimento está crescendo, estável ou caindo.",
    )

    graficos.barras(
        indicadores.pessoas_por_programa(sessao, periodo.inicio, periodo.fim, programa_id),
        "programa",
        "pessoas",
        "Pessoas únicas por programa",
        "Quantas pessoas diferentes cada programa atendeu no período. Quem participou de dois "
        "programas aparece nos dois, então a soma das barras passa do total de pessoas atendidas.",
        horizontal=True,
    )


painel()
