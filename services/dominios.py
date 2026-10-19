"""As listas que o Admin mantém: programas, locais, perfis, tipos de item e companhia.

É a única fonte dos campos analíticos. Nenhuma tela pede para o usuário digitar programa ou
local: ele escolhe de uma destas listas.

Estas listas têm cache porque mudam raramente e não contêm dado pessoal nenhum.
"""

import streamlit as st
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from services import cache, modelo
from services.db import conexao
from services.seguranca import ErroDeValidacao, exige_admin, exige_equipe

# Tabelas que a página Admin pode editar. A lista é fechada de propósito: evita que um
# parâmetro vindo da tela aponte para qualquer tabela do banco.
TABELAS = {
    "programa": modelo.programa,
    "local": modelo.local,
    "tipo_atividade": modelo.tipo_atividade,
    "destino_encaminhamento": modelo.destino_encaminhamento,
    "bairro": modelo.bairro,
    "genero": modelo.genero,
    "tipo_item": modelo.tipo_item,
    "perfil": modelo.perfil,
    "funcao_equipe": modelo.funcao_equipe,
    "faixa_etaria": modelo.faixa_etaria,
}

ROTULOS = {
    "programa": "Programas",
    "local": "Locais",
    "tipo_atividade": "Tipos de atividade",
    "destino_encaminhamento": "Destinos de encaminhamento",
    "bairro": "Bairros",
    "genero": "Gêneros",
    "tipo_item": "Tipos de item",
    "perfil": "Perfis",
    "funcao_equipe": "Funções da equipe",
    "faixa_etaria": "Faixas etárias",
}


def _tabela(nome: str):
    if nome not in TABELAS:
        raise ErroDeValidacao(f"Lista desconhecida: {nome}")
    return TABELAS[nome]


@st.cache_data(ttl=300, show_spinner=False)
def listar(nome: str, apenas_ativos: bool = True) -> list[dict]:
    """Devolve as linhas de uma lista de domínio, em ordem de exibição."""
    tabela = _tabela(nome)
    consulta = select(tabela)
    if apenas_ativos:
        consulta = consulta.where(tabela.c.ativo)
    ordem = tabela.c.ordem if "ordem" in tabela.c else tabela.c.nome
    with conexao() as con:
        return [dict(linha) for linha in con.execute(consulta.order_by(ordem)).mappings()]


def opcoes(nome: str) -> dict[str, str]:
    """Mapa {nome exibido: id}, pronto para alimentar um selectbox."""
    return {linha["nome"]: linha["id"] for linha in listar(nome)}


def rotulos_de_faixa() -> dict[str, str]:
    return {linha["rotulo"]: linha["id"] for linha in listar("faixa_etaria")}


def por_id(nome: str, registro_id: str) -> dict | None:
    for linha in listar(nome, apenas_ativos=False):
        if linha["id"] == registro_id:
            return linha
    return None


def criar(sessao, nome_tabela: str, **campos) -> str:
    exige_admin(sessao)
    tabela = _tabela(nome_tabela)
    if not campos.get("nome", "").strip():
        raise ErroDeValidacao("Escreva o nome.")
    novo = modelo.novo_id()
    try:
        with conexao() as con:
            con.execute(insert(tabela).values(id=novo, created_by=sessao.usuario_id, **campos))
    except IntegrityError as erro:
        raise ErroDeValidacao("Já existe um item com esse nome nesta lista.") from erro
    cache.limpar()
    return novo


def atualizar(sessao, nome_tabela: str, registro_id: str, **campos) -> None:
    exige_admin(sessao)
    tabela = _tabela(nome_tabela)
    with conexao() as con:
        con.execute(update(tabela).where(tabela.c.id == registro_id).values(**campos))
    cache.limpar()


def desativar(sessao, nome_tabela: str, registro_id: str) -> None:
    """Exclusão é sempre lógica: o histórico que usa este item continua valendo."""
    atualizar(sessao, nome_tabela, registro_id, ativo=False)


def reativar(sessao, nome_tabela: str, registro_id: str) -> None:
    atualizar(sessao, nome_tabela, registro_id, ativo=True)


def faixa_de_pessoa(sessao, pessoa_id: str) -> dict | None:
    """Faixa etária de uma pessoa, usada nas validações de perfil e de gestante."""
    exige_equipe(sessao)
    with conexao() as con:
        linha = con.execute(
            select(modelo.faixa_etaria)
            .join(modelo.pessoa, modelo.pessoa.c.faixa_etaria_id == modelo.faixa_etaria.c.id)
            .where(modelo.pessoa.c.id == pessoa_id)
        ).mappings().first()
    return dict(linha) if linha else None
