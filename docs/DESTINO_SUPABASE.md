# Destino da migração — Supabase/Postgres

Este documento é o **alvo da fase 2 de infraestrutura**, não o que será implementado agora.
A fase atual é SQLite (ver `PROPOSTA.md`). O conteúdo abaixo foi aprovado em 19/10/2026 e fica
guardado porque é para cá que o banco vai quando a ONG tiver conta paga no Supabase: o modelo de
dados é o mesmo, o que muda é dialeto, autenticação e a volta das políticas RLS.

Alterações já acordadas depois da aprovação: a tabela `gestacao` **não existe** (virou o campo
`pessoa.gestante`), e o indicador de gestantes foi redefinido (ver `PROPOSTA.md`).


1. [Decisões de arquitetura](#1-decisões-de-arquitetura)
2. [Schema SQL](#2-schema-sql)
3. [Políticas RLS](#3-políticas-rls-0006_rlssql)
4. [Acesso auditado aos dados restritos](#4-acesso-auditado-aos-dados-restritos-0007_rpc_restritosql)
5. [Camada analítica](#5-camada-analítica)
6. [Estrutura de pastas](#6-estrutura-de-pastas)
7. [Mapa de páginas por papel](#7-mapa-de-páginas-por-papel)
8. [Testes de aceite](#8-testes-de-aceite)
9. [Decisões que preciso que você confirme](#9-decisões-que-preciso-que-você-confirme)

---

## 1. Decisões de arquitetura

### D1 — Papel do usuário fica na tabela `usuario`, não no JWT

A RLS consulta `app.papel()`, uma função `stable security definer` que lê a tabela `usuario`.
Alternativa descartada: *custom access token hook* do Supabase, que grava o papel no JWT.
Motivo: com o papel no JWT, desativar alguém só tem efeito depois que o token expira; com a
tabela, o Admin tira o acesso na hora. A função é `stable`, então o Postgres a executa uma vez
por comando, não por linha.

### D2 — `pessoa_contato` e `encaminhamento` não têm `SELECT` para ninguém

O critério de aceite exige que **toda leitura** de dado identificado gere auditoria. RLS não
consegue registrar leituras. Portanto esses dados ficam sem `GRANT` nenhum para o papel
`authenticated` (nem para o Técnico) e são acessados **só** por funções `security definer`
(`fn_contato_ver`, `fn_encaminhamento_listar`, …) que (a) checam o papel, (b) gravam em
`auditoria`, (c) devolvem os dados. A RLS continua ligada com política `false` como segunda
barreira. Resultado: nem o papel Campo nem ninguém lê essas tabelas pela API direta.

### D3 — `pessoa` só pode ser criada pela função `fn_pessoa_criar`

"Não é possível salvar pessoa sem consentimento" precisa ser garantido pelo banco, e pessoa +
consentimento estão em duas tabelas. A função cria as duas linhas numa transação e valida que
menor de 18 tem responsável legal. `INSERT` direto em `pessoa` é revogado.

### D4 — Indicadores são funções SQL com período, não views

O prompt pede "uma view por indicador". **Proponho funções `fn_<indicador>(p_de, p_ate)`** em
vez de views, por três motivos:

1. Quase todo indicador da seção 6.1 é **não aditivo** no tempo (pessoa única, taxa de
   recorrência, taxa de conclusão). Uma view mensal obrigaria o app a recalcular o indicador em
   pandas — exatamente o que a ONG não pode manter. Com função parametrizada, a definição fica
   100% em SQL e o app só desenha o resultado.
2. A função `security definer` resolve o acesso do papel Parceiro, que não tem (e não pode ter)
   `SELECT` nas tabelas base.
3. O período vira argumento, então o filtro do dashboard não pode errar o cálculo.

Fica mantido tudo o que a seção 6.1 exige: um objeto por indicador, versionado em migration,
com `COMMENT` contendo a definição oficial, e os gráficos/PDF leem **apenas** esses objetos.

A lógica de cada indicador é escrita **uma vez** em `app.base_<indicador>()` e consumida por
dois invólucros: `fn_<indicador>` (interno, número cheio) e `fn_ext_<indicador>` (externo, com
supressão). Assim o número do dashboard externo nunca diverge do interno.

As funções são `stable` e calculadas **na hora da consulta**, lendo as tabelas base. Não há
materialized view, tabela de resumo nem job de carga — o requisito 6.3 é atendido do mesmo jeito
que seria com views comuns. A única cópia de número que existe no sistema é o snapshot
`relatorio_emitido` (seção 5.5), que o próprio 6.3 exige para congelar o que foi enviado ao
financiador.

### D5 — PDF com `reportlab`

`weasyprint` precisa de GTK/Pango/Cairo instalados no sistema — quebra fácil no Windows do
desenvolvedor e engorda a imagem Docker. `reportlab` é uma wheel pura, sem dependência de
sistema, e o relatório é simples (logo, cards, tabelas, gráficos exportados como PNG via
`plotly` + `kaleido`). Uma dependência de sistema a menos é uma chance a menos de o app parar
sem ninguém para consertar.

### D6 — Campos novos que o modelo da seção 5 não previa

| Campo/tabela | Por que é necessário |
|---|---|
| `gestacao (pessoa_id, dpp)` | `vw_gestantes_acompanhamento` compara participações antes/depois da data provável do parto — a DPP não existe em nenhuma tabela da seção 5 |
| `bairro` como tabela de domínio | "Nenhum campo analítico em texto livre"; bairro é analítico |
| `genero`, `faixa_etaria`, `funcao_equipe` como tabelas de domínio | mesma regra; `funcao_equipe.conta_voluntariado` é o que permite calcular horas de voluntariado sem o app saber quais funções contam |
| `perfil.faixas_permitidas` | implementa a validação "perfil criança só com faixa etária compatível" de forma editável pelo Admin, sem mexer em código |

---

## 2. Schema SQL

### 2.1 `0001_base.sql` — papéis, auditoria e utilitários

```sql
create extension if not exists pgcrypto;          -- gen_random_uuid()
create schema if not exists app;                  -- funções de apoio; NÃO exposta no PostgREST
grant usage on schema app to authenticated;

create type papel_usuario as enum ('admin', 'tecnico', 'campo', 'parceiro');

create table usuario (
  id            uuid primary key references auth.users (id),
  nome_exibicao text not null,
  papel         papel_usuario not null,
  ativo         boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  created_by    uuid references usuario (id)
);
comment on table usuario is
  'Perfil do usuário. O papel gravado aqui comanda toda a RLS. Desativar = ativo=false.';

create table auditoria (
  id          uuid primary key default gen_random_uuid(),
  usuario_id  uuid references usuario (id),
  acao        text not null,            -- leitura | criacao | alteracao | revogacao_consentimento
  tabela      text not null,
  registro_id uuid,
  created_at  timestamptz not null default now()
);
create index auditoria_busca on auditoria (created_at desc, tabela);
comment on table auditoria is
  'Trilha de acesso a dado identificado (art. 37 LGPD). Só o Admin lê; ninguém altera nem apaga.';

-- Papel do usuário logado. security definer para não cair na RLS da própria tabela usuario.
create function app.papel() returns papel_usuario
  language sql stable security definer set search_path = public, pg_temp
as $$ select u.papel from usuario u where u.id = auth.uid() and u.ativo $$;

create function app.autenticado() returns boolean language sql stable
as $$ select app.papel() is not null $$;

create function app.e_admin() returns boolean language sql stable
as $$ select app.papel() = 'admin' $$;

-- Técnico e Admin: veem dado identificado e os indicadores internos.
create function app.pode_ver_identificado() returns boolean language sql stable
as $$ select app.papel() in ('admin', 'tecnico') $$;

-- Quem opera o registro de campo.
create function app.e_equipe() returns boolean language sql stable
as $$ select app.papel() in ('admin', 'tecnico', 'campo') $$;

create function app.audita(p_acao text, p_tabela text, p_registro uuid default null)
  returns void language sql security definer set search_path = public, pg_temp
as $$ insert into auditoria (usuario_id, acao, tabela, registro_id)
     values (auth.uid(), p_acao, p_tabela, p_registro) $$;

create function app.set_updated_at() returns trigger language plpgsql
as $$ begin new.updated_at := now(); return new; end $$;

-- Supressão estatística para a visão externa (contagens < 5).
create function app.sup(p_n numeric) returns numeric immutable language sql
as $$ select case when p_n < 5 then null else p_n end $$;

create function app.sup_rotulo(p_n numeric) returns text immutable language sql
as $$ select case when p_n < 5 then '<5' else trim(to_char(p_n, '999999990.9')) end $$;
```

### 2.2 `0002_dominios.sql` — listas editáveis pelo Admin

Todas seguem o mesmo molde: `id uuid`, `nome` único, `ativo`, `created_at`, `updated_at`,
`created_by`, trigger de `updated_at`.

```sql
create table programa (
  id uuid primary key default gen_random_uuid(),
  nome text not null unique,
  descricao text,
  publico_alvo text,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);

create table local (
  id uuid primary key default gen_random_uuid(),
  nome text not null unique,
  tipo text not null check (tipo in ('sede', 'boate', 'rua', 'externo')),
  latitude  numeric(8, 5),      -- aproximada, opcional
  longitude numeric(8, 5),
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);

create table tipo_atividade          (... nome unique ...);   -- oficina, aula, abordagem, passeio,
                                                              -- evento, atendimento individual, roda de conversa
create table destino_encaminhamento  (... nome unique ...);   -- CRAS, CREAS, UBS, CAPS, maternidade,
                                                              -- Conselho Tutelar, Defensoria, outro
create table bairro                  (... nome unique ...);
create table genero                  (... nome unique ...);   -- mulher cis, homem cis, mulher trans,
                                                              -- homem trans, não binário, prefere não informar

create table tipo_item (
  id uuid primary key default gen_random_uuid(),
  nome text not null unique,
  unidade text not null default 'unidade',
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);

create table faixa_etaria (
  id uuid primary key default gen_random_uuid(),
  codigo text not null unique,        -- 0-5, 6-11, 12-17, 18-29, 30-44, 45-59, 60+
  rotulo text not null,
  ordem  int  not null,
  menor_de_idade boolean not null,    -- usado para exigir responsável legal no consentimento
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);

create table perfil (
  id uuid primary key default gen_random_uuid(),
  nome text not null unique,          -- gestante, criança, adolescente, TEA, responsável familiar,
                                      -- mulher em situação de prostituição, pessoa trans, idoso
  faixas_permitidas text[],           -- null = qualquer faixa; ex. criança => {'0-5','6-11'}
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);
comment on column perfil.faixas_permitidas is
  'Faixas etárias (faixa_etaria.codigo) compatíveis com o perfil. O banco recusa a combinação errada.';

create table funcao_equipe (
  id uuid primary key default gen_random_uuid(),
  nome text not null unique,          -- assistente social, estagiária, professor, voluntário,
                                      -- nutrição, coordenação
  conta_voluntariado boolean not null default false,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);
```

### 2.3 `0003_pessoas.sql`

```sql
create sequence seq_pessoa_codigo;

create table pessoa (
  id uuid primary key default gen_random_uuid(),
  codigo text not null unique
         default 'PN-' || lpad(nextval('seq_pessoa_codigo')::text, 5, '0'),
  faixa_etaria_id uuid not null references faixa_etaria (id),
  genero_id       uuid not null references genero (id),
  bairro_id       uuid references bairro (id),
  data_primeiro_contato date not null default current_date,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);
comment on table pessoa is
  'Pseudonimizada: nenhum dado identificável. Nome e telefone só em pessoa_contato.';

create table pessoa_perfil (
  pessoa_id uuid not null references pessoa (id),
  perfil_id uuid not null references perfil (id),
  created_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  primary key (pessoa_id, perfil_id)
);

-- Recusa perfil incompatível com a faixa etária (ex.: "criança" com faixa 30-44).
create function app.valida_pessoa_perfil() returns trigger
  language plpgsql set search_path = public, pg_temp as $$
declare v_faixa text; v_permitidas text[];
begin
  select fe.codigo into v_faixa
    from pessoa p join faixa_etaria fe on fe.id = p.faixa_etaria_id
   where p.id = new.pessoa_id;
  select faixas_permitidas into v_permitidas from perfil where id = new.perfil_id;
  if v_permitidas is not null and not (v_faixa = any (v_permitidas)) then
    raise exception 'Perfil incompatível com a faixa etária % da pessoa', v_faixa;
  end if;
  return new;
end $$;
create trigger trg_pessoa_perfil_coerente before insert or update on pessoa_perfil
  for each row execute function app.valida_pessoa_perfil();

-- RESTRITA: sem SELECT para nenhum papel; acesso só pelas funções do 0007.
create table pessoa_contato (
  pessoa_id uuid primary key references pessoa (id),
  nome text,
  apelido text,
  telefone text,
  nome_responsavel text,
  consentimento_data date not null,
  consentimento_por  text not null check (consentimento_por in ('propria_pessoa', 'responsavel_legal')),
  consentimento_revogado_em timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  constraint responsavel_obrigatorio
    check (consentimento_por <> 'responsavel_legal' or nome_responsavel is not null)
);
comment on table pessoa_contato is
  'Dado identificável (art. 11 LGPD). Sem GRANT de SELECT: leitura só via fn_contato_ver, que audita.';

create table gestacao (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references pessoa (id),
  dpp date not null,                  -- data provável do parto
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);
comment on table gestacao is
  'Só a DPP, para medir acompanhamento pré e pós-parto. Nada de prontuário.';
```

### 2.4 `0004_atividades.sql`

```sql
create table atividade (
  id uuid primary key default gen_random_uuid(),
  data date not null,
  hora_inicio time not null,
  hora_fim    time not null,
  programa_id       uuid not null references programa (id),
  local_id          uuid not null references local (id),
  tipo_atividade_id uuid not null references tipo_atividade (id),
  descricao_curta text check (char_length(descricao_curta) <= 200),
  observacao text,                    -- único texto livre; não entra em análise
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  constraint hora_coerente check (hora_fim > hora_inicio)
);

-- Bloqueio de duplicata: mesma data + programa + local + horário.
create unique index atividade_sem_duplicata
  on atividade (data, programa_id, local_id, hora_inicio) where ativo;

-- Desempenho dos indicadores (todos filtram por data e agrupam por programa).
create index atividade_periodo on atividade (data, programa_id, local_id);

create function app.valida_atividade() returns trigger language plpgsql as $$
begin
  if new.data > current_date then
    raise exception 'A data da atividade não pode ser no futuro';
  end if;
  if new.hora_fim - new.hora_inicio > interval '12 hours' then
    raise exception 'Duração acima de 12 horas; confira o horário';
  end if;
  return new;
end $$;
create trigger trg_atividade_valida before insert or update on atividade
  for each row execute function app.valida_atividade();

create table atividade_equipe (
  atividade_id uuid not null references atividade (id),
  funcao_equipe_id uuid not null references funcao_equipe (id),
  quantidade int not null check (quantidade > 0),
  created_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  primary key (atividade_id, funcao_equipe_id)
);

create table participacao (
  atividade_id uuid not null references atividade (id),
  pessoa_id    uuid not null references pessoa (id),
  created_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  primary key (atividade_id, pessoa_id)
);
-- A chave primária já serve a busca por atividade; este índice serve a busca por pessoa
-- (pessoas únicas, taxa de recorrência, acompanhamento de gestantes).
create index participacao_por_pessoa on participacao (pessoa_id);

-- Abordagem de rua e boate: contagem sem identificar ninguém (seção 4.3).
create table contagem_anonima (
  atividade_id uuid primary key references atividade (id),
  abordagens    int not null default 0 check (abordagens >= 0),
  criancas      int not null default 0 check (criancas >= 0),
  adolescentes  int not null default 0 check (adolescentes >= 0),
  adultos       int not null default 0 check (adultos >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  constraint alguma_contagem
    check (abordagens + criancas + adolescentes + adultos > 0)
);

create table item_distribuido (
  atividade_id uuid not null references atividade (id),
  tipo_item_id uuid not null references tipo_item (id),
  quantidade int not null check (quantidade > 0),
  created_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid(),
  primary key (atividade_id, tipo_item_id)
);
```

### 2.5 `0005_encaminhamentos.sql`

```sql
-- RESTRITA: sem SELECT para nenhum papel; acesso só pelas funções do 0007.
create table encaminhamento (
  id uuid primary key default gen_random_uuid(),
  pessoa_id  uuid not null references pessoa (id),
  destino_id uuid not null references destino_encaminhamento (id),
  data date not null default current_date,
  status text not null default 'enviado'
         check (status in ('enviado', 'em_andamento', 'concluido', 'sem_retorno')),
  data_ultima_atualizacao date not null default current_date,
  observacao text,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references usuario (id) default auth.uid()
);
create index encaminhamento_pendente on encaminhamento (status, data_ultima_atualizacao);
```

---

## 3. Políticas RLS (`0006_rls.sql`)

Matriz de acesso (L = ler, E = escrever, — = sem acesso):

| Tabela | Admin | Técnico | Campo | Parceiro |
|---|---|---|---|---|
| `usuario` | L E | L (só a própria linha) | L (só a própria linha) | L (só a própria linha) |
| domínios (`programa`, `local`, …) | L E | L | L | — |
| `pessoa`, `pessoa_perfil` | L E | L E | L (código e atributos) | — |
| `gestacao` | L E | L E | — | — |
| `atividade` e filhas | L E | L E | L E | — |
| `pessoa_contato` | — direto; só via função auditada | — direto; só via função auditada | — | — |
| `encaminhamento` | — direto; só via função auditada | — direto; só via função auditada | — | — |
| `auditoria` | L | — | — | — |
| indicadores `fn_*` | sim | sim | — | — |
| indicadores `fn_ext_*` | sim | sim | — | sim |

```sql
-- Exclusão é sempre lógica: ninguém apaga linha.
revoke delete on all tables in schema public from authenticated;
alter default privileges in schema public revoke delete on tables from authenticated;

alter table usuario enable row level security;
create policy usuario_le_proprio on usuario for select to authenticated
  using (id = auth.uid() or app.e_admin());
create policy usuario_admin_escreve on usuario for insert to authenticated
  with check (app.e_admin());
create policy usuario_admin_altera on usuario for update to authenticated
  using (app.e_admin()) with check (app.e_admin());

-- Domínios: todos da equipe leem; só Admin mantém. (um bloco igual para cada tabela de domínio)
alter table programa enable row level security;
create policy programa_equipe_le on programa for select to authenticated
  using (app.e_equipe());
create policy programa_admin_cria on programa for insert to authenticated
  with check (app.e_admin());
create policy programa_admin_altera on programa for update to authenticated
  using (app.e_admin()) with check (app.e_admin());

alter table pessoa enable row level security;
create policy pessoa_equipe_le on pessoa for select to authenticated
  using (app.e_equipe() and ativo);
create policy pessoa_tecnico_altera on pessoa for update to authenticated
  using (app.pode_ver_identificado()) with check (app.pode_ver_identificado());
-- INSERT: nenhuma política. Pessoa nasce só por fn_pessoa_criar (garante consentimento).
revoke insert on pessoa from authenticated;

alter table pessoa_perfil enable row level security;
create policy pessoa_perfil_equipe_le on pessoa_perfil for select to authenticated
  using (app.e_equipe());
create policy pessoa_perfil_tecnico_escreve on pessoa_perfil for insert to authenticated
  with check (app.pode_ver_identificado());

alter table gestacao enable row level security;
create policy gestacao_tecnico_le on gestacao for select to authenticated
  using (app.pode_ver_identificado() and ativo);
create policy gestacao_tecnico_cria on gestacao for insert to authenticated
  with check (app.pode_ver_identificado());
create policy gestacao_tecnico_altera on gestacao for update to authenticated
  using (app.pode_ver_identificado()) with check (app.pode_ver_identificado());

alter table atividade enable row level security;
create policy atividade_equipe_le on atividade for select to authenticated
  using (app.e_equipe() and ativo);
create policy atividade_equipe_cria on atividade for insert to authenticated
  with check (app.e_equipe());
-- Campo corrige o que ele mesmo registrou; Técnico e Admin corrigem qualquer uma.
create policy atividade_corrige on atividade for update to authenticated
  using (app.pode_ver_identificado() or created_by = auth.uid())
  with check (app.pode_ver_identificado() or created_by = auth.uid());

-- Filhas da atividade: mesmo molde (um bloco por tabela).
alter table participacao enable row level security;
create policy participacao_equipe_le on participacao for select to authenticated
  using (app.e_equipe());
create policy participacao_equipe_cria on participacao for insert to authenticated
  with check (app.e_equipe()
    and exists (select 1 from atividade a where a.id = atividade_id and a.ativo));

-- RESTRITAS: RLS ligada, nenhuma permissão. Acesso exclusivamente pelas funções auditadas.
alter table pessoa_contato enable row level security;
revoke all on pessoa_contato from authenticated, anon;
create policy pessoa_contato_sem_acesso_direto on pessoa_contato for all to authenticated
  using (false) with check (false);

alter table encaminhamento enable row level security;
revoke all on encaminhamento from authenticated, anon;
create policy encaminhamento_sem_acesso_direto on encaminhamento for all to authenticated
  using (false) with check (false);

alter table auditoria enable row level security;
revoke all on auditoria from authenticated, anon;
grant select on auditoria to authenticated;      -- filtrado pela política abaixo
create policy auditoria_admin_le on auditoria for select to authenticated
  using (app.e_admin());
-- Ninguém insere direto: só app.audita (security definer).
```

---

## 4. Acesso auditado aos dados restritos (`0007_rpc_restrito.sql`)

Todas são `security definer`, começam checando o papel e gravam em `auditoria`.

```sql
create function fn_pessoa_criar(
  p_faixa_etaria_id uuid, p_genero_id uuid, p_bairro_id uuid,
  p_data_primeiro_contato date, p_perfis uuid[],
  p_consentimento_data date, p_consentimento_por text,
  p_nome text default null, p_apelido text default null,
  p_telefone text default null, p_nome_responsavel text default null
) returns pessoa
  language plpgsql security definer set search_path = public, pg_temp as $$
declare v_pessoa pessoa; v_menor boolean;
begin
  if not app.pode_ver_identificado() then
    raise exception 'Apenas Técnico ou Admin pode cadastrar pessoa';
  end if;
  select menor_de_idade into v_menor from faixa_etaria where id = p_faixa_etaria_id;
  if v_menor and (p_consentimento_por <> 'responsavel_legal' or p_nome_responsavel is null) then
    raise exception 'Menor de 18 exige consentimento do responsável legal (art. 14 LGPD)';
  end if;

  insert into pessoa (faixa_etaria_id, genero_id, bairro_id, data_primeiro_contato, created_by)
  values (p_faixa_etaria_id, p_genero_id, p_bairro_id,
          coalesce(p_data_primeiro_contato, current_date), auth.uid())
  returning * into v_pessoa;

  insert into pessoa_perfil (pessoa_id, perfil_id)
  select v_pessoa.id, unnest(p_perfis);

  insert into pessoa_contato (pessoa_id, nome, apelido, telefone, nome_responsavel,
                              consentimento_data, consentimento_por, created_by)
  values (v_pessoa.id, p_nome, p_apelido, p_telefone, p_nome_responsavel,
          p_consentimento_data, p_consentimento_por, auth.uid());

  perform app.audita('criacao', 'pessoa_contato', v_pessoa.id);
  return v_pessoa;
end $$;

create function fn_contato_ver(p_pessoa_id uuid)
  returns table (codigo text, nome text, apelido text, telefone text,
                 nome_responsavel text, consentimento_data date, consentimento_revogado_em timestamptz)
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if not app.pode_ver_identificado() then
    raise exception 'Sem permissão para ver dado identificado';
  end if;
  perform app.audita('leitura', 'pessoa_contato', p_pessoa_id);
  return query
    select p.codigo, c.nome, c.apelido, c.telefone, c.nome_responsavel,
           c.consentimento_data, c.consentimento_revogado_em
      from pessoa_contato c join pessoa p on p.id = c.pessoa_id
     where c.pessoa_id = p_pessoa_id;
end $$;

-- fn_contato_salvar(...)                 -> atualiza contato, audita 'alteracao'
-- fn_consentimento_revogar(p_pessoa_id)  -> apaga nome/apelido/telefone/responsável,
--                                           grava consentimento_revogado_em, mantém a pessoa
--                                           e todo o histórico estatístico; audita
-- fn_pessoa_buscar(p_termo)              -> busca por código (qualquer papel da equipe) ou por
--                                           nome (só Técnico/Admin, auditando a busca)
-- fn_encaminhamento_listar(p_status)     -> lista com código da pessoa; audita 'leitura'
-- fn_encaminhamento_criar(...)           -> audita 'criacao'
-- fn_encaminhamento_atualizar(p_id, p_status, p_observacao)
--                                        -> atualiza status e data_ultima_atualizacao; audita
```

O corpo completo das seis funções comentadas entra na etapa de implementação, no mesmo molde.

---

## 5. Camada analítica

### 5.1 Molde de cada indicador (três camadas)

```sql
-- 1. Regra, escrita uma única vez. Schema app => não exposto na API.
create function app.base_atividades_por_programa(p_de date, p_ate date)
  returns table (programa text, atividades bigint, horas numeric)
  language sql stable security definer set search_path = public, pg_temp
as $$
  select pr.nome,
         count(*),
         round(sum(extract(epoch from (a.hora_fim - a.hora_inicio)) / 3600.0), 1)
    from atividade a join programa pr on pr.id = a.programa_id
   where a.ativo and a.data between p_de and p_ate
   group by pr.nome order by 2 desc
$$;

-- 2. Visão interna: número cheio, só Técnico e Admin.
create function fn_atividades_por_programa(p_de date, p_ate date)
  returns table (programa text, atividades bigint, horas numeric)
  language plpgsql stable security definer set search_path = public, pg_temp
as $$ begin
  if not app.pode_ver_identificado() then raise exception 'Sem permissão'; end if;
  return query select * from app.base_atividades_por_programa(p_de, p_ate);
end $$;
comment on function fn_atividades_por_programa is
  'INDICADOR OFICIAL — Atividades por programa: número de atividades ativas com data no período '
  'e soma das horas (hora_fim - hora_inicio) dessas atividades, agrupadas por programa.';

-- 3. Visão externa: mesma regra, contagem < 5 suprimida.
create function fn_ext_atividades_por_programa(p_de date, p_ate date)
  returns table (programa text, atividades numeric, atividades_rotulo text, horas numeric)
  language plpgsql stable security definer set search_path = public, pg_temp
as $$ begin
  if not app.autenticado() then raise exception 'Sem permissão'; end if;
  return query
    select b.programa, app.sup(b.atividades), app.sup_rotulo(b.atividades),
           case when b.atividades < 5 then null else b.horas end
      from app.base_atividades_por_programa(p_de, p_ate) b;
end $$;
```

### 5.2 Os nove indicadores

| Objeto | Definição oficial (vai no `COMMENT`) | Colunas |
|---|---|---|
| `fn_pessoas_unicas_atendidas` | pessoas distintas com ≥1 participação em atividade ativa no período, por programa e perfil | programa, perfil, pessoas |
| `fn_contatos_anonimos` | soma de `contagem_anonima.abordagens` das atividades do período, por local e programa | local, programa, abordagens, criancas, adolescentes, adultos |
| `fn_atividades_por_programa` | nº de atividades e soma das horas realizadas no período, por programa | programa, atividades, horas |
| `fn_taxa_recorrencia` | pessoas com ≥3 participações no período ÷ pessoas com ≥1, por programa | programa, pessoas, pessoas_3mais, taxa_pct |
| `fn_encaminhamentos` | encaminhamentos com data no período, por destino e status; taxa de conclusão = concluídos ÷ total | destino, status, total, taxa_conclusao_pct |
| `fn_gestantes_acompanhamento` | pessoas com perfil gestante e DPP registrada, com participação antes da DPP, depois da DPP e nas duas janelas | gestantes, com_pre, com_pos, com_pre_e_pos |
| `fn_itens_distribuidos` | soma de `item_distribuido.quantidade` das atividades do período, por tipo de item | tipo_item, unidade, quantidade |
| `fn_horas_voluntariado` | soma de (quantidade da equipe × duração da atividade) para funções com `conta_voluntariado`, no período | programa, horas_voluntariado |
| `fn_novos_cadastros` | pessoas com `data_primeiro_contato` no período, por mês | mes, pessoas |

Cada um ganha o par `fn_ext_*` com supressão. Em `fn_ext_taxa_recorrencia` a linha inteira é
suprimida quando a base tem menos de 5 pessoas, porque taxa sobre base pequena identifica.
Nas versões externas o cruzamento é reduzido (programa e mês, sem perfil, bairro ou local)
para impedir isolamento de indivíduo por diferença entre recortes.

### 5.3 Pendências (`0010_pendencias.sql`)

`fn_pendencias()`, só Técnico e Admin, `union all` de quatro consultas, cada linha com
`tipo`, `descricao`, `registro_id`, `data_referencia`:

1. atividade ativa sem nenhuma `participacao` **e** sem `contagem_anonima`;
2. encaminhamento ativo com status ≠ concluído e `data_ultima_atualizacao < current_date - 60`;
3. pessoa ativa sem `pessoa_contato.consentimento_data` ou com consentimento revogado;
4. atividade ativa sem nenhuma linha em `atividade_equipe`.

### 5.4 Atualização em tempo real (seção 6.3)

Sem ETL e sem job: o dashboard lê as funções da seção 5.1, que consultam as tabelas base no
momento da chamada. O que muda no app:

- **Auto-refresh.** Cada bloco de gráficos fica em `@st.fragment(run_every=INTERVALO)`, com
  `INTERVALO = st.secrets.get("intervalo_atualizacao_seg", 60)`. Só o fragmento reconsulta; a
  página não recarrega e o filtro de período escolhido não se perde.
- **Cache coerente.** `st.cache_data` nos indicadores com `ttl = INTERVALO` (nunca maior) e
  chave incluindo papel, período e programa. `services/` chama `st.cache_data.clear()` no fim de
  todo fluxo de gravação (atividade, pessoa, encaminhamento, domínios), então quem acabou de
  registrar vê o número novo na hora.
- **Frescor visível.** Cada dashboard mostra `Atualizado às HH:MM` e o total de registros
  considerados no período (vem de uma coluna `registros` devolvida pelas próprias funções).
- **Período parcial x fechado.** O dashboard marca o mês corrente como **parcial**. O PDF para
  parceiro só aceita período fechado (mês já encerrado) e grava o snapshot abaixo, para que um
  número já enviado a financiador não mude depois que alguém corrigir um registro antigo.

`0011_relatorio_emitido.sql`:

```sql
create table relatorio_emitido (
  id uuid primary key default gen_random_uuid(),
  periodo_de  date not null,
  periodo_ate date not null,
  emitido_em  timestamptz not null default now(),
  indicadores jsonb not null,            -- valores congelados, como foram enviados
  created_by  uuid references usuario (id) default auth.uid(),
  constraint periodo_coerente check (periodo_ate > periodo_de)
);
comment on table relatorio_emitido is
  'Snapshot do que foi enviado ao financiador. Nunca é alterado nem apagado: é a prova do número.';

alter table relatorio_emitido enable row level security;
create policy relatorio_equipe_le on relatorio_emitido for select to authenticated
  using (app.autenticado());
-- Sem política de UPDATE: snapshot é imutável. INSERT só por fn_relatorio_emitir,
-- que recusa período não fechado (periodo_ate >= date_trunc('month', current_date)).
revoke insert, update on relatorio_emitido from authenticated;
```

**Desempenho.** Índices em `atividade (data, programa_id, local_id)`,
`participacao (pessoa_id)` e `encaminhamento (status, data_ultima_atualizacao)`, já no schema
acima. O seed gera **3 anos de atividades fictícias** (≈ 2.500 atividades, 20 mil participações,
900 pessoas) e `tests/test_desempenho.py` afirma que cada conjunto de indicadores de dashboard
responde em menos de 3 segundos.

### 5.5 Seed

- `seed/01_dominios.sql`: os 19 programas do prompt, tipos de atividade, destinos, tipos de
  item, perfis com `faixas_permitidas`, faixas etárias, gêneros, funções de equipe, locais da
  sede. É configuração, não dado pessoal.
- `seed/02_demo.sql`: **só dados fictícios** (nomes inventados), com valores conferidos nos
  testes de indicador.

---

## 6. Estrutura de pastas

```
projeto_paginas_novas/
├─ app.py                      # st.navigation/st.Page: monta o menu conforme o papel
├─ requirements.txt            # versões fixas
├─ Dockerfile
├─ .env.example
├─ .streamlit/config.toml      # tema e layout centralizado (mobile)
├─ pages/                      # SÓ interface; nenhuma consulta SQL aqui
│  ├─ login.py
│  ├─ inicio.py
│  ├─ registrar_atividade.py   # 6 etapas, cada uma em st.form
│  ├─ cadastrar_pessoa.py
│  ├─ encaminhamentos.py
│  ├─ pendencias.py
│  ├─ admin.py
│  ├─ exportar_csv.py
│  ├─ dashboard_interno.py     # fase 2
│  ├─ dashboard_externo.py     # fase 2
│  └─ relatorio_pdf.py         # fase 2
├─ services/                   # acesso ao Supabase; nenhum componente de tela
│  ├─ cliente.py               # client anon (login) e client com o token do usuário
│  ├─ auth.py                  # login, logout, expiração por inatividade, recuperar senha
│  ├─ permissoes.py            # exige_papel(...) chamado dentro de cada página
│  ├─ dominios.py              # listas (único lugar com cache, chaveado pelo papel)
│  ├─ pessoas.py               # fn_pessoa_criar, fn_contato_ver, fn_pessoa_buscar
│  ├─ atividades.py
│  ├─ encaminhamentos.py
│  └─ administracao.py         # usuários e tabelas de domínio
├─ analytics/                  # leitura dos indicadores e gráficos
│  ├─ indicadores.py           # chama fn_* / fn_ext_* -> DataFrame (nunca tabela bruta)
│  ├─ graficos.py              # Plotly + a frase explicativa de cada gráfico
│  └─ pdf.py                   # reportlab
├─ sql/
│  ├─ migrations/              # 0001_base.sql … 0011_relatorio_emitido.sql
│  └─ seed/
├─ scripts/                    # ÚNICO lugar onde service_role pode aparecer
│  ├─ aplicar_migrations.py
│  ├─ backup.py
│  └─ criar_primeiro_admin.py
├─ tests/
│  ├─ conftest.py              # faz login como admin/tecnico/campo/parceiro fictícios
│  ├─ test_rls_campo.py
│  ├─ test_restritas_auditam.py
│  ├─ test_supressao_ext.py
│  ├─ test_consentimento.py
│  ├─ test_qualidade_dados.py
│  ├─ test_indicadores_seed.py
│  └─ test_desempenho.py       # dashboards < 3 s com 3 anos de dados fictícios
├─ docs/PROPOSTA.md
├─ README_ONG.md
└─ README_TECNICO.md
```

Regras que a estrutura impõe (e os testes verificam por varredura de código):
`pages/` só importa de `services/` e `analytics/`; nenhum arquivo fora de `scripts/` menciona
`service_role`; `st.cache_data` só aparece em `services/dominios.py` e `analytics/indicadores.py`.

---

## 7. Mapa de páginas por papel

| Página | Admin | Técnico | Campo | Parceiro |
|---|:--:|:--:|:--:|:--:|
| Login / recuperar senha | ✓ | ✓ | ✓ | ✓ |
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

Na etapa de participantes, o papel Campo vê **apenas o código** (`PN-00001`) e a faixa etária;
nunca nome nem apelido. A checagem é feita duas vezes: ao montar o menu e na primeira linha de
cada página (`exige_papel(...)`), além da barreira do banco.

---

## 8. Testes de aceite

| Critério do prompt | Teste |
|---|---|
| Campo não lê `pessoa_contato`, `encaminhamento`, `auditoria` | `test_rls_campo.py` faz login como Campo pela API e espera erro em cada tabela e em `fn_contato_ver` |
| Nenhuma página usa `service_role` | varredura do repositório fora de `scripts/` |
| Nenhum dado identificado em cache | varredura de `st.cache_*` fora dos dois arquivos permitidos |
| `fn_ext_*` nunca devolve contagem < 5 | roda todas as funções externas no seed e afirma `valor is null or valor >= 5` |
| Pessoa sem consentimento / atividade sem programa, local, data | tentativas diretas na API esperando erro |
| Toda leitura identificada gera auditoria | conta linhas de `auditoria` antes e depois de `fn_contato_ver` |
| Indicadores batem com o seed | valores esperados escritos no teste |
| Dashboard carrega em < 3 s (6.3) | `test_desempenho.py` com 3 anos de dados fictícios |
| Nenhuma materialized view nem tabela de resumo (6.3) | consulta a `pg_matviews` esperando vazio |
| PDF só para período fechado, com snapshot | `fn_relatorio_emitir` recusa mês corrente e grava `relatorio_emitido` |
| Fluxo de atividade < 3 min no celular | roteiro cronometrado em `docs/TESTE_CAMPO.md` (manual; não dá para automatizar) |

---

## 9. Decisões que preciso que você confirme

1. **Indicadores como funções com período** em vez de views (decisão D4). É o único ponto em
   que me afasto da letra da seção 6.1. Se você preferir views literais, o app precisará
   recalcular pessoas únicas e taxa de recorrência em pandas, e eu considero isso um risco de
   manutenção. **Confirma as funções?**
2. **Tabela `gestacao` com a DPP.** Sem ela, `vw_gestantes_acompanhamento` não tem como
   existir. É dado de saúde, ficaria restrita a Técnico/Admin. **Aprova a inclusão?**
3. **`hora_fim` obrigatória.** As horas de atividade e de voluntariado dependem dela. No celular
   o formulário vai oferecer durações prontas (30 min, 1 h, 2 h…) para não custar tempo.
   **Pode ser obrigatória?**
4. **Criação de usuário.** A página Admin não pode usar `service_role`, então ela gerencia
   papel e ativação na tabela `usuario`, enquanto o convite por e-mail é feito pelo painel do
   Supabase (passo a passo no `README_ONG.md`). A alternativa é uma Edge Function em
   TypeScript, que quebra o "tudo em Python". **Fico com o painel do Supabase?**
5. **Supressão na visão externa:** suprimo o número (vira `<5`) mas mantenho a linha, e reduzo
   o cruzamento das `fn_ext_*` a programa e mês. **Concorda, ou prefere omitir a linha inteira?**
6. **Backup.** Requisito 8 pede backup diário. Supabase Pro (US$ 25/mês) já faz backup diário e
   restauração a ponto no tempo; no plano gratuito eu entrego `scripts/backup.py` com `pg_dump`
   agendado no host. **Qual caminho?**
7. **Hospedagem paga.** Sugiro Fly.io ou DigitalOcean App Platform (US$ 5–10/mês), container,
   sem hibernação, repositório privado. **Alguma preferência ou conta já existente?**
8. **Snapshot do PDF.** O `relatorio_emitido` é a única cópia de número no sistema, e é
   imutável de propósito. Consequência: se a ONG corrigir um registro antigo, o PDF novo vai
   divergir do antigo, e o histórico mostra os dois. **É esse o comportamento que você quer?**
9. **Período fechado para o PDF externo.** Vou bloquear a emissão quando o período incluir o mês
   corrente. **Confirma, ou a coordenação precisa de um PDF parcial (marcado como "parcial") para
   uso interno?**
10. **Perfil "criança" e consentimento.** Vou exigir responsável legal para as faixas 0–5, 6–11
   e 12–17 (`faixa_etaria.menor_de_idade`). **Confirma que 12–17 também exige responsável?**
