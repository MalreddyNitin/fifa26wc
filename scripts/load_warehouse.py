import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "dim_teams_all_historical.parquet": "dim_teams",
    "fct_matches.parquet": "fct_matches",
    "fct_team_matches.parquet": "fct_team_matches",
    "fct_team_match_stats.parquet": "fct_team_match_stats",
}


def main():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://worldcup:worldcup@localhost:5432/worldcup",
    )
    environment = {**os.environ, "DATABASE_URL": database_url}
    for filename, table in TABLES.items():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "warehouse/load_jobs/load_parquet.py"),
                str(ROOT / "data/canonical" / filename),
                "raw",
                table,
            ],
            check=True,
            env=environment,
        )


if __name__ == "__main__":
    main()
