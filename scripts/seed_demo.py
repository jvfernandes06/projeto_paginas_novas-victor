"""Dados de demonstração — 100% fictícios.

Para quê: ninguém aprova um sistema olhando dashboard vazio, e ninguém testa desempenho com
dez linhas. Este script cria 18 meses de movimento inventado, com a sazonalidade real da ONG
(mais atividade no sábado; picos em abril, outubro e dezembro) e alguns registros
propositalmente incompletos, para a tela de Pendências ter o que mostrar.

**Nunca rode isto num banco com dado real.** Antes de a ONG começar a usar de verdade,
rode `python scripts/limpar_demo.py`.

Uso:  python scripts/seed_demo.py
"""

import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import insert, select  # noqa: E402

from services import modelo  # noqa: E402
from services.db import conexao  # noqa: E402
from services.seguranca import hash_senha  # noqa: E402

SEMENTE = 42
SENHA_DEMO = "demo1234"
MESES = 18
TOTAL_PESSOAS = 300

USUARIOS_DEMO = [
    ("admin@demo", "Coordenação (demo)", "admin"),
    ("tecnico@demo", "Assistente social (demo)", "tecnico"),
    ("campo@demo", "Estagiária (demo)", "campo"),
    ("parceiro@demo", "Financiador (demo)", "parceiro"),
]

# Programas que acontecem em dia de semana, no contraturno escolar.
PROGRAMAS_SEMANA = [
    "Kidstinga",
    "Projeto Nota 10",
    "Ballet/Dança",
    "Hip Hop",
    "Basquete",
    "Equilibrium",
    "Saúde da Mulher",
    "Saúde Trans",
    "Fábrica dos Sonhos",
    "Oficina de Moda/Crochê",
    "Café com Fé",
    "Bendito o Fruto do Teu Ventre",
]
PROGRAMAS_SABADO = ["Kidstinga", "Bazar Solidário", "Passeio Cultural", "Carreta da Saúde"]
PROGRAMA_RUA = "Abordagem de Rua"
PROGRAMAS_DEZEMBRO = ["Jantar de Natal", "Apadrinhamento de Natal"]

MESES_DE_PICO = (4, 10, 12)
HORARIOS = (8, 10, 14, 16)


def _ids_por_nome(con, tabela) -> dict[str, str]:
    return {
        linha["nome"]: linha["id"]
        for linha in con.execute(select(tabela.c.id, tabela.c.nome)).mappings()
    }


def _criar_usuarios(con) -> str:
    """Cria os quatro usuários de demonstração. Devolve o id do admin."""
    admin_id = None
    for email, nome, papel in USUARIOS_DEMO:
        existente = con.execute(
            select(modelo.usuario.c.id).where(modelo.usuario.c.email == email)
        ).scalar()
        if existente:
            if papel == "admin":
                admin_id = existente
            continue
        novo = modelo.novo_id()
        con.execute(
            insert(modelo.usuario).values(
                id=novo,
                email=email,
                nome_exibicao=nome,
                senha_hash=hash_senha(SENHA_DEMO),
                papel=papel,
                deve_trocar_senha=False,  # só na demonstração, para entrar direto
            )
        )
        if papel == "admin":
            admin_id = novo
    return admin_id


def _criar_locais_ficticios(con, autor: str) -> None:
    """Boates e pontos de rua com nomes inventados, para a demonstração ter território."""
    ficticios = [
        ("Boate Estrela Azul (fictícia)", "boate"),
        ("Boate Luar (fictícia)", "boate"),
        ("Rua das Acácias (fictícia)", "rua"),
        ("Posto da Rodovia (fictício)", "rua"),
        ("Praça Central (fictícia)", "externo"),
    ]
    existentes = _ids_por_nome(con, modelo.local)
    for nome, tipo in ficticios:
        if nome in existentes:
            continue
        con.execute(
            insert(modelo.local).values(
                id=modelo.novo_id(), nome=nome, tipo=tipo, created_by=autor
            )
        )


