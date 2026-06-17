FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMIFY_DATA_DIR=data \
    STREAMIFY_RAW_DIR=data/raw/yamusic \
    STREAMIFY_DUCKDB_PATH=data/streamify.duckdb
