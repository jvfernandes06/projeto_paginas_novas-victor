"""Os indicadores oficiais da Páginas Novas.

Cada indicador é uma função com período (`inicio`, `fim`) e programa opcional. **Toda** página
de dashboard lê daqui; nenhuma página consulta tabela. Assim, a definição de cada número existe
num lugar só, e muda num lugar só.

Por que função com período, e não view: pessoa única e taxa de recorrência não são somáveis.
Pessoas únicas de janeiro mais pessoas únicas de fevereiro não dá pessoas únicas do bimestre,
porque quem foi nos dois meses seria contado duas vezes. Com o período como argumento, o cálculo
certo é feito pelo banco e a tela só desenha.

Cache: cada consulta fica guardada pelo tempo do intervalo de atualização (60 segundos por
padrão) e a chave inclui o papel de quem pergunta. Toda gravação feita pelo app limpa o cache
(services/cache.py), então quem registrou algo vê o número novo na hora.

As funções `ext_*` são a visão do parceiro: contagem menor que 5 nunca sai, vira "<5".
"""

from datetime import date

import pandas as pd
import streamlit as st

from services import config, db, restrito
from services.seguranca import exige_autenticado, exige_identificado

MINIMO_PARA_MOSTRAR = 5

try:  # o intervalo é configurável em .streamlit/secrets.toml
    INTERVALO = int(st.secrets.get("intervalo_atualizacao_seg", config.INTERVALO_ATUALIZACAO))
except Exception:  # sem arquivo de secrets, usa a variável de ambiente
    INTERVALO = config.INTERVALO_ATUALIZACAO

# Com coalesce, o mesmo texto de SQL serve para "todos os programas" e para um só.
FILTRO = """
   and a.ativo = 1
   and a.data between :inicio and :fim
   and a.programa_id = coalesce(:programa, a.programa_id)
"""


@st.cache_data(ttl=INTERVALO, show_spinner=False)
def _consultar(sql: str, papel: str, parametros: dict) -> pd.DataFrame:
    """Executa e guarda em cache. `papel` entra na chave para não misturar visões."""
    return db.tabela(sql, **parametros)


def _parametros(inicio: date, fim: date, programa_id: str | None) -> dict:
    return {"inicio": str(inicio), "fim": str(fim), "programa": programa_id}


def _tabela(sessao, sql: str, inicio, fim, programa_id=None) -> pd.DataFrame:
    exige_identificado(sessao)
    return _consultar(sql, sessao.papel, _parametros(inicio, fim, programa_id))


