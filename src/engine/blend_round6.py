"""Blend Round 6 Verified Improvements into Candidate Submission.

Integrates certified improvements for:
- n=641 (gain +2.06e-06)
- n=805 (gain +1.92e-06)
- n=855 (gain +8.08e-06)
Plus any additions from tmp/deep_quench_out.
"""

import os
import sys
import glob
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

def main():
    base_path = os.path.join(ROOT, "output/submission_final.csv")
    out_path = os.path.join(ROOT, "output/submission_round6.csv")

    df = pd.read_csv(base_path)
    print(f"Loaded base submission: {len(df)} rows")

    replacements = {
        641: os.path.join(ROOT, "tmp/quench_large_out/641.csv"),
        805: os.path.join(ROOT, "tmp/quench_combined_out/805.csv"),
        855: os.path.join(ROOT, "tmp/quench_new_out/855.csv"),
    }

    # Also check if any new files in tmp/deep_quench_out
    deep_files = glob.glob(os.path.join(ROOT, "tmp/deep_quench_out/*.csv"))
    for f in deep_files:
        base = os.path.basename(f)
        if base.endswith(".csv") and base[:-4].isdigit():
            n = int(base[:-4])
            replacements[n] = f

    total_gain = 0.0

    for n, cand_file in sorted(replacements.items()):
        sub_base = df[df['n'] == n].sort_values('square_id')
        recs_base = [
            {'square_id': int(r['square_id']), 'x': str(r['x']), 'y': str(r['y']), 'angle': str(r['angle'])}
            for _, r in sub_base.iterrows()
        ]
        _, s_b, L_b, r_b = metric.evaluate_single_puzzle(n, recs_base)

        df_cand = pd.read_csv(cand_file).sort_values('square_id')
        recs_cand = [
            {'square_id': int(r['square_id']), 'x': str(r['x']), 'y': str(r['y']), 'angle': str(r['angle'])}
            for _, r in df_cand.iterrows()
        ]
        _, s_c, L_c, r_c = metric.evaluate_single_puzzle(n, recs_cand)

        if r_c == "ok" and float(L_c) < float(L_b) - 1e-9:
            dL = float(L_b) - float(L_c)
            gain = dL / (n**0.5)
            total_gain += gain
            print(f"n={n}: L {L_b} -> {L_c} (dL = {dL:.8f}, gain = {gain:.2e}) [CERTIFIED]")

            # Replace in dataframe
            mask = (df['n'] == n)
            df_cand_sorted = df_cand.sort_values('square_id').reset_index(drop=True)
            df.loc[mask, 'x'] = df_cand_sorted['x'].values
            df.loc[mask, 'y'] = df_cand_sorted['y'].values
            df.loc[mask, 'angle'] = df_cand_sorted['angle'].values
        else:
            print(f"n={n}: no improvement or not certified (reason={r_c})")

    # Clean and reindex
    df = df.sort_values(['n', 'square_id']).reset_index(drop=True)
    df['id'] = np.arange(len(df))
    df = df[['id', 'n', 'square_id', 'x', 'y', 'angle']]

    assert len(df) == 500500, f"Expected 500500 rows, got {len(df)}"
    assert list(df['id']) == list(range(500500)), "IDs are not sequential 0..500499"

    df.to_csv(out_path, index=False)
    print(f"Successfully saved {len(df)} rows to {out_path}")
    print(f"Total verified score reduction in this round: {total_gain:.10e}")

if __name__ == "__main__":
    main()
