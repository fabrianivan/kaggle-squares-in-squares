"""Fast 14-Core Parallel Ensemble & Certification for Today's Fresh Atlas.

Merges:
1. Active baseline: output/submission_22.246775.csv
2. Danil's Living Atlas (22.238567): data/fresh_sync_today/danil/submission_merged.csv
3. az0519 (22.2427): data/fresh_sync_today/az0519/submission.csv
4. jazivxt: data/fresh_sync_today/jazivxt/submission.csv
5. Md Muqtadir Fuad: data/fresh_sync_today/mdm/submission.csv

Steps:
- Fast vectorised numpy evaluation across all sources (100% accurate bounding box)
- Identifies every strictly winning candidate (L_cand < L_cur - 1e-9)
- Certifies all candidate wins via official mpmath interval arithmetic across 14 cores
- Assembles complete certified submission (500,500 rows, 1000 puzzles)
- Validates official metric report and updates records
"""

import math
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric

def compute_sides_fast(csv_path):
    df = pd.read_csv(csv_path)
    groups = df.groupby("n")
    sides = {}
    puzzles_dict = {}
    for n, g in groups:
        x = g["x"].values.astype(float)
        y = g["y"].values.astype(float)
        t = g["angle"].values.astype(float)
        c = np.cos(t) * 0.5
        s = np.sin(t) * 0.5
        
        # 4 corners
        x_c = np.vstack([x + c - s, x - c - s, x - c + s, x + c + s])
        y_c = np.vstack([y + s + c, y - s + c, y - s - c, y + s - c])
        L = max(x_c.max() - x_c.min(), y_c.max() - y_c.min())
        sides[int(n)] = L
        puzzles_dict[int(n)] = g.sort_values("square_id")
    return sides, puzzles_dict

def certify_candidate(args):
    n, rows_dict_list = args
    _, sc, L_str, why = metric.evaluate_single_puzzle(n, rows_dict_list)
    if why == "ok" and L_str is not None:
        return n, float(L_str), L_str, rows_dict_list
    return n, None, None, why

def main():
    print("============================================================")
    print("🚀 Fast Multi-Source Ensemble & Certification Engine")
    print("============================================================\n")

    baseline_csv = ROOT / "output" / "submission_22.246775.csv"
    print(f"Loading baseline: {baseline_csv}...")
    base_sides, base_puzzles = compute_sides_fast(baseline_csv)
    base_score = sum(s / math.sqrt(n) - 1.0 for n, s in base_sides.items())
    print(f"Baseline score: {base_score:.12f}\n")

    sources = {
        "danil_atlas": ROOT / "data" / "fresh_sync_today" / "danil" / "submission_merged.csv",
        "az0519":      ROOT / "data" / "fresh_sync_today" / "az0519" / "submission.csv",
        "jazivxt":     ROOT / "data" / "fresh_sync_today" / "jazivxt" / "submission.csv",
        "mdm":         ROOT / "data" / "fresh_sync_today" / "mdm" / "submission.csv",
    }

    candidates = {}
    for name, path in sources.items():
        if path.exists():
            print(f"Scanning {name} ({path.name})...")
            s_dict, p_dict = compute_sides_fast(path)
            s_score = sum(s / math.sqrt(n) - 1.0 for n, s in s_dict.items())
            print(f"  -> Score: {s_score:.12f}")
            candidates[name] = (s_dict, p_dict)

    # Find candidate wins
    candidate_wins = {}
    for n in range(1, 1001):
        cur_L = base_sides[n]
        best_L = cur_L
        best_src = None
        best_df = None
        for name, (s_dict, p_dict) in candidates.items():
            if n in s_dict and s_dict[n] < best_L - 1e-9:
                best_L = s_dict[n]
                best_src = name
                best_df = p_dict[n]
        if best_src is not None:
            candidate_wins[n] = (best_src, cur_L, best_L, best_df)

    print(f"\nFound {len(candidate_wins)} candidate winning puzzles over baseline!")
    if not candidate_wins:
        print("Baseline is already optimal across all sources.")
        return

    # Prepare jobs for certification
    cert_jobs = []
    for n, (src, cur_L, best_L, df_n) in candidate_wins.items():
        rows = df_n.to_dict("records")
        row_dicts = [{"n": str(r["n"]), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])} for r in rows]
        cert_jobs.append((n, row_dicts))

    print(f"\nCertifying {len(cert_jobs)} puzzles using official mpmath interval metric across 14 cores...")
    t0 = time.time()
    certified_wins = {}
    with ProcessPoolExecutor(max_workers=14) as pool:
        for res in pool.map(certify_candidate, cert_jobs):
            n, cert_L, L_str, why_or_rows = res
            src, cur_L, cand_L, _ = candidate_wins[n]
            if cert_L is not None and cert_L < cur_L - 1e-9:
                gain = (cur_L - cert_L) / math.sqrt(n)
                print(f"  🎉 Certified n={n:3d} ({src}): {cur_L:.9f} -> {cert_L:.9f} (gain: {gain:.6e})")
                certified_wins[n] = (cert_L, why_or_rows)
            else:
                print(f"  ❌ n={n:3d} ({src}): rejection ({why_or_rows})")

    elapsed = time.time() - t0
    print(f"\nCertification completed in {elapsed:.1f}s. Successfully certified {len(certified_wins)}/{len(candidate_wins)} wins.")

    if certified_wins:
        print("\nMerging certified wins into new master submission...")
        base_df = pd.read_csv(baseline_csv, dtype=str)
        updates_dict = {n: rows for n, (_, rows) in certified_wins.items()}

        rows_list = []
        cur_id = 0
        for n_str, g in base_df.groupby("n", sort=False):
            n = int(n_str)
            if n in updates_dict:
                for r in updates_dict[n]:
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                    cur_id += 1
            else:
                for _, r in g.sort_values("square_id", key=lambda c: c.astype(int)).iterrows():
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                    cur_id += 1

        new_df = pd.DataFrame(rows_list)
        temp_csv = ROOT / "output" / "submission_atlas_temp.csv"
        new_df.to_csv(temp_csv, index=False)

        val_json = ROOT / "output" / "validation_report_atlas.json"
        print("Running official validation suite with 14 workers...")
        val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(temp_csv), str(val_json), "--workers", "14"]
        subprocess.run(val_cmd, check=True)

        import json
        rep = json.loads(val_json.read_text())
        score_certified = rep["score"]
        print("\n============================================================")
        print(f"🏆 NEW WORLD RECORD CERTIFIED SCORE: {score_certified:.12f}")
        print(f"Total Gain: {base_score - score_certified:.12f}")
        print("============================================================\n")

        final_csv = ROOT / "output" / f"submission_{score_certified:.6f}.csv"
        new_df.to_csv(final_csv, index=False)
        new_df.to_csv(ROOT / "output" / "submission_final.csv", index=False)
        print(f"Saved to {final_csv} and synced to {ROOT / 'output' / 'submission_final.csv'}")

if __name__ == "__main__":
    main()
