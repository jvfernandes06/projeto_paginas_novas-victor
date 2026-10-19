#!/bin/sh
# Sobe o app: primeiro deixa o banco na versão certa, depois (se pedido) cria os dados de
# demonstração, e só então abre o Streamlit.
set -e

echo "Atualizando o banco..."
alembic upgrade head

if [ "$PN_SEED_DEMO" = "1" ]; then
  echo "Criando dados de demonstração (não faz nada se já houver dados)..."
  python scripts/seed_demo.py
fi

echo "Abrindo o app em http://localhost:8501"
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
