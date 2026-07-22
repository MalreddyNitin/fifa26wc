from datetime import datetime, timedelta

from airflow.operators.bash import BashOperator

from airflow import DAG

DEFAULTS = {
    "owner": "world-cup-intelligence",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}
PROJECT = "/opt/airflow/project"

with DAG(
    "all_team_ingestion",
    default_args=DEFAULTS,
    start_date=datetime(2026, 1, 1),
    schedule="0 5 * * *",
    catchup=False,
    tags=["ingestion"],
) as dag:
    events_and_metadata = BashOperator(
        task_id="events_and_metadata",
        bash_command=f"cd {PROJECT} && python scripts/run_batch_pipeline.py",
    )
    statistics = BashOperator(
        task_id="statistics",
        bash_command=(f"cd {PROJECT} && python scripts/run_statistics_pipeline.py"),
    )
    canonical = BashOperator(
        task_id="canonical_and_features",
        bash_command=(
            f"cd {PROJECT} && python scripts/build_canonical_and_features.py"
        ),
    )
    lake = BashOperator(
        task_id="lake",
        bash_command=f"cd {PROJECT} && python scripts/materialize_lake.py",
    )
    events_and_metadata >> statistics >> canonical >> lake
