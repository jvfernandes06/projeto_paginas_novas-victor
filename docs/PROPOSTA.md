# Proposta de arquitetura — Plataforma Páginas Novas (fase SQLite)

> **Leia antes:** este é o documento de projeto da etapa 1. A etapa 2 mudou quatro pontos dele,
> por decisão sua. O que está implementado de verdade está descrito no `README_TECNICO.md`.
>
> | Ponto | Nesta proposta | Como ficou na etapa 2 |
> |---|---|---|
> | Acesso ao banco | SQL cru com `sqlite3` e runner próprio de migrations | SQLAlchemy Core + Alembic, para o código já nascer portável ao Postgres |
> | Login | sem senha nesta fase | senha com bcrypt, troca obrigatória no primeiro acesso, usuários criados pela tela Admin |
> | Gestante | checkbox mais `dpp` opcional | só a checkbox; sem DPP, o indicador mede gestantes atendidas, não acompanhamento pré e pós-parto |
> | Dashboards | fase 2, depois | entregues nesta etapa: 6 internos e 1 do parceiro, com atualização automática a cada 60 s |
>
> As validações que dependiam de consulta (perfil compatível com a faixa, consentimento de
> menor, data no futuro) saíram dos triggers do SQLite e foram para `services/`, com mensagem em
> português para a tela — o banco guarda as declarativas, que são portáveis.

Revisão 2 — 19/10/2026. Incorpora as quatro respostas de hoje:

1. indicadores = funções com período (não views) — **aprovado**;
2. sem tabela `gestacao`: gestante é um sim/não na tabela `pessoa`, com `dpp` opcional na mesma
   tabela — o que preserva o indicador original de pré e pós-parto;
3. **SQLite primeiro**, Supabase depois; usuários em tabela própria, criados pela página Admin;
4. backup = cópia do arquivo SQLite.

E a rodada seguinte: **login sem senha nesta fase**, `dpp` opcional aprovada, cópia externa do
backup por enquanto não, caminho do banco em `PN_BANCO`. O que ficou para depois está em
`DECISOES_PENDENTES.md`.

O modelo de dados aprovado em Postgres, com as políticas RLS, está preservado em
`DESTINO_SUPABASE.md` e continua sendo o alvo da migração.

Sumário:

