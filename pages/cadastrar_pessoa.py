"""Cadastrar pessoa.

Atributos analíticos para todos; nome, apelido e telefone só para Técnico e Admin. O
consentimento é obrigatório para qualquer cadastro, e menor de 18 anos exige o responsável
legal (art. 14 da LGPD).

Ao salvar, o código (PN-00001) aparece em destaque: é por ele que a pessoa será encontrada
depois, e quem está em campo precisa anotar.
"""

from datetime import date

import streamlit as st

import ui
from services import auth, dominios, pessoas, restrito
from services.seguranca import ErroDeValidacao, PermissaoNegada

sessao = auth.exigir_papel("admin", "tecnico", "campo")
ui.definir_layout("centered")

ve_contato = sessao.papel in ("admin", "tecnico")

codigo_novo = st.session_state.pop("pessoa_cadastrada", None)
if codigo_novo:
    ui.titulo("Pessoa cadastrada")
    st.markdown(f"<div class='pn-codigo'>{codigo_novo}</div>", unsafe_allow_html=True)
    st.success("Anote este código: é por ele que você encontra a pessoa nas próximas atividades.")
    if st.button("Cadastrar outra pessoa", use_container_width=True, type="primary"):
        st.rerun()
    st.stop()

ui.titulo("Cadastrar pessoa", "Leva menos de dois minutos.")

faixas = dominios.listar("faixa_etaria")
generos = dominios.opcoes("genero")
bairros = dominios.opcoes("bairro")
perfis = dominios.listar("perfil")

with st.form("cadastrar_pessoa"):
    rotulo_faixa = st.selectbox("Faixa etária", [f["rotulo"] for f in faixas])
    faixa = next(f for f in faixas if f["rotulo"] == rotulo_faixa)

    nome_genero = st.selectbox("Gênero", list(generos))
    nome_bairro = st.selectbox("Bairro", ["Não informado"] + list(bairros))

    nomes_perfis = st.multiselect(
        "Perfis",
        [p["nome"] for p in perfis],
        help="Pode marcar mais de um. O sistema recusa perfil que não combina com a idade.",
    )
    gestante = st.checkbox("Gestante")

    primeiro_contato = st.date_input(
        "Primeiro contato com a ONG", value=date.today(), format="DD/MM/YYYY"
    )

    st.divider()
    st.markdown("**Consentimento** — obrigatório")
    consentimento_data = st.date_input(
        "Data do consentimento", value=date.today(), format="DD/MM/YYYY"
    )
    if faixa["menor_de_idade"]:
        st.info("Menor de 18 anos: quem consente é o responsável legal.")
        consentimento_por = "responsavel_legal"
    else:
        consentimento_por = st.radio(
            "Quem consentiu?",
            ["propria_pessoa", "responsavel_legal"],
            format_func=lambda v: "A própria pessoa" if v == "propria_pessoa" else "Responsável legal",
        )

    nome = apelido = telefone = nome_responsavel = None
    if ve_contato:
        st.divider()
        st.markdown("**Contato** — visível apenas para Técnico e Admin")
        nome = st.text_input("Nome")
        apelido = st.text_input("Como prefere ser chamada")
        telefone = st.text_input("Telefone")
        if consentimento_por == "responsavel_legal":
            nome_responsavel = st.text_input("Nome do responsável legal")
    elif consentimento_por == "responsavel_legal":
        nome_responsavel = st.text_input(
            "Nome do responsável legal",
            help="Necessário para o consentimento de menor de idade.",
        )

    salvar = st.form_submit_button("Salvar pessoa", use_container_width=True, type="primary")

if salvar:
    try:
        criada = pessoas.criar(
            sessao,
            faixa_etaria_id=faixa["id"],
            genero_id=generos[nome_genero],
            bairro_id=bairros.get(nome_bairro),
            perfis=[p["id"] for p in perfis if p["nome"] in nomes_perfis],
            consentimento_data=consentimento_data,
            consentimento_por=consentimento_por,
            gestante=gestante,
            data_primeiro_contato=primeiro_contato,
            nome=nome,
            apelido=apelido,
            telefone=telefone,
            nome_responsavel=nome_responsavel,
        )
    except (ErroDeValidacao, PermissaoNegada) as erro:
        ui.erro(str(erro))
    else:
        st.session_state["pessoa_cadastrada"] = criada["codigo"]
        ui.sucesso("Pessoa cadastrada!")
        st.rerun()


