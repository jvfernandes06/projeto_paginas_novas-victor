"""Schema do banco, em SQLAlchemy Core.

É a única definição das tabelas: as migrations do Alembic constroem o banco a partir daqui.
Está em SQLAlchemy Core, e não em SQL cru, por causa do dia da migração para o Postgres: o
mesmo arquivo serve aos dois bancos.

Convenções:
  - chave primária text com uuid gerado pela aplicação (portável entre bancos);
  - exclusão é sempre lógica (ativo = 0); nenhuma tela executa delete;
  - created_at/updated_at em UTC, mantidos pelo próprio SQLAlchemy;
  - nenhum campo analítico é texto livre: tudo vem das tabelas de domínio.

As validações que dependem de consulta (perfil compatível com a faixa etária, consentimento de
menor, data no futuro) ficam em services/, com mensagem em português para a tela. No banco ficam
as declarativas e portáveis: not null, check e índice único.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Time,
    func,
    text,
)

metadata = MetaData()

PAPEIS = ("admin", "tecnico", "campo", "parceiro")
TIPOS_LOCAL = ("sede", "boate", "rua", "externo")
STATUS_ENCAMINHAMENTO = ("enviado", "em_andamento", "concluido", "sem_retorno")
ACOES_AUDITORIA = ("leitura", "criacao", "alteracao", "desativacao", "revogacao_consentimento")
CONSENTIMENTO_POR = ("propria_pessoa", "responsavel_legal")

TABELAS_RESTRITAS = ("pessoa_contato", "encaminhamento", "auditoria")


def novo_id() -> str:
    return uuid.uuid4().hex


def _comuns():
    """Colunas que toda tabela tem."""
    return [
        Column("created_at", DateTime, nullable=False, server_default=func.now()),
        Column(
            "updated_at",
            DateTime,
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
        Column("created_by", String, ForeignKey("usuario.id")),
    ]


def _dominio(nome: str, *colunas_extra) -> Table:
    """Molde das listas editáveis pelo Admin."""
    return Table(
        nome,
        metadata,
        Column("id", String, primary_key=True, default=novo_id),
        Column("nome", String, nullable=False, unique=True),
        *colunas_extra,
        Column("ativo", Boolean, nullable=False, server_default=text("1")),
        *_comuns(),
    )


usuario = Table(
    "usuario",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("email", String, nullable=False, unique=True),
    Column("nome_exibicao", String, nullable=False),
    Column("senha_hash", String, nullable=False),
    Column("papel", String, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    Column("deve_trocar_senha", Boolean, nullable=False, server_default=text("1")),
    Column("ultimo_login", DateTime),
    *_comuns(),
    CheckConstraint("papel in ('admin', 'tecnico', 'campo', 'parceiro')", name="papel_valido"),
)

# Trilha de acesso a dado identificado (art. 37 da LGPD).
# Só o Admin lê. Nada aqui é alterado nem apagado.
auditoria = Table(
    "auditoria",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("usuario_id", String, ForeignKey("usuario.id")),
    Column("acao", String, nullable=False),
    Column("tabela", String, nullable=False),
    Column("registro_id", String),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    CheckConstraint(
        "acao in ('leitura', 'criacao', 'alteracao', 'desativacao', 'revogacao_consentimento')",
        name="acao_valida",
    ),
)

Index("auditoria_busca", auditoria.c.created_at.desc(), auditoria.c.tabela)

# Gera o código PN-00001. Fica em tabela para o número não depender de max(codigo),
# que teria corrida entre dois cadastros simultâneos.
contador = Table(
    "contador",
    metadata,
    Column("nome", String, primary_key=True),
    Column("valor", Integer, nullable=False, server_default=text("0")),
)

programa = _dominio("programa", Column("descricao", Text), Column("publico_alvo", String))

local = _dominio(
    "local",
    Column("tipo", String, nullable=False),
    Column("latitude", Float),  # aproximada, opcional
    Column("longitude", Float),
)
local.append_constraint(
    CheckConstraint("tipo in ('sede', 'boate', 'rua', 'externo')", name="tipo_local_valido")
)

tipo_atividade = _dominio("tipo_atividade")
destino_encaminhamento = _dominio("destino_encaminhamento")
bairro = _dominio("bairro")
genero = _dominio("genero")
tipo_item = _dominio(
    "tipo_item", Column("unidade", String, nullable=False, server_default="unidade")
)

# menor_de_idade: exige consentimento do responsável legal (art. 14 da LGPD).
# pode_gestar: recusa marcar como gestante quem está em faixa incompatível.
faixa_etaria = Table(
    "faixa_etaria",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("codigo", String, nullable=False, unique=True),
    Column("rotulo", String, nullable=False),
    Column("ordem", Integer, nullable=False),
    Column("menor_de_idade", Boolean, nullable=False),
    Column("pode_gestar", Boolean, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
)

# faixas_permitidas: códigos de faixa_etaria entre vírgulas, por exemplo ",0-5,6-11,".
# Vazio significa qualquer faixa. Quem edita é o Admin, sem mexer em código.
# Gestante não está nesta lista: é a checkbox pessoa.gestante, para o número de
# gestantes não vir de dois lugares diferentes.
perfil = _dominio("perfil", Column("faixas_permitidas", String))

# conta_voluntariado: o indicador de horas de voluntariado soma só estas funções.
funcao_equipe = _dominio(
    "funcao_equipe",
    Column("conta_voluntariado", Boolean, nullable=False, server_default=text("0")),
)

# Pseudonimizada: nenhum dado identificável. Nome e telefone só em pessoa_contato.
pessoa = Table(
    "pessoa",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("codigo", String, nullable=False, unique=True),
    Column("faixa_etaria_id", String, ForeignKey("faixa_etaria.id"), nullable=False),
    Column("genero_id", String, ForeignKey("genero.id"), nullable=False),
    Column("bairro_id", String, ForeignKey("bairro.id")),
    Column("gestante", Boolean, nullable=False, server_default=text("0")),
    Column("data_primeiro_contato", Date, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
)

pessoa_perfil = Table(
    "pessoa_perfil",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("pessoa_id", String, ForeignKey("pessoa.id"), nullable=False),
    Column("perfil_id", String, ForeignKey("perfil.id"), nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
)

Index(
    "pessoa_perfil_unico",
    pessoa_perfil.c.pessoa_id,
    pessoa_perfil.c.perfil_id,
    unique=True,
    sqlite_where=text("ativo = 1"),
    postgresql_where=text("ativo"),
)

# RESTRITA. Dado identificável, art. 11 da LGPD.
# Acesso só por services/restrito.py, que registra toda leitura em auditoria.
pessoa_contato = Table(
    "pessoa_contato",
    metadata,
    Column("pessoa_id", String, ForeignKey("pessoa.id"), primary_key=True),
    Column("nome", String),
    Column("apelido", String),
    Column("telefone", String),
    Column("nome_responsavel", String),
    Column("consentimento_data", Date, nullable=False),
    Column("consentimento_por", String, nullable=False),
    Column("consentimento_revogado_em", DateTime),
    *_comuns(),
    CheckConstraint(
        "consentimento_por in ('propria_pessoa', 'responsavel_legal')",
        name="consentimento_por_valido",
    ),
    # Enquanto o consentimento vale, menor de idade precisa de responsável nomeado. Depois da
    # revogação a regra se inverte: o nome tem de poder ser apagado, senão a revogação não
    # revoga nada.
    CheckConstraint(
        "consentimento_revogado_em is not null"
        " or consentimento_por <> 'responsavel_legal'"
        " or nome_responsavel is not null",
        name="responsavel_obrigatorio",
    ),
)

# duracao_minutos é gravada pelo serviço a partir dos horários. Guardar pronto evita
# aritmética de hora em SQL, que muda de um banco para o outro.
atividade = Table(
    "atividade",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("data", Date, nullable=False),
    Column("hora_inicio", Time, nullable=False),
    Column("hora_fim", Time, nullable=False),
    Column("duracao_minutos", Integer, nullable=False),
    Column("programa_id", String, ForeignKey("programa.id"), nullable=False),
    Column("local_id", String, ForeignKey("local.id"), nullable=False),
    Column("tipo_atividade_id", String, ForeignKey("tipo_atividade.id"), nullable=False),
    Column("descricao_curta", String),
    Column("observacao", Text),  # único texto livre do sistema; não entra em análise
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
    CheckConstraint("duracao_minutos > 0", name="duracao_positiva"),
    CheckConstraint(
        "descricao_curta is null or length(descricao_curta) <= 200",
        name="descricao_curta_limite",
    ),
)

# Bloqueio de duplicata: mesma data + programa + local + horário de início.
Index(
    "atividade_sem_duplicata",
    atividade.c.data,
    atividade.c.programa_id,
    atividade.c.local_id,
    atividade.c.hora_inicio,
    unique=True,
    sqlite_where=text("ativo = 1"),
    postgresql_where=text("ativo"),
)
Index("atividade_periodo", atividade.c.data, atividade.c.programa_id, atividade.c.local_id)

atividade_equipe = Table(
    "atividade_equipe",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("atividade_id", String, ForeignKey("atividade.id"), nullable=False),
    Column("funcao_equipe_id", String, ForeignKey("funcao_equipe.id"), nullable=False),
    Column("quantidade", Integer, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
    CheckConstraint("quantidade > 0", name="quantidade_equipe_positiva"),
)

Index(
    "atividade_equipe_unico",
    atividade_equipe.c.atividade_id,
    atividade_equipe.c.funcao_equipe_id,
    unique=True,
    sqlite_where=text("ativo = 1"),
    postgresql_where=text("ativo"),
)

participacao = Table(
    "participacao",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("atividade_id", String, ForeignKey("atividade.id"), nullable=False),
    Column("pessoa_id", String, ForeignKey("pessoa.id"), nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
)

Index(
    "participacao_unica",
    participacao.c.atividade_id,
    participacao.c.pessoa_id,
    unique=True,
    sqlite_where=text("ativo = 1"),
    postgresql_where=text("ativo"),
)
Index("participacao_por_pessoa", participacao.c.pessoa_id)

# Abordagem de rua e boate não identifica ninguém: só contagem por atividade.
contagem_anonima = Table(
    "contagem_anonima",
    metadata,
    Column("atividade_id", String, ForeignKey("atividade.id"), primary_key=True),
    Column("abordagens", Integer, nullable=False, server_default=text("0")),
    Column("criancas", Integer, nullable=False, server_default=text("0")),
    Column("adolescentes", Integer, nullable=False, server_default=text("0")),
    Column("adultos", Integer, nullable=False, server_default=text("0")),
    *_comuns(),
    CheckConstraint(
        "abordagens >= 0 and criancas >= 0 and adolescentes >= 0 and adultos >= 0",
        name="contagem_nao_negativa",
    ),
    CheckConstraint("abordagens + criancas + adolescentes + adultos > 0", name="alguma_contagem"),
)

item_distribuido = Table(
    "item_distribuido",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("atividade_id", String, ForeignKey("atividade.id"), nullable=False),
    Column("tipo_item_id", String, ForeignKey("tipo_item.id"), nullable=False),
    Column("quantidade", Integer, nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
    CheckConstraint("quantidade > 0", name="quantidade_item_positiva"),
)

Index(
    "item_distribuido_unico",
    item_distribuido.c.atividade_id,
    item_distribuido.c.tipo_item_id,
    unique=True,
    sqlite_where=text("ativo = 1"),
    postgresql_where=text("ativo"),
)

# RESTRITA. Revela contexto de saúde, violência e vulnerabilidade.
# Acesso só por services/restrito.py, que audita a leitura.
encaminhamento = Table(
    "encaminhamento",
    metadata,
    Column("id", String, primary_key=True, default=novo_id),
    Column("pessoa_id", String, ForeignKey("pessoa.id"), nullable=False),
    Column("destino_id", String, ForeignKey("destino_encaminhamento.id"), nullable=False),
    Column("data", Date, nullable=False),
    Column("status", String, nullable=False, server_default="enviado"),
    Column("data_ultima_atualizacao", Date, nullable=False),
    Column("observacao", Text),
    Column("ativo", Boolean, nullable=False, server_default=text("1")),
    *_comuns(),
    CheckConstraint(
        "status in ('enviado', 'em_andamento', 'concluido', 'sem_retorno')", name="status_valido"
    ),
)

Index(
    "encaminhamento_pendente",
    encaminhamento.c.status,
    encaminhamento.c.data_ultima_atualizacao,
)
