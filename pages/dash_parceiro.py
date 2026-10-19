"""Dashboard do parceiro: a visão externa.

Tudo aqui passa pelas funções `ext_*`, que escondem qualquer contagem menor que 5. Com grupos
muito pequenos, um número exato permitiria descobrir quem é a pessoa — e, neste território,
isso pode custar a segurança dela.

Nenhum encaminhamento, nenhum cruzamento de gênero com faixa etária, nenhuma lista de pessoas.
"""

import streamlit as st

import ui
from analytics import graficos, indicadores
from services import auth, dominios

sessao = auth.exigir_papel("admin", "tecnico", "parceiro")
ui.definir_layout("wide")

ui.titulo("Relatório para parceiros", "Números agregados, sem nenhum dado individual.")
periodo, programa_id = ui.filtro_periodo_e_programa(dominios.opcoes("programa"))


def _rotulo(cartoes: dict, chave: str) -> str:
    return cartoes.get(f"{chave}_rotulo", "—")


@st.fragment(run_every=indicadores.INTERVALO)
def painel() -> None:
    cartoes = indicadores.ext_cartoes(sessao, periodo.inicio, periodo.fim, programa_id)
    ui.cabecalho_dashboard(periodo, cartoes["registros"])

    primeira = st.columns(3)
    ui.cartao(primeira[0], "Pessoas atendidas", _rotulo(cartoes, "pessoas_unicas"))
    ui.cartao(primeira[1], "Participações", _rotulo(cartoes, "participacoes"))
    ui.cartao(primeira[2], "Atividades realizadas", _rotulo(cartoes, "atividades"))

    segunda = st.columns(3)
    ui.cartao(segunda[0], "Contatos na rua", _rotulo(cartoes, "contatos_anonimos"))
    ui.cartao(segunda[1], "Itens distribuídos", _rotulo(cartoes, "itens"))
    ui.cartao(segunda[2], "Horas de voluntariado", cartoes["horas_voluntariado"], sufixo=" h")

    st.caption(
        'Onde aparece "<5", havia menos de cinco pessoas no grupo. O número exato é omitido '
        "para proteger quem foi atendido."
    )

    st.divider()

    pessoas = indicadores.ext_pessoas_por_programa(sessao, periodo.inicio, periodo.fim, programa_id)
    graficos.barras(
        pessoas,
        "programa",
        "pessoas",
        "Pessoas atendidas por programa",
        "Quantas pessoas diferentes cada programa atendeu no período. Programas com menos de "
        "cinco pessoas não aparecem com número.",
        horizontal=True,
    )

    participacoes = indicadores.ext_participacoes_por_mes(
        sessao, periodo.inicio, periodo.fim, programa_id
    )
    graficos.linha(
        participacoes,
        "mes",
        "participacoes",
        "Participações por mês",
        "Total de presenças registradas em cada mês do período.",
    )

    st.divider()
    st.markdown("**Baixar os números**")
    st.caption("O arquivo traz exatamente os números desta tela, já com a supressão aplicada.")

    colunas = st.columns(2)
    if not pessoas.empty:
        colunas[0].download_button(
            "Pessoas por programa (CSV)",
            pessoas.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"pessoas_por_programa_{periodo.inicio}_{periodo.fim}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    if not participacoes.empty:
        colunas[1].download_button(
            "Participações por mês (CSV)",
            participacoes.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"participacoes_por_mes_{periodo.inicio}_{periodo.fim}.csv",
            mime="text/csv",
            use_container_width=True,
        )


painel()
