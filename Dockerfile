FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV U2NET_HOME=/app/.u2net

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    ca-certificates \
    libvpx-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /opt/venv/bin && \
    printf '#!/bin/sh\nexec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}\n' \
        > /opt/venv/bin/uvicorn && \
    chmod +x /opt/venv/bin/uvicorn

# Pre-download the u2net model so first request is instant
RUN python -c "from rembg import new_session; new_session('u2net')" || true

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
