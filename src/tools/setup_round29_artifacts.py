"""Synthesize the artifacts/ tree the round29 pipeline expects, from our union.

Creates:
  artifacts/round29_submission.csv   = the precision-preserving union submission
  artifacts/round29_summary.json      = minimal valid summary
  artifacts/round29_union_scan.json   = {wins, new_leader_changes} target lists

Targets (the union scan) = every sub-grid puzzle (beats the integer grid), so the
complement search has the widest pool.  Puzzles that already match the grid are
skipped (no room).

Run from the workspace root:
    python src/tools/setup_round29_artifacts.py
"""

import json
import math
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import packing_geometry as pg  # noqa: E402

BASE = TOOLS.parent.parent
ART = BASE / "artifacts"
OUT = BASE / "output"


def grid(n):
    k = math.ceil(math.sqrt(n))
    return np.array([(i % k + 0.5, i // k + 0.5, 0.0) for i in range(n)])


def main():
    ART.mkdir(parents=True, exist_ok=True)
    union_csv = OUT / "submission_union.csv"
    assert union_csv.exists(), "run make_union.py first"

    # Copy union as the round29 submission (load_bank fills grid for missing n).
    shutil.copy(union_csv, ART / "round29_submission.csv")
    print(f"round29_submission.csv <- union ({union_csv.stat().st_size} bytes)")

    # Build the bank to classify sub-grid puzzles.
    bank = {n: grid(n) for n in range(1, 1001)}
    df = pd.read_csv(union_csv)
    for n, g in df.groupby("n"):
        n = int(n)
        bank[n] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    sub_grid = []
    for n in range(1, 1001):
        L = pg.side(bank[n])
        if L < math.ceil(math.sqrt(n)) - 1e-6:
            sub_grid.append(n)
    print(f"sub-grid puzzles: {len(sub_grid)}")

    # wins = sub-grid puzzles (high-priority targets); new_leader_changes = same
    # (the complement search dedups and slices [:60] for the second list).
    scan = {
        "wins": [{"n": n} for n in sub_grid],
        "new_leader_changes": [{"n": n} for n in sub_grid],
    }
    (ART / "round29_union_scan.json").write_text(json.dumps(scan))
    (ART / "round29_summary.json").write_text(json.dumps({
        "score": 22.2516024080,
        "leader_score": 22.2533185532,
        "submitted_ns": sub_grid,
    }))
    print(f"round29_union_scan.json: {len(sub_grid)} targets")
    print("artifacts ready for run_round29_complement_search.py")


if __name__ == "__main__":
    main()
