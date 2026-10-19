"""Ambiente do Alembic.

O banco vem de services/config.py, ou seja, da variável de ambiente PN_BANCO.
`render_as_batch` está ligado porque o SQLite não sabe alterar coluna: o Alembic precisa
recriar a tabela quando uma migration futura mudar algo.
"""

import sys
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.db import engine  # noqa: E402
from services.modelo import metadata  # noqa: E402

target_metadata = metadata


def executar() -> None:
    with engine().connect() as con:
        context.configure(connection=con, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


executar()
