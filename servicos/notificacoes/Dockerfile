# o build roda a partir da raiz do repositório (por causa da pasta comum/)
FROM python:3.12-slim

# não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 helpdesk

WORKDIR /srv
COPY servicos/notificacoes/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comum ./comum
COPY servicos/notificacoes/app ./app

USER helpdesk
ENV EXIGIR_SEGREDO=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/saude', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
