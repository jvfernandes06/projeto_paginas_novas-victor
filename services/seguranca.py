"""Papéis, senhas e auditoria.

Sem RLS no banco, a permissão é verificada aqui — e **toda** função de services/ que toca dado
sensível começa chamando um dos `exige_*`. A tela também verifica, mas a tela não é barreira:
a barreira é esta camada.
"""

import secrets
from dataclasses import dataclass

import bcrypt
from sqlalchemy import insert

from services import modelo

EQUIPE = ("admin", "tecnico", "campo")
VE_IDENTIFICADO = ("admin", "tecnico")

NOMES_DOS_PAPEIS = {
    "admin": "Administrador",
    "tecnico": "Técnico",
    "campo": "Campo",
    "parceiro": "Parceiro",
}


@dataclass(frozen=True)
class Sessao:
    """Quem está usando o sistema agora.

    É congelada (frozen) porque serve de chave de cache dos indicadores: assim o cache de um
    papel nunca é entregue a outro.
    """

    usuario_id: str
    email: str
    nome: str
    papel: str

    @property
    def papel_legivel(self) -> str:
        return NOMES_DOS_PAPEIS.get(self.papel, self.papel)


class PermissaoNegada(Exception):
    """O papel do usuário não permite a operação."""


class ErroDeValidacao(Exception):
    """Dado inválido, com mensagem pronta para mostrar na tela, em português simples."""


def exige(sessao: Sessao | None, *papeis: str) -> None:
    if sessao is None or sessao.papel not in papeis:
        raise PermissaoNegada("Seu perfil de acesso não permite esta ação.")


def exige_equipe(sessao: Sessao | None) -> None:
    """Admin, Técnico ou Campo: quem registra trabalho de campo."""
    exige(sessao, *EQUIPE)


def exige_identificado(sessao: Sessao | None) -> None:
    """Só Admin e Técnico veem nome, telefone, contato e encaminhamento."""
    exige(sessao, *VE_IDENTIFICADO)


def exige_admin(sessao: Sessao | None) -> None:
    exige(sessao, "admin")


def exige_autenticado(sessao: Sessao | None) -> None:
    exige(sessao, *modelo.PAPEIS)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def senha_confere(senha: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash_guardado.encode())


def senha_provisoria() -> str:
    """Senha fácil de ditar e de digitar no celular, usada uma única vez."""
    letras = "abcdefghjkmnpqrstuvwxyz"  # sem i, l, o: confundem com 1 e 0
    numeros = "23456789"
    sorteio = [secrets.choice(letras) for _ in range(4)] + [
        secrets.choice(numeros) for _ in range(3)
    ]
    return "".join(sorteio)


def registrar_auditoria(con, sessao: Sessao, acao: str, tabela: str, registro_id=None) -> None:
    """Grava o acesso na mesma transação da operação auditada.

    Fica na mesma transação de propósito: se a operação falhar, não existe registro de
    auditoria mentindo que ela aconteceu.
    """
    con.execute(
        insert(modelo.auditoria).values(
            id=modelo.novo_id(),
            usuario_id=sessao.usuario_id,
            acao=acao,
            tabela=tabela,
            registro_id=registro_id,
        )
    )
