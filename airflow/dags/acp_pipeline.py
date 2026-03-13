from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "acp",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="acp_pipeline",
    description="Orchestrates ACP bronze -> silver -> gold pipeline",
    default_args=default_args,
    start_date=datetime(2026, 3, 13),
    schedule=None, 
    catchup=False,
    tags=["acp", "aether", "platform"],
) as dag:

    bronze_ingest = BashOperator(
        task_id="bronze_ingest",
        bash_command="cd /opt/airflow/acp && aether bronze ingest odin",
    )

    silver_transform = BashOperator(
        task_id="silver_transform",
        bash_command="cd /opt/airflow/acp && aether silver build odin",
    )

    gold_transform = BashOperator(
        task_id="gold_transform",
        bash_command="cd /opt/airflow/acp && aether gold build odin",
    )

    bronze_ingest >> silver_transform >> gold_transform