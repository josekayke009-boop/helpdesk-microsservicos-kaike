# build a partir da raiz (usa comum/seguranca_http.py)
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 helpdesk

WORKDIR /srv
COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comum ./comum
COPY gateway/app ./app
COPY gateway/web ./web

USER helpdesk
ENV WEB_DIR=/srv/web PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/app.js', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
