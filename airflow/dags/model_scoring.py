from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator

from airflow import DAG

PROJECT = "/opt/airflow/project"
with DAG(
    "model_scoring",
    default_args={
        "owner": "world-cup-intelligence",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
) as dag:
    train_and_score = BashOperator(
        task_id="train_and_score",
        bash_command=f"cd {PROJECT} && python scripts/train_models.py",
    )
