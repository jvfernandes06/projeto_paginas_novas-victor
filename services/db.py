"""Conexão com o banco.

Este é o único módulo do sistema que abre conexão. Nenhuma página faz isso: página fala com
services/ e analytics/, que falam com o banco.
"""

from contextlib import contextmanager

import pandas as pd
from sqlalchemy import create_engine, event, text

from services import config

_engines: dict[str, object] = {}


def engine():
    """Devolve o engine do banco atual, criando na primeira vez."""
    url = config.url_banco()
    if url not in _engines:
        motor = create_engine(url)

        @event.listens_for(motor, "connect")
        def ligar_pragmas(conexao_dbapi, _registro):
            cursor = conexao_dbapi.cursor()
            cursor.execute("pragma foreign_keys = on")
            cursor.execute("pragma journal_mode = wal")
            cursor.close()

        _engines[url] = motor
    return _engines[url]


@contextmanager
def conexao():
    """Abre uma transação: confirma ao fim do bloco, desfaz se houver erro."""
    with engine().begin() as con:
        yield con


def consultar(sql: str, **parametros) -> list:
    with conexao() as con:
        return con.execute(text(sql), parametros).mappings().all()


def consultar_um(sql: str, **parametros):
    with conexao() as con:
        return con.execute(text(sql), parametros).mappings().first()


def consultar_valor(sql: str, padrao=0, **parametros):
    """Para consultas que devolvem um único número."""
    with conexao() as con:
        valor = con.execute(text(sql), parametros).scalar()
    return padrao if valor is None else valor


def tabela(sql: str, **parametros) -> pd.DataFrame:
    """Devolve o resultado como DataFrame, que é o que os gráficos consomem."""
    with conexao() as con:
        return pd.DataFrame(con.execute(text(sql), parametros).mappings().all())
