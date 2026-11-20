"""Merge certified winning packings for n=501, 505, 556, 798, 990 into current best.
Preserves exact string coordinates and runs official interval arithmetic certification.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "data" / "new_sources" / "alexchilton_starter_kit"))
from ensemble import side, certify
sys.path.insert(0, str(ROOT_DIR / "src" / "metric"))
import metric

def main():
    base_path = ROOT_DIR / "output" / "submission_final.csv"
    out_path = ROOT_DIR / "output" / "submission_22.250374.csv"
    
    print(f"Loading baseline from {base_path}...")
    base_df = pd.read_csv(base_path, dtype=str)
    
    # Packings to update
    updates = {}
    
    # 1. busyaprime: 501, 505, 990
    bp_path = ROOT_DIR / "data" / "latest_sync_1900" / "busyaprime" / "packings.csv"
    bp_df = pd.read_csv(bp_path, dtype=str)
    for n in [501, 505, 990]:
        g = bp_df[bp_df['n'] == str(n)].copy()
        updates[n] = g[['square_id', 'x', 'y', 'angle']].copy()
        print(f"Loaded n={n} from busyaprime ({len(updates[n])} squares)")
        
    # 2. mdm: 556, 798
    mdm_path = ROOT_DIR / "data" / "latest_sync_1900" / "mdmuqtadirfuad" / "portfolio.csv"
    mdm_df = pd.read_csv(mdm_path, dtype=str)
    for n in [556, 798]:
        g = mdm_df[mdm_df['n'] == str(n)].copy()
        updates[n] = g[['square_id', 'x', 'y', 'angle']].copy()
        print(f"Loaded n={n} from MDM ({len(updates[n])} squares)")
        
    # Verify each update with official metric
    for n, u_df in updates.items():
        rows = u_df.to_dict('records')
        n_res, sc, L_str, reason = metric.evaluate_single_puzzle(n, rows)
        if reason != "ok" or L_str is None:
            print(f"ERROR: Update for n={n} is invalid: {reason}")
            return
        print(f"  Verified n={n}: L={L_str}, reason={reason}")

    # Build new dataframe
    rows_list = []
    current_id = 0
    
    for n_str, g in base_df.groupby('n', sort=False):
        n = int(n_str)
        if n in updates:
            up = updates[n]
            # Ensure square_id is 0..n-1
            up = up.sort_values('square_id').reset_index(drop=True)
            for i, r in up.iterrows():
                rows_list.append({
                    'id': str(current_id),
                    'n': str(n),
                    'square_id': str(i),
                    'x': r['x'].strip(),
                    'y': r['y'].strip(),
                    'angle': r['angle'].strip()
                })
                current_id += 1
        else:
            g = g.sort_values('square_id').reset_index(drop=True)
            for i, r in g.iterrows():
                rows_list.append({
                    'id': str(current_id),
                    'n': str(n),
                    'square_id': str(i),
                    'x': r['x'].strip(),
                    'y': r['y'].strip(),
                    'angle': r['angle'].strip()
                })
                current_id += 1

    new_df = pd.DataFrame(rows_list)
    print(f"Total rows assembled: {len(new_df)}")
    assert len(new_df) == 500500, f"Expected 500500 rows, got {len(new_df)}"
    
    new_df.to_csv(out_path, index=False)
    print(f"Saved new submission to {out_path}")
    
    # Fast score check on the 5 updated puzzles vs previous baseline
    print("\n--- Summary of improvements ---")
    score_diff_total = 0.0
    for n in sorted(updates.keys()):
        base_g = base_df[base_df['n'] == str(n)]
        _, _, base_L, _ = metric.evaluate_single_puzzle(n, base_g.to_dict('records'))
        new_g = new_df[new_df['n'] == str(n)]
        _, _, new_L, _ = metric.evaluate_single_puzzle(n, new_g.to_dict('records'))
        
        dL = float(base_L) - float(new_L)
        gain = dL / (n ** 0.5)
        score_diff_total += gain
        print(f"  n={n:3d}: {base_L} -> {new_L} | dL={dL:.6e} | gain={gain:.6e}")
        
    print(f"\nTotal certified score reduction: {score_diff_total:.12f}")
    prev_score = 22.250441015717
    new_score = prev_score - score_diff_total
    print(f"Official Previous Score: {prev_score:.12f}")
    print(f"NEW CERTIFIED RECORD SCORE: {new_score:.12f}")

if __name__ == "__main__":
    main()
