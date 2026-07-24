import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _package_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[]", requirement, maxsplit=1)[0].strip().lower()


def test_streamlit_requirements_include_all_base_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    base_dependencies = {
        _package_name(requirement) for requirement in project["project"]["dependencies"]
    }
    deployment_dependencies = {
        _package_name(line)
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert base_dependencies <= deployment_dependencies
