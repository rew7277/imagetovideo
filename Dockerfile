FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8082
ENV PATH="/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /opt/venv/bin && \
    printf '%s\n' \
'#!/bin/sh' \
'FIXED_ARGS=""' \
'SKIP_NEXT=0' \
'for arg in "$@"; do' \
'  if [ "$SKIP_NEXT" = "1" ]; then' \
'    SKIP_NEXT=0' \
'    continue' \
'  fi' \
'  if [ "$arg" = "--port" ]; then' \
'    FIXED_ARGS="$FIXED_ARGS --port ${PORT:-8082}"' \
'    SKIP_NEXT=1' \
'  elif echo "$arg" | grep -q "PORT"; then' \
'    FIXED_ARGS="$FIXED_ARGS ${PORT:-8082}"' \
'  else' \
'    FIXED_ARGS="$FIXED_ARGS $arg"' \
'  fi' \
'done' \
'exec python -m uvicorn $FIXED_ARGS' \
> /opt/venv/bin/uvicorn && \
    chmod +x /opt/venv/bin/uvicorn && \
    /opt/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8082 --help > /dev/null || true

COPY . .

EXPOSE 8082

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8082}"]