def _criar_pessoas(con, autor: str, sorteio: random.Random, hoje: date) -> list[dict]:
    faixas = {
        linha["codigo"]: linha
        for linha in con.execute(select(modelo.faixa_etaria)).mappings()
    }
    generos = _ids_por_nome(con, modelo.genero)
    bairros = _ids_por_nome(con, modelo.bairro)
    perfis = _ids_por_nome(con, modelo.perfil)

    # Peso parecido com o público da ONG: muita criança e adolescente, muita mulher adulta.
    pesos_faixa = {"0-5": 12, "6-11": 22, "12-17": 18, "18-29": 20, "30-44": 18, "45-59": 8, "60+": 2}
    pesos_genero = {
        "Mulher cisgênero": 55,
        "Homem cisgênero": 20,
        "Mulher trans": 10,
        "Travesti": 7,
        "Homem trans": 3,
        "Não binário": 2,
        "Prefere não informar": 3,
    }

    pessoas, linhas_pessoa, linhas_perfil, linhas_contato = [], [], [], []
    contador = con.execute(
        select(modelo.contador.c.valor).where(modelo.contador.c.nome == "pessoa_codigo")
    ).scalar() or 0

    for indice in range(TOTAL_PESSOAS):
        codigo_faixa = sorteio.choices(list(pesos_faixa), weights=list(pesos_faixa.values()))[0]
        faixa = faixas[codigo_faixa]
        nome_genero = sorteio.choices(list(pesos_genero), weights=list(pesos_genero.values()))[0]
        gestante = bool(faixa["pode_gestar"] and nome_genero in ("Mulher cisgênero", "Homem trans") and sorteio.random() < 0.07)
        primeiro_contato = hoje - timedelta(days=sorteio.randint(0, MESES * 30))

        contador += 1
        pessoa_id = modelo.novo_id()
        linhas_pessoa.append(
            {
                "id": pessoa_id,
                "codigo": f"PN-{contador:05d}",
                "faixa_etaria_id": faixa["id"],
                "genero_id": generos[nome_genero],
                "bairro_id": bairros["Jardim Itatinga"] if sorteio.random() < 0.8 else bairros["Outro"],
                "gestante": gestante,
                "data_primeiro_contato": primeiro_contato,
                "created_by": autor,
            }
        )

        # Perfis coerentes com a faixa etária, que é o que o sistema exige.
        escolhidos = []
        if codigo_faixa in ("0-5", "6-11"):
            escolhidos.append("Criança")
            if sorteio.random() < 0.12:
                escolhidos.append("TEA")
        elif codigo_faixa == "12-17":
            escolhidos.append("Adolescente")
            if sorteio.random() < 0.08:
                escolhidos.append("TEA")
        else:
            if sorteio.random() < 0.45:
                escolhidos.append("Mulher em situação de prostituição")
            if sorteio.random() < 0.35:
                escolhidos.append("Responsável familiar")
            if codigo_faixa == "60+":
                escolhidos.append("Idoso")
        if nome_genero in ("Mulher trans", "Homem trans", "Travesti"):
            escolhidos.append("Pessoa trans")

        for nome_perfil in set(escolhidos):
            linhas_perfil.append(
                {
                    "id": modelo.novo_id(),
                    "pessoa_id": pessoa_id,
                    "perfil_id": perfis[nome_perfil],
                    "created_by": autor,
                }
            )

        # 10 pessoas com consentimento revogado, para a tela de Pendências ter o que mostrar.
        revogado = datetime.now() if indice < 10 else None
        linhas_contato.append(
            {
                "pessoa_id": pessoa_id,
                "nome": None if revogado else f"Pessoa Fictícia {contador}",
                "apelido": None if revogado else f"Fict{contador}",
                "telefone": None if revogado else f"19 9{sorteio.randint(1000, 9999)}-{sorteio.randint(1000, 9999)}",
                "nome_responsavel": (
                    f"Responsável Fictício {contador}" if faixa["menor_de_idade"] and not revogado else None
                ),
                "consentimento_data": primeiro_contato,
                "consentimento_por": "responsavel_legal" if faixa["menor_de_idade"] else "propria_pessoa",
                "consentimento_revogado_em": revogado,
                "created_by": autor,
            }
        )
        pessoas.append({"id": pessoa_id, "faixa": codigo_faixa, "gestante": gestante})

    con.execute(insert(modelo.pessoa), linhas_pessoa)
    con.execute(insert(modelo.pessoa_perfil), linhas_perfil)
    con.execute(insert(modelo.pessoa_contato), linhas_contato)
    con.execute(
        modelo.contador.update()
        .where(modelo.contador.c.nome == "pessoa_codigo")
        .values(valor=contador)
    )
    return pessoas


