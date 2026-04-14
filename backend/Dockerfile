# Contexto: este directorio (backend/), no la raíz del monorepo.
# Desde la raíz del repo:
#   docker build -f backend/Dockerfile -t laneta-backend backend
# Desde backend/:
#   docker build -t laneta-backend .
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app
ENV PORT=8000
ENV RUN_MIGRATIONS_ON_START=true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

EXPOSE 8000

CMD ["/bin/sh", "/app/scripts/start.sh"]
