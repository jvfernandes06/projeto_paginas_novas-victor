"""Apaga os dados de demonstração, para o banco receber dado real.

Apaga pessoas, atividades, participações, contagens, itens, encaminhamentos, auditoria e os
usuários @demo. **Mantém** as listas do sistema (programas, locais, perfis), que são
configuração, e os usuários reais que já tiverem sido criados.

Aqui a exclusão é física, diferente do resto do sistema: a ideia é justamente não deixar
rastro de dado inventado no banco que vai receber dado real.

Uso:  python scripts/limpar_demo.py --sim
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select, update  # noqa: E402

from services import modelo  # noqa: E402
from services.db import conexao  # noqa: E402

# Ordem importa: filhos antes dos pais, por causa das chaves estrangeiras.
TABELAS = [
    modelo.participacao,
    modelo.contagem_anonima,
    modelo.item_distribuido,
    modelo.atividade_equipe,
    modelo.encaminhamento,
    modelo.atividade,
    modelo.pessoa_contato,
    modelo.pessoa_perfil,
    modelo.pessoa,
    modelo.auditoria,
]


def contar() -> dict[str, int]:
    with conexao() as con:
        return {
            tabela.name: con.execute(select(func.count()).select_from(tabela)).scalar()
            for tabela in TABELAS
        }


def limpar() -> dict[str, int]:
    apagados = contar()
    with conexao() as con:
        for tabela in TABELAS:
            con.execute(delete(tabela))
        con.execute(delete(modelo.usuario).where(modelo.usuario.c.email.like("%@demo")))
        con.execute(
            update(modelo.contador)
            .where(modelo.contador.c.nome == "pessoa_codigo")
            .values(valor=0)
        )
    return apagados


def main() -> None:
    argumentos = argparse.ArgumentParser(description="Apaga os dados de demonstração.")
    argumentos.add_argument("--sim", action="store_true", help="confirma a exclusão")
    opcoes = argumentos.parse_args()

    totais = contar()
    print("Vou apagar:")
    for nome, quantidade in totais.items():
        print(f"  {quantidade:>7} em {nome}")
    print("  todos os usuários com e-mail terminando em @demo")

    if not opcoes.sim:
        print()
        print("Nada foi apagado. Rode de novo com --sim para confirmar.")
        return

    limpar()
    print()
    print("Pronto. O banco está limpo e o contador de códigos voltou para PN-00001.")
    print("Crie o primeiro usuário real com scripts/criar_admin.py.")


if __name__ == "__main__":
    main()
