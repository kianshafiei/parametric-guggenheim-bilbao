"""Assemble grasshopper/gugg_bilbao_gh.py (one file to paste into a Grasshopper Python 3 component)
from src/header.py + src/core.py + data/osm_raw.txt + src/rhino_layer.py.

    python tools/build_gh_script.py
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build() -> str:
    header = (ROOT / "src/header.py").read_text(encoding="utf-8")
    core = (ROOT / "src/core.py").read_text(encoding="utf-8")
    core = re.sub(r'^""".*?"""\n', "", core, count=1, flags=re.S)  # drop the module docstring
    data = (ROOT / "data/osm_raw.txt").read_text(encoding="utf-8").strip()
    layer = (ROOT / "src/rhino_layer.py").read_text(encoding="utf-8")
    out = ("#! python3\n" + header + core.rstrip() + "\n\n\n"
           + 'OSM_DATA = """\n' + data + '\n"""\n\n\n' + layer)
    ast.parse(out)
    return out


if __name__ == "__main__":
    target = ROOT / "grasshopper/gugg_bilbao_gh.py"
    target.write_text(build(), encoding="utf-8")
    print("wrote", target.relative_to(ROOT))
