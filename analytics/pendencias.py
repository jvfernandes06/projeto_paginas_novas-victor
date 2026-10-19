"""O que está incompleto no sistema e precisa de alguém.

A ideia é não deixar a qualidade do dado para depois: em vez de alguém limpar planilha no fim
do ano, o sistema aponta hoje o que ficou pela metade.
"""

from sqlalchemy import Date, DateTime, text

from services.db import conexao
from services.seguranca import exige_identificado

SQL_ATIVIDADE_SEM_PESSOAS = """
-- Atividade registrada sem nenhum participante e sem contagem anônima: não dá para saber
-- quantas pessoas foram atendidas.
select a.id, a.data, pr.nome as programa, lo.nome as local
  from atividade a
  join programa pr on pr.id = a.programa_id
  join local lo on lo.id = a.local_id
 where a.ativo = 1
   and not exists (select 1 from participacao pa
                    where pa.atividade_id = a.id and pa.ativo = 1)
   and not exists (select 1 from contagem_anonima ca where ca.atividade_id = a.id)
 order by a.data desc
"""

SQL_ATIVIDADE_SEM_EQUIPE = """
-- Atividade sem equipe informada: as horas de voluntariado deixam de ser contadas.
select a.id, a.data, pr.nome as programa, lo.nome as local
  from atividade a
  join programa pr on pr.id = a.programa_id
  join local lo on lo.id = a.local_id
 where a.ativo = 1
   and not exists (select 1 from atividade_equipe ae
                    where ae.atividade_id = a.id and ae.ativo = 1)
 order by a.data desc
"""

SQL_GESTANTE_ANTIGA = """
-- Pessoa marcada como gestante há mais de 10 meses: a marcação é um sim/não, sem data de
-- parto, então alguém precisa confirmar se ainda vale.
select p.id, p.codigo, p.updated_at
  from pessoa p
 where p.ativo = 1 and p.gestante = 1
   and p.updated_at < datetime('now', '-10 months')
 order by p.updated_at
"""


def _lista(sql: str, **tipos) -> list[dict]:
    """Executa declarando o tipo das colunas de data, para a tela poder formatar."""
    with conexao() as con:
        return [dict(linha) for linha in con.execute(text(sql).columns(**tipos)).mappings()]


def atividades_sem_pessoas(sessao) -> list[dict]:
    exige_identificado(sessao)
    return _lista(SQL_ATIVIDADE_SEM_PESSOAS, data=Date)


def atividades_sem_equipe(sessao) -> list[dict]:
    exige_identificado(sessao)
    return _lista(SQL_ATIVIDADE_SEM_EQUIPE, data=Date)


def gestantes_para_revisar(sessao) -> list[dict]:
    exige_identificado(sessao)
    return _lista(SQL_GESTANTE_ANTIGA, updated_at=DateTime)
