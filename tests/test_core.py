"""Tests for the pure-Python geometry core (no Rhino needed)."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import core  # noqa: E402

DATA = (ROOT / "data/osm_raw.txt").read_text(encoding="utf-8")


def test_parse_reads_every_record():
    recs = core.parse(DATA)
    tags = [t for t, _ in recs]
    assert tags[0] == "M"                       # museum outline first
    assert sum(t.startswith("P") for t in tags) == 20   # 20 building parts
    assert tags.count("B") == 5 and tags.count("Q") == 4


def test_footprint_area_is_plausible():
    outline = core.parse(DATA)[0][1]
    a = abs(core.area(outline))
    assert 11_000 < a < 13_500                  # ~12,200 m2 from OSM


def test_orthogonality_separates_stone_from_titanium():
    m = core.build(DATA)
    assert len(m["stone"]) == 5
    assert len(m["hulls"]) == 15
    for s in m["stone"]:
        assert core.orthogonality(s["poly"]) >= core.STONE_THRESHOLD


def test_sail_sections_close_to_a_ridge():
    m = core.build(DATA)
    secs = m["hulls"][0]["sections"]
    assert len(secs) == 8 + 1                    # n_sec + closing ridge
    assert all(len(s) == len(secs[0]) for s in secs)
    top = max(p[2] for p in secs[-1])
    assert top >= max(p[2] for p in secs[-2])    # ridge sits above the last section


def test_atrium_is_tallest_and_about_fifty_metres():
    m = core.build(DATA)
    z = max(p[2] for h in m["hulls"] for s in h["sections"] for p in s)
    assert 45 < z < 75


def test_rule_parameters_change_the_geometry():
    a = core.build(DATA, {"pinch": 0.2})
    b = core.build(DATA, {"pinch": 0.8})
    wa = max(abs(p[0]) for p in a["hulls"][3]["sections"][-2])
    wb = max(abs(p[0]) for p in b["hulls"][3]["sections"][-2])
    assert not math.isclose(wa, wb)


def test_build_is_deterministic():
    assert core.build(DATA) == core.build(DATA)
