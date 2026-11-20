"""Sweep optimal global rotation over every puzzle and keep certified wins.

The official metric measures the axis-aligned bounding square, so a packing
submitted at a non-optimal global angle wastes score.  This finds, for every
puzzle, the rotation minimizing the bounding square and keeps it when it beats
the current one (certified by the pinned official metric).

Wins are written to a patch npz compatible with ``portfolio_union``.

Usage (from workspace root):
    python src/tools/rotation_sweep.py [--baseline output/submission_union.csv]
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "reference_sources"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import packing_geometry as pg  # noqa: E402
import official_metric as metric  # noqa: E402

BASE = TOOLS.parent.parent


def grid(n):
    k = math.ceil(math.sqrt(n))
    return np.array([(i % k + 0.5, i // k + 0.5, 0.0) for i in range(n)])


def certify(n, q):
    rows = [
        {"n": str(n), "square_id": str(i),
         "x": format(float(q[i, 0]), ".17g"),
         "y": format(float(q[i, 1]), ".17g"),
         "angle": format(float(q[i, 2]), ".17g")}
        for i in range(len(q))
    ]
    _, _s, L_text, reason = metric.evaluate_single_puzzle(n, rows)
    return float(L_text) if reason == "ok" and L_text is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=str(BASE / "output" / "submission_union.csv"))
    ap.add_argument("--patch-out", default=str(BASE / "output" / "cpu_patch.npz"))
    args = ap.parse_args()

    print(f"Loading baseline: {args.baseline}")
    bank = {n: grid(n) for n in range(1, 1001)}
    df = pd.read_csv(args.baseline)
    for n, g in df.groupby("n"):
        n = int(n)
        bank[n] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    wins = {}
    start = time.perf_counter()
    for n in range(1, 1001):
        p = bank[n]
        L0 = pg.side(p)
        # Skip perfect-square grid packings (already optimal, score 0).
        if L0 <= math.sqrt(n) + 1e-9:
            continue
        try:
            q_rot, ang = pg.optimal_rotation(p)
        except Exception:
            continue
        L1 = pg.side(q_rot)
        if L1 < L0 - 1e-8:
            # Certify the rotated packing.
            L_cert = certify(n, q_rot)
            if L_cert is not None and L_cert < L0 - 1e-8:
                wins[n] = q_rot
                gain = (L0 - L_cert) / math.sqrt(n)
                print(f"  WIN n={n:4d}: {L0:.10f} -> {L_cert:.10f} "
                      f"(rot {ang:+.5f}, gain {gain:.10f})", flush=True)
        if n % 200 == 0:
            print(f"  ... scanned to n={n}, {len(wins)} wins, "
                  f"{time.perf_counter()-start:.0f}s", flush=True)

    print(f"\n=== rotation sweep: {len(wins)} certified wins "
          f"in {time.perf_counter()-start:.0f}s ===")
    if wins:
        # Merge with any existing patch.
        patch_path = Path(args.patch_out)
        existing = {}
        if patch_path.exists():
            with np.load(patch_path) as z:
                for key in z.files:
                    existing[int(key)] = z[key]
        for n, q in wins.items():
            # Keep whichever is better (certified already for new wins; for
            # existing entries assume they were certified).
            if n not in existing or pg.side(q) < pg.side(existing[n]):
                existing[n] = q
        pg.save_bank(str(patch_path), existing)
        total_gain = sum((pg.side(bank[n]) - pg.side(wins[n])) / math.sqrt(n)
                         for n in wins)
        print(f"patch written: {patch_path}  (est. gain {total_gain:.10f})")
        Path(BASE / "output" / "rotation_wins.json").write_text(json.dumps(
            {str(n): {"gain": (pg.side(bank[n]) - pg.side(wins[n])) / math.sqrt(n),
                       "L0": pg.side(bank[n]), "L1": pg.side(wins[n])}
             for n in wins}, indent=2))
    else:
        print("no wins; patch unchanged")


if __name__ == "__main__":
    main()
