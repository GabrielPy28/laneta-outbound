FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app
ENV PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Windows CRLF en el script rompe el shebang dentro del contenedor Linux ("no such file or directory").
RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

EXPOSE 8000

# Invocar con sh evita depender del shebang si el archivo volviera con CRLF.
CMD ["/bin/sh", "/app/scripts/start.sh"]
