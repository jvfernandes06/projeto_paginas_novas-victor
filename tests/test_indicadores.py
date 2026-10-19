"""Os indicadores, conferidos sobre um cenário montado à mão.

Os números esperados estão escritos no teste junto com a conta que os justifica. Se alguém
mudar a definição de um indicador sem querer, o teste diz exatamente qual número mudou.

O cenário é montado com datas fixas (março e abril de 2026), e não com o seed de demonstração,
que é aleatório e relativo a hoje.
"""

from datetime import date, time

import pytest

from analytics import indicadores
from services import dominios

MARCO = (date(2026, 3, 1), date(2026, 3, 31))
ABRIL = (date(2026, 4, 1), date(2026, 4, 30))
BIMESTRE = (date(2026, 3, 1), date(2026, 4, 30))


@pytest.fixture
def cenario(tecnico, nova_pessoa, nova_atividade):
    """Cenário documentado.

    Três pessoas: Ana (30-44), Bia (12-17, adolescente), Cris (18-29, gestante).

    Março:
      - 10/03 Kidstinga 14h-16h (2 h): Ana, Bia, Cris        -> 3 participações
      - 17/03 Kidstinga 14h-16h (2 h): Ana                   -> 1 participação
      - 24/03 Kidstinga 14h-16h (2 h): Ana                   -> 1 participação
      - 26/03 Abordagem de Rua 20h-22h (2 h): 20 abordagens, 50 preservativos
      - equipe: 2 voluntários em cada uma das três atividades do Kidstinga
    Abril:
      - 07/04 Kidstinga 14h-16h (2 h): Ana, Bia              -> 2 participações

    Contas esperadas:
      - pessoas únicas em março = 3 (Ana, Bia, Cris)
      - pessoas únicas em abril = 2 (Ana, Bia)
      - pessoas únicas no bimestre = 3, e NÃO 5: Ana e Bia participaram nos dois meses
      - participações em março = 5; em abril = 2
      - atividades em março = 4 (3 do Kidstinga + 1 de rua); horas = 8
      - recorrência do Kidstinga em março: 1 de 3 pessoas com 3+ presenças = 33,3%
      - horas de voluntariado em março = 3 atividades x 2 voluntários x 2 h = 12 h
      - contatos anônimos em março = 20
    """
    ana = nova_pessoa(tecnico, faixa="30-44")
    bia = nova_pessoa(tecnico, faixa="12-17", perfis=("Adolescente",))
    cris = nova_pessoa(tecnico, faixa="18-29", gestante=True)

    voluntario = dominios.opcoes("funcao_equipe")["Voluntário"]
    equipe = {voluntario: 2}

    nova_atividade(
        tecnico,
        dia=date(2026, 3, 10),
        participantes=[ana["id"], bia["id"], cris["id"]],
        equipe=equipe,
    )
    nova_atividade(tecnico, dia=date(2026, 3, 17), participantes=[ana["id"]], equipe=equipe)
    nova_atividade(tecnico, dia=date(2026, 3, 24), participantes=[ana["id"]], equipe=equipe)
    nova_atividade(
        tecnico,
        dia=date(2026, 3, 26),
        programa="Abordagem de Rua",
        local="Rua — Jardim Itatinga",
        tipo="Abordagem",
        hora_inicio=time(20, 0),
        hora_fim=time(22, 0),
        contagem={"abordagens": 20, "criancas": 0, "adolescentes": 2, "adultos": 18},
        itens={dominios.opcoes("tipo_item")["Preservativo"]: 50},
    )
    nova_atividade(
        tecnico, dia=date(2026, 4, 7), participantes=[ana["id"], bia["id"]], equipe=equipe
    )
    return {"ana": ana, "bia": bia, "cris": cris}


