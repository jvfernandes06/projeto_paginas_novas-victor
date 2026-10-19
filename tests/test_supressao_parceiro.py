"""A visão do parceiro nunca mostra contagem menor que 5.

Num território pequeno, "1 gestante atendida no Kidstinga em março" é quase um nome. Por isso
as funções ext_* devolvem vazio no número e a etiqueta "<5" no lugar.
"""

from datetime import date

import pytest

from analytics import indicadores
from analytics.indicadores import MINIMO_PARA_MOSTRAR
from services import dominios

PERIODO = (date(2026, 3, 1), date(2026, 3, 31))

COLUNAS_DE_CONTAGEM = {
    "ext_pessoas_por_programa": "pessoas",
    "ext_participacoes_por_mes": "participacoes",
}


@pytest.fixture
def poucas_pessoas(tecnico, nova_pessoa, nova_atividade):
    """Três pessoas no Kidstinga: abaixo do mínimo de propósito."""
    pessoas = [nova_pessoa(tecnico) for _ in range(3)]
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[p["id"] for p in pessoas])
    return pessoas


@pytest.fixture
def muitas_pessoas(tecnico, nova_pessoa, nova_atividade):
    """Sete pessoas no Kidstinga: acima do mínimo."""
    pessoas = [nova_pessoa(tecnico) for _ in range(7)]
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[p["id"] for p in pessoas])
    return pessoas


@pytest.mark.parametrize("funcao, coluna", COLUNAS_DE_CONTAGEM.items())
def test_contagem_pequena_nunca_aparece(funcao, coluna, poucas_pessoas, parceiro):
    df = getattr(indicadores, funcao)(parceiro, *PERIODO)
    assert not df.empty
    assert df[coluna].dropna().empty, "número abaixo de 5 vazou para a visão do parceiro"
    assert (df[f"{coluna}_rotulo"] == "<5").all()


@pytest.mark.parametrize("funcao, coluna", COLUNAS_DE_CONTAGEM.items())
def test_contagem_grande_aparece(funcao, coluna, muitas_pessoas, parceiro):
    df = getattr(indicadores, funcao)(parceiro, *PERIODO)
    assert (df[coluna].dropna() >= MINIMO_PARA_MOSTRAR).all()
    assert df[coluna].dropna().any()


def test_cartoes_do_parceiro_suprimem(poucas_pessoas, parceiro):
    cartoes = indicadores.ext_cartoes(parceiro, *PERIODO)
    assert cartoes["pessoas_unicas"] is None
    assert cartoes["pessoas_unicas_rotulo"] == "<5"


def test_cartoes_do_parceiro_mostram_numero_grande(muitas_pessoas, parceiro):
    cartoes = indicadores.ext_cartoes(parceiro, *PERIODO)
    assert cartoes["pessoas_unicas"] == 7


def test_nenhuma_funcao_ext_devolve_numero_abaixo_do_minimo(muitas_pessoas, nova_pessoa,
                                                            nova_atividade, tecnico, parceiro):
    """Cenário misto: um programa com muita gente e outro com pouca."""
    poucas = [nova_pessoa(tecnico) for _ in range(2)]
    nova_atividade(
        tecnico,
        dia=date(2026, 3, 12),
        programa="Hip Hop",
        participantes=[p["id"] for p in poucas],
    )

    for funcao, coluna in COLUNAS_DE_CONTAGEM.items():
        df = getattr(indicadores, funcao)(parceiro, *PERIODO)
        valores = df[coluna].dropna()
        assert (valores >= MINIMO_PARA_MOSTRAR).all(), f"{funcao} devolveu contagem pequena"

    cartoes = indicadores.ext_cartoes(parceiro, *PERIODO)
    for chave, valor in cartoes.items():
        if chave.endswith("_rotulo") or chave in ("registros", "horas_voluntariado"):
            continue
        assert valor is None or valor >= MINIMO_PARA_MOSTRAR


def test_parceiro_nao_alcanca_indicador_interno(parceiro):
    """A versão interna dos mesmos números exige Técnico ou Admin."""
    from services.seguranca import PermissaoNegada

    with pytest.raises(PermissaoNegada):
        indicadores.cartoes(parceiro, *PERIODO)
    with pytest.raises(PermissaoNegada):
        indicadores.pessoas_por_programa(parceiro, *PERIODO)


def test_programa_filtrado_tambem_suprime(poucas_pessoas, parceiro):
    kidstinga = dominios.opcoes("programa")["Kidstinga"]
    df = indicadores.ext_pessoas_por_programa(parceiro, *PERIODO, kidstinga)
    assert df["pessoas"].dropna().empty
