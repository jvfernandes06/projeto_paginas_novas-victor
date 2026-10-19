"""As três regras de arquitetura que protegem o dado, verificadas por varredura do código.

Sem RLS no banco, a segurança depende de o código continuar organizado assim. Teste que lê
código parece estranho, mas é o que impede a erosão: alguém com pressa escreve um SELECT dentro
da tela, e em seis meses ninguém sabe mais por onde o dado sai.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ARQUIVOS_DE_PAGINA = sorted((RAIZ / "pages").glob("*.py"))
ARQUIVOS_PYTHON = [
    caminho
    for pasta in ("pages", "services", "analytics", "scripts", "tests")
    for caminho in sorted((RAIZ / pasta).glob("*.py"))
] + [RAIZ / "app.py", RAIZ / "ui.py"]

TABELAS_RESTRITAS = ("pessoa_contato", "encaminhamento", "auditoria")

# Quem pode falar de tabela restrita: o único módulo de acesso, o schema, as migrations,
# a tela de pendências e os testes.
PODEM_CITAR_RESTRITAS = {
    "restrito.py",
    "modelo.py",
    "limpar_demo.py",
    "seed_demo.py",
    "test_invariantes_codigo.py",
    "test_permissoes.py",
    "test_auditoria.py",
}

PODEM_USAR_CACHE = {
    "dominios.py",
    "indicadores.py",
    "cache.py",
    "test_cache.py",
    "test_invariantes_codigo.py",
}


def test_pagina_nao_abre_banco_nem_escreve_sql():
    """Invariante 1: página fala com services/ e analytics/, nunca com o banco."""
    proibido = re.compile(r"\b(sqlalchemy|sqlite3|select\s+\w+\s+from|insert\s+into|db\.conexao)\b", re.I)
    for arquivo in ARQUIVOS_DE_PAGINA:
        encontrado = proibido.search(arquivo.read_text(encoding="utf-8"))
        assert not encontrado, f"{arquivo.name} fala direto com o banco: {encontrado.group(0)!r}"


def test_tabelas_restritas_so_aparecem_no_modulo_de_acesso():
    """Invariante 3: quem quiser dado restrito passa por services/restrito.py, que audita."""
    for arquivo in ARQUIVOS_PYTHON:
        if arquivo.name in PODEM_CITAR_RESTRITAS:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for tabela in TABELAS_RESTRITAS:
            # "encaminhamento" aparece em texto de tela e em nome de função; o que não pode é
            # consulta à tabela.
            consulta = re.search(rf"(from|join|into|update)\s+{tabela}\b", texto, re.I)
            assert not consulta, f"{arquivo.name} consulta {tabela} fora de services/restrito.py"


def test_cache_so_onde_e_permitido():
    """Cache é para lista de domínio e número agregado. Dado identificado nunca entra."""
    for arquivo in ARQUIVOS_PYTHON:
        if arquivo.name in PODEM_USAR_CACHE:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        assert "st.cache_data" not in texto, f"{arquivo.name} usa cache fora do lugar permitido"
        assert "st.cache_resource" not in texto, f"{arquivo.name} usa cache fora do lugar permitido"


def test_toda_pagina_verifica_o_papel():
    """Invariante 2 na camada de tela: esconder do menu não é proteção."""
    for arquivo in ARQUIVOS_DE_PAGINA:
        texto = arquivo.read_text(encoding="utf-8")
        assert "auth.exigir_papel(" in texto, f"{arquivo.name} não verifica o papel"


def test_nenhum_arquivo_do_app_usa_delete():
    """Exclusão é sempre lógica. Só o script de limpeza da demonstração apaga de verdade."""
    for arquivo in ARQUIVOS_PYTHON:
        if arquivo.name in ("limpar_demo.py", "test_invariantes_codigo.py", "modelo.py"):
            continue
        texto = arquivo.read_text(encoding="utf-8")
        assert not re.search(r"\bdelete\s*\(", texto), f"{arquivo.name} apaga registro"
        assert not re.search(r"\bdelete\s+from\b", texto, re.I), f"{arquivo.name} apaga registro"