1. [O que muda ao sair do Supabase](#1-o-que-muda-ao-sair-do-supabase)
2. [Modelo de segurança sem RLS](#2-modelo-de-segurança-sem-rls)
3. [Schema SQLite](#3-schema-sqlite)
4. [Camada analítica](#4-camada-analítica)
5. [Estrutura de pastas](#5-estrutura-de-pastas)
6. [Mapa de páginas por papel](#6-mapa-de-páginas-por-papel)
7. [Operação: backup, deploy e migração futura](#7-operação-backup-deploy-e-migração-futura)
8. [Testes de aceite](#8-testes-de-aceite)
9. [Decisões que preciso que você confirme](#9-decisões-que-preciso-que-você-confirme)

---

## 1. O que muda ao sair do Supabase

| Item | Supabase (aprovado) | SQLite (agora) |
|---|---|---|
| Permissão | políticas RLS, aplicadas pelo banco | verificação em `services/`, aplicada pelo Python |
| Login | Supabase Auth | tabela `usuario`; **nesta fase, sem senha** (ver 2.1) |
| Recuperar senha | e-mail do Supabase | não existe enquanto não houver senha |
| Indicadores | funções SQL `security definer` | mesmas consultas SQL, chamadas por funções Python |
| Leitura auditada | função no banco, inescapável | módulo único de acesso, com teste que prova que é o único |
| Backup | PITR do Supabase | cópia a quente do arquivo `.db` (`sqlite3.Connection.backup`) |
| Concorrência | servidor Postgres | um processo, modo WAL; **não dá para rodar duas réplicas** |

**O que se perde, dito com clareza:** no Supabase, um erro de programação na tela não vazava
dado porque o banco recusava a consulta. No SQLite, a última barreira é o código Python. Mitigo
isso com três regras verificadas por teste automatizado (seção 2), mas é mais fraco que RLS — e
é o motivo de a migração para Postgres continuar no mapa.

**O que se ganha:** nenhuma dependência externa, nenhuma conta paga, nenhum segredo de
infraestrutura, e o banco inteiro é um arquivo que a ONG consegue copiar. Para começar e validar
o uso em campo, é a troca certa.

---

## 2. Modelo de segurança sem RLS

Três invariantes, cada uma com um teste que falha se alguém quebrar a regra:

**I1 — Nenhuma página abre o banco.** Só `services/` importa `services/db.py`. Página nenhuma
monta SQL. Teste: varredura do repositório procurando `sqlite3`, `db.conectar` ou `select ` em
`pages/`.

**I2 — Toda função de serviço recebe a sessão e checa o papel na primeira linha.** A sessão
(`usuario_id`, `papel`) nasce no login e vive em `st.session_state`; nunca é parâmetro de URL.
Teste: para cada função pública de `services/`, chamar com sessão de papel **Campo** e exigir
`PermissaoNegada` nas que não são dele.

**I3 — As tabelas restritas têm um único módulo de acesso.** `pessoa_contato`, `encaminhamento`
e `auditoria` só aparecem em `services/restrito.py`. Toda função de lá começa com
`exige_tecnico(sessao)` e termina com `registrar_auditoria(...)` antes de devolver o dado.
Teste: varredura provando que os nomes dessas três tabelas não aparecem em nenhum outro arquivo.

### 2.1 Login sem senha nesta fase

Decisão de 19/10/2026: por enquanto não há senha. O usuário escolhe quem é na tela de entrada e
a sessão passa a valer. **Consequência:** quem alcançar a URL entra com qualquer papel,
inclusive Admin. Então, enquanto isso valer, o app só pode rodar na máquina da ONG ou em rede
fechada, nunca publicado na internet.

Para isso não acontecer por engano, o app lê `PN_AMBIENTE` e **se recusa a subir** com
`PN_AMBIENTE=producao` enquanto a autenticação não existir. A tela de entrada também mostra um
aviso permanente de que o acesso está aberto.

O que fica pronto para quando a senha entrar: a tabela `usuario` já tem `email`, `papel` e
`ativo`, e a verificação de papel (I2) já funciona igual. A migration `0007` acrescentará
`senha_hash` (`hashlib.scrypt`, biblioteca padrão), `deve_trocar_senha`, `tentativas_falhas` e
`bloqueado_ate` — colunas que não existem agora porque não teriam uso.

Complementos:

- Sessão expira com 30 minutos de inatividade; botão "Sair" em todas as páginas.
- O arquivo `.db` contém dado sensível em texto claro: fica fora da pasta do código, com
  permissão só do usuário do serviço, em volume cifrado, e **o backup também é cifrado**.
- Nada de dado pessoal em log. O log registra `usuario_id` e código `PN-#####`, nunca nome.

---

## 3. Schema SQLite

Convenções do dialeto (o modelo é o mesmo do `DESTINO_SUPABASE.md`):

- chave primária `text` com UUID: `default (lower(hex(randomblob(16))))`;
- datas `text` no formato `YYYY-MM-DD`; horários `HH:MM`; timestamps `datetime('now')` em UTC;
- booleanos `integer` 0/1 com `check`;
- toda conexão abre com `pragma foreign_keys = on`, `journal_mode = wal`, `busy_timeout = 5000`;
- `check` não aceita `date('now')` no SQLite, então validação que depende de "hoje" vira trigger;
- exclusão é sempre lógica (`ativo = 0`); nenhuma tela executa `delete`;
- `updated_at` é mantido por trigger `after update` em cada tabela.

### 3.1 `0001_base.sql` — usuários, auditoria e contador

```sql
-- Sem colunas de senha nesta fase (ver 2.1); a migration 0007 as acrescenta.
create table usuario (
  id            text primary key default (lower(hex(randomblob(16)))),
  email         text not null unique,
  nome_exibicao text not null,
  papel         text not null check (papel in ('admin', 'tecnico', 'campo', 'parceiro')),
  ativo         integer not null default 1 check (ativo in (0, 1)),
  ultimo_login  text,
  created_at    text not null default (datetime('now')),
  updated_at    text not null default (datetime('now')),
  created_by    text references usuario (id)
);

create table auditoria (
  id          text primary key default (lower(hex(randomblob(16)))),
  usuario_id  text references usuario (id),
  acao        text not null check (acao in ('leitura', 'criacao', 'alteracao', 'revogacao_consentimento')),
  tabela      text not null,
  registro_id text,
  created_at  text not null default (datetime('now'))
);
create index auditoria_busca on auditoria (created_at desc, tabela);
-- Trilha de acesso a dado identificado (art. 37 LGPD). Só o Admin lê; ninguém altera nem apaga.

-- SQLite não tem sequence: o contador gera o código PN-00001.
create table contador (nome text primary key, valor integer not null default 0);
insert into contador (nome, valor) values ('pessoa_codigo', 0);
```

### 3.2 `0002_dominios.sql` — listas editáveis pelo Admin

Molde comum a todas: `id` uuid, `nome` único, `ativo`, `created_at`, `updated_at`, `created_by`
e trigger de `updated_at`.

```sql
create table programa (
  id text primary key default (lower(hex(randomblob(16)))),
  nome text not null unique,
  descricao text,
  publico_alvo text,
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create trigger trg_programa_updated after update on programa
begin update programa set updated_at = datetime('now') where id = new.id; end;

create table local (
  id text primary key default (lower(hex(randomblob(16)))),
  nome text not null unique,
  tipo text not null check (tipo in ('sede', 'boate', 'rua', 'externo')),
  latitude real, longitude real,          -- aproximadas, opcionais
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);

create table tipo_atividade         (... nome unique ...);  -- oficina, aula, abordagem, passeio,
                                                            -- evento, atendimento individual, roda de conversa
create table destino_encaminhamento (... nome unique ...);  -- CRAS, CREAS, UBS, CAPS, maternidade,
                                                            -- Conselho Tutelar, Defensoria, outro
create table bairro                 (... nome unique ...);
create table genero                 (... nome unique ...);  -- mulher cis, homem cis, mulher trans,
                                                            -- homem trans, não binário, prefere não informar
create table tipo_item              (... nome unique, unidade text not null default 'unidade' ...);

create table faixa_etaria (
  id text primary key default (lower(hex(randomblob(16)))),
  codigo text not null unique,            -- 0-5, 6-11, 12-17, 18-29, 30-44, 45-59, 60+
  rotulo text not null,
  ordem  integer not null,
  menor_de_idade integer not null check (menor_de_idade in (0, 1)),
  pode_gestar    integer not null check (pode_gestar in (0, 1)),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);

create table perfil (
  id text primary key default (lower(hex(randomblob(16)))),
  nome text not null unique,              -- criança, adolescente, TEA, responsável familiar,
                                          -- mulher em situação de prostituição, pessoa trans, idoso
  faixas_permitidas text,                 -- null = qualquer faixa; senão ',0-5,6-11,'
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
-- faixas_permitidas guarda os códigos entre vírgulas para o SQLite poder usar instr().
-- "gestante" saiu desta lista: virou o campo pessoa.gestante, para o número não vir de dois lugares.

create table funcao_equipe (
  id text primary key default (lower(hex(randomblob(16)))),
  nome text not null unique,              -- assistente social, estagiária, professor, voluntário,
                                          -- nutrição, coordenação
  conta_voluntariado integer not null default 0 check (conta_voluntariado in (0, 1)),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
```

### 3.3 `0003_pessoas.sql`

```sql
create table pessoa (
  id text primary key default (lower(hex(randomblob(16)))),
  codigo text unique,                     -- preenchido pelo trigger: PN-00001
  faixa_etaria_id text not null references faixa_etaria (id),
  genero_id       text not null references genero (id),
  bairro_id       text references bairro (id),
  gestante integer not null default 0 check (gestante in (0, 1)),
  dpp text,                               -- data provável do parto, opcional
  data_primeiro_contato text not null default (date('now')),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
-- Pseudonimizada: nenhum dado identificável. Nome e telefone só em pessoa_contato.

create trigger trg_pessoa_codigo after insert on pessoa
begin
  update contador set valor = valor + 1 where nome = 'pessoa_codigo';
  update pessoa
     set codigo = 'PN-' || substr('00000' ||
                  (select valor from contador where nome = 'pessoa_codigo'), -5)
   where id = new.id;
end;

-- Coerência: quem está marcado como gestante tem de estar em faixa etária compatível.
create trigger trg_pessoa_gestante_insert after insert on pessoa
when new.gestante = 1
 and (select pode_gestar from faixa_etaria where id = new.faixa_etaria_id) = 0
begin
  select raise(abort, 'Faixa etária incompatível com gestação');
end;
-- (um trigger igual para after update)

create table pessoa_perfil (
  id text primary key default (lower(hex(randomblob(16)))),
  pessoa_id text not null references pessoa (id),
  perfil_id text not null references perfil (id),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create unique index pessoa_perfil_unico on pessoa_perfil (pessoa_id, perfil_id) where ativo = 1;

-- Recusa perfil incompatível com a faixa etária (ex.: "criança" com faixa 30-44).
create trigger trg_pessoa_perfil_coerente after insert on pessoa_perfil
when (select pf.faixas_permitidas from perfil pf where pf.id = new.perfil_id) is not null
 and instr(
      (select pf.faixas_permitidas from perfil pf where pf.id = new.perfil_id),
      ',' || (select fe.codigo from pessoa p join faixa_etaria fe on fe.id = p.faixa_etaria_id
               where p.id = new.pessoa_id) || ','
     ) = 0
begin
  select raise(abort, 'Perfil incompatível com a faixa etária da pessoa');
end;

-- RESTRITA: acesso só por services/restrito.py, que audita toda leitura.
create table pessoa_contato (
  pessoa_id text primary key references pessoa (id),
  nome text,
  apelido text,
  telefone text,
  nome_responsavel text,
  consentimento_data text not null,
  consentimento_por  text not null check (consentimento_por in ('propria_pessoa', 'responsavel_legal')),
  consentimento_revogado_em text,
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id),
  constraint responsavel_obrigatorio
    check (consentimento_por <> 'responsavel_legal' or nome_responsavel is not null)
);
```

Consentimento obrigatório: no Postgres isso era garantido por função no banco. No SQLite, a
garantia é que `pessoa` e `pessoa_contato` são gravadas na **mesma transação** por
`services/pessoas.criar()`, que recusa menor de 18 sem responsável legal — e um trigger
`after insert on pessoa_contato` valida a regra do responsável também no banco.

### 3.4 `0004_atividades.sql`

```sql
create table atividade (
  id text primary key default (lower(hex(randomblob(16)))),
  data text not null,                     -- YYYY-MM-DD
  hora_inicio text not null,              -- HH:MM
  hora_fim    text not null,
  programa_id       text not null references programa (id),
  local_id          text not null references local (id),
  tipo_atividade_id text not null references tipo_atividade (id),
  descricao_curta text check (length(descricao_curta) <= 200),
  observacao text,                        -- único texto livre; não entra em análise
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id),
  constraint hora_coerente check (hora_fim > hora_inicio)
);

-- Bloqueio de duplicata: mesma data + programa + local + horário.
create unique index atividade_sem_duplicata
  on atividade (data, programa_id, local_id, hora_inicio) where ativo = 1;
-- Desempenho dos indicadores (todos filtram por data e agrupam por programa).
create index atividade_periodo on atividade (data, programa_id, local_id);

create trigger trg_atividade_data_futura after insert on atividade
when new.data > date('now')
begin select raise(abort, 'A data da atividade não pode ser no futuro'); end;

create table atividade_equipe (
  id text primary key default (lower(hex(randomblob(16)))),
  atividade_id text not null references atividade (id),
  funcao_equipe_id text not null references funcao_equipe (id),
  quantidade integer not null check (quantidade > 0),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create unique index atividade_equipe_unico
  on atividade_equipe (atividade_id, funcao_equipe_id) where ativo = 1;

create table participacao (
  id text primary key default (lower(hex(randomblob(16)))),
  atividade_id text not null references atividade (id),
  pessoa_id    text not null references pessoa (id),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create unique index participacao_unica on participacao (atividade_id, pessoa_id) where ativo = 1;
create index participacao_por_pessoa on participacao (pessoa_id);

-- Abordagem de rua e boate: contagem sem identificar ninguém (seção 4.3 do prompt).
create table contagem_anonima (
  atividade_id text primary key references atividade (id),
  abordagens   integer not null default 0 check (abordagens >= 0),
  criancas     integer not null default 0 check (criancas >= 0),
  adolescentes integer not null default 0 check (adolescentes >= 0),
  adultos      integer not null default 0 check (adultos >= 0),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id),
  constraint alguma_contagem check (abordagens + criancas + adolescentes + adultos > 0)
);

create table item_distribuido (
  id text primary key default (lower(hex(randomblob(16)))),
  atividade_id text not null references atividade (id),
  tipo_item_id text not null references tipo_item (id),
  quantidade integer not null check (quantidade > 0),
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create unique index item_distribuido_unico
  on item_distribuido (atividade_id, tipo_item_id) where ativo = 1;
```

### 3.5 `0005_encaminhamentos.sql`

```sql
-- RESTRITA: acesso só por services/restrito.py, que audita toda leitura.
create table encaminhamento (
  id text primary key default (lower(hex(randomblob(16)))),
  pessoa_id  text not null references pessoa (id),
  destino_id text not null references destino_encaminhamento (id),
  data text not null default (date('now')),
  status text not null default 'enviado'
         check (status in ('enviado', 'em_andamento', 'concluido', 'sem_retorno')),
  data_ultima_atualizacao text not null default (date('now')),
  observacao text,
  ativo integer not null default 1 check (ativo in (0, 1)),
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now')),
  created_by text references usuario (id)
);
create index encaminhamento_pendente on encaminhamento (status, data_ultima_atualizacao);
```

### 3.6 `0006_relatorio_emitido.sql`

```sql
create table relatorio_emitido (
  id text primary key default (lower(hex(randomblob(16)))),
  periodo_de  text not null,
  periodo_ate text not null,
  emitido_em  text not null default (datetime('now')),
  indicadores text not null,              -- JSON com os valores congelados
  created_by  text references usuario (id),
  constraint periodo_coerente check (periodo_ate > periodo_de)
);
-- Snapshot do que foi enviado ao financiador. Nunca é alterado nem apagado: é a prova do número.
-- Nenhuma função de serviço faz update ou delete nesta tabela.
```

---

## 4. Camada analítica

### 4.1 Molde de cada indicador

O SQL fica em `analytics/indicadores.py`, uma constante por indicador, escrito em dialeto comum
aos dois bancos para migrar sem reescrita. A regra é escrita **uma vez** e usada por duas
funções: a interna (número cheio) e a externa (com supressão em SQL).

```python
PESSOAS_UNICAS = """
-- INDICADOR OFICIAL — Pessoas únicas atendidas: pessoas distintas com pelo menos uma
-- participação ativa em atividade ativa cuja data está no período, por programa e perfil.
select pr.nome as programa,
       pf.nome as perfil,
       count(distinct p.id) as pessoas
  from participacao pa
  join atividade a  on a.id = pa.atividade_id and a.ativo = 1
  join pessoa p     on p.id = pa.pessoa_id    and p.ativo = 1
  join programa pr  on pr.id = a.programa_id
  left join pessoa_perfil pp on pp.pessoa_id = p.id and pp.ativo = 1
  left join perfil pf        on pf.id = pp.perfil_id
 where pa.ativo = 1 and a.data between :de and :ate
 group by pr.nome, pf.nome
 order by pessoas desc
"""

def pessoas_unicas_atendidas(sessao, de, ate) -> pd.DataFrame:
    exige_tecnico(sessao)
    return consultar(PESSOAS_UNICAS, de=de, ate=ate)

def ext_pessoas_unicas_atendidas(sessao, de, ate) -> pd.DataFrame:
    exige_autenticado(sessao)
    return consultar(suprimir(PESSOAS_UNICAS, coluna="pessoas"), de=de, ate=ate)
```

`suprimir()` envolve a consulta base, sem duplicar a regra:

```sql
select programa, perfil,
       case when pessoas < 5 then null else pessoas end as pessoas,
       case when pessoas < 5 then '<5' else cast(pessoas as text) end as pessoas_rotulo
  from ( <consulta base> )
```

Assim o número do dashboard externo nunca diverge do interno, e a supressão continua sendo
responsabilidade do SQL, não da tela.

### 4.2 Os nove indicadores

| Função | Definição oficial (vai no comentário do SQL) | Colunas |
|---|---|---|
| `pessoas_unicas_atendidas` | pessoas distintas com ≥1 participação no período, por programa e perfil | programa, perfil, pessoas |
| `contatos_anonimos` | soma das abordagens de contagem anônima das atividades do período, por local e programa | local, programa, abordagens, criancas, adolescentes, adultos |
| `atividades_por_programa` | nº de atividades e soma das horas (hora_fim − hora_inicio) no período, por programa | programa, atividades, horas |
| `taxa_recorrencia` | pessoas com ≥3 participações no período ÷ pessoas com ≥1, por programa | programa, pessoas, pessoas_3mais, taxa_pct |
| `encaminhamentos` | encaminhamentos com data no período, por destino e status; taxa de conclusão = concluídos ÷ total | destino, status, total, taxa_conclusao_pct |
| `gestantes_acompanhamento` | gestantes com DPP informada e com participação antes da DPP, depois da DPP e nas duas janelas (ver 4.3) | gestantes, com_pre, com_pos, com_pre_e_pos |
| `itens_distribuidos` | soma das quantidades distribuídas nas atividades do período, por tipo de item | tipo_item, unidade, quantidade |
| `horas_voluntariado` | soma de (quantidade da equipe × duração da atividade) nas funções com `conta_voluntariado`, no período | programa, horas_voluntariado |
| `novos_cadastros` | pessoas com `data_primeiro_contato` no período, por mês | mes, pessoas |

Cada uma tem o par `ext_*` com supressão. Em `ext_taxa_recorrencia` a linha inteira é suprimida
quando a base tem menos de 5 pessoas, porque taxa sobre base pequena identifica. Nas versões
externas o cruzamento é reduzido a programa e mês — sem perfil, bairro ou local — para impedir
isolamento de indivíduo por diferença entre recortes.

### 4.3 Indicador de gestantes

Com `pessoa.gestante` e `pessoa.dpp` (opcional), o indicador da seção 6.1 fica preservado:

> **Gestantes em acompanhamento:** pessoas marcadas como gestante, com DPP informada, contadas
> por terem participação em atividade do período **antes** da DPP (pré-natal), **depois** da DPP
> (pós-parto) e nas duas janelas.

A DPP é opcional porque em abordagem de rua muitas vezes não se sabe. Gestante sem DPP entra na
contagem de atendimento, mas não no acompanhamento pré/pós — o indicador informa as duas
quantidades, para o relatório não parecer menor do que o trabalho foi.

Efeito colateral do sim/não: a marca não tem história. Depois do parto, a pessoa continua
marcada como gestante até alguém desmarcar. A tela de Pendências lista "gestante com DPP há mais
de 3 meses" para a Técnica revisar.

### 4.4 Pendências

`analytics/pendencias.py`, só Técnico e Admin, `union all` de cinco consultas, cada linha com
`tipo`, `descricao`, `registro_id`, `data_referencia`:

1. atividade ativa sem nenhuma participação **e** sem contagem anônima;
2. encaminhamento ativo não concluído com `data_ultima_atualizacao` há mais de 60 dias;
3. pessoa ativa sem consentimento válido (sem data ou com revogação);
4. atividade ativa sem nenhuma linha de equipe;
5. pessoa marcada como gestante com DPP há mais de 3 meses (ver 4.3).

### 4.5 Atualização em tempo real (seção 6.3 do prompt)

Nada de ETL nem de tabela de resumo: as consultas rodam na hora, no arquivo local — que para
este volume é mais rápido que ir à rede buscar no Postgres.

- blocos de gráfico em `@st.fragment(run_every=INTERVALO)`, com
  `INTERVALO = st.secrets.get("intervalo_atualizacao_seg", 60)`;
- `st.cache_data` com `ttl = INTERVALO` e chave incluindo papel, período e programa;
  `st.cache_data.clear()` no fim de todo fluxo de gravação;
- cada dashboard mostra `Atualizado às HH:MM` e o total de registros do período;
- mês corrente aparece marcado como **parcial**; o PDF para parceiro só sai para mês encerrado
  e grava o snapshot em `relatorio_emitido`;
- seed com **3 anos de dados fictícios** (≈ 2.500 atividades, 20 mil participações, 900
  pessoas) e teste provando que cada dashboard responde em menos de 3 segundos.

### 4.6 Seed

- `sql/seed/01_dominios.sql`: os 19 programas do prompt, tipos de atividade, destinos, tipos de
  item, perfis com `faixas_permitidas`, faixas etárias, gêneros, funções de equipe, locais. É
  configuração, não dado pessoal.
- `scripts/gerar_demo.py`: **só dados fictícios**, com semente fixa (`random.seed`) para os
  números do teste de indicador serem sempre os mesmos.

---

## 5. Estrutura de pastas

```
projeto_paginas_novas/
├─ app.py                      # st.navigation/st.Page: monta o menu conforme o papel
├─ requirements.txt            # streamlit, pandas, plotly, kaleido, reportlab (versões fixas)
├─ Dockerfile                  # 1 processo + volume para o arquivo .db
├─ .env.example                # caminho do banco, intervalo de atualização, tempo de sessão
├─ .streamlit/config.toml      # tema e layout centralizado (celular)
├─ pages/                      # SÓ interface; nunca abre o banco nem monta SQL
│  ├─ login.py
│  ├─ inicio.py
│  ├─ registrar_atividade.py   # 6 etapas, cada uma em st.form
│  ├─ cadastrar_pessoa.py
│  ├─ encaminhamentos.py
│  ├─ pendencias.py
│  ├─ admin.py                 # usuários, papéis e tabelas de domínio
│  ├─ auditoria.py
│  ├─ exportar_csv.py
│  ├─ dashboard_interno.py     # fase 2
│  ├─ dashboard_externo.py     # fase 2
│  └─ relatorio_pdf.py         # fase 2
├─ services/                   # acesso ao banco; nenhum componente de tela
│  ├─ db.py                    # conexão (WAL, foreign_keys), transação, consultar/executar
│  ├─ seguranca.py             # Sessao, exige_papel, expiração, scrypt, bloqueio por tentativa
│  ├─ auth.py                  # entrar, sair, trocar senha
│  ├─ dominios.py              # listas (único lugar com cache de domínio)
│  ├─ pessoas.py               # criar (pessoa + consentimento na mesma transação), buscar
│  ├─ atividades.py
│  ├─ restrito.py              # ÚNICO módulo que toca pessoa_contato, encaminhamento, auditoria
│  └─ administracao.py
├─ analytics/                  # leitura dos indicadores e gráficos
│  ├─ indicadores.py           # o SQL oficial de cada indicador + versões ext_
│  ├─ pendencias.py
│  ├─ graficos.py              # Plotly + a frase explicativa de cada gráfico
│  └─ pdf.py                   # reportlab
├─ sql/
│  ├─ migrations/              # 0001_base.sql … 0006_relatorio_emitido.sql
│  └─ seed/01_dominios.sql
├─ scripts/
│  ├─ aplicar_migrations.py    # controla o que já foi aplicado em schema_migracao
│  ├─ criar_primeiro_admin.py
│  ├─ backup.py                # cópia a quente + retenção de 30 dias
│  └─ gerar_demo.py
├─ tests/
│  ├─ conftest.py              # banco temporário + migrations + seed + 4 sessões fictícias
│  ├─ test_invariantes_codigo.py   # I1, I2, I3 por varredura do repositório
│  ├─ test_permissao_campo.py
│  ├─ test_auditoria.py
│  ├─ test_supressao_ext.py
│  ├─ test_consentimento.py
│  ├─ test_qualidade_dados.py
│  ├─ test_indicadores_seed.py
│  └─ test_desempenho.py
├─ docs/PROPOSTA.md  docs/DESTINO_SUPABASE.md  docs/TESTE_CAMPO.md
├─ README_ONG.md
└─ README_TECNICO.md
```

---

## 6. Mapa de páginas por papel

Sem mudança em relação ao aprovado:

| Página | Admin | Técnico | Campo | Parceiro |
|---|:--:|:--:|:--:|:--:|
| Login / trocar senha | ✓ | ✓ | ✓ | ✓ |
| Início (atalhos grandes) | ✓ | ✓ | ✓ | — |
| Registrar atividade | ✓ | ✓ | ✓ | — |
| Cadastrar pessoa | ✓ | ✓ | — | — |
| Encaminhamentos | ✓ | ✓ | — | — |
| Pendências | ✓ | ✓ | — | — |
| Admin (usuários e listas) | ✓ | — | — | — |
| Auditoria | ✓ | — | — | — |
| Exportação CSV | ✓ | ✓ | — | — |
| Dashboard interno (fase 2) | ✓ | ✓ | — | — |
| Dashboard externo (fase 2) | ✓ | ✓ | — | ✓ |
| Relatório PDF (fase 2) | ✓ | ✓ | — | ✓ (versão externa) |

Na etapa de participantes, o papel Campo vê **apenas o código** (`PN-00001`) e a faixa etária.
A checagem é feita duas vezes: ao montar o menu e na primeira linha de cada página.

---

## 7. Operação: backup, deploy e migração futura

**Backup.** `scripts/backup.py` usa `sqlite3.Connection.backup()`, que copia o banco em uso sem
parar o app. Gera `backups/paginas_novas_AAAA-MM-DD.db`, mantém 30 dias, e é agendado uma vez
por dia (Agendador de Tarefas no Windows, `cron` no Linux). Restaurar = parar o app, trocar o
arquivo, subir. As duas instruções ficam no `README_ONG.md`, em linguagem não técnica. O backup
sai cifrado e **precisa de uma cópia fora da máquina** — do contrário, perder o servidor é
perder tudo (pergunta 3 da seção 9).

**Deploy.** Container com um único processo Streamlit e um volume para o `.db`. Não pode haver
duas réplicas: duas instâncias escrevendo no mesmo arquivo corrompem o banco. Fly.io com volume
ou uma VPS pequena atendem.

**Migração para Supabase, quando houver conta.** O caminho fica curto porque: o SQL dos
indicadores é portável, todo acesso passa por `services/db.py`, e as regras de permissão do
`seguranca.py` traduzem uma a uma para as políticas RLS de `DESTINO_SUPABASE.md`. O trabalho
será: trocar o driver, gerar as migrations em dialeto Postgres, reescrever as três invariantes
como RLS e importar os dados. As senhas não migram — os usuários recebem convite pelo Supabase
Auth.

---

## 8. Testes de aceite

| Critério do prompt | Como fica no SQLite |
|---|---|
| Campo não lê `pessoa_contato`, `encaminhamento`, `auditoria` | `test_permissao_campo.py` chama cada função de `restrito.py` com sessão Campo e exige `PermissaoNegada`; `test_invariantes_codigo.py` prova que não existe outro caminho até essas tabelas |
| Nenhuma página usa chave privilegiada | vira: nenhuma página abre o banco (invariante I1, por varredura) |
| Nenhum dado identificado em cache | varredura de `st.cache_*` fora de `services/dominios.py` e `analytics/` |
| `ext_*` nunca devolve contagem < 5 | roda todas as funções externas no seed e afirma `valor is None or valor >= 5` |
| Pessoa sem consentimento / atividade sem programa, local, data | chamada direta aos serviços esperando erro, e `insert` cru esperando erro de constraint |
| Toda leitura identificada gera auditoria | conta linhas de `auditoria` antes e depois de cada função de leitura de `restrito.py` |
| Indicadores batem com o seed | valores esperados escritos no teste, com semente fixa no gerador |
| Dashboard < 3 s | `test_desempenho.py` com 3 anos de dados fictícios |
| Fluxo de atividade < 3 min no celular | roteiro cronometrado em `docs/TESTE_CAMPO.md` (manual) |

---

## 9. Decisões

Todas as perguntas abertas, mais as que foram adiadas de propósito, estão em
`DECISOES_PENDENTES.md`, com o que cada uma impede e quando precisa ser respondida.
Nada aqui está travado esperando resposta: a etapa 1 segue com as decisões já tomadas.
