"""Gráficos dos dashboards.

Regras de desenho, decididas uma vez aqui para todos os dashboards ficarem iguais:

* **Uma cor só para gráfico de magnitude.** Barra de "pessoas por programa" compara tamanho,
  não identidade: pintar cada programa de uma cor diferente não informa nada e faz o leitor
  procurar legenda. Assim também se cumpre, por construção, a regra de nunca pintar o mesmo
  programa de cores diferentes em páginas diferentes.
* **Cor com significado só no empilhado de status**, onde a cor é a informação. A ordem das
  faixas (sem retorno, enviado, em andamento, concluído) foi escolhida para que vermelho e
  verde nunca fiquem lado a lado, que é o par que some para quem tem daltonismo.
* **Nunca dois eixos verticais.** Quando há duas medidas (atividades e horas), são dois
  gráficos.
* Grade discreta, rótulo direto nos valores, e uma frase em português abaixo de cada gráfico
  dizendo o que ele mostra.

A paleta foi validada para contraste e daltonismo (protanopia, deuteranopia, tritanopia).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

LARANJA = "#eb6834"  # cor da marca; usada em tudo que é magnitude
PRETO = "#0b0b0b"
CINZA_TEXTO = "#52514e"
CINZA_GRADE = "#e8e6e1"
SUPERFICIE = "#fcfcfb"

# Ordem proposital: do pior para o melhor desfecho, e nunca vermelho junto de verde.
CORES_STATUS = {
    "sem_retorno": "#e34948",
    "enviado": "#2a78d6",
    "em_andamento": "#eda100",
    "concluido": "#008300",
}

NOMES_STATUS = {
    "sem_retorno": "Sem retorno",
    "enviado": "Enviado",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
}


def _moldura(figura: go.Figure, altura: int = 320) -> go.Figure:
    figura.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor=SUPERFICIE,
        plot_bgcolor=SUPERFICIE,
        font=dict(family="system-ui, sans-serif", size=13, color=PRETO),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", font_size=13),
        bargap=0.25,
    )
    figura.update_xaxes(
        showgrid=False, zeroline=False, linecolor=CINZA_GRADE, tickfont=dict(color=CINZA_TEXTO)
    )
    figura.update_yaxes(
        showgrid=True,
        gridcolor=CINZA_GRADE,
        zeroline=False,
        tickfont=dict(color=CINZA_TEXTO),
    )
    return figura


def _vazio(titulo: str, frase: str) -> None:
    st.markdown(f"**{titulo}**")
    st.info("Ainda não há dados para este período.")
    st.caption(frase)


def barras(df: pd.DataFrame, categoria: str, valor: str, titulo: str, frase: str,
           horizontal: bool = False, sufixo: str = "") -> None:
    """Gráfico de barras de uma cor, com o valor escrito em cada barra."""
    if df.empty or df[valor].fillna(0).sum() == 0:
        return _vazio(titulo, frase)

    st.markdown(f"**{titulo}**")
    dados = df.dropna(subset=[valor]).copy()
    rotulos = [f"{v:g}{sufixo}" for v in dados[valor]]

    if horizontal:
        dados = dados.iloc[::-1]
        rotulos = rotulos[::-1]
        figura = go.Figure(
            go.Bar(
                x=dados[valor],
                y=dados[categoria],
                orientation="h",
                marker_color=LARANJA,
                text=rotulos,
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}: %{x}" + sufixo + "<extra></extra>",
            )
        )
        figura = _moldura(figura, altura=max(260, 34 * len(dados)))
        figura.update_xaxes(showgrid=True, gridcolor=CINZA_GRADE)
        figura.update_yaxes(showgrid=False)
    else:
        figura = go.Figure(
            go.Bar(
                x=dados[categoria],
                y=dados[valor],
                marker_color=LARANJA,
                text=rotulos,
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{x}: %{y}" + sufixo + "<extra></extra>",
            )
        )
        figura = _moldura(figura)

    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})
    st.caption(frase)


def linha(df: pd.DataFrame, eixo_x: str, valor: str, titulo: str, frase: str) -> None:
    """Série no tempo: linha de 2px com marcador em cada ponto e tooltip no eixo."""
    if df.empty or df[valor].fillna(0).sum() == 0:
        return _vazio(titulo, frase)

    st.markdown(f"**{titulo}**")
    figura = go.Figure(
        go.Scatter(
            x=df[eixo_x],
            y=df[valor],
            mode="lines+markers",
            line=dict(color=LARANJA, width=2),
            marker=dict(size=8, color=LARANJA),
            hovertemplate="%{x}: %{y}<extra></extra>",
        )
    )
    figura = _moldura(figura)
    figura.update_layout(hovermode="x unified")
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})
    st.caption(frase)


def barras_empilhadas_por_status(df: pd.DataFrame, categoria: str, valor: str, titulo: str,
                                 frase: str) -> None:
    """Empilhado onde a cor é a informação: situação de cada encaminhamento.

    Cada faixa leva o número escrito dentro, porque cor sozinha não pode ser a única pista.
    """
    if df.empty:
        return _vazio(titulo, frase)

    st.markdown(f"**{titulo}**")
    figura = go.Figure()
    for status, cor in CORES_STATUS.items():
        parte = df[df["status"] == status]
        if parte.empty:
            continue
        figura.add_bar(
            x=parte[categoria],
            y=parte[valor],
            name=NOMES_STATUS[status],
            marker=dict(color=cor, line=dict(color=SUPERFICIE, width=2)),
            text=parte[valor],
            textposition="inside",
            insidetextfont=dict(color="white"),
            hovertemplate="%{x} — " + NOMES_STATUS[status] + ": %{y}<extra></extra>",
        )
    figura = _moldura(figura, altura=360)
    figura.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(orientation="h", y=-0.25, font=dict(color=CINZA_TEXTO)),
    )
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})
    st.caption(frase)
