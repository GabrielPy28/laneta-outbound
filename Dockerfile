# Contexto: raíz del monorepo (Railway por defecto). Build: docker build -f Dockerfile .
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app
ENV PORT=8000

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

EXPOSE 8000

CMD ["/bin/sh", "/app/scripts/start.sh"]
