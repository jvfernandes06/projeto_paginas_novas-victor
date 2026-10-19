"""O sistema recusa dado ruim, com mensagem que a pessoa em campo entende.

Ninguém vai limpar esses dados depois: cada regra da especificação tem aqui um teste que tenta
gravar o erro e exige a recusa.
"""

from datetime import date, time, timedelta

import pytest

from services import atividades, dominios, pessoas
from services.seguranca import ErroDeValidacao


def test_pessoa_sem_consentimento_nao_salva(tecnico):
    faixa = next(f["id"] for f in dominios.listar("faixa_etaria") if f["codigo"] == "30-44")
    with pytest.raises(ErroDeValidacao, match="consentimento"):
        pessoas.criar(
            tecnico,
            faixa_etaria_id=faixa,
            genero_id=dominios.opcoes("genero")["Mulher cisgênero"],
            bairro_id=None,
            perfis=[],
            consentimento_data=None,
            consentimento_por="propria_pessoa",
        )


def test_menor_de_idade_exige_responsavel(tecnico):
    faixa = next(f["id"] for f in dominios.listar("faixa_etaria") if f["codigo"] == "12-17")
    with pytest.raises(ErroDeValidacao, match="responsável legal"):
        pessoas.criar(
            tecnico,
            faixa_etaria_id=faixa,
            genero_id=dominios.opcoes("genero")["Mulher cisgênero"],
            bairro_id=None,
            perfis=[],
            consentimento_data=date(2026, 1, 1),
            consentimento_por="propria_pessoa",
        )


def test_menor_com_responsavel_salva(tecnico):
    faixa = next(f["id"] for f in dominios.listar("faixa_etaria") if f["codigo"] == "12-17")
    criada = pessoas.criar(
        tecnico,
        faixa_etaria_id=faixa,
        genero_id=dominios.opcoes("genero")["Mulher cisgênero"],
        bairro_id=None,
        perfis=[],
        consentimento_data=date(2026, 1, 1),
        consentimento_por="responsavel_legal",
        nome_responsavel="Responsável Fictícia",
    )
    assert criada["codigo"].startswith("PN-")


def test_perfil_incompativel_com_a_idade(tecnico, nova_pessoa):
    with pytest.raises(ErroDeValidacao, match="não combina"):
        nova_pessoa(tecnico, faixa="30-44", perfis=("Criança",))


def test_gestante_em_faixa_incompativel(tecnico, nova_pessoa):
    with pytest.raises(ErroDeValidacao, match="gestante"):
        nova_pessoa(tecnico, faixa="6-11", gestante=True)


def test_codigo_da_pessoa_e_sequencial(tecnico, nova_pessoa):
    primeira = nova_pessoa(tecnico)
    segunda = nova_pessoa(tecnico)
    assert (primeira["codigo"], segunda["codigo"]) == ("PN-00001", "PN-00002")


def test_atividade_exige_programa_local_e_data(tecnico):
    comuns = dict(
        hora_inicio=time(14, 0),
        hora_fim=time(16, 0),
        local_id=dominios.opcoes("local")["Sede Páginas Novas"],
        tipo_atividade_id=dominios.opcoes("tipo_atividade")["Oficina"],
    )
    with pytest.raises(ErroDeValidacao, match="programa"):
        atividades.criar(tecnico, data=date(2026, 3, 1), programa_id=None, **comuns)

    with pytest.raises(ErroDeValidacao, match="local"):
        atividades.criar(
            tecnico,
            data=date(2026, 3, 1),
            programa_id=dominios.opcoes("programa")["Kidstinga"],
            hora_inicio=time(14, 0),
            hora_fim=time(16, 0),
            local_id=None,
            tipo_atividade_id=comuns["tipo_atividade_id"],
        )

    with pytest.raises(ErroDeValidacao, match="data"):
        atividades.criar(
            tecnico,
            data=None,
            programa_id=dominios.opcoes("programa")["Kidstinga"],
            **comuns,
        )


def test_atividade_duplicada_e_bloqueada(tecnico, nova_atividade):
    nova_atividade(tecnico)
    with pytest.raises(ErroDeValidacao, match="Já existe uma atividade"):
        nova_atividade(tecnico)


def test_mesmo_dia_em_outro_horario_e_permitido(tecnico, nova_atividade):
    nova_atividade(tecnico, hora_inicio=time(14, 0), hora_fim=time(16, 0))
    nova_atividade(tecnico, hora_inicio=time(16, 30), hora_fim=time(18, 0))


def test_hora_de_termino_depois_do_inicio(tecnico, nova_atividade):
    with pytest.raises(ErroDeValidacao, match="término"):
        nova_atividade(tecnico, hora_inicio=time(16, 0), hora_fim=time(14, 0))


def test_atividade_no_futuro_e_recusada(tecnico, nova_atividade):
    with pytest.raises(ErroDeValidacao, match="futuro"):
        nova_atividade(tecnico, dia=date.today() + timedelta(days=1))


def test_descricao_curta_limitada(tecnico, nova_atividade):
    with pytest.raises(ErroDeValidacao, match="200"):
        nova_atividade(tecnico, descricao_curta="x" * 201)


def test_pessoa_nao_repete_na_mesma_atividade(tecnico, nova_pessoa, nova_atividade):
    pessoa = nova_pessoa(tecnico)
    with pytest.raises(ErroDeValidacao):
        nova_atividade(tecnico, participantes=[pessoa["id"], pessoa["id"]])


def test_lista_desativada_continua_valendo_no_historico(admin, nova_atividade):
    """Item desativado sai dos formulários, mas o que já foi registrado continua de pé."""
    atividade = nova_atividade(admin)
    kidstinga = dominios.opcoes("programa")["Kidstinga"]
    dominios.desativar(admin, "programa", kidstinga)

    assert "Kidstinga" not in dominios.opcoes("programa")
    assert atividades.por_id(admin, atividade)["programa"] == "Kidstinga"
