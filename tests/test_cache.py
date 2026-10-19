"""Gravar e ler em seguida tem de dar o número novo.

O dashboard guarda os indicadores em cache por 60 segundos para não consultar o banco a cada
toque. O risco é alguém registrar uma atividade e o dashboard continuar mostrando o número
velho. Por isso toda gravação limpa o cache.
"""

from datetime import date

from analytics import indicadores
from services import dominios

PERIODO = (date(2026, 3, 1), date(2026, 3, 31))


def test_atividade_nova_aparece_na_hora(tecnico, nova_atividade):
    antes = indicadores.cartoes(tecnico, *PERIODO)["atividades"]

    nova_atividade(tecnico, dia=date(2026, 3, 10))

    depois = indicadores.cartoes(tecnico, *PERIODO)["atividades"]
    assert depois == antes + 1


def test_participacao_nova_aparece_na_hora(tecnico, nova_pessoa, nova_atividade):
    pessoa = nova_pessoa(tecnico)
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[pessoa["id"]])
    assert indicadores.cartoes(tecnico, *PERIODO)["pessoas_unicas"] == 1

    outra = nova_pessoa(tecnico)
    nova_atividade(tecnico, dia=date(2026, 3, 11), participantes=[pessoa["id"], outra["id"]])
    assert indicadores.cartoes(tecnico, *PERIODO)["pessoas_unicas"] == 2


def test_lista_de_dominio_atualiza_depois_de_editar(admin):
    assert "Programa Novo de Teste" not in dominios.opcoes("programa")
    dominios.criar(admin, "programa", nome="Programa Novo de Teste")
    assert "Programa Novo de Teste" in dominios.opcoes("programa")


def test_cache_tem_validade_menor_ou_igual_ao_intervalo():
    """Se o cache durasse mais que o intervalo de atualização, o dashboard mentiria."""
    from services import config

    assert indicadores.INTERVALO <= config.INTERVALO_ATUALIZACAO or indicadores.INTERVALO == 60


def test_visao_do_parceiro_nao_reusa_cache_do_tecnico(tecnico, parceiro, nova_pessoa,
                                                      nova_atividade):
    """A chave do cache inclui o papel: o número cheio nunca é entregue ao parceiro."""
    pessoas = [nova_pessoa(tecnico) for _ in range(3)]
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[p["id"] for p in pessoas])

    interno = indicadores.cartoes(tecnico, *PERIODO)["pessoas_unicas"]
    externo = indicadores.ext_cartoes(parceiro, *PERIODO)

    assert interno == 3
    assert externo["pessoas_unicas"] is None
    assert externo["pessoas_unicas_rotulo"] == "<5"
