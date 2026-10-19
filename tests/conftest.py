"""Base dos testes.

Cada teste roda num banco novo, em arquivo temporário, criado pelas migrations de verdade —
e não por um schema paralelo escrito à mão, que poderia divergir do que vai para produção.
"""

import sys
from datetime import date, time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from services import atividades, cache, dominios, modelo, pessoas, usuarios  # noqa: E402
from services.db import conexao  # noqa: E402
from services.seguranca import Sessao  # noqa: E402


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("PN_BANCO", str(tmp_path / "teste.db"))
    configuracao = Config(str(RAIZ / "alembic.ini"))
    configuracao.set_main_option("script_location", str(RAIZ / "migrations"))
    command.upgrade(configuracao, "head")
    cache.limpar()  # o cache de indicadores é global: cada teste começa limpo
    yield
    cache.limpar()


def _sessao(papel: str) -> Sessao:
    senha = usuarios._criar(f"{papel}@teste", f"{papel.title()} de Teste", papel)
    with conexao() as con:
        from sqlalchemy import select

        usuario_id = con.execute(
            select(modelo.usuario.c.id).where(modelo.usuario.c.email == f"{papel}@teste")
        ).scalar()
    assert senha
    return Sessao(usuario_id, f"{papel}@teste", f"{papel.title()} de Teste", papel)


@pytest.fixture
def admin(banco) -> Sessao:
    return _sessao("admin")


@pytest.fixture
def tecnico(banco) -> Sessao:
    return _sessao("tecnico")


@pytest.fixture
def campo(banco) -> Sessao:
    return _sessao("campo")


@pytest.fixture
def parceiro(banco) -> Sessao:
    return _sessao("parceiro")


@pytest.fixture
def nova_pessoa(banco):
    """Cria uma pessoa com consentimento válido. Devolve o dicionário com id e código."""

    def criar(sessao, faixa="30-44", genero="Mulher cisgênero", gestante=False, perfis=()):
        escolhida = next(f for f in dominios.listar("faixa_etaria") if f["codigo"] == faixa)
        nomes = {p["nome"]: p["id"] for p in dominios.listar("perfil")}
        menor = escolhida["menor_de_idade"]
        ve_contato = sessao.papel != "campo"
        return pessoas.criar(
            sessao,
            faixa_etaria_id=escolhida["id"],
            genero_id=dominios.opcoes("genero")[genero],
            bairro_id=None,
            perfis=[nomes[n] for n in perfis],
            consentimento_data=date(2026, 1, 10),
            consentimento_por="responsavel_legal" if menor else "propria_pessoa",
            gestante=gestante,
            nome="Fulana Fictícia" if ve_contato else None,
            nome_responsavel="Responsável Fictícia" if menor else None,
        )

    return criar


@pytest.fixture
def nova_atividade(banco):
    """Cria uma atividade. Por padrão, Kidstinga na sede, duas horas."""

    def criar(
        sessao,
        dia=date(2026, 3, 10),
        programa="Kidstinga",
        local="Sede Páginas Novas",
        tipo="Oficina",
        hora_inicio=time(14, 0),
        hora_fim=time(16, 0),
        **extras,
    ):
        return atividades.criar(
            sessao,
            data=dia,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            programa_id=dominios.opcoes("programa")[programa],
            local_id=dominios.opcoes("local")[local],
            tipo_atividade_id=dominios.opcoes("tipo_atividade")[tipo],
            **extras,
        )

    return criar


@pytest.fixture
def _rascunho_na_etapa_5(banco):
    """Rascunho de atividade pronto até a etapa 5, para o teste do fluxo não repetir cliques."""
    return {
        "etapa": 5,
        "participantes": [],
        "itens": {},
        "equipe": {dominios.opcoes("funcao_equipe")["Voluntário"]: 2},
        "programa": "Kidstinga",
        "programa_id": dominios.opcoes("programa")["Kidstinga"],
        "local": "Sede Páginas Novas",
        "local_id": dominios.opcoes("local")["Sede Páginas Novas"],
        "tipo": "Oficina",
        "tipo_atividade_id": dominios.opcoes("tipo_atividade")["Oficina"],
        "data": date(2026, 3, 10),
        "hora_inicio": time(14, 0),
        "hora_fim": time(16, 0),
        "descricao_curta": None,
        "modo": "codigo",
    }
