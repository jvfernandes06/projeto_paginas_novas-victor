# Imagem do app. Um processo só: o banco é um arquivo SQLite, e dois processos
# escrevendo no mesmo arquivo corrompem o banco.
FROM python:3.11-slim

WORKDIR /app

# As dependências vêm antes do código para o Docker reaproveitar a camada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O banco e os backups ficam no volume, fora da imagem.
ENV PN_BANCO=/dados/paginas_novas.db \
    PYTHONUNBUFFERED=1

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

ENTRYPOINT ["sh", "docker/entrada.sh"]
