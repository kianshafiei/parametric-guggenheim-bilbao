"""Smoke test: the assembled Grasshopper script runs end to end against a mock RhinoCommon,
and the 'stage' input builds the museum up step by step."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/mock_rhino"))
sys.path.insert(0, str(ROOT / "tools"))

import build_gh_script  # noqa: E402


def run(stage):
    g = {"ghenv": object(), "stage": stage, "__name__": "gh"}
    exec(build_gh_script.build(), g)
    return g


def test_assembled_file_is_up_to_date():
    committed = (ROOT / "grasshopper/gugg_bilbao_gh.py").read_text(encoding="utf-8")
    assert committed == build_gh_script.build(), "run: python tools/build_gh_script.py"


def test_stages_add_elements_in_order():
    s0, s3, s6 = run(0), run(3), run(6)
    assert s0["stone"] == [] and s0["titanium"] == [] and s0["ground"] == []
    assert len(s3["stone"]) == 5 and s3["titanium"] == []
    assert len(s6["titanium"]) == 18 and s6["glass"]
    assert s6["info"].startswith("Step 6")
