"""Cadastro de pessoa.

A pessoa é pseudonimizada: a tabela `pessoa` guarda código e atributos analíticos, e o que
identifica alguém (nome, apelido, telefone, responsável) fica só em `pessoa_contato`.

Quem tem papel Campo pode cadastrar, mas não envia nem lê dado de contato — só registra o
consentimento, que é obrigatório para qualquer cadastro.
"""

from datetime import date

from sqlalchemy import Date, insert, select, text, update

from services import cache, modelo
from services.db import conexao
from services.seguranca import (
    ErroDeValidacao,
    PermissaoNegada,
    exige_equipe,
    exige_identificado,
    registrar_auditoria,
)

CAMPOS_DE_CONTATO = ("nome", "apelido", "telefone")


def _proximo_codigo(con) -> str:
    """Código PN-00001, tirado do contador dentro da mesma transação do cadastro."""
    con.execute(
        update(modelo.contador)
        .where(modelo.contador.c.nome == "pessoa_codigo")
        .values(valor=modelo.contador.c.valor + 1)
    )
    valor = con.execute(
        select(modelo.contador.c.valor).where(modelo.contador.c.nome == "pessoa_codigo")
    ).scalar()
    return f"PN-{valor:05d}"


def _faixa(con, faixa_etaria_id):
    faixa = con.execute(
        select(modelo.faixa_etaria).where(modelo.faixa_etaria.c.id == faixa_etaria_id)
    ).mappings().first()
    if faixa is None:
        raise ErroDeValidacao("Escolha a faixa etária.")
    return faixa


def _validar_atributos(con, faixa, gestante, perfis):
    """Coerência entre faixa etária, marcação de gestante e perfis escolhidos."""
    if gestante and not faixa["pode_gestar"]:
        raise ErroDeValidacao(
            f"A faixa etária {faixa['rotulo']} não é compatível com a marcação de gestante."
        )

    for perfil_id in perfis:
        perfil = con.execute(
            select(modelo.perfil).where(modelo.perfil.c.id == perfil_id)
        ).mappings().first()
        permitidas = (perfil or {}).get("faixas_permitidas")
        if permitidas and f",{faixa['codigo']}," not in permitidas:
            raise ErroDeValidacao(
                f"O perfil {perfil['nome']} não combina com a faixa etária {faixa['rotulo']}."
            )


def _validar_consentimento(faixa, consentimento_data, consentimento_por, nome_responsavel):
    """Consentimento é obrigatório (art. 14 da LGPD); menor de 18 exige responsável legal."""
    if not consentimento_data:
        raise ErroDeValidacao("Informe a data do consentimento. Sem isso não é possível salvar.")

    if faixa["menor_de_idade"] and (
        consentimento_por != "responsavel_legal" or not (nome_responsavel or "").strip()
    ):
        raise ErroDeValidacao(
            "Pessoa menor de 18 anos só pode ser cadastrada com o consentimento do "
            "responsável legal. Informe quem é o responsável."
        )


def criar(
    sessao,
    faixa_etaria_id: str,
    genero_id: str,
    bairro_id: str | None,
    perfis: list[str],
    consentimento_data: date,
    consentimento_por: str,
    gestante: bool = False,
    data_primeiro_contato: date | None = None,
    nome: str | None = None,
    apelido: str | None = None,
    telefone: str | None = None,
    nome_responsavel: str | None = None,
) -> dict:
    """Cria a pessoa e o consentimento na mesma transação. Devolve id e código."""
    exige_equipe(sessao)

    if sessao.papel == "campo" and (nome or apelido or telefone):
        raise PermissaoNegada("Seu perfil de acesso não registra dados de contato.")

    if not genero_id:
        raise ErroDeValidacao("Escolha o gênero.")

    with conexao() as con:
        faixa = _faixa(con, faixa_etaria_id)
        _validar_atributos(con, faixa, gestante, perfis)
        _validar_consentimento(faixa, consentimento_data, consentimento_por, nome_responsavel)

        pessoa_id = modelo.novo_id()
        codigo = _proximo_codigo(con)
        con.execute(
            insert(modelo.pessoa).values(
                id=pessoa_id,
                codigo=codigo,
                faixa_etaria_id=faixa_etaria_id,
                genero_id=genero_id,
                bairro_id=bairro_id or None,
                gestante=bool(gestante),
                data_primeiro_contato=data_primeiro_contato or date.today(),
                created_by=sessao.usuario_id,
            )
        )
        for perfil_id in perfis:
            con.execute(
                insert(modelo.pessoa_perfil).values(
                    id=modelo.novo_id(),
                    pessoa_id=pessoa_id,
                    perfil_id=perfil_id,
                    created_by=sessao.usuario_id,
                )
            )
        con.execute(
            insert(modelo.pessoa_contato).values(
                pessoa_id=pessoa_id,
                nome=(nome or None),
                apelido=(apelido or None),
                telefone=(telefone or None),
                nome_responsavel=(nome_responsavel or None),
                consentimento_data=consentimento_data,
                consentimento_por=consentimento_por,
                created_by=sessao.usuario_id,
            )
        )
        registrar_auditoria(con, sessao, "criacao", "pessoa_contato", pessoa_id)

    cache.limpar()
    return {"id": pessoa_id, "codigo": codigo}


