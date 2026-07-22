import argparse
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def load_parquet(path, schema, table, database_url):
    engine = create_engine(database_url)
    load_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    frame = pd.read_parquet(path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE raw.load_audit SET finished_at=:started,"
                "status='interrupted',error_message='superseded by retry' "
                "WHERE dataset_name=:name AND status='running'"
            ),
            {"started": started, "name": f"{schema}.{table}"},
        )
        connection.execute(
            text(
                "INSERT INTO raw.load_audit "
                "(load_id,dataset_name,started_at,status) "
                "VALUES (:id,:name,:started,'running')"
            ),
            {
                "id": load_id,
                "name": f"{schema}.{table}",
                "started": started,
            },
        )
    try:
        # dbt views bind to the raw table object. A snapshot refresh therefore
        # has to invalidate those views explicitly; the next DAG task rebuilds
        # the complete dbt graph. This keeps reruns idempotent even after dbt
        # has already materialized downstream relations.
        with engine.begin() as connection:
            connection.execute(
                text(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE')
            )
        frame.to_sql(
            table,
            engine,
            schema=schema,
            if_exists="append",
            index=False,
            chunksize=1_000,
            method=None,
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE raw.load_audit SET finished_at=:finished,"
                    "row_count=:rows,status='success' WHERE load_id=:id"
                ),
                {
                    "finished": datetime.now(timezone.utc),
                    "rows": len(frame),
                    "id": load_id,
                },
            )
    except Exception as exc:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE raw.load_audit SET finished_at=:finished,"
                    "status='failed',error_message=:error WHERE load_id=:id"
                ),
                {
                    "finished": datetime.now(timezone.utc),
                    "error": repr(exc),
                    "id": load_id,
                },
            )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("schema")
    parser.add_argument("table")
    args = parser.parse_args()
    load_parquet(
        args.path,
        args.schema,
        args.table,
        os.environ["DATABASE_URL"],
    )
