"""O app visto de fora: menu por papel e página que não abre pela URL.

Usa o AppTest do próprio Streamlit, que executa o app de verdade sem abrir navegador.
"""

from datetime import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from services.seguranca import Sessao

RAIZ_APP = "app.py"

def _app(sessao: Sessao | None) -> AppTest:
    teste = AppTest.from_file(RAIZ_APP, default_timeout=30)
    if sessao is not None:
        teste.session_state["sessao"] = sessao
        teste.session_state["deve_trocar_senha"] = False
        teste.session_state["ultima_interacao"] = datetime.now()
    return teste.run()


def test_sem_login_aparece_a_tela_de_entrada(banco):
    app = _app(None)
    assert not app.exception
    assert any("Páginas Novas" in texto.value for texto in app.markdown)
    assert app.text_input  # campos de e-mail e senha


def test_login_errado_nao_entra(banco, admin):
    app = _app(None)
    app.text_input[0].set_value("admin@teste").run()
    app.text_input[1].set_value("senha errada").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("incorret" in erro.value.lower() for erro in app.error)
    assert "sessao" not in app.session_state


def test_menu_de_cada_papel(banco):
    """O menu é uma tabela de dados: confere direto, sem subir o app."""
    import navegacao

    assert set(navegacao.paginas_do_papel("campo")) == {
        "inicio.py",
        "registrar_atividade.py",
        "cadastrar_pessoa.py",
    }
    assert navegacao.paginas_do_papel("parceiro") == ["dash_parceiro.py"]

    tecnico = navegacao.paginas_do_papel("tecnico")
    assert "dash_visao_geral.py" in tecnico and "pendencias.py" in tecnico
    assert "admin.py" not in tecnico

    admin = navegacao.paginas_do_papel("admin")
    assert "admin.py" in admin
    assert set(tecnico) <= set(admin)


def test_todo_arquivo_do_menu_existe(banco):
    import navegacao

    for papel in ("admin", "tecnico", "campo", "parceiro"):
        for arquivo in navegacao.paginas_do_papel(papel):
            assert (Path("pages") / arquivo).exists(), f"{arquivo} está no menu e não existe"


def test_campo_nao_tem_pagina_de_dado_restrito(banco):
    import navegacao

    proibidas = {"encaminhamentos.py", "pendencias.py", "admin.py"}
    assert not proibidas & set(navegacao.paginas_do_papel("campo"))


def test_app_sobe_para_cada_papel(admin, tecnico, campo, parceiro):
    for sessao in (admin, tecnico, campo, parceiro):
        app = _app(sessao)
        assert not app.exception, f"o app quebrou para o papel {sessao.papel}"


@pytest.mark.parametrize(
    "pagina, papel_proibido",
    [
        ("pages/admin.py", "tecnico"),
        ("pages/admin.py", "campo"),
        ("pages/encaminhamentos.py", "campo"),
        ("pages/pendencias.py", "campo"),
        ("pages/dash_visao_geral.py", "campo"),
        ("pages/dash_visao_geral.py", "parceiro"),
        ("pages/dash_encaminhamentos.py", "parceiro"),
        ("pages/cadastrar_pessoa.py", "parceiro"),
    ],
)
def test_pagina_proibida_nao_abre_nem_pela_url(pagina, papel_proibido, banco, request):
    """Quem digita o endereço da página na mão também é barrado."""
    sessao = request.getfixturevalue(papel_proibido)
    app = AppTest.from_file(pagina, default_timeout=30)
    app.session_state["sessao"] = sessao
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception
    assert any("não permite" in erro.value for erro in app.error)


def test_sessao_expirada_derruba_o_acesso(campo):
    from datetime import timedelta

    app = AppTest.from_file(RAIZ_APP, default_timeout=30)
    app.session_state["sessao"] = campo
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now() - timedelta(hours=2)
    app.run()

    assert "sessao" not in app.session_state
    assert any("inatividade" in info.value for info in app.info)


