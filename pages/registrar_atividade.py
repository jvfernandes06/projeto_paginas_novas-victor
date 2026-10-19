"""Registrar atividade, em 6 etapas curtas.

Cada etapa é um `st.form`: o Streamlit roda a página inteira de novo a cada toque, e o
formulário garante que nada é perdido no caminho. O progresso fica em `st.session_state`,
e o banco só é gravado na confirmação final, de uma vez.

As escolhas da etapa anterior viram padrão da próxima vez (programa, local), porque em campo
a mesma equipe costuma registrar a mesma coisa várias vezes no dia.
"""

from datetime import date, time

import streamlit as st

import ui
from services import atividades, auth, dominios, pessoas
from services.seguranca import ErroDeValidacao, PermissaoNegada

sessao = auth.exigir_papel("admin", "tecnico", "campo")
ui.definir_layout("centered")

TOTAL_ETAPAS = 6
CHAVE = "nova_atividade"
ULTIMA_ESCOLHA = "ultima_escolha"


def rascunho() -> dict:
    if CHAVE not in st.session_state:
        st.session_state[CHAVE] = {"etapa": 1, "participantes": [], "itens": {}, "equipe": {}}
    return st.session_state[CHAVE]


def ir_para(etapa: int) -> None:
    rascunho()["etapa"] = etapa
    st.rerun()


def lembrar(campo: str, valor) -> None:
    st.session_state.setdefault(ULTIMA_ESCOLHA, {})[campo] = valor


def lembrado(campo: str):
    return st.session_state.get(ULTIMA_ESCOLHA, {}).get(campo)


def indice_lembrado(campo: str, nomes: list[str]) -> int:
    anterior = lembrado(campo)
    return nomes.index(anterior) if anterior in nomes else 0


dados = rascunho()
etapa = dados["etapa"]

programas = dominios.opcoes("programa")
locais = dominios.opcoes("local")
tipos = dominios.opcoes("tipo_atividade")
funcoes = dominios.listar("funcao_equipe")
itens_disponiveis = dominios.listar("tipo_item")

ui.titulo("Registrar atividade")

# --- Etapa 1: programa ---------------------------------------------------------------------
if etapa == 1:
    ui.passos(1, TOTAL_ETAPAS, "Programa")
    with st.form("etapa_programa"):
        nome = st.selectbox(
            "Qual programa?", list(programas), index=indice_lembrado("programa", list(programas))
        )
        if st.form_submit_button("Continuar", use_container_width=True, type="primary"):
            dados["programa"] = nome
            dados["programa_id"] = programas[nome]
            lembrar("programa", nome)
            ir_para(2)

# --- Etapa 2: local ------------------------------------------------------------------------
elif etapa == 2:
    ui.passos(2, TOTAL_ETAPAS, "Local")
    with st.form("etapa_local"):
        nome = st.selectbox(
            "Onde foi?", list(locais), index=indice_lembrado("local", list(locais))
        )
        coluna_voltar, coluna_seguir = st.columns(2)
        voltar = coluna_voltar.form_submit_button("Voltar", use_container_width=True)
        seguir = coluna_seguir.form_submit_button(
            "Continuar", use_container_width=True, type="primary"
        )
    if voltar:
        ir_para(1)
    if seguir:
        dados["local"] = nome
        dados["local_id"] = locais[nome]
        lembrar("local", nome)
        ir_para(3)

