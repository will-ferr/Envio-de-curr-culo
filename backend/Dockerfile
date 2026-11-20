# syntax=docker/dockerfile:1
# Imagem oficial do Playwright: já traz o Chromium e as bibliotecas de sistema para gerar PDFs.
# A versão precisa bater com a do pacote `playwright` (pyproject.toml).
FROM mcr.microsoft.com/playwright/python:v1.65.2-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

# Dependências primeiro (camada em cache enquanto o pyproject não muda).
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install . && rm -rf app

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-deps . \
 && mkdir -p /data && chown -R pwuser:pwuser /data

# Usuário sem privilégios (já existe na imagem base).
USER pwuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