def test_troca_de_senha_obrigatoria_bloqueia_o_resto(campo):
    app = AppTest.from_file(RAIZ_APP, default_timeout=30)
    app.session_state["sessao"] = campo
    app.session_state["deve_trocar_senha"] = True
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert any("Crie a sua senha" in texto.value for texto in app.markdown)
    assert not app.get("navigation")


PAGINAS_DE_DASHBOARD = [
    "dash_visao_geral.py",
    "dash_programas.py",
    "dash_publico.py",
    "dash_territorio.py",
    "dash_encaminhamentos.py",
    "dash_equipe.py",
    "dash_parceiro.py",
]


@pytest.mark.parametrize("arquivo", PAGINAS_DE_DASHBOARD)
def test_dashboard_abre_com_dados(arquivo, tecnico, nova_pessoa, nova_atividade):
    """Cada dashboard precisa desenhar sem erro, com dado de verdade no banco."""
    from datetime import date

    pessoas = [nova_pessoa(tecnico) for _ in range(6)]
    nova_atividade(tecnico, dia=date.today(), participantes=[p["id"] for p in pessoas])

    app = AppTest.from_file(f"pages/{arquivo}", default_timeout=60)
    app.session_state["sessao"] = tecnico
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"{arquivo} quebrou: {app.exception}"


@pytest.mark.parametrize("arquivo", PAGINAS_DE_DASHBOARD)
def test_dashboard_abre_vazio(arquivo, tecnico):
    """E precisa desenhar sem erro também quando ainda não há nada registrado."""
    app = AppTest.from_file(f"pages/{arquivo}", default_timeout=60)
    app.session_state["sessao"] = tecnico
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"{arquivo} quebrou com banco vazio: {app.exception}"


@pytest.mark.parametrize("arquivo", ["inicio.py", "registrar_atividade.py", "cadastrar_pessoa.py"])
def test_telas_de_registro_abrem_para_campo(arquivo, campo):
    app = AppTest.from_file(f"pages/{arquivo}", default_timeout=60)
    app.session_state["sessao"] = campo
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"{arquivo} quebrou para o papel Campo: {app.exception}"


# As telas abaixo formatam datas. Abrir com a tabela vazia não prova nada: o que quebra é
# formatar o que veio do banco. Por isso cada uma é aberta **com** registro dentro.


def test_pendencias_abre_com_pendencias_de_verdade(tecnico, nova_pessoa, nova_atividade):
    from datetime import date

    from services import dominios, restrito

    nova_atividade(tecnico, dia=date(2026, 3, 10))  # sem participantes e sem equipe
    pessoa = nova_pessoa(tecnico)
    restrito.criar_encaminhamento(
        tecnico, pessoa["id"], dominios.opcoes("destino_encaminhamento")["CRAS"]
    )
    restrito.revogar_consentimento(tecnico, pessoa["id"])  # vira pendência de consentimento

    app = AppTest.from_file("pages/pendencias.py", default_timeout=60)
    app.session_state["sessao"] = tecnico
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"a tela de pendências quebrou: {app.exception}"
    assert any("pendência" in legenda.value for legenda in app.caption)


def test_encaminhamentos_abre_com_registro(tecnico, nova_pessoa):
    from services import dominios, restrito

    pessoa = nova_pessoa(tecnico)
    restrito.criar_encaminhamento(
        tecnico, pessoa["id"], dominios.opcoes("destino_encaminhamento")["UBS"]
    )

    app = AppTest.from_file("pages/encaminhamentos.py", default_timeout=60)
    app.session_state["sessao"] = tecnico
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"a tela de encaminhamentos quebrou: {app.exception}"
    assert any(pessoa["codigo"] in bloco.value for bloco in app.markdown)


def test_admin_abre_com_usuarios_e_auditoria(admin, nova_pessoa):
    nova_pessoa(admin)  # gera linha de auditoria

    app = AppTest.from_file("pages/admin.py", default_timeout=60)
    app.session_state["sessao"] = admin
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    app.run()

    assert not app.exception, f"a tela de administração quebrou: {app.exception}"
    assert any("admin@teste" in bloco.value for bloco in app.markdown)
