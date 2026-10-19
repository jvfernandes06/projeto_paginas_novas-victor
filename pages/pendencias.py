"""Pendências: o que está incompleto, com o caminho para corrigir."""

import streamlit as st

import ui
from analytics import pendencias
from services import auth, restrito

sessao = auth.exigir_papel("admin", "tecnico")
ui.definir_layout("centered")

ui.titulo("Pendências", "O que o sistema encontrou incompleto.")

sem_pessoas = pendencias.atividades_sem_pessoas(sessao)
sem_equipe = pendencias.atividades_sem_equipe(sessao)
parados = restrito.encaminhamentos_parados(sessao)
sem_consentimento = restrito.pessoas_sem_consentimento(sessao)
gestantes = pendencias.gestantes_para_revisar(sessao)

total = len(sem_pessoas) + len(sem_equipe) + len(parados) + len(sem_consentimento) + len(gestantes)
if total == 0:
    st.success("Nada pendente. Tudo em ordem!")
    st.stop()

st.caption(f"{total} pendência(s).")


def bloco(titulo: str, explicacao: str, itens: list, desenhar, pagina: str, rotulo_acao: str):
    if not itens:
        return
    with st.expander(f"{titulo} ({len(itens)})", expanded=len(itens) <= 5):
        st.caption(explicacao)
        for item in itens[:50]:
            st.markdown(f"<div class='pn-item'>{desenhar(item)}</div>", unsafe_allow_html=True)
        if len(itens) > 50:
            st.caption(f"e mais {len(itens) - 50}.")
        if st.button(rotulo_acao, key=f"ir_{titulo}", use_container_width=True):
            st.switch_page(pagina)


bloco(
    "Atividades sem pessoas",
    "Ninguém foi registrado nestas atividades, nem por código nem por contagem anônima.",
    sem_pessoas,
    lambda i: f"<b>{i['programa']}</b> — {i['data'].strftime('%d/%m/%Y')} · {i['local']}",
    "pages/registrar_atividade.py",
    "Registrar atividade",
)

bloco(
    "Atividades sem equipe informada",
    "Sem a equipe, as horas de voluntariado destas atividades não entram no relatório.",
    sem_equipe,
    lambda i: f"<b>{i['programa']}</b> — {i['data'].strftime('%d/%m/%Y')} · {i['local']}",
    "pages/registrar_atividade.py",
    "Registrar atividade",
)

bloco(
    "Encaminhamentos parados há mais de 60 dias",
    "Sem atualização há mais de dois meses. Vale ligar para o serviço e registrar o retorno.",
    parados,
    lambda i: (
        f"<b>{i['pessoa_codigo']}</b> → {i['destino']} · "
        f"desde {i['data_ultima_atualizacao'].strftime('%d/%m/%Y')}"
    ),
    "pages/encaminhamentos.py",
    "Abrir encaminhamentos",
)

bloco(
    "Pessoas sem consentimento válido",
    "Cadastro sem data de consentimento, ou com consentimento revogado.",
    sem_consentimento,
    lambda i: f"<b>{i['codigo']}</b>",
    "pages/cadastrar_pessoa.py",
    "Abrir cadastro de pessoa",
)

bloco(
    "Gestantes para revisar",
    "Marcadas como gestantes há mais de dez meses. Confirme se a marcação ainda vale.",
    gestantes,
    lambda i: f"<b>{i['codigo']}</b>",
    "pages/cadastrar_pessoa.py",
    "Abrir cadastro de pessoa",
)
