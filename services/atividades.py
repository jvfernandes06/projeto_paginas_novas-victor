"""Registro de atividade: o que a equipe fez, onde, com quem e com que equipe.

Tudo de uma atividade é gravado numa única transação, ao fim do fluxo de 6 etapas: se algo
falhar, nada fica pela metade.
"""

from datetime import date, time

from sqlalchemy import Date, Time, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from services import cache, modelo
from services.db import conexao
from services.seguranca import (
    ErroDeValidacao,
    exige_equipe,
    exige_identificado,
    registrar_auditoria,
)

def duracao_em_minutos(hora_inicio: time, hora_fim: time) -> int:
    inicio = hora_inicio.hour * 60 + hora_inicio.minute
    fim = hora_fim.hour * 60 + hora_fim.minute
    return fim - inicio


def _validar(dados: dict) -> None:
    if not dados.get("programa_id"):
        raise ErroDeValidacao("Escolha o programa.")
    if not dados.get("local_id"):
        raise ErroDeValidacao("Escolha o local.")
    if not dados.get("tipo_atividade_id"):
        raise ErroDeValidacao("Escolha o tipo de atividade.")
    if not dados.get("data"):
        raise ErroDeValidacao("Informe a data.")
    if dados["data"] > date.today():
        raise ErroDeValidacao("A data não pode ser no futuro.")
    if duracao_em_minutos(dados["hora_inicio"], dados["hora_fim"]) <= 0:
        raise ErroDeValidacao("O horário de término precisa ser depois do horário de início.")
    if len(dados.get("descricao_curta") or "") > 200:
        raise ErroDeValidacao("A descrição precisa ter no máximo 200 caracteres.")


def criar(
    sessao,
    data: date,
    hora_inicio: time,
    hora_fim: time,
    programa_id: str,
    local_id: str,
    tipo_atividade_id: str,
    equipe: dict[str, int] | None = None,
    participantes: list[str] | None = None,
    contagem: dict[str, int] | None = None,
    itens: dict[str, int] | None = None,
    descricao_curta: str | None = None,
    observacao: str | None = None,
) -> str:
    """Grava a atividade e tudo que vem com ela. Devolve o id da atividade."""
    exige_equipe(sessao)

    dados = {
        "data": data,
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "programa_id": programa_id,
        "local_id": local_id,
        "tipo_atividade_id": tipo_atividade_id,
        "descricao_curta": descricao_curta,
    }
    _validar(dados)

    atividade_id = modelo.novo_id()
    try:
        with conexao() as con:
            con.execute(
                insert(modelo.atividade).values(
                    id=atividade_id,
                    duracao_minutos=duracao_em_minutos(hora_inicio, hora_fim),
                    observacao=observacao or None,
                    created_by=sessao.usuario_id,
                    **dados,
                )
            )
            for funcao_id, quantidade in (equipe or {}).items():
                if quantidade:
                    con.execute(
                        insert(modelo.atividade_equipe).values(
                            id=modelo.novo_id(),
                            atividade_id=atividade_id,
                            funcao_equipe_id=funcao_id,
                            quantidade=int(quantidade),
                            created_by=sessao.usuario_id,
                        )
                    )
            for pessoa_id in participantes or []:
                con.execute(
                    insert(modelo.participacao).values(
                        id=modelo.novo_id(),
                        atividade_id=atividade_id,
                        pessoa_id=pessoa_id,
                        created_by=sessao.usuario_id,
                    )
                )
            if contagem and sum(contagem.values()) > 0:
                con.execute(
                    insert(modelo.contagem_anonima).values(
                        atividade_id=atividade_id,
                        created_by=sessao.usuario_id,
                        **contagem,
                    )
                )
            for item_id, quantidade in (itens or {}).items():
                if quantidade:
                    con.execute(
                        insert(modelo.item_distribuido).values(
                            id=modelo.novo_id(),
                            atividade_id=atividade_id,
                            tipo_item_id=item_id,
                            quantidade=int(quantidade),
                            created_by=sessao.usuario_id,
                        )
                    )
    except IntegrityError as erro:
        # A mensagem do SQLite cita as colunas; a do Postgres cita o nome do índice.
        aviso = str(erro.orig).lower()
        if "unique" in aviso and "atividade" in aviso and "pessoa" not in aviso:
            raise ErroDeValidacao(
                "Já existe uma atividade desse programa, nesse local, nessa data e nesse "
                "horário. Confira se alguém já registrou."
            ) from erro
        raise ErroDeValidacao("Não foi possível salvar. Confira os dados e tente de novo.") from erro

    cache.limpar()
    return atividade_id


