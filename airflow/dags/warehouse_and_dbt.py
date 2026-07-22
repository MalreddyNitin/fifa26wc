from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator

from airflow import DAG

PROJECT = "/opt/airflow/project"
with DAG(
    "warehouse_and_dbt",
    default_args={
        "owner": "world-cup-intelligence",
        "retries": 2,
        "retry_delay": timedelta(minutes=3),
    },
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
) as dag:
    load = BashOperator(
        task_id="load_canonical",
        bash_command=(f"cd {PROJECT} && python scripts/load_warehouse.py"),
    )
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(f"cd {PROJECT} && dbt run --project-dir dbt --profiles-dir dbt"),
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(f"cd {PROJECT} && dbt test --project-dir dbt --profiles-dir dbt"),
    )
    load >> dbt_run >> dbt_test