def _por_semana(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Agrupa uma série diária por semana. Feito em pandas para não depender do banco."""
    if df.empty:
        return pd.DataFrame({"semana": [], coluna: []})
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"])
    semanal = df.set_index("data").resample("W-SUN")[coluna].sum().reset_index()
    return semanal.rename(columns={"data": "semana"})


# --- Cartões da visão geral ---------------------------------------------------------------

SQL_CARTOES = f"""
-- INDICADOR OFICIAL — Cartões da visão geral, todos restritos ao período e ao programa:
--   pessoas_unicas: pessoas distintas com ao menos uma participação;
--   participacoes: total de presenças registradas (a mesma pessoa conta uma vez por atividade);
--   atividades: atividades realizadas;
--   contatos_anonimos: soma das abordagens registradas sem identificar ninguém;
--   itens: soma das quantidades distribuídas;
--   horas_voluntariado: soma de (voluntários na atividade x duração da atividade);
--   gestantes: pessoas marcadas como gestante com ao menos uma participação;
--   registros: quantas linhas do banco entraram nesta conta.
select
  (select count(distinct pa.pessoa_id)
     from participacao pa join atividade a on a.id = pa.atividade_id
    where pa.ativo = 1 {FILTRO}) as pessoas_unicas,
  (select count(*)
     from participacao pa join atividade a on a.id = pa.atividade_id
    where pa.ativo = 1 {FILTRO}) as participacoes,
  (select count(*) from atividade a where 1 = 1 {FILTRO}) as atividades,
  (select coalesce(sum(ca.abordagens), 0)
     from contagem_anonima ca join atividade a on a.id = ca.atividade_id
    where 1 = 1 {FILTRO}) as contatos_anonimos,
  (select coalesce(sum(it.quantidade), 0)
     from item_distribuido it join atividade a on a.id = it.atividade_id
    where it.ativo = 1 {FILTRO}) as itens,
  (select coalesce(round(sum(ae.quantidade * a.duracao_minutos) / 60.0, 1), 0)
     from atividade_equipe ae
     join atividade a on a.id = ae.atividade_id
     join funcao_equipe f on f.id = ae.funcao_equipe_id
    where ae.ativo = 1 and f.conta_voluntariado = 1 {FILTRO}) as horas_voluntariado,
  (select count(distinct p.id)
     from participacao pa
     join atividade a on a.id = pa.atividade_id
     join pessoa p on p.id = pa.pessoa_id
    where pa.ativo = 1 and p.gestante = 1 {FILTRO}) as gestantes,
  (select count(*) from atividade a where 1 = 1 {FILTRO})
  + (select count(*) from participacao pa join atividade a on a.id = pa.atividade_id
      where pa.ativo = 1 {FILTRO})
  + (select count(*) from contagem_anonima ca join atividade a on a.id = ca.atividade_id
      where 1 = 1 {FILTRO})
  + (select count(*) from item_distribuido it join atividade a on a.id = it.atividade_id
      where it.ativo = 1 {FILTRO}) as registros
"""


def cartoes(sessao, inicio: date, fim: date, programa_id: str | None = None) -> dict:
    df = _tabela(sessao, SQL_CARTOES, inicio, fim, programa_id)
    return df.iloc[0].to_dict()


# --- Visão geral --------------------------------------------------------------------------

SQL_PARTICIPACOES_POR_DIA = f"""
-- INDICADOR OFICIAL — Participações por dia: presenças registradas por data de atividade.
-- A tela agrupa por semana.
select a.data, count(*) as participacoes
  from participacao pa join atividade a on a.id = pa.atividade_id
 where pa.ativo = 1 {FILTRO}
 group by a.data order by a.data
"""


def participacoes_por_semana(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    diario = _tabela(sessao, SQL_PARTICIPACOES_POR_DIA, inicio, fim, programa_id)
    return _por_semana(diario, "participacoes")


SQL_PESSOAS_POR_PROGRAMA = f"""
-- INDICADOR OFICIAL — Pessoas únicas por programa: pessoas distintas com ao menos uma
-- participação no período, contadas uma vez em cada programa de que participaram.
select pr.nome as programa, count(distinct pa.pessoa_id) as pessoas
  from participacao pa
  join atividade a on a.id = pa.atividade_id
  join programa pr on pr.id = a.programa_id
 where pa.ativo = 1 {FILTRO}
 group by pr.nome order by pessoas desc
"""


def pessoas_por_programa(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_PESSOAS_POR_PROGRAMA, inicio, fim, programa_id)


# --- Programas ----------------------------------------------------------------------------

SQL_ATIVIDADES_POR_PROGRAMA = f"""
-- INDICADOR OFICIAL — Atividades e horas por programa: número de atividades realizadas no
-- período e soma das durações (hora de término menos hora de início).
select pr.nome as programa,
       count(*) as atividades,
       round(sum(a.duracao_minutos) / 60.0, 1) as horas
  from atividade a join programa pr on pr.id = a.programa_id
 where 1 = 1 {FILTRO}
 group by pr.nome order by atividades desc
"""


def atividades_por_programa(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_ATIVIDADES_POR_PROGRAMA, inicio, fim, programa_id)


SQL_RECORRENCIA = f"""
-- INDICADOR OFICIAL — Taxa de recorrência: entre as pessoas atendidas no período, o percentual
-- das que participaram 3 vezes ou mais, por programa.
with presencas as (
  select pr.nome as programa, pa.pessoa_id, count(*) as vezes
    from participacao pa
    join atividade a on a.id = pa.atividade_id
    join programa pr on pr.id = a.programa_id
   where pa.ativo = 1 {FILTRO}
   group by pr.nome, pa.pessoa_id
)
select programa,
       count(*) as pessoas,
       sum(case when vezes >= 3 then 1 else 0 end) as pessoas_3mais,
       round(100.0 * sum(case when vezes >= 3 then 1 else 0 end) / count(*), 1) as taxa_pct
  from presencas group by programa order by taxa_pct desc
"""


def taxa_recorrencia(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_RECORRENCIA, inicio, fim, programa_id)


def resumo_por_programa(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    """Tabela do dashboard de programas: junta atividades, pessoas e recorrência."""
    atividades = atividades_por_programa(sessao, inicio, fim, programa_id)
    pessoas = pessoas_por_programa(sessao, inicio, fim, programa_id)
    recorrencia = taxa_recorrencia(sessao, inicio, fim, programa_id)
    if atividades.empty:
        return pd.DataFrame()
    resumo = atividades.merge(pessoas, on="programa", how="left")
    if not recorrencia.empty:
        resumo = resumo.merge(
            recorrencia[["programa", "pessoas_3mais", "taxa_pct"]], on="programa", how="left"
        )
    return resumo.fillna(0)


# --- Público atendido ---------------------------------------------------------------------

SQL_POR_FAIXA = f"""
-- INDICADOR OFICIAL — Pessoas únicas por faixa etária, entre as atendidas no período.
select fe.rotulo as faixa_etaria, fe.ordem, count(distinct p.id) as pessoas
  from participacao pa
  join atividade a on a.id = pa.atividade_id
  join pessoa p on p.id = pa.pessoa_id
  join faixa_etaria fe on fe.id = p.faixa_etaria_id
 where pa.ativo = 1 {FILTRO}
 group by fe.rotulo, fe.ordem order by fe.ordem
"""

SQL_POR_GENERO = f"""
-- INDICADOR OFICIAL — Pessoas únicas por gênero, entre as atendidas no período.
select g.nome as genero, count(distinct p.id) as pessoas
  from participacao pa
  join atividade a on a.id = pa.atividade_id
  join pessoa p on p.id = pa.pessoa_id
  join genero g on g.id = p.genero_id
 where pa.ativo = 1 {FILTRO}
 group by g.nome order by pessoas desc
"""

SQL_POR_PERFIL = f"""
-- INDICADOR OFICIAL — Pessoas únicas por perfil, entre as atendidas no período. Uma pessoa com
-- mais de um perfil aparece em cada um deles, então a soma das barras passa do total atendido.
select pf.nome as perfil, count(distinct p.id) as pessoas
  from participacao pa
  join atividade a on a.id = pa.atividade_id
  join pessoa p on p.id = pa.pessoa_id
  join pessoa_perfil pp on pp.pessoa_id = p.id and pp.ativo = 1
  join perfil pf on pf.id = pp.perfil_id
 where pa.ativo = 1 {FILTRO}
 group by pf.nome order by pessoas desc
"""

SQL_NOVOS_CADASTROS = """
-- INDICADOR OFICIAL — Novos cadastros por mês: pessoas cujo primeiro contato caiu no período.
select substr(p.data_primeiro_contato, 1, 7) as mes, count(*) as pessoas
  from pessoa p
 where p.ativo = 1 and p.data_primeiro_contato between :inicio and :fim
 group by mes order by mes
"""


def pessoas_por_faixa(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_POR_FAIXA, inicio, fim, programa_id)


def pessoas_por_genero(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_POR_GENERO, inicio, fim, programa_id)


def pessoas_por_perfil(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_POR_PERFIL, inicio, fim, programa_id)


def novos_cadastros_por_mes(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    """Não depende de programa: conta quem entrou no cadastro no período."""
    return _tabela(sessao, SQL_NOVOS_CADASTROS, inicio, fim, programa_id)


# --- Território e abordagem de rua --------------------------------------------------------

SQL_ANONIMOS_POR_LOCAL = f"""
-- INDICADOR OFICIAL — Contatos anônimos por local: soma das abordagens e das contagens por
-- faixa registradas em atividades do período, agrupadas por local.
select lo.nome as local, lo.tipo,
       sum(ca.abordagens) as abordagens,
       sum(ca.criancas) as criancas,
       sum(ca.adolescentes) as adolescentes,
       sum(ca.adultos) as adultos
  from contagem_anonima ca
  join atividade a on a.id = ca.atividade_id
  join local lo on lo.id = a.local_id
 where 1 = 1 {FILTRO}
 group by lo.nome, lo.tipo order by abordagens desc
"""

SQL_ABORDAGENS_POR_DIA = f"""
-- INDICADOR OFICIAL — Abordagens por dia (a tela agrupa por semana).
select a.data, sum(ca.abordagens) as abordagens
  from contagem_anonima ca join atividade a on a.id = ca.atividade_id
 where 1 = 1 {FILTRO}
 group by a.data order by a.data
"""

SQL_ITENS_POR_TIPO = f"""
-- INDICADOR OFICIAL — Itens distribuídos por tipo: soma das quantidades entregues em
-- atividades do período.
select ti.nome as tipo_item, ti.unidade, sum(it.quantidade) as quantidade
  from item_distribuido it
  join atividade a on a.id = it.atividade_id
  join tipo_item ti on ti.id = it.tipo_item_id
 where it.ativo = 1 {FILTRO}
 group by ti.nome, ti.unidade order by quantidade desc
"""


def contatos_anonimos_por_local(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_ANONIMOS_POR_LOCAL, inicio, fim, programa_id)


def abordagens_por_semana(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    diario = _tabela(sessao, SQL_ABORDAGENS_POR_DIA, inicio, fim, programa_id)
    return _por_semana(diario, "abordagens")


def itens_por_tipo(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_ITENS_POR_TIPO, inicio, fim, programa_id)


# --- Equipe e voluntariado ----------------------------------------------------------------

SQL_HORAS_VOLUNTARIADO_MES = f"""
-- INDICADOR OFICIAL — Horas de voluntariado por mês: soma de (quantidade de voluntários na
-- atividade x duração da atividade), apenas para as funções marcadas como voluntariado.
select substr(a.data, 1, 7) as mes,
       round(sum(ae.quantidade * a.duracao_minutos) / 60.0, 1) as horas
  from atividade_equipe ae
  join atividade a on a.id = ae.atividade_id
  join funcao_equipe f on f.id = ae.funcao_equipe_id
 where ae.ativo = 1 and f.conta_voluntariado = 1 {FILTRO}
 group by mes order by mes
"""

SQL_COMPOSICAO_EQUIPE = f"""
-- INDICADOR OFICIAL — Composição média da equipe por atividade: para cada função, a soma das
-- pessoas informadas dividida pelo número de atividades do período.
select f.nome as funcao,
       round(1.0 * sum(ae.quantidade) /
             (select count(*) from atividade a2 where 1 = 1
                and a2.ativo = 1
                and a2.data between :inicio and :fim
                and a2.programa_id = coalesce(:programa, a2.programa_id)), 2) as media,
       sum(ae.quantidade) as total
  from atividade_equipe ae
  join atividade a on a.id = ae.atividade_id
  join funcao_equipe f on f.id = ae.funcao_equipe_id
 where ae.ativo = 1 {FILTRO}
 group by f.nome order by total desc
"""


def horas_voluntariado_por_mes(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_HORAS_VOLUNTARIADO_MES, inicio, fim, programa_id)


def composicao_equipe(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    return _tabela(sessao, SQL_COMPOSICAO_EQUIPE, inicio, fim, programa_id)


# --- Encaminhamentos ----------------------------------------------------------------------
# A tabela encaminhamento é restrita: só services/restrito.py a consulta. Aqui só repassamos,
# para o dashboard continuar lendo tudo de um lugar só.


def resumo_encaminhamentos(sessao, inicio, fim) -> dict:
    return restrito.resumo_encaminhamentos(sessao, inicio, fim)


def encaminhamentos_por_destino(sessao, inicio, fim) -> pd.DataFrame:
    return pd.DataFrame(restrito.encaminhamentos_por_destino(sessao, inicio, fim))


def encaminhamentos_por_status(sessao, inicio, fim) -> pd.DataFrame:
    return pd.DataFrame(restrito.encaminhamentos_por_destino_e_status(sessao, inicio, fim))


# --- Visão do parceiro --------------------------------------------------------------------


def suprimir(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Esconde contagem menor que 5, que poderia identificar alguém.

    O número sai como vazio e aparece a etiqueta "<5" na coluna `<coluna>_rotulo`.
    """
    if df.empty:
        return df
    resultado = df.copy()
    pequeno = resultado[coluna] < MINIMO_PARA_MOSTRAR
    resultado[f"{coluna}_rotulo"] = resultado[coluna].map(lambda n: f"{n:.0f}")
    resultado.loc[pequeno, f"{coluna}_rotulo"] = f"<{MINIMO_PARA_MOSTRAR}"
    resultado.loc[pequeno, coluna] = None
    return resultado


def _suprimir_valor(valor) -> tuple[float | None, str]:
    if valor is None or valor < MINIMO_PARA_MOSTRAR:
        return None, f"<{MINIMO_PARA_MOSTRAR}"
    return valor, f"{valor:.0f}"


def ext_cartoes(sessao, inicio: date, fim: date, programa_id: str | None = None) -> dict:
    """Cartões da visão do parceiro: mesmos números, com supressão de contagem pequena."""
    exige_autenticado(sessao)
    df = _consultar(SQL_CARTOES, sessao.papel, _parametros(inicio, fim, programa_id))
    brutos = df.iloc[0].to_dict()
    resultado = {}
    for chave, valor in brutos.items():
        if chave in ("registros", "horas_voluntariado"):
            resultado[chave] = valor  # não é contagem de pessoas: não identifica ninguém
            continue
        numero, rotulo = _suprimir_valor(valor)
        resultado[chave] = numero
        resultado[f"{chave}_rotulo"] = rotulo
    return resultado


def ext_pessoas_por_programa(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    exige_autenticado(sessao)
    df = _consultar(SQL_PESSOAS_POR_PROGRAMA, sessao.papel, _parametros(inicio, fim, programa_id))
    return suprimir(df, "pessoas")


SQL_PARTICIPACOES_POR_MES = f"""
-- INDICADOR OFICIAL — Participações por mês (visão do parceiro).
select substr(a.data, 1, 7) as mes, count(*) as participacoes
  from participacao pa join atividade a on a.id = pa.atividade_id
 where pa.ativo = 1 {FILTRO}
 group by mes order by mes
"""


def ext_participacoes_por_mes(sessao, inicio, fim, programa_id=None) -> pd.DataFrame:
    exige_autenticado(sessao)
    df = _consultar(
        SQL_PARTICIPACOES_POR_MES, sessao.papel, _parametros(inicio, fim, programa_id)
    )
    return suprimir(df, "participacoes")
