"""Toda leitura de dado identificado deixa rastro.

É exigência do art. 37 da LGPD e é também proteção da equipe: se um dia houver suspeita de
vazamento, existe de onde partir.
"""

from datetime import date

from services import modelo, restrito
from services.db import conexao


def _auditoria(tabela: str | None = None) -> list[dict]:
    from sqlalchemy import select

    consulta = select(modelo.auditoria)
    if tabela:
        consulta = consulta.where(modelo.auditoria.c.tabela == tabela)
    with conexao() as con:
        return [dict(linha) for linha in con.execute(consulta).mappings()]


def test_cadastro_de_pessoa_fica_auditado(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    registros = _auditoria("pessoa_contato")
    assert len(registros) == 1
    assert registros[0]["acao"] == "criacao"
    assert registros[0]["registro_id"] == pessoa["id"]
    assert registros[0]["usuario_id"] == tecnico.usuario_id


def test_leitura_de_contato_fica_auditada(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    antes = len(_auditoria())

    contato = restrito.contato(tecnico, pessoa["id"])
    assert contato["nome"] == "Fulana Fictícia"

    leituras = [r for r in _auditoria("pessoa_contato") if r["acao"] == "leitura"]
    assert len(leituras) == 1
    assert len(_auditoria()) == antes + 1


def test_busca_por_nome_fica_auditada(tecnico, nova_pessoa):
    nova_pessoa(tecnico)
    restrito.buscar_por_nome(tecnico, "fulana")
    assert any(r["acao"] == "leitura" for r in _auditoria("pessoa_contato"))


def test_revogacao_apaga_o_nome_e_fica_auditada(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    restrito.revogar_consentimento(tecnico, pessoa["id"])

    contato = restrito.contato(tecnico, pessoa["id"])
    assert contato["nome"] is None
    assert contato["telefone"] is None
    assert contato["consentimento_revogado_em"] is not None
    assert any(r["acao"] == "revogacao_consentimento" for r in _auditoria("pessoa_contato"))


def test_revogacao_mantem_o_historico_estatistico(tecnico, nova_pessoa, nova_atividade):
    """A pessoa sai do cadastro identificado, mas o atendimento continuou existindo."""
    from analytics import indicadores

    pessoa = nova_pessoa(tecnico)
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[pessoa["id"]])

    antes = indicadores.cartoes(tecnico, date(2026, 3, 1), date(2026, 3, 31))["participacoes"]
    restrito.revogar_consentimento(tecnico, pessoa["id"])
    depois = indicadores.cartoes(tecnico, date(2026, 3, 1), date(2026, 3, 31))["participacoes"]

    assert antes == depois == 1


def test_encaminhamento_auditado_na_criacao_e_na_leitura(tecnico, nova_pessoa):
    from services import dominios

    pessoa = nova_pessoa(tecnico)
    destino = dominios.opcoes("destino_encaminhamento")["CRAS"]
    restrito.criar_encaminhamento(tecnico, pessoa["id"], destino)
    restrito.listar_encaminhamentos(tecnico)

    acoes = {r["acao"] for r in _auditoria("encaminhamento")}
    assert acoes == {"criacao", "leitura"}


def test_agregado_de_dashboard_nao_enche_a_auditoria(tecnico, nova_pessoa):
    """Número agregado não identifica ninguém; auditar a cada 60 segundos só geraria ruído."""
    from services import dominios

    pessoa = nova_pessoa(tecnico)
    restrito.criar_encaminhamento(
        tecnico, pessoa["id"], dominios.opcoes("destino_encaminhamento")["CRAS"]
    )
    antes = len(_auditoria())

    restrito.resumo_encaminhamentos(tecnico, date(2026, 1, 1), date(2026, 12, 31))
    restrito.encaminhamentos_por_destino(tecnico, date(2026, 1, 1), date(2026, 12, 31))

    assert len(_auditoria()) == antes


def test_admin_le_a_trilha(admin, nova_pessoa):
    nova_pessoa(admin)
    trilha = restrito.listar_auditoria(admin)
    assert trilha
    assert trilha[0]["papel"] == "admin"
