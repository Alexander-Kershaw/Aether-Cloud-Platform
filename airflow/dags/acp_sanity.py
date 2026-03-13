from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="acp_sanity",
    start_date=datetime(2026, 3, 13),
    schedule=None,
    catchup=False,
    tags=["acp"],
) as dag:
    show_repo = BashOperator(
        task_id="show_repo",
        bash_command="""
        echo "=====|Checking ACP repo mount|====="
        cd /opt/airflow/acp
        pwd
        ls -la

        echo "=====|Python version|====="
        python --version

        echo "=====|Try package import|====="
        python -c "import aether; print('aether import OK')"

        echo "=====|Try CLI help|====="
        python -m aether.cli --help
        """,
    )