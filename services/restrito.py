"""Dado identificado e encaminhamentos: o único caminho até as tabelas restritas.

As tabelas `pessoa_contato`, `encaminhamento` e `auditoria` só aparecem neste arquivo. Toda
função aqui começa verificando o papel e registra o acesso em `auditoria` antes de devolver
qualquer coisa — é o que substitui, nesta fase, a proteção que o RLS daria no banco.

Papel Campo nunca passa daqui: não lê nome, telefone, contato nem encaminhamento.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, insert, select, text, update

from services import cache, config, modelo
from services.db import conexao
from services.seguranca import (
    ErroDeValidacao,
    exige_admin,
    exige_identificado,
    registrar_auditoria,
)


def contato(sessao, pessoa_id: str) -> dict | None:
    """Nome, apelido, telefone e consentimento de uma pessoa. Gera registro de auditoria."""
    exige_identificado(sessao)
    with conexao() as con:
        linha = con.execute(
            text(
                "select p.codigo, c.* from pessoa_contato c"
                "  join pessoa p on p.id = c.pessoa_id"
                " where c.pessoa_id = :id"
            ),
            {"id": pessoa_id},
        ).mappings().first()
        registrar_auditoria(con, sessao, "leitura", "pessoa_contato", pessoa_id)
    return dict(linha) if linha else None


def salvar_contato(sessao, pessoa_id: str, **campos) -> None:
    exige_identificado(sessao)
    with conexao() as con:
        con.execute(
            update(modelo.pessoa_contato)
            .where(modelo.pessoa_contato.c.pessoa_id == pessoa_id)
            .values(**campos)
        )
        registrar_auditoria(con, sessao, "alteracao", "pessoa_contato", pessoa_id)


def revogar_consentimento(sessao, pessoa_id: str) -> None:
    """Apaga o que identifica a pessoa e guarda a data da revogação.

    O histórico estatístico (participações, atividades) continua inteiro: o que sai é a
    ligação entre o código e a pessoa real.
    """
    exige_identificado(sessao)
    with conexao() as con:
        con.execute(
            update(modelo.pessoa_contato)
            .where(modelo.pessoa_contato.c.pessoa_id == pessoa_id)
            .values(
                nome=None,
                apelido=None,
                telefone=None,
                nome_responsavel=None,
                consentimento_revogado_em=datetime.now(),
            )
        )
        registrar_auditoria(con, sessao, "revogacao_consentimento", "pessoa_contato", pessoa_id)
    cache.limpar()


def buscar_por_nome(sessao, termo: str) -> list[dict]:
    """Busca por nome ou apelido. Só Técnico e Admin, e a busca em si fica auditada."""
    exige_identificado(sessao)
    termo = (termo or "").strip()
    if len(termo) < 3:
        return []
    with conexao() as con:
        linhas = con.execute(
            text(
                "select p.id, p.codigo, c.nome, c.apelido, fe.rotulo as faixa_etaria"
                "  from pessoa_contato c"
                "  join pessoa p on p.id = c.pessoa_id"
                "  join faixa_etaria fe on fe.id = p.faixa_etaria_id"
                " where p.ativo = 1 and c.consentimento_revogado_em is null"
                "   and (lower(c.nome) like :termo or lower(c.apelido) like :termo)"
                " order by c.nome limit 20"
            ),
            {"termo": f"%{termo.lower()}%"},
        )
        resultado = [dict(linha) for linha in linhas.mappings()]
        registrar_auditoria(con, sessao, "leitura", "pessoa_contato", None)
    return resultado


SQL_ENCAMINHAMENTOS = """
select e.id, e.data, e.status, e.data_ultima_atualizacao, e.observacao,
       p.codigo as pessoa_codigo, p.id as pessoa_id, d.nome as destino
  from encaminhamento e
  join pessoa p on p.id = e.pessoa_id
  join destino_encaminhamento d on d.id = e.destino_id
 where e.ativo = 1