# --- Etapa 3: data, horário e tipo ---------------------------------------------------------
elif etapa == 3:
    ui.passos(3, TOTAL_ETAPAS, "Data e horário")
    with st.form("etapa_quando"):
        dia = st.date_input("Quando foi?", value=date.today(), format="DD/MM/YYYY")
        coluna_inicio, coluna_fim = st.columns(2)
        hora_inicio = coluna_inicio.time_input("Começou às", value=time(14, 0), step=1800)
        hora_fim = coluna_fim.time_input("Terminou às", value=time(16, 0), step=1800)
        tipo = st.selectbox(
            "Tipo de atividade", list(tipos), index=indice_lembrado("tipo", list(tipos))
        )
        descricao = st.text_input("Descrição curta (opcional)", max_chars=200)
        coluna_voltar, coluna_seguir = st.columns(2)
        voltar = coluna_voltar.form_submit_button("Voltar", use_container_width=True)
        seguir = coluna_seguir.form_submit_button(
            "Continuar", use_container_width=True, type="primary"
        )
    if voltar:
        ir_para(2)
    if seguir:
        if dia > date.today():
            ui.erro("A data não pode ser no futuro.")
        elif atividades.duracao_em_minutos(hora_inicio, hora_fim) <= 0:
            ui.erro("O horário de término precisa ser depois do horário de início.")
        else:
            dados.update(
                data=dia,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                tipo=tipo,
                tipo_atividade_id=tipos[tipo],
                descricao_curta=descricao or None,
            )
            lembrar("tipo", tipo)
            ir_para(4)

# --- Etapa 4: equipe -----------------------------------------------------------------------
elif etapa == 4:
    ui.passos(4, TOTAL_ETAPAS, "Equipe")
    st.caption("Quantas pessoas da equipe participaram, por função.")
    with st.form("etapa_equipe"):
        quantidades = {}
        for funcao in funcoes:
            quantidades[funcao["id"]] = st.number_input(
                funcao["nome"],
                min_value=0,
                max_value=50,
                step=1,
                value=int(dados["equipe"].get(funcao["id"], 0)),
            )
        coluna_voltar, coluna_seguir = st.columns(2)
        voltar = coluna_voltar.form_submit_button("Voltar", use_container_width=True)
        seguir = coluna_seguir.form_submit_button(
            "Continuar", use_container_width=True, type="primary"
        )
    if voltar:
        ir_para(3)
    if seguir:
        dados["equipe"] = {k: v for k, v in quantidades.items() if v}
        ir_para(5)

# --- Etapa 5: quem foi atendido e o que foi entregue ---------------------------------------
elif etapa == 5:
    ui.passos(5, TOTAL_ETAPAS, "Quem foi atendido")
    modo = st.radio(
        "Como registrar as pessoas?",
        ["Por código da pessoa", "Contagem anônima (rua e boate)"],
        horizontal=False,
        index=1 if dados.get("modo") == "anonimo" else 0,
    )
    dados["modo"] = "anonimo" if modo.startswith("Contagem") else "codigo"

    if dados["modo"] == "codigo":
        with st.form("buscar_pessoa", clear_on_submit=True):
            codigo = st.text_input("Código da pessoa", placeholder="PN-00001")
            if st.form_submit_button("Adicionar", use_container_width=True):
                encontrada = pessoas.buscar_por_codigo(sessao, codigo)
                if encontrada is None:
                    ui.erro("Não encontrei esse código. Confira o número.")
                elif any(p["id"] == encontrada["id"] for p in dados["participantes"]):
                    ui.erro("Essa pessoa já está na lista.")
                else:
                    dados["participantes"].append(encontrada)
                    ui.sucesso(f"{encontrada['codigo']} adicionada")

        if dados["participantes"]:
            st.markdown(f"**{len(dados['participantes'])} pessoa(s) na atividade**")
            for pessoa in list(dados["participantes"]):
                coluna_texto, coluna_botao = st.columns([4, 1])
                coluna_texto.markdown(
                    f"<div class='pn-item'><b>{pessoa['codigo']}</b> · "
                    f"{pessoa['faixa_etaria']}</div>",
                    unsafe_allow_html=True,
                )
                if coluna_botao.button("Tirar", key=f"tirar_{pessoa['id']}"):
                    dados["participantes"].remove(pessoa)
                    st.rerun()
        else:
            st.caption("Nenhuma pessoa adicionada ainda.")
    else:
        with st.form("contagem"):
            st.caption("Abordagem de rua e boate não precisa identificar ninguém.")
            contagem = dados.get("contagem", {})
            abordagens = st.number_input(
                "Abordagens", min_value=0, step=1, value=int(contagem.get("abordagens", 0))
            )
            coluna_a, coluna_b, coluna_c = st.columns(3)
            criancas = coluna_a.number_input(
                "Crianças", min_value=0, step=1, value=int(contagem.get("criancas", 0))
            )
            adolescentes = coluna_b.number_input(
                "Adolesc.", min_value=0, step=1, value=int(contagem.get("adolescentes", 0))
            )
            adultos = coluna_c.number_input(
                "Adultos", min_value=0, step=1, value=int(contagem.get("adultos", 0))
            )
            if st.form_submit_button("Guardar contagem", use_container_width=True):
                dados["contagem"] = {
                    "abordagens": abordagens,
                    "criancas": criancas,
                    "adolescentes": adolescentes,
                    "adultos": adultos,
                }
                ui.sucesso("Contagem guardada")

    with st.expander("Itens distribuídos (opcional)"):
        with st.form("itens"):
            quantidades = {}
            for item in itens_disponiveis:
                quantidades[item["id"]] = st.number_input(
                    f"{item['nome']} ({item['unidade']})",
                    min_value=0,
                    step=1,
                    value=int(dados["itens"].get(item["id"], 0)),
                )
            if st.form_submit_button("Guardar itens", use_container_width=True):
                dados["itens"] = {k: v for k, v in quantidades.items() if v}
                ui.sucesso("Itens guardados")

    coluna_voltar, coluna_seguir = st.columns(2)
    if coluna_voltar.button("Voltar", use_container_width=True):
        ir_para(4)
    if coluna_seguir.button("Continuar", use_container_width=True, type="primary"):
        ir_para(6)

