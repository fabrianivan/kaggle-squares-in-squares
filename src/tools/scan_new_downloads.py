"""Scan all newly downloaded datasets against our current record submission (22.250441).
Validates any potential improvement with exact 50-digit interval arithmetic.
"""

import os
import sys
import glob
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src" / "metric"))
import metric

def load_csv_puzzles(csv_path):
    """Load puzzles grouped by n from a CSV with string coordinates."""
    df = pd.read_csv(csv_path, dtype=str)
    
    # Standardize column names cleanly
    cols = {c: c.strip().lower() for c in df.columns}
    inv = {v: k for k, v in cols.items()}
    
    # Find x
    x_col = next((inv[c] for c in ['x', 'x_center'] if c in inv), None)
    y_col = next((inv[c] for c in ['y', 'y_center'] if c in inv), None)
    a_col = next((inv[c] for c in ['angle', 'deg', 'angle_deg', 'angle_rad'] if c in inv), None)
    n_col = next((inv[c] for c in ['n'] if c in inv), None)
    s_col = next((inv[c] for c in ['square_id', 'squareid'] if c in inv), None)
    
    clean_df = pd.DataFrame()
    clean_df['n'] = df[n_col].astype(int)
    clean_df['x'] = df[x_col]
    clean_df['y'] = df[y_col]
    clean_df['angle'] = df[a_col]
    if s_col is not None:
        clean_df['square_id'] = df[s_col]
    else:
        clean_df['square_id'] = None

    puzzles = {}
    for n, group in clean_df.groupby('n'):
        g = group.copy().reset_index(drop=True)
        # If square_id is missing or doesn't match 0..n-1, assign sequential 0..n-1
        if g['square_id'].isnull().any() or set(g['square_id']) != set(str(i) for i in range(len(g))):
            g['square_id'] = [str(i) for i in range(len(g))]
        puzzles[int(n)] = g
    return puzzles

def evaluate_group(n, group):
    """Return certified L from a dataframe group using metric.evaluate_single_puzzle."""
    rows = group.to_dict('records')
    n_res, score, L_str, reason = metric.evaluate_single_puzzle(n, rows)
    is_valid = (L_str is not None)
    return {
        'is_valid': is_valid,
        'side_length': L_str,
        'score': score,
        'description': reason
    }

def main():
    base_path = ROOT_DIR / "output" / "submission_final.csv"
    print(f"Loading baseline from {base_path}...")
    base_puzzles = load_csv_puzzles(base_path)
    
    print("Evaluating baseline L for all 1000 puzzles...")
    base_L = {}
    for n, group in base_puzzles.items():
        res = evaluate_group(n, group)
        if not res['is_valid']:
            print(f"ERROR: Baseline puzzle n={n} is invalid: {res['description']}")
            return
        base_L[n] = float(res['side_length'])

    print(f"Baseline loaded: 1000 valid puzzles. Checking sources...")

    sources = [
        ("kmmmvs_private/local_bank.csv", ROOT_DIR / "data" / "new_downloads" / "kmmmvs_private" / "local_bank.csv"),
        ("mdmuqtadirfuad/portfolio.csv", ROOT_DIR / "data" / "new_downloads" / "mdmuqtadirfuad" / "portfolio.csv"),
        ("kmmmvs_nb/submission.csv", ROOT_DIR / "data" / "new_downloads" / "kmmmvs_nb" / "submission.csv"),
        ("prvsiyan_live/finds.csv", ROOT_DIR / "data" / "new_downloads" / "prvsiyan_live" / "finds.csv"),
        ("prvsiyan_live/submission.csv", ROOT_DIR / "data" / "new_downloads" / "prvsiyan_live" / "submission.csv"),
    ]

    bundle_dir = ROOT_DIR / "data" / "new_downloads" / "kmmmvs_private" / "portfolio_bundle"
    bundle_files = list(bundle_dir.glob("*.csv")) if bundle_dir.exists() else []
    print(f"Found {len(bundle_files)} individual puzzle files in portfolio_bundle.")

    improvements = []

    for name, path in sources:
        if not path.exists():
            print(f"Skipping {name}: file not found.")
            continue
        print(f"\nScanning {name}...")
        try:
            cand_puzzles = load_csv_puzzles(path)
        except Exception as e:
            print(f"Error loading {name}: {e}")
            continue

        for n, cand_group in cand_puzzles.items():
            if n not in base_L:
                continue
            # Fast check
            try:
                xs = cand_group['x'].astype(float).values
                ys = cand_group['y'].astype(float).values
                rough_L = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1.0
                if rough_L > base_L[n] + 0.05:
                    continue
            except:
                pass

            res = evaluate_group(n, cand_group)
            if res['is_valid']:
                cand_L = float(res['side_length'])
                if cand_L < base_L[n] - 1e-9:
                    diff = base_L[n] - cand_L
                    gain = diff / (n ** 0.5)
                    print(f"  FOUND IMPROVEMENT for n={n} in {name}!")
                    print(f"    old L: {base_L[n]:.12f} -> new L: {cand_L:.12f} (delta={diff:.6e}, gain={gain:.6e})")
                    improvements.append({
                        'n': n,
                        'source': name,
                        'old_L': base_L[n],
                        'new_L': cand_L,
                        'gain': gain,
                        'group': cand_group
                    })
                    base_L[n] = cand_L

    if bundle_files:
        print(f"\nScanning {len(bundle_files)} bundle files...")
        for bf in bundle_files:
            try:
                cand_puzzles = load_csv_puzzles(bf)
                for n, cand_group in cand_puzzles.items():
                    if n not in base_L:
                        continue
                    res = evaluate_group(n, cand_group)
                    if res['is_valid']:
                        cand_L = float(res['side_length'])
                        if cand_L < base_L[n] - 1e-9:
                            diff = base_L[n] - cand_L
                            gain = diff / (n ** 0.5)
                            print(f"  FOUND IMPROVEMENT for n={n} in {bf.name}!")
                            print(f"    old L: {base_L[n]:.12f} -> new L: {cand_L:.12f} (delta={diff:.6e}, gain={gain:.6e})")
                            improvements.append({
                                'n': n,
                                'source': bf.name,
                                'old_L': base_L[n],
                                'new_L': cand_L,
                                'gain': gain,
                                'group': cand_group
                            })
                            base_L[n] = cand_L
            except Exception as e:
                pass

    print(f"\n==========================================")
    print(f"Scan complete. Total verified improvements: {len(improvements)}")
    total_gain = sum(item['gain'] for item in improvements)
    print(f"Total potential score gain: {total_gain:.12f}")
    print(f"New projected score: {22.250441015717 - total_gain:.12f}")

    if improvements:
        out_file = ROOT_DIR / "output" / "found_improvements.json"
        summary = [{
            'n': item['n'],
            'source': item['source'],
            'old_L': item['old_L'],
            'new_L': item['new_L'],
            'gain': item['gain']
        } for item in improvements]
        import json
        with open(out_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Saved summary to {out_file}")

if __name__ == "__main__":
    main()
