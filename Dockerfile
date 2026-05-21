FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints-docker.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -c constraints-docker.txt -r requirements.txt

COPY requirements-dev.txt .
RUN python -m pip install -r requirements-dev.txt

COPY . .

CMD ["python", "--version"]