SQL_LISTA = """
select a.id, a.data, a.hora_inicio, a.hora_fim, a.duracao_minutos,
       pr.nome as programa, lo.nome as local, ta.nome as tipo_atividade,
       a.descricao_curta, a.created_by,
       (select count(*) from participacao pa where pa.atividade_id = a.id and pa.ativo = 1)
         as participantes,
       (select coalesce(sum(ca.abordagens + ca.criancas + ca.adolescentes + ca.adultos), 0)
          from contagem_anonima ca where ca.atividade_id = a.id) as contagem_anonima,
       (select coalesce(sum(ae.quantidade), 0) from atividade_equipe ae
         where ae.atividade_id = a.id and ae.ativo = 1) as equipe
  from atividade a
  join programa pr on pr.id = a.programa_id
  join local lo on lo.id = a.local_id
  join tipo_atividade ta on ta.id = a.tipo_atividade_id
 where a.ativo = 1
"""


def _consulta(complemento: str = ""):
    """Diz ao SQLAlchemy que data e hora são data e hora.

    Em consulta escrita à mão o banco devolveria texto, e a tela quebraria ao formatar
    a data. Declarar o tipo aqui resolve para todas as telas de uma vez.
    """
    return text(SQL_LISTA + complemento).columns(data=Date, hora_inicio=Time, hora_fim=Time)


def minhas_ultimas(sessao, limite: int = 5) -> list[dict]:
    """As últimas atividades registradas por quem está logado, para a tela de Início."""
    exige_equipe(sessao)
    with conexao() as con:
        linhas = con.execute(
            _consulta(" and a.created_by = :autor order by a.data desc, a.hora_inicio desc limit :limite"),
            {"autor": sessao.usuario_id, "limite": limite},
        )
        return [dict(linha) for linha in linhas.mappings()]


def listar(sessao, programa_id: str | None = None, limite: int = 100) -> list[dict]:
    exige_equipe(sessao)
    filtro = " and a.programa_id = :programa" if programa_id else ""
    with conexao() as con:
        linhas = con.execute(
            _consulta(filtro + " order by a.data desc, a.hora_inicio desc limit :limite"),
            {"programa": programa_id, "limite": limite},
        )
        return [dict(linha) for linha in linhas.mappings()]


def por_id(sessao, atividade_id: str) -> dict | None:
    exige_equipe(sessao)
    with conexao() as con:
        linha = con.execute(
            _consulta(" and a.id = :id"), {"id": atividade_id}
        ).mappings().first()
    return dict(linha) if linha else None


def participantes_de(sessao, atividade_id: str) -> list[dict]:
    exige_equipe(sessao)
    with conexao() as con:
        linhas = con.execute(
            text(
                "select p.id, p.codigo, fe.rotulo as faixa_etaria"
                "  from participacao pa"
                "  join pessoa p on p.id = pa.pessoa_id"
                "  join faixa_etaria fe on fe.id = p.faixa_etaria_id"
                " where pa.atividade_id = :id and pa.ativo = 1"
                " order by p.codigo"
            ),
            {"id": atividade_id},
        )
        return [dict(linha) for linha in linhas.mappings()]


def atualizar(sessao, atividade_id: str, **campos) -> None:
    """Campo corrige o que ele mesmo registrou; Técnico e Admin corrigem qualquer uma."""
    exige_equipe(sessao)
    with conexao() as con:
        atual = con.execute(
            select(modelo.atividade).where(modelo.atividade.c.id == atividade_id)
        ).mappings().first()
        if atual is None:
            raise ErroDeValidacao("Atividade não encontrada.")
        if sessao.papel == "campo" and atual["created_by"] != sessao.usuario_id:
            raise ErroDeValidacao("Esta atividade foi registrada por outra pessoa da equipe.")

        dados = {**dict(atual), **campos}
        _validar(dados)
        campos["duracao_minutos"] = duracao_em_minutos(dados["hora_inicio"], dados["hora_fim"])
        con.execute(
            update(modelo.atividade).where(modelo.atividade.c.id == atividade_id).values(**campos)
        )
        registrar_auditoria(con, sessao, "alteracao", "atividade", atividade_id)
    cache.limpar()


def desativar(sessao, atividade_id: str) -> None:
    """Exclusão lógica. O registro sai dos indicadores, mas continua no banco."""
    exige_identificado(sessao)
    with conexao() as con:
        con.execute(
            update(modelo.atividade).where(modelo.atividade.c.id == atividade_id).values(ativo=False)
        )
        registrar_auditoria(con, sessao, "desativacao", "atividade", atividade_id)
    cache.limpar()
