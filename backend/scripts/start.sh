#!/bin/sh
# Redis siempre dentro de este contenedor. FastAPI + Celery (worker + beat).

set -e
PORT="${PORT:-8000}"

# Ignoramos REDIS_URL del .env: en Docker "localhost" apuntaría al propio contenedor sin servidor,
# y valores vacíos o con comillas rompen el broker de Celery (No such transport: '').
export REDIS_URL="redis://127.0.0.1:6379/0"

echo "Starting Redis (internal) on 127.0.0.1:6379..."
redis-server --save "" --appendonly no --bind 127.0.0.1 --port 6379 &
REDIS_PID=$!

# Espera breve a que Redis responda (evita carrera con Celery)
if command -v redis-cli >/dev/null 2>&1; then
  i=0
  while [ "$i" -lt 50 ]; do
    if redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then
      break
    fi
    i=$((i + 1))
    sleep 0.1
  done
else
  sleep 1
fi

# Crear tablas vía Alembic antes de la API (Supabase sin migraciones → relation "leads" does not exist).
if [ "${RUN_MIGRATIONS_ON_START}" = "true" ]; then
  echo "RUN_MIGRATIONS_ON_START=true — ejecutando alembic upgrade head..."
  alembic upgrade head
fi

echo "Starting API on port $PORT..."
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
UVICORN_PID=$!

echo "Starting Celery worker + beat (bajo consumo)..."
celery -A worker.celery_app.celery worker --beat --loglevel=info --pool=solo --concurrency=1

kill "$UVICORN_PID" 2>/dev/null || true
kill "$REDIS_PID" 2>/dev/null || true
