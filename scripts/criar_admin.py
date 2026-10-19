"""Cria o primeiro usuário administrador, quando o banco ainda não tem ninguém.

Depois disso, todos os outros usuários são criados pela própria página Admin.

Uso:  python scripts/criar_admin.py coordenacao@paginasnovas.org "Nome da Coordenação"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.usuarios import _criar  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        return

    email, nome = sys.argv[1], sys.argv[2]
    senha = _criar(email, nome, "admin")
    print(f"Usuário criado: {email}")
    print(f"Senha provisória: {senha}")
    print("Entre com ela uma vez; o sistema vai pedir para criar a sua senha definitiva.")


if __name__ == "__main__":
    main()
