import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script, *arguments):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ingestion", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.skip_ingestion:
        run("run_batch_pipeline.py")
        run(
            "run_statistics_pipeline.py",
            *(["--max-events", "50"] if args.demo else []),
        )
    run("build_canonical_and_features.py")
    run("materialize_lake.py")
    run("train_models.py")
    run("build_odds_outputs.py")
    run(
        "simulate_tournament.py",
        "--simulations",
        "1000" if args.demo else "50000",
    )
    run("run_monitoring.py")
    run("build_final_report.py")


if __name__ == "__main__":
    main()
