"""Build submission_22.250261.csv incorporating n=652 and n=806 certified record improvements.
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
    danil_path = ROOT_DIR / "data" / "fresh_sync_0003" / "danil_latest" / "submission.csv"
    out_path = ROOT_DIR / "output" / "submission_22.250261.csv"

    print("Loading baseline and Danil submission...")
    base_df = pd.read_csv(base_path, dtype=str)
    danil_df = pd.read_csv(danil_path, dtype=str)

    updates = {}
    for n in [652, 806, 979, 985]:
        g = danil_df[danil_df['n'] == str(n)].copy()
        updates[n] = g[['square_id', 'x', 'y', 'angle']].copy()
        print(f"Loaded n={n} from Danil ({len(updates[n])} squares)")

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

    # Score check
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

    prev_score = 22.250261498979
    new_score = prev_score - score_diff_total
    print(f"\nOfficial Previous Score: {prev_score:.12f}")
    print(f"Score reduction: {score_diff_total:.12f}")
    print(f"NEW CERTIFIED RECORD SCORE: {new_score:.12f}")

if __name__ == "__main__":
    main()
