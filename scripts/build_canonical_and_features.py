import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.canonical import materialize_canonical  # noqa: E402
from world_cup_intelligence.features.build import materialize_features  # noqa: E402


def main():
    dims, matches, team_matches, stats = materialize_canonical(ROOT)
    print(
        f"canonical: teams={len(dims):,}, matches={len(matches):,}, "
        f"team_matches={len(team_matches):,}, stats={len(stats):,}"
    )
    features, coverage = materialize_features(ROOT)
    print(
        f"features: rows={len(features):,}, columns={len(features.columns):,}, "
        f"documented_features={len(coverage):,}"
    )


if __name__ == "__main__":
    main()
