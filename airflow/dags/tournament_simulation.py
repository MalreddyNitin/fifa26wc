from datetime import datetime

from airflow.operators.bash import BashOperator

from airflow import DAG

PROJECT = "/opt/airflow/project"
with DAG(
    "tournament_simulation",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
) as dag:
    simulate = BashOperator(
        task_id="simulate_50000",
        bash_command=(
            f"cd {PROJECT} && python scripts/simulate_tournament.py --simulations 50000"
        ),
    )
