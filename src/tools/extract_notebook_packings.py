"""Extract Danil + PJ notebook packings into a full 1000-puzzle submission CSV.

The notebooks store packings as float64 arrays (Danil via lzma+base64 blob,
PJ via a Python dict).  We emit every puzzle n=1..1000; puzzles not present in
either notebook fall back to the integer grid so the file is a valid standalone
submission and can be unioned with the other CSV sources.

Usage:
    python extract_notebook_packings.py <output_csv>
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent.parent  # workspace root
NB_DIR = BASE / "data" / "external_packings"


def grid(n):
    k = math.ceil(math.sqrt(n))
    return np.array([(i % k + 0.5, i // k + 0.5, 0.0) for i in range(n)])


def load_danil():
    """Return {n: (n,3) float64 array} from the living-atlas notebook cell 22."""
    packings = {}
    path = NB_DIR / "squares-in-squares-living-atlas-of-tight-packings.ipynb"
    if not path.exists():
        print(f"[danil] notebook not found: {path}")
        return packings
    import base64
    import lzma

    with open(path) as f:
        nb = json.load(f)
    scope = {}
    exec("".join(nb["cells"][22]["source"]), scope)
    matrix = np.frombuffer(
        lzma.decompress(base64.b64decode(scope["REPLAY_B64"])), dtype="<f8"
    ).reshape(3, -1).T
    offset = 0
    for n in scope["REPLAY_NS"]:
        packings[int(n)] = matrix[offset : offset + n].copy()
        offset += n
    print(f"[danil] loaded {len(packings)} packings")
    return packings


def load_pj():
    """Return {n: (n,3) float64 array} from the three-records notebook cell 3."""
    packings = {}
    path = NB_DIR / "three-square-packings-that-beat-the-records.ipynb"
    if not path.exists():
        print(f"[pj] notebook not found: {path}")
        return packings
    with open(path) as f:
        nb = json.load(f)
    scope = {}
    exec("".join(nb["cells"][3]["source"]), scope)
    for n, coords in scope["PACKINGS"].items():
        packings[int(n)] = np.array(coords, dtype=float)
    print(f"[pj] loaded {len(packings)} packings: {sorted(packings)}")
    return packings


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "output" / "notebook_packings.csv"
    danil = load_danil()
    pj = load_pj()

    # Per-puzzle best across notebooks (float64 side estimate).
    def side(p):
        c = np.cos(p[:, 2])
        s = np.sin(p[:, 2])
        h = (np.abs(c) + np.abs(s)) / 2
        lo = p[:, :2] - h[:, None]
        hi = p[:, :2] + h[:, None]
        return float(np.max(hi.max(0) - lo.min(0)))

    chosen = {}
    for n in range(1, 1001):
        cand = {}
        if n in danil:
            cand["danil"] = danil[n]
        if n in pj:
            cand["pj"] = pj[n]
        if cand:
            chosen[n] = min(cand.values(), key=side)
        else:
            chosen[n] = grid(n)

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "n", "square_id", "x", "y", "angle"])
        rid = 0
        for n in range(1, 1001):
            p = chosen[n]
            for sid in range(n):
                w.writerow([rid, n, sid, format(float(p[sid, 0]), ".17g"),
                            format(float(p[sid, 1]), ".17g"),
                            format(float(p[sid, 2]), ".17g")])
                rid += 1
    print(f"[extract] wrote {rid} rows to {out}")


if __name__ == "__main__":
    main()
