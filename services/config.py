"""Configuração vinda do ambiente. Nenhum valor sensível fica no código.

O caminho do banco é lido a cada chamada, e não uma vez na importação, para que os testes
possam apontar para um arquivo temporário.
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Dashboards se atualizam sozinhos neste intervalo (segundos). O cache usa o mesmo número.
INTERVALO_ATUALIZACAO = int(os.environ.get("PN_INTERVALO_ATUALIZACAO", "60"))

# Sessão expira com este tempo de inatividade (minutos).
MINUTOS_INATIVIDADE = int(os.environ.get("PN_MINUTOS_INATIVIDADE", "30"))

# Encaminhamento parado mais tempo que isto vira pendência.
DIAS_PARA_PENDENCIA = 60


def caminho_banco() -> Path:
    return Path(os.environ.get("PN_BANCO", RAIZ / "dados" / "paginas_novas.db"))


def url_banco() -> str:
    caminho = caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{caminho}"
