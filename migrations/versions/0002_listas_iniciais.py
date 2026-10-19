"""Listas iniciais: programas, locais, perfis, faixas etárias e demais domínios.

É configuração, não dado pessoal. Depois disto, quem mantém as listas é o Admin, pela página
Admin, sem precisar de programador.

Revision ID: 0002
"""

from alembic import op

from services import modelo

revision = "0002"
down_revision = "0001"


def _linhas(valores: list[dict]) -> list[dict]:
    return [{"id": modelo.novo_id(), **v} for v in valores]


PROGRAMAS = [
    {"nome": "Kidstinga", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Projeto Nota 10", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Ballet/Dança", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Hip Hop", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Basquete", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Bendito o Fruto do Teu Ventre", "publico_alvo": "gestantes"},
    {"nome": "Café com Fé", "publico_alvo": "comunidade"},
    {"nome": "Fábrica dos Sonhos", "publico_alvo": "mulheres e pessoas trans"},
    {"nome": "Oficina de Moda/Crochê", "publico_alvo": "mulheres e pessoas trans"},
    {"nome": "Bazar Solidário", "publico_alvo": "famílias"},
    {"nome": "Carreta da Saúde", "publico_alvo": "comunidade"},
    {"nome": "Saúde da Mulher", "publico_alvo": "mulheres"},
    {"nome": "Saúde Trans", "publico_alvo": "pessoas trans"},
    {"nome": "Equilibrium", "publico_alvo": "saúde mental"},
    {
        "nome": "Abordagem de Rua",
        "publico_alvo": "mulheres e pessoas trans em situação de prostituição",
    },
    {"nome": "Passeio Cultural", "publico_alvo": "crianças, adolescentes e famílias"},
    {"nome": "Jantar de Natal", "publico_alvo": "comunidade"},
    {"nome": "Apadrinhamento de Natal", "publico_alvo": "crianças e adolescentes"},
    {"nome": "Curso Panorama da Prostituição", "publico_alvo": "público externo e voluntários"},
]

# Locais genéricos. Os nomes reais de boates e pontos de abordagem só a ONG pode informar, e é
# preciso decidir antes se essa informação deve entrar no sistema (DECISOES_PENDENTES, 12).
LOCAIS = [
    {"nome": "Sede Páginas Novas", "tipo": "sede"},
    {"nome": "Rua — Jardim Itatinga", "tipo": "rua"},
    {"nome": "Boate — a informar", "tipo": "boate"},
    {"nome": "Local externo — a informar", "tipo": "externo"},
]

TIPOS_ATIVIDADE = [
    "Oficina",
    "Aula",
    "Abordagem",
    "Passeio",
    "Evento",
    "Atendimento individual",
    "Roda de conversa",
]

DESTINOS = [
    "CRAS",
    "CREAS",
    "UBS",
    "CAPS / saúde mental",
    "Maternidade",
    "Conselho Tutelar",
    "Defensoria Pública",
    "Outro",
]

# Lista mínima: a real vem da coordenação (DECISOES_PENDENTES, 11).
BAIRROS = ["Jardim Itatinga", "Outro"]

GENEROS = [
    "Mulher cisgênero",
    "Homem cisgênero",
    "Mulher trans",
    "Homem trans",
    "Travesti",
    "Não binário",
    "Prefere não informar",
]

ITENS = [
    {"nome": "Preservativo", "unidade": "unidade"},
    {"nome": "Refeição", "unidade": "refeição"},
    {"nome": "Kit de higiene", "unidade": "kit"},
    {"nome": "Cesta básica", "unidade": "cesta"},
    {"nome": "Brinquedo", "unidade": "unidade"},
    {"nome": "Roupa", "unidade": "peça"},
    {"nome": "Fralda", "unidade": "pacote"},
    {"nome": "Absorvente", "unidade": "pacote"},
    {"nome": "Material escolar", "unidade": "kit"},
]

FAIXAS = [
    {"codigo": "0-5", "rotulo": "0 a 5 anos", "ordem": 1, "menor_de_idade": True, "pode_gestar": False},
    {"codigo": "6-11", "rotulo": "6 a 11 anos", "ordem": 2, "menor_de_idade": True, "pode_gestar": False},
    {"codigo": "12-17", "rotulo": "12 a 17 anos", "ordem": 3, "menor_de_idade": True, "pode_gestar": True},
    {"codigo": "18-29", "rotulo": "18 a 29 anos", "ordem": 4, "menor_de_idade": False, "pode_gestar": True},
    {"codigo": "30-44", "rotulo": "30 a 44 anos", "ordem": 5, "menor_de_idade": False, "pode_gestar": True},
    {"codigo": "45-59", "rotulo": "45 a 59 anos", "ordem": 6, "menor_de_idade": False, "pode_gestar": True},
    {"codigo": "60+", "rotulo": "60 anos ou mais", "ordem": 7, "menor_de_idade": False, "pode_gestar": False},
]

# faixas_permitidas: códigos entre vírgulas; vazio = qualquer faixa.
# A coordenação precisa conferir estas combinações (DECISOES_PENDENTES, 13).
PERFIS = [
    {"nome": "Criança", "faixas_permitidas": ",0-5,6-11,"},
    {"nome": "Adolescente", "faixas_permitidas": ",12-17,"},
    {"nome": "TEA", "faixas_permitidas": None},
    {"nome": "Responsável familiar", "faixas_permitidas": ",18-29,30-44,45-59,60+,"},
    {
        "nome": "Mulher em situação de prostituição",
        "faixas_permitidas": ",12-17,18-29,30-44,45-59,60+,",
    },
    {"nome": "Pessoa trans", "faixas_permitidas": None},
    {"nome": "Idoso", "faixas_permitidas": ",60+,"},
]

# Só "Voluntário" conta no indicador de horas de voluntariado. Se estagiária ou professor
# também contarem, o Admin marca na tela (DECISOES_PENDENTES, 14).
FUNCOES = [
    {"nome": "Assistente social", "conta_voluntariado": False},
    {"nome": "Estagiária", "conta_voluntariado": False},
    {"nome": "Professor", "conta_voluntariado": False},
    {"nome": "Voluntário", "conta_voluntariado": True},
    {"nome": "Nutrição", "conta_voluntariado": False},
    {"nome": "Coordenação", "conta_voluntariado": False},
]


def upgrade() -> None:
    op.bulk_insert(modelo.programa, _linhas(PROGRAMAS))
    op.bulk_insert(modelo.local, _linhas(LOCAIS))
    op.bulk_insert(modelo.tipo_atividade, _linhas([{"nome": n} for n in TIPOS_ATIVIDADE]))
    op.bulk_insert(modelo.destino_encaminhamento, _linhas([{"nome": n} for n in DESTINOS]))
    op.bulk_insert(modelo.bairro, _linhas([{"nome": n} for n in BAIRROS]))
    op.bulk_insert(modelo.genero, _linhas([{"nome": n} for n in GENEROS]))
    op.bulk_insert(modelo.tipo_item, _linhas(ITENS))
    op.bulk_insert(modelo.faixa_etaria, _linhas(FAIXAS))
    op.bulk_insert(modelo.perfil, _linhas(PERFIS))
    op.bulk_insert(modelo.funcao_equipe, _linhas(FUNCOES))
    op.bulk_insert(modelo.contador, [{"nome": "pessoa_codigo", "valor": 0}])


def downgrade() -> None:
    for tabela in (
        modelo.funcao_equipe,
        modelo.perfil,
        modelo.faixa_etaria,
        modelo.tipo_item,
        modelo.genero,
        modelo.bairro,
        modelo.destino_encaminhamento,
        modelo.tipo_atividade,
        modelo.local,
        modelo.programa,
        modelo.contador,
    ):
        op.execute(tabela.delete())
