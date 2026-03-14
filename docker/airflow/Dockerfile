FROM apache/airflow:2.10.5

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/airflow/acp

COPY --chown=airflow:root pyproject.toml /opt/airflow/acp/pyproject.toml
COPY --chown=airflow:root aether /opt/airflow/acp/aether

USER airflow

RUN pip install --no-cache-dir /opt/airflow/acp