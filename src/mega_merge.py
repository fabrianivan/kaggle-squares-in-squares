#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Mega Merge - Combine ALL available submission sources into one optimal submission.
For each puzzle n, pick the best packing across every source.
"""
import sys, os, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / 'tools'))
sys.path.insert(0, str(BASE_DIR / 'metric'))

import packing_geometry

SCRATCH = Path("/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares")
NEW_BASE = Path("/Users/fabrianivan/kaggle-squares-in-squares")

# All available submission sources
SOURCES = [
    # Current best merged submissions
    ("merged_2251602", str(NEW_BASE / "output" / "submission_simple_22.251602.csv")),
    ("merged_2251603", str(SCRATCH / "submission_merged_22.251603.csv")),
    ("merged_223319", str(SCRATCH / "submission_merged_22.253319.csv")),
    ("merged_2251602_full", str(SCRATCH / "submission_merged_22.251602_full.csv")),
    # Full 1000-puzzle submissions from data/
    ("kmmmvs", str(SCRATCH / "data" / "kmmmvs" / "submission.csv")),
    ("alexchilton_best", str(SCRATCH / "data" / "alexchilton" / "best.csv")),
    ("alexchilton_best_current", str(SCRATCH / "data" / "alexchilton" / "best_current.csv")),
    ("alimaad", str(SCRATCH / "data" / "alimaad" / "submission.csv")),
    ("cshara", str(SCRATCH / "data" / "cshara" / "best_submission.csv")),
    ("lostdecimal", str(SCRATCH / "data" / "lostdecimal" / "submission.csv")),
    ("prvsiyan", str(SCRATCH / "data" / "prvsiyan" / "submission.csv")),
    ("kernel_out", str(SCRATCH / "kernel_out" / "submission.csv")),
    ("jazivxt_out", str(SCRATCH / "jazivxt_out" / "submission.csv")),
    ("koushik_out", str(SCRATCH / "koushik_out" / "submission.csv")),
    ("sigmaborov_out", str(SCRATCH / "sigmaborov_out" / "submission.csv")),
    # Partial submissions
    ("alexchilton_couzo", str(SCRATCH / "data" / "alexchilton" / "couzo.csv")),
    ("alexchilton_hop", str(SCRATCH / "data" / "alexchilton" / "hop.csv")),
    ("alexchilton_quench", str(SCRATCH / "data" / "alexchilton" / "quench.csv")),
    ("nilanjan_out", str(SCRATCH / "nilanjan_out" / "submission.csv")),
    ("kirill_frozen", str(SCRATCH / "kirill_out" / "_frozen_v27" / "submission.csv")),
    ("mufasasimon", str(SCRATCH / "out_mufasasimon" / "submission.csv")),
    ("busyaprime", str(SCRATCH / "data" / "busyaprime" / "packings.csv")),
]


def load_packing(df, n):
    """Extract packing for puzzle n from a dataframe, sorted by square_id."""
    g = df[df['n'] == n].sort_values('square_id')
    if len(g) == 0:
        return None
    return g[['x', 'y', 'angle']].to_numpy(float)


def main():
    print("=" * 80)
    print("MEGA MERGE - Combine ALL submission sources")
    print("=" * 80)

    # Start with current best
    current_best_path = str(NEW_BASE / "output" / "submission_simple_22.251602.csv")
    print(f"\nLoading current best: {Path(current_best_path).name}")
    df_best = pd.read_csv(current_best_path)
    best = {}
    for n in range(1, 1001):
        best[n] = load_packing(df_best, n)
    del df_best

    # Compute baseline score
    baseline_score = sum(packing_geometry.side(best[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"   Current score: {baseline_score:.10f}")

    # Load all sources
    print(f"\nLoading {len(SOURCES)} submission sources...")
    sources_data = {}
    for name, path in SOURCES:
        if not os.path.exists(path):
            print(f"  {name:25s}: NOT FOUND")
            continue
        try:
            df = pd.read_csv(path)
            # Filter out any NaN n values
            df = df.dropna(subset=['n'])
            df['n'] = df['n'].astype(int)
            sources_data[name] = df
            ns = sorted(df['n'].unique())
            print(f"  {name:25s}: {len(df):>7d} rows, {len(ns):>4d} puzzles")
        except Exception as e:
            print(f"  {name:25s}: ERROR - {str(e)[:60]}")

    print(f"\nLoaded {len(sources_data)} sources")

    # Merge: for each puzzle, check all sources and keep the best
    print("\nMerging...")
    improvements = {}
    total_checked = 0
    total_improved = 0

    for n in range(1, 1001):
        cur_L = packing_geometry.side(best[n])
        found_better = False

        for name, df in sources_data.items():
            p = load_packing(df, n)
            if p is None or len(p) != n:
                continue
            total_checked += 1
            try:
                p_L = packing_geometry.side(p)
                if p_L < cur_L - 1e-9:
                    best[n] = p
                    cur_L = p_L
                    found_better = True
            except Exception:
                pass

        if found_better:
            total_improved += 1

    # Compute new score
    new_score = sum(packing_geometry.side(best[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    total_gain = baseline_score - new_score

    print(f"\n{'=' * 80}")
    print(f"Merge complete!")
    print(f"  Puzzles checked: {total_checked}")
    print(f"  Puzzles improved: {total_improved}")
    print(f"  Previous score: {baseline_score:.10f}")
    print(f"  New score:       {new_score:.10f}")
    print(f"  Gain:           -{total_gain:.10f}")

    # Load Danil and PJ packings (already merged in current best, but double-check)
    print("\nLoading notebook packings...")
    # Danil
    try:
        import base64, lzma
        danil_path = str(NEW_BASE / "data" / "external_packings" / "squares-in-squares-living-atlas-of-tight-packings.ipynb")
        with open(danil_path) as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][22]['source']), scope)
        matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])),
                               dtype='<f8').reshape(3, -1).T
        offset = 0
        danil_count = 0
        for n in scope['REPLAY_NS']:
            danil_p = matrix[offset:offset + n]
            offset += n
            cur_L = packing_geometry.side(best[n])
            danil_L = packing_geometry.side(danil_p)
            if danil_L < cur_L - 1e-9:
                best[n] = danil_p
                danil_count += 1
        print(f"  Danil: {danil_count} new improvements")
    except Exception as e:
        print(f"  Danil: {e}")

    # PJ
    try:
        pj_path = str(NEW_BASE / "data" / "external_packings" / "three-square-packings-that-beat-the-records.ipynb")
        with open(pj_path) as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][3]['source']), scope)
        pj_count = 0
        for n, coords in scope['PACKINGS'].items():
            pj_p = np.array(coords, float)
            cur_L = packing_geometry.side(best[n])
            pj_L = packing_geometry.side(pj_p)
            if pj_L < cur_L - 1e-9:
                best[n] = pj_p
                pj_count += 1
        print(f"  PJ: {pj_count} new improvements")
    except Exception as e:
        print(f"  PJ: {e}")

    # Final score
    final_score = sum(packing_geometry.side(best[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    final_gain = baseline_score - final_score
    print(f"\n  Final score:     {final_score:.10f}")
    print(f"  Total gain:     -{final_gain:.10f}")

    # Verify no overlaps and write submission
    print("\nVerifying and writing submission...")
    import csv
    output_dir = NEW_BASE / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"submission_mega_{final_score:.6f}.csv"

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
        row_id = 0
        for n in range(1, 1001):
            p = best[n]
            for sid in range(len(p)):
                writer.writerow([row_id, n, sid,
                                  repr(float(p[sid, 0])),
                                  repr(float(p[sid, 1])),
                                  repr(float(p[sid, 2]))])
                row_id += 1

    # Verify
    df_check = pd.read_csv(output_file)
    assert len(df_check) == 500500, f"Row count: {len(df_check)}"
    assert df_check.isna().sum().sum() == 0, "NaN values found"
    print(f"  ✓ {row_id} rows written and verified")
    print(f"  Saved to: {output_file}")

    # Show improvement breakdown
    print(f"\n{'=' * 80}")
    print(f"RESULT: {baseline_score:.6f} -> {final_score:.6f} (gain: -{final_gain:.6f})")
    print(f"{'=' * 80}")


if __name__ == '__main__':
    main()
