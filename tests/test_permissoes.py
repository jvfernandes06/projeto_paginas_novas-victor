"""O papel Campo não alcança dado identificado, encaminhamento nem auditoria.

Sem RLS no banco, é a camada services/ que protege. Estes testes chamam cada função na cara,
com sessão de Campo, e exigem recusa. Se alguém apagar um `exige_*`, um teste aqui quebra.
"""

from datetime import date

import pytest

from services import pessoas, restrito, usuarios
from services.seguranca import PermissaoNegada


def funcoes_restritas(pessoa_id: str) -> dict:
    """Tudo que toca tabela restrita, com argumentos válidos."""
    hoje = date.today()
    return {
        "contato": lambda s: restrito.contato(s, pessoa_id),
        "salvar_contato": lambda s: restrito.salvar_contato(s, pessoa_id, telefone="19 90000-0000"),
        "revogar_consentimento": lambda s: restrito.revogar_consentimento(s, pessoa_id),
        "buscar_por_nome": lambda s: restrito.buscar_por_nome(s, "fulana"),
        "listar_encaminhamentos": lambda s: restrito.listar_encaminhamentos(s),
        "criar_encaminhamento": lambda s: restrito.criar_encaminhamento(s, pessoa_id, "x"),
        "atualizar_status": lambda s: restrito.atualizar_status(s, "x", "concluido"),
        "encaminhamentos_parados": lambda s: restrito.encaminhamentos_parados(s),
        "pessoas_sem_consentimento": lambda s: restrito.pessoas_sem_consentimento(s),
        "resumo_encaminhamentos": lambda s: restrito.resumo_encaminhamentos(s, hoje, hoje),
        "encaminhamentos_por_destino": lambda s: restrito.encaminhamentos_por_destino(s, hoje, hoje),
        "encaminhamentos_por_destino_e_status": (
            lambda s: restrito.encaminhamentos_por_destino_e_status(s, hoje, hoje)
        ),
        "listar_auditoria": lambda s: restrito.listar_auditoria(s),
    }


@pytest.mark.parametrize("nome", list(funcoes_restritas("x")))
def test_campo_nao_acessa_nada_restrito(nome, campo, tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    funcao = funcoes_restritas(pessoa["id"])[nome]
    with pytest.raises(PermissaoNegada):
        funcao(campo)


@pytest.mark.parametrize("nome", list(funcoes_restritas("x")))
def test_parceiro_nao_acessa_nada_restrito(nome, parceiro, tecnico, nova_pessoa):
    pessoa = nova_pessoa(tecnico)
    funcao = funcoes_restritas(pessoa["id"])[nome]
    with pytest.raises(PermissaoNegada):
        funcao(parceiro)


def test_auditoria_e_so_do_admin(tecnico):
    """Técnico vê dado identificado, mas não vê quem andou olhando."""
    with pytest.raises(PermissaoNegada):
        restrito.listar_auditoria(tecnico)


def test_campo_nao_envia_dado_de_contato(campo):
    """Campo cadastra pessoa, mas o nome não passa por ele."""
    from services import dominios

    faixa = next(f["id"] for f in dominios.listar("faixa_etaria") if f["codigo"] == "30-44")
    with pytest.raises(PermissaoNegada):
        pessoas.criar(
            campo,
            faixa_etaria_id=faixa,
            genero_id=dominios.opcoes("genero")["Mulher cisgênero"],
            bairro_id=None,
            perfis=[],
            consentimento_data=date(2026, 1, 1),
            consentimento_por="propria_pessoa",
            nome="Nome Que Não Deveria Passar",
        )


def test_campo_cadastra_pessoa_sem_contato(campo):
    """O que Campo pode: cadastrar a pessoa e registrar o consentimento."""
    from services import dominios

    faixa = next(f["id"] for f in dominios.listar("faixa_etaria") if f["codigo"] == "30-44")
    criada = pessoas.criar(
        campo,
        faixa_etaria_id=faixa,
        genero_id=dominios.opcoes("genero")["Mulher cisgênero"],
        bairro_id=None,
        perfis=[],
        consentimento_data=date(2026, 1, 1),
        consentimento_por="propria_pessoa",
    )
    assert criada["codigo"] == "PN-00001"


def test_so_admin_administra_usuarios(tecnico, campo):
    for sessao in (tecnico, campo):
        with pytest.raises(PermissaoNegada):
            usuarios.listar(sessao)
        with pytest.raises(PermissaoNegada):
            usuarios.criar(sessao, "novo@teste", "Novo", "campo")


def test_so_admin_edita_as_listas(tecnico, campo):
    from services import dominios

    for sessao in (tecnico, campo):
        with pytest.raises(PermissaoNegada):
            dominios.criar(sessao, "programa", nome="Programa Inventado")
