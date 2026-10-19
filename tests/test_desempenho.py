"""Cada dashboard precisa carregar em menos de 3 segundos com 18 meses de dados.

Roda o seed de demonstração inteiro (300 pessoas, ~1.100 atividades, ~11 mil participações) e
cronometra o conjunto de indicadores de cada página. É o teste que avisa se alguém escrever uma
consulta que varre o banco inteiro sem usar índice.
"""

import time
from datetime import date, timedelta

import pytest

from analytics import indicadores, pendencias
from scripts import seed_demo

LIMITE_SEGUNDOS = 3.0


@pytest.fixture
def muitos_dados(banco, admin):
    seed_demo.main()
    return admin


def _periodo_de_um_ano() -> tuple[date, date]:
    fim = date.today()
    return fim - timedelta(days=365), fim


def _cronometrar(funcao, *args) -> float:
    inicio = time.perf_counter()
    funcao(*args)
    return time.perf_counter() - inicio


def test_volume_do_seed(muitos_dados):
    """Se o volume cair, o teste de desempenho deixa de provar qualquer coisa."""
    from services.db import consultar_valor

    assert consultar_valor("select count(*) from pessoa") == 300
    assert consultar_valor("select count(*) from atividade") > 900
    assert consultar_valor("select count(*) from participacao") > 5000


def test_visao_geral_carrega_rapido(muitos_dados):
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    gasto = sum(
        [
            _cronometrar(indicadores.cartoes, sessao, inicio, fim),
            _cronometrar(indicadores.participacoes_por_semana, sessao, inicio, fim),
            _cronometrar(indicadores.pessoas_por_programa, sessao, inicio, fim),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"visão geral levou {gasto:.2f}s"


def test_programas_carrega_rapido(muitos_dados):
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    gasto = sum(
        [
            _cronometrar(indicadores.atividades_por_programa, sessao, inicio, fim),
            _cronometrar(indicadores.taxa_recorrencia, sessao, inicio, fim),
            _cronometrar(indicadores.resumo_por_programa, sessao, inicio, fim),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"programas levou {gasto:.2f}s"


def test_publico_carrega_rapido(muitos_dados):
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    gasto = sum(
        [
            _cronometrar(indicadores.cartoes, sessao, inicio, fim),
            _cronometrar(indicadores.pessoas_por_faixa, sessao, inicio, fim),
            _cronometrar(indicadores.pessoas_por_genero, sessao, inicio, fim),
            _cronometrar(indicadores.pessoas_por_perfil, sessao, inicio, fim),
            _cronometrar(indicadores.novos_cadastros_por_mes, sessao, inicio, fim),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"público atendido levou {gasto:.2f}s"


def test_territorio_e_equipe_carregam_rapido(muitos_dados):
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    gasto = sum(
        [
            _cronometrar(indicadores.contatos_anonimos_por_local, sessao, inicio, fim),
            _cronometrar(indicadores.abordagens_por_semana, sessao, inicio, fim),
            _cronometrar(indicadores.itens_por_tipo, sessao, inicio, fim),
            _cronometrar(indicadores.horas_voluntariado_por_mes, sessao, inicio, fim),
            _cronometrar(indicadores.composicao_equipe, sessao, inicio, fim),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"território e equipe levaram {gasto:.2f}s"


def test_encaminhamentos_e_parceiro_carregam_rapido(muitos_dados):
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    gasto = sum(
        [
            _cronometrar(indicadores.resumo_encaminhamentos, sessao, inicio, fim),
            _cronometrar(indicadores.encaminhamentos_por_destino, sessao, inicio, fim),
            _cronometrar(indicadores.encaminhamentos_por_status, sessao, inicio, fim),
            _cronometrar(indicadores.ext_cartoes, sessao, inicio, fim),
            _cronometrar(indicadores.ext_pessoas_por_programa, sessao, inicio, fim),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"encaminhamentos e parceiro levaram {gasto:.2f}s"


def test_pendencias_carrega_rapido(muitos_dados):
    sessao = muitos_dados
    gasto = sum(
        [
            _cronometrar(pendencias.atividades_sem_pessoas, sessao),
            _cronometrar(pendencias.atividades_sem_equipe, sessao),
            _cronometrar(pendencias.gestantes_para_revisar, sessao),
        ]
    )
    assert gasto < LIMITE_SEGUNDOS, f"pendências levou {gasto:.2f}s"


def test_o_seed_gera_pendencias(muitos_dados):
    """A tela de Pendências precisa ter o que mostrar na demonstração."""
    from services import restrito

    sessao = muitos_dados
    assert pendencias.atividades_sem_pessoas(sessao)
    assert pendencias.atividades_sem_equipe(sessao)
    assert restrito.encaminhamentos_parados(sessao)
    assert restrito.pessoas_sem_consentimento(sessao)


def test_nenhum_dashboard_abre_vazio_com_o_seed(muitos_dados):
    """Critério da especificação: com o seed, nenhum dashboard aparece sem dados."""
    sessao = muitos_dados
    inicio, fim = _periodo_de_um_ano()

    cartoes = indicadores.cartoes(sessao, inicio, fim)
    assert cartoes["pessoas_unicas"] > 0
    assert cartoes["atividades"] > 0
    assert cartoes["contatos_anonimos"] > 0
    assert cartoes["itens"] > 0
    assert cartoes["horas_voluntariado"] > 0

    for funcao in (
        indicadores.pessoas_por_programa,
        indicadores.atividades_por_programa,
        indicadores.taxa_recorrencia,
        indicadores.pessoas_por_faixa,
        indicadores.pessoas_por_genero,
        indicadores.pessoas_por_perfil,
        indicadores.contatos_anonimos_por_local,
        indicadores.itens_por_tipo,
        indicadores.horas_voluntariado_por_mes,
        indicadores.composicao_equipe,
        indicadores.novos_cadastros_por_mes,
    ):
        assert not funcao(sessao, inicio, fim).empty, f"{funcao.__name__} voltou vazio"

    assert indicadores.resumo_encaminhamentos(sessao, inicio, fim)["total"] > 0
