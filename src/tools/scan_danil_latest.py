"""Scan Danil latest submission for certified improvements against our current baseline (22.250261).
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
    
    if not danil_path.exists() or danil_path.stat().st_size == 0:
        print("Danil submission.csv not ready yet.")
        return

    print("Loading baseline and Danil submission...")
    base_df = pd.read_csv(base_path, dtype=str)
    danil_df = pd.read_csv(danil_path, dtype=str)
    
    base = {}
    for n_str, g in base_df.groupby('n'):
        base[int(n_str)] = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)

    wins = []
    for n_str, g in danil_df.groupby('n'):
        n = int(n_str)
        if n not in base:
            continue
        cand_sq = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
        s_base = side(base[n])
        s_cand = side(cand_sq)
        
        if s_cand < s_base - 1e-8:
            r = certify(n, cand_sq)
            if r is not None and r[0] < s_base - 1e-8:
                gain = (s_base - r[0]) / (n ** 0.5)
                print(f"*** CERTIFIED WIN for n={n} ***: {s_base:.12f} -> {r[0]:.12f} (gain: {gain:.6e})")
                wins.append((n, r[0], s_base, gain, g))

    print(f"\nTotal certified wins: {len(wins)}")
    if wins:
        tot_gain = sum(w[3] for w in wins)
        print(f"Total score gain: {tot_gain:.10f}")
        print(f"New score: {22.250261498979 - tot_gain:.10f}")

if __name__ == "__main__":
    main()