def _programas_do_dia(dia: date, sorteio: random.Random) -> list[str]:
    if dia.weekday() == 6:  # domingo: a ONG não abre
        return []

    if dia.weekday() == 5:  # sábado é o dia mais cheio
        escolha = sorteio.sample(PROGRAMAS_SABADO, k=sorteio.randint(2, 3))
    else:
        escolha = sorteio.sample(PROGRAMAS_SEMANA, k=sorteio.randint(1, 3))

    if dia.weekday() in (3, 4) and sorteio.random() < 0.7:  # abordagem às quintas e sextas
        escolha.append(PROGRAMA_RUA)
    if dia.month == 12 and sorteio.random() < 0.25:
        escolha.append(sorteio.choice(PROGRAMAS_DEZEMBRO))
    if dia.month in MESES_DE_PICO and sorteio.random() < 0.4:
        escolha.append(sorteio.choice(PROGRAMAS_SEMANA))

    return list(dict.fromkeys(escolha))


def _criar_atividades(con, autor: str, sorteio: random.Random, hoje: date, pessoas: list[dict]) -> int:
    programas = _ids_por_nome(con, modelo.programa)
    locais = {
        linha["nome"]: linha
        for linha in con.execute(select(modelo.local)).mappings()
    }
    tipos = _ids_por_nome(con, modelo.tipo_atividade)
    funcoes = _ids_por_nome(con, modelo.funcao_equipe)
    itens = _ids_por_nome(con, modelo.tipo_item)

    locais_rua = [nome for nome, linha in locais.items() if linha["tipo"] in ("rua", "boate")]
    sede = "Sede Páginas Novas"

    # Quem frequenta muito e quem aparece pouco: é isso que faz a taxa de recorrência ter sentido.
    assiduos = sorteio.sample(pessoas, k=int(len(pessoas) * 0.35))
    eventuais = [p for p in pessoas if p not in assiduos]

    linhas_atividade, linhas_equipe, linhas_part, linhas_contagem, linhas_item = [], [], [], [], []
    inicio = hoje - timedelta(days=MESES * 30)
    dia = inicio
    total = 0

    while dia <= hoje:
        for ordem, nome_programa in enumerate(_programas_do_dia(dia, sorteio)):
            de_rua = nome_programa == PROGRAMA_RUA
            # Horários de início possíveis, para duas atividades do mesmo dia não colidirem.
            hora_inicio = time(20, 0) if de_rua else time(HORARIOS[ordem % len(HORARIOS)], 0)
            duracao = sorteio.choice([90, 120, 180])
            minuto_fim = hora_inicio.hour * 60 + duracao
            if minuto_fim >= 24 * 60:
                continue
            hora_fim = time(minuto_fim // 60, minuto_fim % 60)

            atividade_id = modelo.novo_id()
            local_nome = sorteio.choice(locais_rua) if de_rua and locais_rua else sede
            linhas_atividade.append(
                {
                    "id": atividade_id,
                    "data": dia,
                    "hora_inicio": hora_inicio,
                    "hora_fim": hora_fim,
                    "duracao_minutos": duracao,
                    "programa_id": programas[nome_programa],
                    "local_id": locais[local_nome]["id"],
                    "tipo_atividade_id": tipos["Abordagem"] if de_rua else tipos[
                        sorteio.choice(["Oficina", "Aula", "Roda de conversa", "Evento"])
                    ],
                    "descricao_curta": None,
                    "observacao": None,
                    "created_by": autor,
                }
            )
            total += 1

            # 3% das atividades ficam sem equipe informada, para gerar pendência.
            if sorteio.random() > 0.03:
                for nome_funcao in sorteio.sample(
                    ["Assistente social", "Estagiária", "Professor", "Voluntário", "Nutrição"],
                    k=sorteio.randint(1, 4),
                ):
                    linhas_equipe.append(
                        {
                            "id": modelo.novo_id(),
                            "atividade_id": atividade_id,
                            "funcao_equipe_id": funcoes[nome_funcao],
                            "quantidade": sorteio.randint(1, 4),
                            "created_by": autor,
                        }
                    )

            if de_rua:
                abordagens = sorteio.randint(8, 30)
                linhas_contagem.append(
                    {
                        "atividade_id": atividade_id,
                        "abordagens": abordagens,
                        "criancas": sorteio.randint(0, 2),
                        "adolescentes": sorteio.randint(0, 4),
                        "adultos": abordagens - sorteio.randint(0, 3),
                        "created_by": autor,
                    }
                )
                for nome_item in ("Preservativo", "Kit de higiene"):
                    linhas_item.append(
                        {
                            "id": modelo.novo_id(),
                            "atividade_id": atividade_id,
                            "tipo_item_id": itens[nome_item],
                            "quantidade": sorteio.randint(10, 120),
                            "created_by": autor,
                        }
                    )
            elif sorteio.random() > 0.02:  # 2% ficam sem ninguém, para gerar pendência
                quantos = sorteio.randint(4, 18)
                presentes = sorteio.sample(
                    assiduos, k=min(quantos, len(assiduos))
                ) if sorteio.random() < 0.7 else sorteio.sample(eventuais, k=min(quantos, len(eventuais)))
                for pessoa in presentes:
                    linhas_part.append(
                        {
                            "id": modelo.novo_id(),
                            "atividade_id": atividade_id,
                            "pessoa_id": pessoa["id"],
                            "created_by": autor,
                        }
                    )
                if sorteio.random() < 0.3:
                    linhas_item.append(
                        {
                            "id": modelo.novo_id(),
                            "atividade_id": atividade_id,
                            "tipo_item_id": itens[sorteio.choice(["Refeição", "Brinquedo", "Roupa"])],
                            "quantidade": sorteio.randint(5, 60),
                            "created_by": autor,
                        }
                    )

        dia += timedelta(days=1)

    con.execute(insert(modelo.atividade), linhas_atividade)
    if linhas_equipe:
        con.execute(insert(modelo.atividade_equipe), linhas_equipe)
    if linhas_part:
        con.execute(insert(modelo.participacao), linhas_part)
    if linhas_contagem:
        con.execute(insert(modelo.contagem_anonima), linhas_contagem)
    if linhas_item:
        con.execute(insert(modelo.item_distribuido), linhas_item)
    return total


def _criar_encaminhamentos(con, autor: str, sorteio: random.Random, hoje: date, pessoas: list[dict]) -> int:
    destinos = list(_ids_por_nome(con, modelo.destino_encaminhamento).values())
    linhas = []
    for _ in range(140):
        pessoa = sorteio.choice(pessoas)
        data = hoje - timedelta(days=sorteio.randint(0, MESES * 30))
        status = sorteio.choices(
            ["enviado", "em_andamento", "concluido", "sem_retorno"], weights=[25, 25, 35, 15]
        )[0]
        # Metade dos não concluídos fica sem atualização há mais de 60 dias: pendência.
        if status != "concluido" and sorteio.random() < 0.5:
            atualizacao = hoje - timedelta(days=sorteio.randint(61, 200))
        else:
            atualizacao = data + timedelta(days=sorteio.randint(0, 30))
        linhas.append(
            {
                "id": modelo.novo_id(),
                "pessoa_id": pessoa["id"],
                "destino_id": sorteio.choice(destinos),
                "data": data,
                "status": status,
                "data_ultima_atualizacao": max(data, min(atualizacao, hoje)),
                "observacao": None,
                "created_by": autor,
            }
        )
    con.execute(insert(modelo.encaminhamento), linhas)
    return len(linhas)


def main() -> None:
    sorteio = random.Random(SEMENTE)
    hoje = date.today()

    with conexao() as con:
        if con.execute(select(modelo.pessoa.c.id).limit(1)).scalar():
            print("O banco já tem pessoas cadastradas. Rode scripts/limpar_demo.py primeiro.")
            return

        autor = _criar_usuarios(con)
        _criar_locais_ficticios(con, autor)
        pessoas = _criar_pessoas(con, autor, sorteio, hoje)
        atividades = _criar_atividades(con, autor, sorteio, hoje, pessoas)
        encaminhamentos = _criar_encaminhamentos(con, autor, sorteio, hoje, pessoas)

    print(f"{len(pessoas)} pessoas fictícias")
    print(f"{atividades} atividades em {MESES} meses")
    print(f"{encaminhamentos} encaminhamentos")
    print()
    print("Usuários de demonstração (senha igual para todos):")
    for email, nome, papel in USUARIOS_DEMO:
        print(f"  {email:<16} {papel:<9} senha: {SENHA_DEMO}")
    print()
    print("São dados inventados. Rode scripts/limpar_demo.py antes de usar com dado real.")


if __name__ == "__main__":
    main()
