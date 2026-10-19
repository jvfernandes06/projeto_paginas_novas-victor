"""O fluxo de 6 etapas, dirigido de fora como se fosse o dedo de alguém no celular.

Prova as duas coisas que importam no uso em campo: que o progresso não se perde entre as
etapas (o Streamlit reexecuta o script a cada toque) e que a atividade chega ao banco com
participantes, equipe e itens.
"""

from datetime import date, datetime, time

from streamlit.testing.v1 import AppTest

from analytics import indicadores
from services import atividades, dominios

PAGINA = "pages/registrar_atividade.py"


def _abrir(sessao, rascunho: dict | None = None) -> AppTest:
    app = AppTest.from_file(PAGINA, default_timeout=60)
    app.session_state["sessao"] = sessao
    app.session_state["deve_trocar_senha"] = False
    app.session_state["ultima_interacao"] = datetime.now()
    if rascunho is not None:
        app.session_state["nova_atividade"] = rascunho
    return app.run()


def _etapa(app) -> int:
    return app.session_state["nova_atividade"]["etapa"]


def _botao(app, rotulo: str):
    """Acha o botão pelo texto. Por índice daria errado: a tela muda de botões a cada etapa."""
    return next(botao for botao in app.button if botao.label == rotulo)


def test_primeira_etapa_pergunta_o_programa(campo):
    app = _abrir(campo)
    assert not app.exception
    assert _etapa(app) == 1
    assert app.selectbox[0].label == "Qual programa?"


def test_escolher_programa_avanca_e_guarda(campo):
    app = _abrir(campo)
    app.selectbox[0].set_value("Hip Hop")
    _botao(app, "Continuar").click().run()

    assert not app.exception
    assert app.session_state["nova_atividade"]["programa"] == "Hip Hop"
    assert _etapa(app) == 2
    assert app.selectbox[0].label == "Onde foi?"  # já está na tela do local


def test_programa_escolhido_vira_padrao_da_proxima_vez(campo):
    app = _abrir(campo)
    app.selectbox[0].set_value("Basquete")
    _botao(app, "Continuar").click().run()
    escolha_anterior = app.session_state["ultima_escolha"]

    # Um registro novo, com a memória do anterior: o programa vem pronto.
    seguinte = AppTest.from_file(PAGINA, default_timeout=60)
    seguinte.session_state["sessao"] = campo
    seguinte.session_state["deve_trocar_senha"] = False
    seguinte.session_state["ultima_interacao"] = datetime.now()
    seguinte.session_state["ultima_escolha"] = escolha_anterior
    seguinte.run()

    assert seguinte.selectbox[0].value == "Basquete"


def test_horario_invertido_avisa_em_portugues(campo):
    rascunho = {
        "etapa": 3,
        "participantes": [],
        "itens": {},
        "equipe": {},
        "programa": "Kidstinga",
        "programa_id": dominios.opcoes("programa")["Kidstinga"],
        "local": "Sede Páginas Novas",
        "local_id": dominios.opcoes("local")["Sede Páginas Novas"],
    }
    app = _abrir(campo, rascunho)
    app.time_input[0].set_value(time(16, 0))
    app.time_input[1].set_value(time(14, 0))
    _botao(app, "Continuar").click().run()

    assert not app.exception
    assert any("término" in erro.value for erro in app.error)
    assert _etapa(app) == 3  # não avança com erro


def test_busca_por_codigo_inexistente_avisa(campo, _rascunho_na_etapa_5):
    app = _abrir(campo, _rascunho_na_etapa_5)
    app.text_input[0].set_value("PN-99999")
    _botao(app, "Adicionar").click().run()

    assert any("Não encontrei" in erro.value for erro in app.error)
    assert app.session_state["nova_atividade"]["participantes"] == []


def test_adicionar_tres_participantes_pelo_codigo(campo, tecnico, nova_pessoa,
                                                  _rascunho_na_etapa_5):
    """Etapa 5: três buscas por código, três pessoas na lista, nada perdido entre os toques."""
    pessoas = [nova_pessoa(tecnico) for _ in range(3)]

    app = _abrir(campo, _rascunho_na_etapa_5)
    for pessoa in pessoas:
        app.text_input[0].set_value(pessoa["codigo"])
        _botao(app, "Adicionar").click().run()

    guardados = app.session_state["nova_atividade"]["participantes"]
    assert [p["codigo"] for p in guardados] == [p["codigo"] for p in pessoas]

    _botao(app, "Continuar").click().run()
    assert _etapa(app) == 6


def test_confirmar_salva_com_participantes_equipe_e_itens(campo, tecnico, nova_pessoa,
                                                          _rascunho_na_etapa_5):
    """Etapa 6: o que estava na tela chega inteiro ao banco, numa transação só."""
    pessoas = [nova_pessoa(tecnico) for _ in range(3)]
    preservativo = dominios.opcoes("tipo_item")["Preservativo"]
    rascunho = dict(
        _rascunho_na_etapa_5,
        etapa=6,
        participantes=[{"id": p["id"], "codigo": p["codigo"], "faixa_etaria": "30 a 44 anos"}
                       for p in pessoas],
        itens={preservativo: 20},
    )

    app = _abrir(campo, rascunho)
    app.text_area[0].set_value("Oficina tranquila.")
    _botao(app, "Confirmar e salvar").click().run()

    assert not app.exception
    assert any("registrada" in sucesso.value for sucesso in app.success)
    # Depois de salvar, o rascunho volta ao início, pronto para o próximo registro.
    assert _etapa(app) == 1
    assert app.session_state["nova_atividade"]["participantes"] == []

    registradas = atividades.minhas_ultimas(campo)
    assert len(registradas) == 1
    assert registradas[0]["programa"] == "Kidstinga"
    assert registradas[0]["participantes"] == 3
    assert registradas[0]["equipe"] == 2

    itens = indicadores.itens_por_tipo(tecnico, date(2026, 3, 1), date(2026, 3, 31))
    assert itens.set_index("tipo_item").loc["Preservativo", "quantidade"] == 20


def test_resumo_avisa_atividade_sem_ninguem(campo, _rascunho_na_etapa_5):
    rascunho = dict(_rascunho_na_etapa_5, etapa=6)
    app = _abrir(campo, rascunho)

    assert any("Pendências" in aviso.value for aviso in app.warning)


def test_contagem_anonima_chega_ao_banco(campo, _rascunho_na_etapa_5):
    rascunho = dict(
        _rascunho_na_etapa_5,
        etapa=6,
        contagem={"abordagens": 18, "criancas": 0, "adolescentes": 2, "adultos": 16},
    )
    app = _abrir(campo, rascunho)
    app.text_area[0].set_value("")
    _botao(app, "Confirmar e salvar").click().run()

    assert not app.exception
    registradas = atividades.minhas_ultimas(campo)
    assert registradas[0]["contagem_anonima"] == 36  # 18 + 0 + 2 + 16


def test_duplicata_avisa_sem_quebrar(campo, _rascunho_na_etapa_5, nova_atividade):
    """Alguém já registrou a mesma atividade: a tela explica, em vez de dar erro técnico."""
    nova_atividade(campo, dia=_rascunho_na_etapa_5["data"])

    rascunho = dict(_rascunho_na_etapa_5, etapa=6)
    app = _abrir(campo, rascunho)
    app.text_area[0].set_value("")
    _botao(app, "Confirmar e salvar").click().run()

    assert not app.exception
    assert any("Já existe uma atividade" in erro.value for erro in app.error)
