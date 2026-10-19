"""Quais páginas cada papel vê no menu.

Está separado do app.py de propósito: é uma tabela de dados, que o teste confere direto, sem
precisar subir o app. A proteção de verdade está dentro de cada página (`auth.exigir_papel`),
porque esconder do menu não protege quem digita o endereço na mão.
"""

INICIO = ("inicio.py", "Início", ":material/home:")
REGISTRAR = ("registrar_atividade.py", "Registrar atividade", ":material/edit_calendar:")
PESSOA = ("cadastrar_pessoa.py", "Cadastrar pessoa", ":material/person_add:")
ENCAMINHAMENTOS = ("encaminhamentos.py", "Encaminhamentos", ":material/share:")
PENDENCIAS = ("pendencias.py", "Pendências", ":material/warning:")
ADMIN = ("admin.py", "Admin", ":material/settings:")

VISAO_GERAL = ("dash_visao_geral.py", "Visão geral", ":material/dashboard:")
PROGRAMAS = ("dash_programas.py", "Programas", ":material/category:")
PUBLICO = ("dash_publico.py", "Público atendido", ":material/groups:")
TERRITORIO = ("dash_territorio.py", "Território e rua", ":material/location_on:")
DASH_ENCAMINHAMENTOS = ("dash_encaminhamentos.py", "Encaminhamentos", ":material/route:")
EQUIPE = ("dash_equipe.py", "Equipe e voluntariado", ":material/volunteer_activism:")
PARCEIRO = ("dash_parceiro.py", "Relatório para parceiros", ":material/handshake:")

REGISTRO = [INICIO, REGISTRAR, PESSOA, ENCAMINHAMENTOS, PENDENCIAS]
DASHBOARDS = [
    VISAO_GERAL,
    PROGRAMAS,
    PUBLICO,
    TERRITORIO,
    DASH_ENCAMINHAMENTOS,
    EQUIPE,
    PARCEIRO,
]

MENUS = {
    "admin": {"Registro": REGISTRO, "Dashboards": DASHBOARDS, "Administração": [ADMIN]},
    "tecnico": {"Registro": REGISTRO, "Dashboards": DASHBOARDS},
    "campo": {"Registro": [INICIO, REGISTRAR, PESSOA]},
    "parceiro": {"Impacto": [PARCEIRO]},
}


def menu(papel: str) -> dict[str, list[tuple[str, str, str]]]:
    return MENUS.get(papel, {})


def paginas_do_papel(papel: str) -> list[str]:
    """Só os nomes de arquivo, para conferência rápida."""
    return [arquivo for grupo in menu(papel).values() for arquivo, _, _ in grupo]
