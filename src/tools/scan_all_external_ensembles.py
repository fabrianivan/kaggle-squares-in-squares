"""Scan all external submissions in data/new_sources against current submission.

If any external submission has a strictly smaller certified side length for ANY puzzle n,
report it and optionally blend into a new submission.
"""

import glob
import math
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))
sys.path.insert(0, str(ROOT / "src" / "metric"))

import fault_dp as F
from ensemble import side, certify
import metric

CURRENT_SUB = ROOT / "output" / "submission_22.248338.csv"

def main():
    print(f"Loading current baseline: {CURRENT_SUB}")
    cur = F.load_csv(str(CURRENT_SUB))
    cur_sides = {n: side(cur[n]) for n in cur}
    for n in range(1, 1001):
        if n not in cur_sides:
            cur_sides[n] = float(math.ceil(math.sqrt(n)))

    # Find candidate CSV files
    candidates = [
        "data/new_sources/lucifer/submission.csv",
        "data/new_sources/lucifer/v31_anchor.csv",
        "data/new_sources/lucifer/v30_anchor.csv",
        "data/new_sources/kmmmvs_latest/submission.csv",
        "data/new_sources/kmmmvs_best/submission.csv",
        "data/new_sources/danil_v52/submission.csv",
        "data/new_sources/danil_latest/submission.csv",
        "data/new_sources/nilanjan/submission.csv",
        "data/new_sources/saamhm/submission.csv",
        "data/new_sources/jazivxt_boxed/submission.csv",
        "data/new_sources/alexchilton/submission.csv",
        "data/new_sources/alexchilton_updated/best_current.csv",
        "data/new_sources/prvsiyan/submission.csv",
        "data/new_sources/emptydaboi/submission.csv",
        "data/new_sources/more_datasets/best_submission.csv",
    ]

    all_improvements = {} # n -> (best_L, best_text, source_file)

    for cpath in candidates:
        p = ROOT / cpath
        if not p.exists():
            continue
        print(f"\nScanning: {cpath} ...")
        try:
            cand_dict = F.load_csv(str(p))
        except Exception as e:
            print(f"  Error reading {cpath}: {e}")
            continue

        file_wins = 0
        for n, sq in cand_dict.items():
            if n < 1 or n > 1000:
                continue
            s_cand = side(sq)
            s_curr = cur_sides[n]
            if s_cand < s_curr - 1e-9:
                # Certify with official interval arithmetic metric
                ok, s_cert, text = certify(n, sq)
                if ok and s_cert < s_curr - 1e-9:
                    current_best = all_improvements[n][0] if n in all_improvements else s_curr
                    if s_cert < current_best - 1e-9:
                        gain = (s_curr - s_cert) / math.sqrt(n)
                        print(f"  🎉 FOUND CERTIFIED WIN on n={n}: {s_curr:.9f} -> {s_cert:.9f} (gain: {gain:.2e}) from {p.name}")
                        all_improvements[n] = (s_cert, text, str(p))
                        file_wins += 1

        print(f"  Total winning puzzles from {p.name}: {file_wins}")

    print("\n" + "=" * 60)
    print(f"Total puzzle wins across all external sources: {len(all_improvements)}")
    total_score_gain = 0.0
    for n, (s_win, _, src) in sorted(all_improvements.items()):
        gain = (cur_sides[n] - s_win) / math.sqrt(n)
        total_score_gain += gain
        print(f"n={n:3d}: {cur_sides[n]:.9f} -> {s_win:.9f} (gain: {gain:.4e}) [{Path(src).name}]")

    print(f"Total potential score reduction: {total_score_gain:.8f}")

    if all_improvements:
        print("\nMerging external wins into new submission...")
        base_df = pd.read_csv(str(CURRENT_SUB), dtype=str)
        updates_dict = {n: text for n, (_, text, _) in all_improvements.items()}

        rows_list = []
        cur_id = 0
        for n_str, g in base_df.groupby("n", sort=False):
            n = int(n_str)
            if n in updates_dict:
                for i, (a, b, t) in enumerate(updates_dict[n]):
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(i), "x": str(a), "y": str(b), "angle": str(t)})
                    cur_id += 1
            else:
                for _, r in g.sort_values("square_id", key=lambda c: c.astype(int)).iterrows():
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                    cur_id += 1

        new_df = pd.DataFrame(rows_list)
        out_csv = ROOT / "output" / "submission_external_merged.csv"
        new_df.to_csv(out_csv, index=False)
        print(f"Saved merged submission to {out_csv}")

        val_json = ROOT / "output" / "validation_report_external_merged.json"
        val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json)]
        subprocess.run(val_cmd, check=True)
        print(f"Validation complete! Report saved to {val_json}")

if __name__ == "__main__":
    main()