# --- Corrigir uma pessoa já cadastrada ----------------------------------------------------
# Fica no fim desta tela, e não em página própria, para não encher o menu de quem usa o
# celular em campo. A busca é sempre pelo código.

st.divider()
with st.expander("Corrigir ou desativar uma pessoa"):
    codigo = st.text_input("Código da pessoa", placeholder="PN-00001", key="busca_corrigir")
    encontrada = pessoas.buscar_por_codigo(sessao, codigo) if codigo else None

    if codigo and encontrada is None:
        ui.erro("Não encontrei esse código. Confira o número.")

    if encontrada:
        st.markdown(
            f"<div class='pn-item'><b>{encontrada['codigo']}</b> · "
            f"{encontrada['faixa_etaria']} · {encontrada['genero']}<br>"
            f"<span style='color:#52514e'>{encontrada['perfis'] or 'sem perfil'}</span></div>",
            unsafe_allow_html=True,
        )

        with st.form("corrigir_pessoa"):
            rotulos = [f["rotulo"] for f in faixas]
            nova_faixa = st.selectbox(
                "Faixa etária", rotulos, index=rotulos.index(encontrada["faixa_etaria"])
            )
            nomes_genero = list(generos)
            novo_genero = st.selectbox(
                "Gênero", nomes_genero, index=nomes_genero.index(encontrada["genero"])
            )
            atuais = pessoas.perfis_de(sessao, encontrada["id"])
            novos_perfis = st.multiselect(
                "Perfis",
                [p["nome"] for p in perfis],
                default=[p["nome"] for p in perfis if p["id"] in atuais],
            )
            nova_gestante = st.checkbox("Gestante", value=bool(encontrada["gestante"]))
            salvar_correcao = st.form_submit_button(
                "Salvar correção", use_container_width=True, type="primary"
            )

        if salvar_correcao:
            try:
                pessoas.atualizar(
                    sessao,
                    encontrada["id"],
                    perfis=[p["id"] for p in perfis if p["nome"] in novos_perfis],
                    faixa_etaria_id=next(f["id"] for f in faixas if f["rotulo"] == nova_faixa),
                    genero_id=generos[novo_genero],
                    gestante=nova_gestante,
                )
            except (ErroDeValidacao, PermissaoNegada) as erro:
                ui.erro(str(erro))
            else:
                ui.sucesso("Correção salva")
                st.rerun()

        if ve_contato:
            contato = restrito.contato(sessao, encontrada["id"])
            revogado = contato and contato["consentimento_revogado_em"]

            with st.form("corrigir_contato"):
                st.markdown("**Contato**")
                if revogado:
                    st.info("O consentimento desta pessoa foi revogado: não há mais contato.")
                novo_nome = st.text_input("Nome", value=(contato or {}).get("nome") or "")
                novo_apelido = st.text_input(
                    "Como prefere ser chamada", value=(contato or {}).get("apelido") or ""
                )
                novo_telefone = st.text_input(
                    "Telefone", value=(contato or {}).get("telefone") or ""
                )
                if st.form_submit_button("Salvar contato", use_container_width=True):
                    restrito.salvar_contato(
                        sessao,
                        encontrada["id"],
                        nome=novo_nome or None,
                        apelido=novo_apelido or None,
                        telefone=novo_telefone or None,
                    )
                    ui.sucesso("Contato salvo")
                    st.rerun()

            st.caption(
                "Revogar o consentimento apaga nome, apelido e telefone. O histórico de "
                "atendimento continua contando nos relatórios, só sem ligação com a pessoa."
            )
            if not revogado and st.button("Revogar consentimento", use_container_width=True):
                restrito.revogar_consentimento(sessao, encontrada["id"])
                ui.sucesso("Consentimento revogado")
                st.rerun()

            if st.button("Desativar pessoa", use_container_width=True):
                pessoas.desativar(sessao, encontrada["id"])
                ui.sucesso("Pessoa desativada")
                st.rerun()
        else:
            st.caption(
                "Dados de contato e desativação são tarefas da assistente social ou da "
                "coordenação."
            )