"""


def _consulta(complemento: str = ""):
    """Declara o tipo das datas, para a tela poder formatar sem quebrar."""
    return text(SQL_ENCAMINHAMENTOS + complemento).columns(
        data=Date, data_ultima_atualizacao=Date
    )


def listar_encaminhamentos(sessao, status: str | None = None) -> list[dict]:
    exige_identificado(sessao)
    filtro = " and e.status = :status" if status else ""
    with conexao() as con:
        linhas = con.execute(
            _consulta(filtro + " order by e.data_ultima_atualizacao"),
            {"status": status},
        )
        resultado = [dict(linha) for linha in linhas.mappings()]
        registrar_auditoria(con, sessao, "leitura", "encaminhamento", None)
    return resultado


def criar_encaminhamento(
    sessao, pessoa_id: str, destino_id: str, observacao: str | None = None
) -> str:
    exige_identificado(sessao)
    if not pessoa_id:
        raise ErroDeValidacao("Escolha a pessoa.")
    if not destino_id:
        raise ErroDeValidacao("Escolha o destino.")

    novo = modelo.novo_id()
    with conexao() as con:
        con.execute(
            insert(modelo.encaminhamento).values(
                id=novo,
                pessoa_id=pessoa_id,
                destino_id=destino_id,
                data=date.today(),
                data_ultima_atualizacao=date.today(),
                observacao=observacao or None,
                created_by=sessao.usuario_id,
            )
        )
        registrar_auditoria(con, sessao, "criacao", "encaminhamento", novo)
    cache.limpar()
    return novo


def atualizar_status(sessao, encaminhamento_id: str, status: str) -> None:
    """Atualização em um toque: muda o status e marca a data de hoje."""
    exige_identificado(sessao)
    if status not in modelo.STATUS_ENCAMINHAMENTO:
        raise ErroDeValidacao("Status inválido.")
    with conexao() as con:
        con.execute(
            update(modelo.encaminhamento)
            .where(modelo.encaminhamento.c.id == encaminhamento_id)
            .values(status=status, data_ultima_atualizacao=date.today())
        )
        registrar_auditoria(con, sessao, "alteracao", "encaminhamento", encaminhamento_id)
    cache.limpar()


def encaminhamentos_parados(sessao) -> list[dict]:
    """Encaminhamentos sem atualização há mais de 60 dias, para a tela de Pendências."""
    exige_identificado(sessao)
    with conexao() as con:
        linhas = con.execute(
            _consulta(
                " and e.status <> 'concluido'"
                "   and e.data_ultima_atualizacao < date('now', :dias)"
                " order by e.data_ultima_atualizacao"
            ),
            {"dias": f"-{config.DIAS_PARA_PENDENCIA} days"},
        )
        resultado = [dict(linha) for linha in linhas.mappings()]
        registrar_auditoria(con, sessao, "leitura", "encaminhamento", None)
    return resultado


def pessoas_sem_consentimento(sessao) -> list[dict]:
    """Pessoas ativas sem consentimento válido, para a tela de Pendências."""
    exige_identificado(sessao)
    with conexao() as con:
        linhas = con.execute(
            text(
                "select p.id, p.codigo, c.consentimento_revogado_em"
                "  from pessoa p left join pessoa_contato c on c.pessoa_id = p.id"
                " where p.ativo = 1"
                "   and (c.pessoa_id is null or c.consentimento_data is null"
                "        or c.consentimento_revogado_em is not null)"
                " order by p.codigo"
            )
        )
        resultado = [dict(linha) for linha in linhas.mappings()]
        registrar_auditoria(con, sessao, "leitura", "pessoa_contato", None)
    return resultado


# --- Agregados para o dashboard -----------------------------------------------------------
# Os agregados abaixo não geram auditoria: devolvem contagem por destino e status, sem nome,
# sem código e sem linha individual. Auditar a cada atualização automática de dashboard
# encheria a trilha de ruído e esconderia o que importa, que é a leitura de dado identificado.


def resumo_encaminhamentos(sessao, inicio: date, fim: date) -> dict:
    exige_identificado(sessao)
    with conexao() as con:
        linha = con.execute(
            text(
                "select count(*) as total,"
                "       sum(case when status = 'concluido' then 1 else 0 end) as concluidos,"
                "       sum(case when status <> 'concluido'"
                "                 and data_ultima_atualizacao < date('now', :dias)"
                "                then 1 else 0 end) as parados"
                "  from encaminhamento"
                " where ativo = 1 and data between :inicio and :fim"
            ),
            {"inicio": inicio, "fim": fim, "dias": f"-{config.DIAS_PARA_PENDENCIA} days"},
        ).mappings().first()
    total = linha["total"] or 0
    concluidos = linha["concluidos"] or 0
    return {
        "total": total,
        "concluidos": concluidos,
        "parados": linha["parados"] or 0,
        "taxa_conclusao": round(100 * concluidos / total, 1) if total else 0.0,
    }


def encaminhamentos_por_destino(sessao, inicio: date, fim: date) -> list[dict]:
    exige_identificado(sessao)
    with conexao() as con:
        linhas = con.execute(
            text(
                "select d.nome as destino, count(*) as encaminhamentos"
                "  from encaminhamento e"
                "  join destino_encaminhamento d on d.id = e.destino_id"
                " where e.ativo = 1 and e.data between :inicio and :fim"
                " group by d.nome order by encaminhamentos desc"
            ),
            {"inicio": inicio, "fim": fim},
        )
        return [dict(linha) for linha in linhas.mappings()]


def encaminhamentos_por_destino_e_status(sessao, inicio: date, fim: date) -> list[dict]:
    exige_identificado(sessao)
    with conexao() as con:
        linhas = con.execute(
            text(
                "select d.nome as destino, e.status, count(*) as encaminhamentos"
                "  from encaminhamento e"
                "  join destino_encaminhamento d on d.id = e.destino_id"
                " where e.ativo = 1 and e.data between :inicio and :fim"
                " group by d.nome, e.status order by d.nome"
            ),
            {"inicio": inicio, "fim": fim},
        )
        return [dict(linha) for linha in linhas.mappings()]


def listar_auditoria(sessao, limite: int = 200) -> list[dict]:
    """Quem leu ou alterou dado identificado. Só o Admin."""
    exige_admin(sessao)
    with conexao() as con:
        linhas = con.execute(
            text(
                "select a.created_at, a.acao, a.tabela, a.registro_id,"
                "       u.nome_exibicao as usuario, u.papel"
                "  from auditoria a left join usuario u on u.id = a.usuario_id"
                " order by a.created_at desc limit :limite"
            ).columns(created_at=DateTime),
            {"limite": limite},
        )
        return [dict(linha) for linha in linhas.mappings()]
