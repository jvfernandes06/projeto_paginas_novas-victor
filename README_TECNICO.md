# README técnico

Para quem for mexer no código. A operação do dia a dia está no `README_ONG.md`.

## Como rodar

Com Docker, do jeito que roda em produção:

```bash
docker compose up
```

Para desenvolver:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

alembic upgrade head            # cria o banco e as listas iniciais
python scripts/seed_demo.py     # 300 pessoas e 18 meses de dados fictícios
streamlit run app.py

python -m pytest tests -q       # 154 testes
```

Variáveis de ambiente em `.env.example`. A única que importa de verdade é `PN_BANCO`, o caminho
do arquivo SQLite.

Usuários de demonstração, criados pelo seed: `admin@demo`, `tecnico@demo`, `campo@demo` e
`parceiro@demo`, todos com senha `demo1234` (e sem troca obrigatória, só na demonstração).

## Arquitetura

```
app.py            entrada, login, troca de senha e montagem do menu
navegacao.py      tabela de quais páginas cada papel vê
ui.py             peças de tela compartilhadas (layout, cartões, filtro de período)
pages/            uma tela por arquivo; SÓ interface
services/         acesso ao banco e regras de negócio
analytics/        indicadores, pendências e gráficos
migrations/       Alembic
scripts/          seed, limpeza, backup, criação do primeiro admin
tests/            a suíte
```

Dependência em uma direção só: `pages/` → (`services/`, `analytics/`, `ui`) → `services/db` →
banco. Página nunca abre conexão nem escreve SQL, e isso é verificado por teste.

### Por que SQLite agora

Decisão de projeto: começar sem servidor de banco, sem conta paga e sem segredo de
infraestrutura, com o código já portável (SQLAlchemy Core + Alembic) para a migração ao
Supabase/Postgres depois. O desenho de destino, com as políticas RLS, está em
`docs/DESTINO_SUPABASE.md`.

Consequências que valem saber:

- **Um processo só.** Duas instâncias escrevendo no mesmo arquivo corrompem o banco. O
  `docker-compose.yml` sobe um container e não pode ser escalado horizontalmente.
- **Sem RLS.** No Postgres, o próprio banco recusaria a consulta errada. Aqui a última barreira
  é o Python — daí as três invariantes abaixo.
- **O arquivo `.db` tem dado sensível em texto claro.** Em produção ele precisa estar em volume
  cifrado, e o backup também.

### Segurança: as três invariantes

Cada uma tem teste em `tests/test_invariantes_codigo.py`, que falha se alguém quebrar a regra:

1. **Nenhuma página abre o banco.** Só `services/db.py` cria conexão.
2. **Toda função de serviço recebe a sessão e checa o papel na primeira linha** (`exige_equipe`,
   `exige_identificado`, `exige_admin`). A tela checa também, mas a tela não é barreira.
3. **`pessoa_contato`, `encaminhamento` e `auditoria` só são consultadas em
   `services/restrito.py`**, onde toda leitura individual grava uma linha em `auditoria`, na
   mesma transação.

Exceção consciente da invariante 3: os **agregados** de encaminhamento (contagem por destino e
status) não geram auditoria. Auditar a cada atualização automática de dashboard encheria a
trilha de ruído e esconderia o que importa, que é a leitura de dado identificado.

Quem tem papel Campo grava consentimento (é obrigatório para cadastrar), mas não envia nem lê
nome, apelido e telefone — `services/pessoas.criar` recusa esses campos para ele.

### Indicadores

`analytics/indicadores.py`. Cada indicador é uma função com `(sessao, inicio, fim,
programa_id=None)`, e o SQL fica numa constante ao lado, com a definição oficial em comentário.

São funções com período, e não views, porque pessoa única e taxa de recorrência **não são
somáveis**: pessoas únicas de janeiro mais as de fevereiro não dá as do bimestre, porque quem
foi nos dois meses contaria duas vezes. `tests/test_indicadores.py` prova isso num cenário com
números escritos à mão.

As funções `ext_*` são a visão do parceiro: `suprimir()` troca qualquer contagem menor que 5 por
vazio, com a etiqueta `<5`. A regra é escrita uma vez e usada pelas duas visões, para o número
externo nunca divergir do interno.

Cache: `@st.cache_data(ttl=INTERVALO)` com `INTERVALO` de 60 segundos, e a chave inclui o papel
de quem pergunta. Toda gravação chama `services/cache.limpar()`, então quem registrou algo vê o
número novo na hora. Cache só existe em `services/dominios.py` e `analytics/indicadores.py`;
dado identificado nunca entra, e há teste de varredura para isso.

Atualização automática: cada bloco de dashboard é um `@st.fragment(run_every=INTERVALO)`. Só o
fragmento reconsulta, então o filtro de período escolhido não se perde.

### Gráficos

`analytics/graficos.py`. Três formas e nada mais: barra, linha e barra empilhada por situação.
Decisões que valem manter:

- **uma cor só** (o laranja da marca) em gráfico de magnitude, porque ali a cor não informa
  nada — e assim o mesmo programa nunca aparece de cores diferentes em páginas diferentes;
- **cor com significado só no empilhado de status**, na ordem sem retorno → enviado → em
  andamento → concluído, escolhida para vermelho e verde nunca ficarem lado a lado (é o par que
  some para quem tem daltonismo), com o número escrito dentro de cada faixa;
- **nunca dois eixos verticais**: atividades e horas são dois gráficos, não um com dois eixos;
- uma frase em português embaixo de cada gráfico.

A paleta foi validada para contraste e para os três tipos de daltonismo.

## Migrations

Em `migrations/versions/`, aplicadas por `alembic upgrade head`.

- `0001` cria o schema **a partir de `services/modelo.py`** (`metadata.create_all`), para não
  existirem duas descrições das mesmas tabelas podendo divergir.
- `0002` insere as listas iniciais (os 19 programas, perfis, faixas etárias e companhia).
- Da `0003` em diante, migrations incrementais normais (`op.add_column`, `op.create_table`).
  **Não edite uma migration já aplicada**: crie a seguinte. `render_as_batch` está ligado no
  `env.py` porque o SQLite não altera coluna — o Alembic recria a tabela.

Convenções do schema:

- chave primária `text` com uuid gerado pela aplicação (portável entre bancos);
- exclusão sempre lógica (`ativo = 0`); nenhuma tela executa `delete`;
- `created_at`/`updated_at` em UTC, mantidos pelo SQLAlchemy;
- validação declarativa no banco (`not null`, `check`, índice único parcial); validação que
  precisa de consulta fica em `services/`, com mensagem em português para a tela;
- `atividade.duracao_minutos` é gravada pelo serviço. Guardar a duração pronta evita aritmética
  de hora em SQL, que muda de um banco para o outro;
- o código `PN-00001` vem da tabela `contador`, incrementada na mesma transação do cadastro.

## Testes

```bash
python -m pytest tests -q
```

| Arquivo | O que prova |
|---|---|
| `test_permissoes.py` | Campo e Parceiro não alcançam nenhuma função de dado restrito |
| `test_invariantes_codigo.py` | as três invariantes, por varredura do código |
| `test_auditoria.py` | toda leitura identificada gera registro; revogação apaga o nome e mantém a estatística |
| `test_qualidade_dados.py` | consentimento obrigatório, duplicata, horário, perfil incompatível |
| `test_indicadores.py` | números conferidos num cenário documentado, e a não aditividade |
| `test_supressao_parceiro.py` | nenhuma função `ext_*` devolve contagem menor que 5 |
| `test_cache.py` | gravar e ler em seguida dá o número novo |
| `test_app_papeis.py` | menu por papel, página que não abre pela URL, e os 7 dashboards desenhando com e sem dados |
| `test_desempenho.py` | cada dashboard abaixo de 3 s com o seed de 18 meses |
| `test_backup.py` | o backup restaura |
| `test_correcao.py` | corrigir e desativar atividade e pessoa, com auditoria |
| `test_fluxo_registrar_atividade.py` | o fluxo de 6 etapas dirigido de fora, até gravar no banco |

Os testes do app usam `streamlit.testing.v1.AppTest`, que executa as páginas de verdade sem
navegador.

## Estado da implementação

| Etapa | Situação |
|---|---|
| Schema, migrations e seed | pronta |
| Autenticação, papéis e troca de senha | pronta |
| Registrar atividade (6 etapas) | pronta |
| Cadastrar pessoa e consentimento | pronta |
| Encaminhamentos | pronta |
| Pendências | pronta |
| Admin (usuários, listas, auditoria) | pronta |
| Dashboards internos e do parceiro | pronta |
| Editar e desativar atividade e pessoa | pronta (na tela de Início e no fim do cadastro de pessoa) |
| Exportação CSV | só na tela do parceiro, com os números agregados |
| Relatório PDF e snapshot `relatorio_emitido` | fora desta etapa |
| Migração para Supabase | fora desta etapa; desenho em `docs/DESTINO_SUPABASE.md` |

O que ficou pendente de decisão, com o que cada item trava, está em
`docs/DECISOES_PENDENTES.md`.
