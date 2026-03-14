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
    dag_id="odin_pipeline",
    description="ODIN end-to-end Spark pipeline in ACP",
    default_args=default_args,
    start_date=datetime(2026, 3, 14),
    schedule=None,
    catchup=False,
    tags=["acp", "odin", "spark"],
) as dag:

    ingest_odin_bronze = BashOperator(
        task_id="ingest_odin_bronze",
        bash_command="cd /opt/airflow/acp && python -m aether.cli spark-run scripts/ingest_odin_bronze.py",
    )

    bronze_to_silver_odin = BashOperator(
        task_id="bronze_to_silver_odin",
        bash_command="cd /opt/airflow/acp && python -m aether.cli spark-run scripts/bronze_to_silver_odin.py",
    )

    silver_to_gold_odin = BashOperator(
        task_id="silver_to_gold_odin",
        bash_command="cd /opt/airflow/acp && python -m aether.cli spark-run scripts/silver_to_gold_odin.py",
    )

    validate_odin_gold = BashOperator(
        task_id="validate_odin_gold",
        bash_command='cd /opt/airflow/acp && python -m aether.cli ls gold/odin/carrier_delay_summary',
    )
    

    ingest_odin_bronze >> bronze_to_silver_odin >> silver_to_gold_odin >> validate_odin_gold