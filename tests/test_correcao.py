"""Corrigir e desativar: o que foi registrado errado precisa ter conserto.

Exclusão é sempre lógica, e toda correção fica na trilha de auditoria.
"""

from datetime import date, datetime, time

import pytest
from streamlit.testing.v1 import AppTest

from analytics import indicadores
from services import atividades, dominios, modelo, pessoas
from services.db import conexao
from services.seguranca import ErroDeValidacao, PermissaoNegada

MARCO = (date(2026, 3, 1), date(2026, 3, 31))


def _acoes_auditadas(tabela: str) -> list[str]:
    from sqlalchemy import select

    with conexao() as con:
        return [
            linha["acao"]
            for linha in con.execute(
                select(modelo.auditoria).where(modelo.auditoria.c.tabela == tabela)
            ).mappings()
        ]


def test_corrigir_horario_da_atividade(tecnico, nova_atividade):
    atividade = nova_atividade(tecnico, dia=date(2026, 3, 10))
    atividades.atualizar(tecnico, atividade, hora_inicio=time(9, 0), hora_fim=time(12, 0))

    corrigida = atividades.por_id(tecnico, atividade)
    assert corrigida["hora_inicio"] == time(9, 0)
    assert corrigida["duracao_minutos"] == 180
    assert "alteracao" in _acoes_auditadas("atividade")


def test_correcao_mantem_as_validacoes(tecnico, nova_atividade):
    atividade = nova_atividade(tecnico, dia=date(2026, 3, 10))
    with pytest.raises(ErroDeValidacao, match="término"):
        atividades.atualizar(tecnico, atividade, hora_inicio=time(16, 0), hora_fim=time(14, 0))


def test_campo_corrige_so_o_que_ele_registrou(campo, tecnico, nova_atividade):
    de_outra_pessoa = nova_atividade(tecnico, dia=date(2026, 3, 10))
    with pytest.raises(ErroDeValidacao, match="outra pessoa"):
        atividades.atualizar(campo, de_outra_pessoa, descricao_curta="mexendo no alheio")

    propria = nova_atividade(campo, dia=date(2026, 3, 11))
    atividades.atualizar(campo, propria, descricao_curta="oficina de dança")
    assert atividades.por_id(campo, propria)["descricao_curta"] == "oficina de dança"


def test_campo_nao_desativa_atividade(campo, nova_atividade):
    propria = nova_atividade(campo, dia=date(2026, 3, 10))
    with pytest.raises(PermissaoNegada):
        atividades.desativar(campo, propria)


def test_atividade_desativada_sai_dos_indicadores(tecnico, nova_pessoa, nova_atividade):
    pessoa = nova_pessoa(tecnico)
    atividade = nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[pessoa["id"]])
    assert indicadores.cartoes(tecnico, *MARCO)["atividades"] == 1

    atividades.desativar(tecnico, atividade)

    cartoes = indicadores.cartoes(tecnico, *MARCO)
    assert cartoes["atividades"] == 0
    assert cartoes["participacoes"] == 0
    assert "desativacao" in _acoes_auditadas("atividade")
    # Exclusão lógica: a linha continua no banco.
    assert atividades.por_id(tecnico, atividade) is None


def test_corrigir_perfis_e_gestante_da_pessoa(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico, faixa="18-29")
    perfil_trans = dominios.opcoes("perfil")["Pessoa trans"]

    pessoas.atualizar(tecnico, pessoa["id"], perfis=[perfil_trans], gestante=True)

    assert pessoas.perfis_de(tecnico, pessoa["id"]) == [perfil_trans]
    assert pessoas.buscar_por_codigo(tecnico, pessoa["codigo"])["gestante"]
    assert "alteracao" in _acoes_auditadas("pessoa")


def test_correcao_de_pessoa_recusa_combinacao_impossivel(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico, faixa="30-44")
    with pytest.raises(ErroDeValidacao, match="não combina"):
        pessoas.atualizar(
            tecnico, pessoa["id"], perfis=[dominios.opcoes("perfil")["Criança"]]
        )


def test_correcao_de_pessoa_nao_aceita_dado_de_contato(tecnico, nova_pessoa):
    """Nome e telefone se alteram na tela de contato, que audita a operação."""
    pessoa = nova_pessoa(tecnico)
    with pytest.raises(PermissaoNegada):
        pessoas.atualizar(tecnico, pessoa["id"], nome="Outro Nome")


def test_pessoa_desativada_sai_da_busca_e_mantem_historico(tecnico, nova_pessoa,
                                                           nova_atividade):
    pessoa = nova_pessoa(tecnico)
    nova_atividade(tecnico, dia=date(2026, 3, 10), participantes=[pessoa["id"]])

    pessoas.desativar(tecnico, pessoa["id"])

    assert pessoas.buscar_por_codigo(tecnico, pessoa["codigo"]) is None
    assert "desativacao" in _acoes_auditadas("pessoa")
    # A participação já registrada continua contando: o atendimento aconteceu.
    assert indicadores.cartoes(tecnico, *MARCO)["participacoes"] == 1


def test_campo_nao_desativa_pessoa(campo, nova_pessoa):
    pessoa = nova_pessoa(campo)
    with pytest.raises(PermissaoNegada):
        pessoas.desativar(campo, pessoa["id"])


def _abrir(pagina: str, sessao) -> AppTest:
    app = AppTest.from_file(pagina, default_timeout=60)
    app.session_state["sessao"] = sessao
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    return app.run()


def test_tela_de_inicio_oferece_correcao(campo, nova_atividade):
    nova_atividade(campo, dia=date(2026, 3, 10))
    app = _abrir("pages/inicio.py", campo)

    assert not app.exception
    assert any(botao.label == "Salvar correção" for botao in app.button)
    assert not any(botao.label == "Desativar atividade" for botao in app.button)


def test_tela_de_inicio_deixa_tecnico_desativar(tecnico, nova_atividade):
    nova_atividade(tecnico, dia=date(2026, 3, 10))
    app = _abrir("pages/inicio.py", tecnico)

    assert any(botao.label == "Desativar atividade" for botao in app.button)


def test_correcao_de_pessoa_na_tela(tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    app = _abrir("pages/cadastrar_pessoa.py", tecnico)

    busca = next(campo for campo in app.text_input if campo.label == "Código da pessoa")
    busca.set_value(pessoa["codigo"]).run()

    assert not app.exception
    assert any(botao.label == "Revogar consentimento" for botao in app.button)
    assert any(botao.label == "Desativar pessoa" for botao in app.button)


def test_campo_nao_ve_contato_na_correcao(campo, nova_pessoa):
    pessoa = nova_pessoa(campo)
    app = _abrir("pages/cadastrar_pessoa.py", campo)

    busca = next(c for c in app.text_input if c.label == "Código da pessoa")
    busca.set_value(pessoa["codigo"]).run()

    assert not app.exception
    rotulos = [c.label for c in app.text_input]
    assert "Telefone" not in rotulos
    assert not any(b.label == "Revogar consentimento" for b in app.button)
