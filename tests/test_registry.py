import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.registry import (  # noqa: E402
    build_aliases,
    load_team_registry,
)


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_team_registry(ROOT / "configs" / "teams.yml")

    def test_registry_has_48_unique_teams(self):
        self.assertEqual(len(self.registry), 48)
        self.assertFalse(self.registry["team_id"].duplicated().any())
        self.assertFalse(self.registry["fifa_code"].duplicated().any())

    def test_all_sofascore_ids_are_resolved(self):
        self.assertFalse(self.registry["sofascore_team_id"].isna().any())
        self.assertFalse(self.registry["sofascore_slug"].isna().any())

    def test_groups_have_four_teams(self):
        group_sizes = self.registry.groupby("world_cup_group").size()
        self.assertEqual(set(group_sizes.index), set("ABCDEFGHIJKL"))
        self.assertTrue(group_sizes.eq(4).all())

    def test_aliases_cover_source_variants(self):
        aliases = build_aliases(self.registry).set_index("source_name")
        self.assertEqual(
            aliases.loc["Korea Republic", "canonical_team_id"],
            "south_korea",
        )
        self.assertEqual(
            aliases.loc["Congo DR", "canonical_team_id"],
            "dr_congo",
        )


if __name__ == "__main__":
    unittest.main()