def test_cartoes_de_marco(cenario, tecnico):
    cartoes = indicadores.cartoes(tecnico, *MARCO)
    assert cartoes["pessoas_unicas"] == 3
    assert cartoes["participacoes"] == 5
    assert cartoes["atividades"] == 4
    assert cartoes["contatos_anonimos"] == 20
    assert cartoes["itens"] == 50
    assert cartoes["horas_voluntariado"] == 12
    assert cartoes["gestantes"] == 1


def test_pessoas_unicas_nao_e_somavel(cenario, tecnico):
    """O motivo de os indicadores serem função com período, e não view mensal."""
    marco = indicadores.cartoes(tecnico, *MARCO)["pessoas_unicas"]
    abril = indicadores.cartoes(tecnico, *ABRIL)["pessoas_unicas"]
    bimestre = indicadores.cartoes(tecnico, *BIMESTRE)["pessoas_unicas"]

    assert (marco, abril) == (3, 2)
    assert bimestre == 3
    assert bimestre != marco + abril, "somar os meses contaria duas vezes quem voltou"


def test_participacoes_sao_somaveis(cenario, tecnico):
    """Participação é evento: aí somar está certo. Pessoa única é que não soma."""
    marco = indicadores.cartoes(tecnico, *MARCO)["participacoes"]
    abril = indicadores.cartoes(tecnico, *ABRIL)["participacoes"]
    bimestre = indicadores.cartoes(tecnico, *BIMESTRE)["participacoes"]
    assert bimestre == marco + abril == 7


def test_atividades_e_horas_por_programa(cenario, tecnico):
    df = indicadores.atividades_por_programa(tecnico, *MARCO).set_index("programa")
    assert df.loc["Kidstinga", "atividades"] == 3
    assert df.loc["Kidstinga", "horas"] == 6
    assert df.loc["Abordagem de Rua", "atividades"] == 1


def test_taxa_de_recorrencia(cenario, tecnico):
    df = indicadores.taxa_recorrencia(tecnico, *MARCO).set_index("programa")
    assert df.loc["Kidstinga", "pessoas"] == 3
    assert df.loc["Kidstinga", "pessoas_3mais"] == 1  # só Ana foi três vezes
    assert df.loc["Kidstinga", "taxa_pct"] == pytest.approx(33.3)


def test_publico_por_faixa_e_perfil(cenario, tecnico):
    faixas = indicadores.pessoas_por_faixa(tecnico, *MARCO).set_index("faixa_etaria")
    assert faixas.loc["12 a 17 anos", "pessoas"] == 1
    assert faixas.loc["30 a 44 anos", "pessoas"] == 1

    perfis = indicadores.pessoas_por_perfil(tecnico, *MARCO).set_index("perfil")
    assert perfis.loc["Adolescente", "pessoas"] == 1


def test_itens_e_contagem_de_rua(cenario, tecnico):
    itens = indicadores.itens_por_tipo(tecnico, *MARCO).set_index("tipo_item")
    assert itens.loc["Preservativo", "quantidade"] == 50

    locais = indicadores.contatos_anonimos_por_local(tecnico, *MARCO).set_index("local")
    assert locais.loc["Rua — Jardim Itatinga", "abordagens"] == 20


def test_filtro_de_programa(cenario, tecnico):
    kidstinga = dominios.opcoes("programa")["Kidstinga"]
    cartoes = indicadores.cartoes(tecnico, *MARCO, kidstinga)
    assert cartoes["atividades"] == 3
    assert cartoes["contatos_anonimos"] == 0  # a abordagem de rua é de outro programa


def test_participacoes_por_semana(cenario, tecnico):
    df = indicadores.participacoes_por_semana(tecnico, *MARCO)
    assert df["participacoes"].sum() == 5
    assert len(df) >= 3  # três semanas com atividade do Kidstinga


def test_horas_de_voluntariado_por_mes(cenario, tecnico):
    df = indicadores.horas_voluntariado_por_mes(tecnico, *BIMESTRE).set_index("mes")
    assert df.loc["2026-03", "horas"] == 12
    assert df.loc["2026-04", "horas"] == 4
