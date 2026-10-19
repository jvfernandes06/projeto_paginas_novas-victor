"""Backup do banco.

O banco é um arquivo só, então o backup é uma cópia dele. A cópia é feita pela API de backup
do SQLite, que funciona **com o app rodando**, sem risco de copiar o arquivo no meio de uma
gravação.

Uso:
    python scripts/backup.py                      cria o backup do dia e apaga os antigos
    python scripts/backup.py --restaurar ARQUIVO  volta o banco para o estado daquele arquivo

Para rodar todo dia: Agendador de Tarefas no Windows, ou cron no Linux. O passo a passo está
no README_ONG.md.
"""

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import config  # noqa: E402

DIAS_GUARDADOS = 30


def pasta_de_backup() -> Path:
    pasta = config.caminho_banco().parent / "backups"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def criar_backup(quando: date | None = None) -> Path:
    """Copia o banco em uso para a pasta de backups. Devolve o caminho do arquivo criado."""
    origem = config.caminho_banco()
    if not origem.exists():
        raise FileNotFoundError(f"Não encontrei o banco em {origem}")

    destino = pasta_de_backup() / f"paginas_novas_{(quando or date.today()):%Y-%m-%d}.db"
    with sqlite3.connect(origem) as banco_origem, sqlite3.connect(destino) as banco_destino:
        banco_origem.backup(banco_destino)
    return destino


def apagar_antigos() -> list[Path]:
    """Mantém os backups dos últimos 30 dias; devolve o que foi apagado."""
    arquivos = sorted(pasta_de_backup().glob("paginas_novas_*.db"))
    excedentes = arquivos[:-DIAS_GUARDADOS] if len(arquivos) > DIAS_GUARDADOS else []
    for arquivo in excedentes:
        arquivo.unlink()
    return excedentes


def restaurar(arquivo: Path) -> Path:
    """Volta o banco para o estado de um backup.

    O banco atual é guardado antes, com o sufixo .antes-de-restaurar, para dar para voltar
    atrás se a restauração for a errada.
    """
    arquivo = Path(arquivo)
    if not arquivo.exists():
        raise FileNotFoundError(f"Não encontrei o backup {arquivo}")

    destino = config.caminho_banco()
    if destino.exists():
        reserva = destino.with_suffix(".antes-de-restaurar.db")
        with sqlite3.connect(destino) as atual, sqlite3.connect(reserva) as copia:
            atual.backup(copia)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(arquivo) as origem, sqlite3.connect(destino) as novo:
        origem.backup(novo)
    return destino


def main() -> None:
    argumentos = argparse.ArgumentParser(description="Backup e restauração do banco.")
    argumentos.add_argument("--restaurar", metavar="ARQUIVO")
    opcoes = argumentos.parse_args()

    if opcoes.restaurar:
        destino = restaurar(Path(opcoes.restaurar))
        print(f"Banco restaurado em {destino}")
        print("Se o app estava rodando, pare e suba de novo.")
        return

    arquivo = criar_backup()
    tamanho = arquivo.stat().st_size / 1_048_576
    print(f"Backup criado: {arquivo} ({tamanho:.1f} MB)")
    for apagado in apagar_antigos():
        print(f"Backup antigo apagado: {apagado.name}")


if __name__ == "__main__":
    main()
