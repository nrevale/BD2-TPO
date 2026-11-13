FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# El código se monta en /workspace; con PYTHONPATH alcanza `python -m farmared` sin instalar el paquete.
ENV PYTHONPATH=/workspace/src \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