SQL_RESUMO = """
select p.id, p.codigo, fe.rotulo as faixa_etaria, g.nome as genero, b.nome as bairro,
       p.gestante, p.data_primeiro_contato,
       (select group_concat(pf2.nome, ', ')
          from pessoa_perfil pp join perfil pf2 on pf2.id = pp.perfil_id
         where pp.pessoa_id = p.id and pp.ativo = 1) as perfis
  from pessoa p
  join faixa_etaria fe on fe.id = p.faixa_etaria_id
  join genero g on g.id = p.genero_id
  left join bairro b on b.id = p.bairro_id
 where p.ativo = 1
"""


def _consulta(complemento: str = ""):
    """Declara o tipo das datas: em SQL escrito à mão, o banco devolveria texto."""
    return text(SQL_RESUMO + complemento).columns(data_primeiro_contato=Date)


def buscar_por_codigo(sessao, codigo: str) -> dict | None:
    """Busca pelo código PN-00001. É o único jeito que o papel Campo tem de achar alguém."""
    exige_equipe(sessao)
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    if not codigo.startswith("PN-"):
        codigo = f"PN-{codigo.zfill(5)}"
    with conexao() as con:
        linha = con.execute(_consulta(" and p.codigo = :codigo"), {"codigo": codigo})
        linha = linha.mappings().first()
    return dict(linha) if linha else None


def listar(sessao, limite: int = 100) -> list[dict]:
    exige_equipe(sessao)
    with conexao() as con:
        linhas = con.execute(
            _consulta(" order by p.created_at desc limit :limite"), {"limite": limite}
        )
        return [dict(linha) for linha in linhas.mappings()]


def perfis_de(sessao, pessoa_id: str) -> list[str]:
    exige_equipe(sessao)
    with conexao() as con:
        return [
            linha[0]
            for linha in con.execute(
                select(modelo.pessoa_perfil.c.perfil_id).where(
                    (modelo.pessoa_perfil.c.pessoa_id == pessoa_id)
                    & modelo.pessoa_perfil.c.ativo
                )
            )
        ]


def atualizar(sessao, pessoa_id: str, perfis: list[str] | None = None, **campos) -> None:
    """Altera atributos analíticos. Dado de contato se altera em services/restrito.py."""
    exige_equipe(sessao)
    if any(campo in campos for campo in CAMPOS_DE_CONTATO):
        raise PermissaoNegada("Dados de contato são alterados na tela de contato.")

    with conexao() as con:
        atual = con.execute(
            select(modelo.pessoa).where(modelo.pessoa.c.id == pessoa_id)
        ).mappings().first()
        if atual is None:
            raise ErroDeValidacao("Pessoa não encontrada.")

        faixa = _faixa(con, campos.get("faixa_etaria_id", atual["faixa_etaria_id"]))
        _validar_atributos(con, faixa, campos.get("gestante", atual["gestante"]), perfis or [])

        if campos:
            con.execute(
                update(modelo.pessoa).where(modelo.pessoa.c.id == pessoa_id).values(**campos)
            )

        if perfis is not None:
            con.execute(
                update(modelo.pessoa_perfil)
                .where(modelo.pessoa_perfil.c.pessoa_id == pessoa_id)
                .values(ativo=False)
            )
            for perfil_id in perfis:
                ja_existe = con.execute(
                    select(modelo.pessoa_perfil.c.id).where(
                        (modelo.pessoa_perfil.c.pessoa_id == pessoa_id)
                        & (modelo.pessoa_perfil.c.perfil_id == perfil_id)
                    )
                ).scalar()
                if ja_existe:
                    con.execute(
                        update(modelo.pessoa_perfil)
                        .where(modelo.pessoa_perfil.c.id == ja_existe)
                        .values(ativo=True)
                    )
                else:
                    con.execute(
                        insert(modelo.pessoa_perfil).values(
                            id=modelo.novo_id(),
                            pessoa_id=pessoa_id,
                            perfil_id=perfil_id,
                            created_by=sessao.usuario_id,
                        )
                    )
        registrar_auditoria(con, sessao, "alteracao", "pessoa", pessoa_id)
    cache.limpar()


def desativar(sessao, pessoa_id: str) -> None:
    """Exclusão lógica: o histórico de participações continua contando nos indicadores."""
    exige_identificado(sessao)
    with conexao() as con:
        con.execute(update(modelo.pessoa).where(modelo.pessoa.c.id == pessoa_id).values(ativo=False))
        registrar_auditoria(con, sessao, "desativacao", "pessoa", pessoa_id)
    cache.limpar()