# --- Etapa 6: resumo e confirmação ---------------------------------------------------------
else:
    ui.passos(6, TOTAL_ETAPAS, "Confirmar")
    contagem = dados.get("contagem", {})
    total_anonimo = sum(contagem.values()) if contagem else 0

    st.markdown(
        f"<div class='pn-item'>"
        f"<b>{dados.get('programa', '—')}</b><br>"
        f"{dados['data'].strftime('%d/%m/%Y')} · "
        f"{dados['hora_inicio'].strftime('%H:%M')} às {dados['hora_fim'].strftime('%H:%M')}<br>"
        f"{dados.get('local', '—')} · {dados.get('tipo', '—')}<br>"
        f"Equipe: {sum(dados['equipe'].values()) or 'não informada'}<br>"
        f"Pessoas: {len(dados['participantes']) or total_anonimo or 'nenhuma'}<br>"
        f"Itens: {sum(dados['itens'].values()) or 'nenhum'}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not dados["participantes"] and not total_anonimo:
        st.warning(
            "Esta atividade vai ficar sem participantes e sem contagem. Ela aparecerá na tela "
            "de Pendências até alguém completar."
        )

    observacao = st.text_area("Observação (opcional)", help="Não entra nos gráficos.")

    coluna_voltar, coluna_salvar = st.columns(2)
    if coluna_voltar.button("Voltar", use_container_width=True):
        ir_para(5)

    if coluna_salvar.button("Confirmar e salvar", use_container_width=True, type="primary"):
        try:
            atividades.criar(
                sessao,
                data=dados["data"],
                hora_inicio=dados["hora_inicio"],
                hora_fim=dados["hora_fim"],
                programa_id=dados["programa_id"],
                local_id=dados["local_id"],
                tipo_atividade_id=dados["tipo_atividade_id"],
                equipe=dados["equipe"],
                participantes=[p["id"] for p in dados["participantes"]],
                contagem=dados.get("contagem"),
                itens=dados["itens"],
                descricao_curta=dados.get("descricao_curta"),
                observacao=observacao or None,
            )
        except (ErroDeValidacao, PermissaoNegada) as erro:
            ui.erro(str(erro))
        else:
            st.session_state.pop(CHAVE)
            st.session_state["atividade_salva"] = True
            st.rerun()

if st.session_state.pop("atividade_salva", False):
    ui.sucesso("Atividade registrada!")
    st.success("Atividade registrada. Obrigada!")
    if st.button("Registrar outra", use_container_width=True, type="primary"):
        st.rerun()
