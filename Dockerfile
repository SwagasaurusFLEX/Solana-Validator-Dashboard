FROM apache/airflow:2.9.3-python3.11

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements_docker.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt