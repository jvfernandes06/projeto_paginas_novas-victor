"""Aviso de que os dados mudaram.

Os indicadores ficam em cache por pouco tempo para o dashboard não consultar o banco a cada
rerun do Streamlit. Toda gravação feita pelo app chama `limpar()`, então quem acabou de
registrar algo vê o número novo na hora, sem esperar o intervalo de atualização.
"""

import streamlit as st


def limpar() -> None:
    st.cache_data.clear()
