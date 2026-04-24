FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PATH="/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/venv/bin"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r requirements.txt

# Railway may still try old Nixpacks path: /opt/venv/bin/uvicorn.
# This wrapper makes that old command valid even in Docker deployments.
RUN mkdir -p /opt/venv/bin && \
    printf '#!/bin/sh\nexec python -m uvicorn "$@"\n' > /opt/venv/bin/uvicorn && \
    chmod +x /opt/venv/bin/uvicorn

COPY . .

RUN chmod +x /app/start.sh

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
