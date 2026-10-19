"""O backup tem de dar para restaurar. Backup que ninguém testou não é backup."""

from datetime import date

import pytest

from scripts import backup
from services import config
from services.db import _engines, consultar_valor


@pytest.fixture(autouse=True)
def _fecha_engines():
    """O SQLite no Windows não deixa trocar o arquivo com conexão aberta."""
    yield
    for motor in list(_engines.values()):
        motor.dispose()


def test_backup_e_restauracao(tecnico, nova_pessoa, nova_atividade):
    nova_pessoa(tecnico)
    nova_atividade(tecnico, dia=date(2026, 3, 10))

    arquivo = backup.criar_backup()
    assert arquivo.exists()
    assert arquivo.stat().st_size > 0

    # Depois do backup, mais uma pessoa entra no banco.
    nova_pessoa(tecnico)
    assert consultar_valor("select count(*) from pessoa") == 2

    for motor in list(_engines.values()):
        motor.dispose()
    backup.restaurar(arquivo)

    # O banco voltou ao estado do backup: uma pessoa, uma atividade.
    assert consultar_valor("select count(*) from pessoa") == 1
    assert consultar_valor("select count(*) from atividade") == 1

    reserva = config.caminho_banco().with_suffix(".antes-de-restaurar.db")
    assert reserva.exists(), "a restauração precisa guardar o estado anterior"


def test_backup_mantem_apenas_os_ultimos_trinta(tecnico, nova_pessoa):
    nova_pessoa(tecnico)
    pasta = backup.pasta_de_backup()
    for dia in range(1, 40):
        (pasta / f"paginas_novas_2026-01-{dia:02d}.db").write_bytes(b"backup antigo")

    apagados = backup.apagar_antigos()
    restantes = sorted(pasta.glob("paginas_novas_*.db"))

    assert len(restantes) == backup.DIAS_GUARDADOS
    assert apagados, "os backups mais antigos deveriam sair"


def test_restaurar_arquivo_inexistente_avisa(banco):
    with pytest.raises(FileNotFoundError):
        backup.restaurar(config.caminho_banco().parent / "nao_existe.db")
