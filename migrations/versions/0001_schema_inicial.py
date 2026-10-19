"""Schema inicial.

O schema é descrito em services/modelo.py, e esta migration o constrói a partir de lá, para
não existirem duas descrições das mesmas tabelas podendo divergir. As migrations seguintes são
incrementais (add_column, create_table) como de costume no Alembic.

Revision ID: 0001
"""

from alembic import op

from services.modelo import metadata

revision = "0001"
down_revision = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
