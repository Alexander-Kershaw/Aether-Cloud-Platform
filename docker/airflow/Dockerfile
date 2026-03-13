FROM apache/airflow:2.10.5

WORKDIR /opt/airflow/acp

COPY --chown=airflow:root pyproject.toml /opt/airflow/acp/pyproject.toml
COPY --chown=airflow:root aether /opt/airflow/acp/aether

USER airflow

RUN pip install --no-cache-dir /opt/airflow/acp