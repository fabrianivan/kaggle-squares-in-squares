"""Assemble the final complete submission (all 500500 rows).

Steps:
  1. Precision-preserving union of all CSV sources, folding the CPU patch
     (``output/cpu_patch.npz``) if present.
  2. Fill any grid-fallback puzzles (omitted by build_portfolio) with the
     actual integer-grid packing so the file has every n=1..1000.

Run from the workspace root:
    python src/tools/assemble_final.py [--patch output/cpu_patch.npz]
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import numpy as np  # noqa: E402
import portfolio_union  # noqa: E402

BASE = TOOLS.parent.parent
OUT = BASE / "output"

SOURCES = {
    "baseline": str(BASE / "data" / "submission_merged_22.253319.csv"),
    "aleksandr": str(BASE / "data" / "external_packings" / "kaggle_public_candidate_20261102.csv"),
    "notebook": str(OUT / "notebook_packings.csv"),
}


def grid(n):
    k = math.ceil(math.sqrt(n))
    return np.array([(i % k + 0.5, i // k + 0.5, 0.0) for i in range(n)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", default=str(OUT / "cpu_patch.npz"))
    ap.add_argument("--out", default=str(OUT / "submission_final.csv"))
    args = ap.parse_args()

    patch = args.patch if Path(args.patch).exists() else None
    if patch:
        print(f"Folding CPU patch: {patch}")
    else:
        print("No CPU patch found; union only.")

    union_csv = OUT / "_union_patched.csv"
    summary = portfolio_union.build_portfolio(
        source_paths=SOURCES,
        leader_name="baseline",
        output_path=str(union_csv),
        patch_path=patch,
    )
    print(f"union score (float64): {summary['score']:.10f}")
    print(f"  leader baseline:      {summary['leader_score']:.10f}")
    print(f"  gain vs baseline:     {summary['leader_score'] - summary['score']:.10f}")

    # Now fill grid-fallback puzzles.  Read the union CSV, find which n are
    # present, and write the final file with grid rows inserted for the rest.
    present = set()
    with open(union_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows_by_n = {}
        for row in reader:
            n = int(row["n"])
            present.add(n)
            rows_by_n.setdefault(n, []).append(
                [row["square_id"], row["x"], row["y"], row["angle"]]
            )

    missing = [n for n in range(1, 1001) if n not in present]
    print(f"present puzzles: {len(present)}  missing (grid fill): {len(missing)}")

    rid = 0
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "n", "square_id", "x", "y", "angle"])
        for n in range(1, 1001):
            if n in rows_by_n:
                for sid, x, y, ang in rows_by_n[n]:
                    w.writerow([rid, n, sid, x, y, ang])
                    rid += 1
            else:
                p = grid(n)
                for sid in range(n):
                    w.writerow([rid, n, sid, repr(float(p[sid, 0])),
                                 repr(float(p[sid, 1])), repr(float(p[sid, 2]))])
                    rid += 1

    print(f"\nFinal submission: {args.out}")
    print(f"Total rows: {rid} (expected 500500)")
    assert rid == 500500, f"row count mismatch: {rid}"

    # Persist a small manifest of CPU wins if available.
    wins_path = OUT / "cpu_wins.json"
    if wins_path.exists():
        wins = json.loads(wins_path.read_text())
        cpu_gain = sum(v["gain"] for v in wins.values())
        print(f"CPU certified wins: {len(wins)} puzzles, est. gain {cpu_gain:.10f}")

    (OUT / "final_summary.json").write_text(json.dumps({
        "union_score_float64": summary["score"],
        "baseline_score_float64": summary["leader_score"],
        "rows": rid,
        "patch_used": bool(patch),
    }, indent=2))


if __name__ == "__main__":
    main()
