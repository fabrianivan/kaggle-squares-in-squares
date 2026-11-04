"""Blend Round 5 Record Improvements into Final Submission.

Integrates certified improvements for:
- n=546 (dL = 0.00005461, score gain = 2.34e-06)
- n=913 (dL = 0.00213154, score gain = 7.05e-05)
- n=975 (dL = 0.00213154, score gain = 6.83e-05)

Total verified score gain: +0.0001411444
"""

import os
import sys
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

def main():
    base_path = os.path.join(ROOT, "output/submission_final.csv")
    out_path = os.path.join(ROOT, "output/submission_22.250111.csv")
    final_path = os.path.join(ROOT, "output/submission_final.csv")

    df = pd.read_csv(base_path)
    print(f"Loaded base submission: {len(df)} rows")

    replacements = {
        546: os.path.join(ROOT, "tmp/quench_out/546.csv"),
        913: os.path.join(ROOT, "tmp/quench_med_out/913.csv"),
        975: os.path.join(ROOT, "tmp/quench_med_out/975.csv"),
    }

    total_gain = 0.0

    for n, cand_file in replacements.items():
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

        assert r_c == "ok", f"Puzzle n={n} failed certification: {r_c}"
        assert float(L_c) < float(L_b), f"Puzzle n={n} did not improve side: {L_c} vs {L_b}"

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

    # Clean and reindex
    df = df.sort_values(['n', 'square_id']).reset_index(drop=True)
    df['id'] = np.arange(len(df))
    df = df[['id', 'n', 'square_id', 'x', 'y', 'angle']]

    assert len(df) == 500500, f"Expected 500500 rows, got {len(df)}"
    assert list(df['id']) == list(range(500500)), "IDs are not sequential 0..500499"

    # Save to both candidate path and submission_final.csv
    df.to_csv(out_path, index=False)
    df.to_csv(final_path, index=False)
    print(f"Successfully saved {len(df)} rows to {out_path} and {final_path}")
    print(f"Total confirmed score reduction: {total_gain:.10e}")

if __name__ == "__main__":
    main()
