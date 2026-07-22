import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def statistics_payload():
    return {
        "statistics": [
            {
                "period": "ALL",
                "groups": [
                    {
                        "groupName": "Match overview",
                        "statisticsItems": [
                            {
                                "name": "Ball possession",
                                "home": "52%",
                                "away": "48%",
                            }
                        ],
                    }
                ],
            }
        ]
    }
