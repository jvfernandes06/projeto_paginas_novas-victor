"""Peças de tela usadas por todas as páginas: layout, cartões, filtros e avisos.

Fica fora de pages/ porque é compartilhado, e fora de services/ porque não toca no banco.
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from services import auth

RAIZ = Path(__file__).resolve().parent
CSS = RAIZ / "assets" / "style.css"
LOGO = RAIZ / "assets" / "logo.png"

CHAVE_LAYOUT = "layout"


def aplicar_css() -> None:
    """Injeta o CSS uma única vez, no começo da execução do app."""
    if CSS.exists():
        st.html(f"<style>{CSS.read_text(encoding='utf-8')}</style>")


def definir_layout(tipo: str) -> None:
    """Páginas de cadastro pedem "centered"; dashboards pedem "wide".

    O Streamlit só aceita definir o layout uma vez por execução, então a página anota o que
    precisa e manda rodar de novo. Para quem usa, é imperceptível.
    """
    if st.session_state.get(CHAVE_LAYOUT) != tipo:
        st.session_state[CHAVE_LAYOUT] = tipo
        st.rerun()


def layout_atual() -> str:
    return st.session_state.get(CHAVE_LAYOUT, "centered")


def titulo(texto: str, subtitulo: str = "") -> None:
    st.markdown(f"## {texto}")
    if subtitulo:
        st.caption(subtitulo)


def barra_lateral(sessao) -> None:
    """Identificação de quem está logado e o botão de sair, visível em todas as páginas."""
    with st.sidebar:
        st.markdown(
            f"<div class='pn-usuario'>{sessao.nome}<br>"
            f"<span>{sessao.papel_legivel}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Sair", use_container_width=True, key="botao_sair"):
            auth.sair()
            st.rerun()


def passos(atual: int, total: int, nome: str) -> None:
    """Indicador de progresso dos fluxos em etapas."""
    st.progress(atual / total, text=f"Etapa {atual} de {total} — {nome}")


def cartao(coluna, rotulo: str, valor, variacao=None, sufixo: str = "") -> None:
    """Número grande com variação em relação ao período anterior."""
    texto = "—" if valor is None else (f"{valor:g}{sufixo}" if isinstance(valor, (int, float)) else str(valor))
    delta = None
    if variacao is not None and valor is not None:
        if variacao == 0:
            delta = "sem base anterior" if valor == 0 else "novo no período"
        else:
            delta = f"{(valor - variacao) / variacao * 100:+.0f}% vs. período anterior"
    coluna.metric(rotulo, texto, delta)


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date
    rotulo: str
    parcial: bool

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1

    def anterior(self) -> "Periodo":
        """Período anterior do mesmo tamanho, para a variação dos cartões."""
        from datetime import timedelta

        fim = self.inicio - timedelta(days=1)
        return Periodo(fim - timedelta(days=self.dias - 1), fim, "período anterior", False)


def _primeiro_dia(ano: int, mes: int) -> date:
    return date(ano, mes, 1)


def _mes_anterior(hoje: date) -> tuple[date, date]:
    primeiro_deste = _primeiro_dia(hoje.year, hoje.month)
    from datetime import timedelta

    ultimo_do_passado = primeiro_deste - timedelta(days=1)
    return _primeiro_dia(ultimo_do_passado.year, ultimo_do_passado.month), ultimo_do_passado


ATALHOS = ["Este mês", "Mês passado", "Últimos 3 meses", "Este ano", "Personalizado"]


def filtro_periodo_e_programa(programas: dict[str, str]) -> tuple[Periodo, str | None]:
    """A única linha de filtros dos dashboards: período e programa."""
    hoje = date.today()
    coluna_periodo, coluna_programa = st.columns([3, 2])

    with coluna_periodo:
        atalho = st.radio("Período", ATALHOS, horizontal=True, label_visibility="collapsed")

    if atalho == "Este mês":
        periodo = Periodo(_primeiro_dia(hoje.year, hoje.month), hoje, "este mês", True)
    elif atalho == "Mês passado":
        inicio, fim = _mes_anterior(hoje)
        periodo = Periodo(inicio, fim, "mês passado", False)
    elif atalho == "Últimos 3 meses":
        mes = hoje.month - 2
        ano = hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        periodo = Periodo(_primeiro_dia(ano, mes), hoje, "últimos 3 meses", True)
    elif atalho == "Este ano":
        periodo = Periodo(_primeiro_dia(hoje.year, 1), hoje, "este ano", True)
    else:
        with coluna_periodo:
            escolha = st.date_input(
                "De / até",
                value=(_primeiro_dia(hoje.year, hoje.month), hoje),
                format="DD/MM/YYYY",
            )
        inicio, fim = escolha if isinstance(escolha, tuple) and len(escolha) == 2 else (hoje, hoje)
        periodo = Periodo(inicio, fim, "período escolhido", fim >= hoje)

    with coluna_programa:
        nome = st.selectbox("Programa", ["Todos os programas"] + list(programas))
    programa_id = programas.get(nome)

    return periodo, programa_id


def cabecalho_dashboard(periodo: Periodo, registros) -> None:
    """Frescor dos dados: quando atualizou e quantos registros entraram na conta."""
    agora = datetime.now().strftime("%H:%M:%S")
    selo = (
        "<span class='pn-selo'>parcial</span>"
        if periodo.parcial
        else "<span class='pn-selo pn-selo-fechado'>período fechado</span>"
    )
    st.markdown(
        f"<div class='pn-frescor'>Atualizado às {agora} · "
        f"{int(registros or 0)} registros considerados · "
        f"{periodo.inicio.strftime('%d/%m/%Y')} a {periodo.fim.strftime('%d/%m/%Y')} {selo}</div>",
        unsafe_allow_html=True,
    )
    if periodo.parcial:
        st.caption(
            "O período ainda está em andamento, então os números devem crescer até o fim dele."
        )


def erro(mensagem: str) -> None:
    """Erro de validação em linguagem simples, nunca em linguagem de programador."""
    st.error(mensagem, icon=":material/error:")


def sucesso(mensagem: str) -> None:
    st.toast(mensagem, icon="✅")
