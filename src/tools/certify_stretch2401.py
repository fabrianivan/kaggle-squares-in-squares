"""Certify wins from az0519 22.2401 stretch submission and merge with our best."""
import pandas as pd
import numpy as np
import sys
import math
import time
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'data' / 'new_sources' / 'alexchilton_starter_kit'))
from ensemble import side, certify

CUR_PATH = ROOT / 'output' / 'submission_22.233798.csv'
NEW_SOURCES = [
    ROOT / 'data' / 'fresh_sync_today' / 'stretch_2401' / 'submission.csv',
    ROOT / 'data' / 'fresh_sync_today' / 'danil_latest' / 'submission.csv',
    ROOT / 'data' / 'fresh_sync_today' / 'danil_latest' / 'submission_merged.csv',
]


def find_wins(cur_p, candidate_path):
    """Return list of (n, cand_arr, s_cur, s_cand) where cand beats cur."""
    try:
        df = pd.read_csv(candidate_path)
    except Exception as e:
        print(f"  Could not read {candidate_path}: {e}")
        return []
    cand_p = {n: g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
              for n, g in df.groupby('n')}
    wins = []
    for n in range(1, 1001):
        if n in cand_p and n in cur_p:
            sc = side(cur_p[n])
            sn = side(cand_p[n])
            if sn < sc - 1e-9:
                wins.append((n, cand_p[n].copy(), sc, sn))
    return wins


def certify_one(args):
    n, cand_arr, s_cur, s_cand, source = args
    # Need re-import inside subprocess
    import sys
    from pathlib import Path
    ROOT = Path('.').resolve()
    sys.path.insert(0, str(ROOT / 'data' / 'new_sources' / 'alexchilton_starter_kit'))
    from ensemble import side, certify
    import time

    t0 = time.time()
    r = certify(n, cand_arr)
    dt = time.time() - t0
    if r is not None and r[0] < s_cur - 1e-9:
        return n, r[0], s_cur, 'CERTIFIED', r[2], dt, source
    return n, s_cand, s_cur, 'FAILED', None, dt, source


def main():
    print("=" * 60)
    print("Certifying wins from new public stretch submissions")
    print("=" * 60)

    cur_df = pd.read_csv(CUR_PATH)
    cur_p = {n: g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
             for n, g in cur_df.groupby('n')}

    all_wins = {}  # n -> (s_new, coords, source)

    for src in NEW_SOURCES:
        if not src.exists():
            print(f"  Skipping {src.name} (not found)")
            continue
        wins = find_wins(cur_p, src)
        print(f"\n{src.name}: {len(wins)} candidates beat current best")
        if not wins:
            continue

        jobs = [(n, cand, sc, sn, src.name) for n, cand, sc, sn in wins]
        with ProcessPoolExecutor(max_workers=14) as pool:
            futures = [pool.submit(certify_one, job) for job in jobs]
            for f in as_completed(futures):
                n, s_new, s_cur, status, coords, dt, src_name = f.result()
                gain = s_cur - s_new
                print(f"  n={n:4d}: {status} -> L={s_new:.9f} (gain={gain:+.6e}, {dt:.1f}s, src={src_name})", flush=True)
                if status == 'CERTIFIED':
                    if n not in all_wins or s_new < all_wins[n][0]:
                        all_wins[n] = (s_new, coords, src_name)

    if not all_wins:
        print("\nNo certified wins found. Stopping.")
        return

    print(f"\n{'='*60}")
    print(f"TOTAL CERTIFIED WINS: {len(all_wins)}")
    total_score_gain = sum(
        (cur_p[n] is not None and (side(cur_p[n]) - all_wins[n][0]) / math.sqrt(n))
        for n in all_wins
    )
    print(f"Estimated score gain: {total_score_gain:.6f}")

    # Merge into new submission
    print("\nMerging certified wins into new submission...")
    out_df_rows = []
    cur_id = 0
    for n in range(1, 1001):
        g = cur_df[cur_df.n == n].sort_values('square_id')
        if n in all_wins:
            coords = all_wins[n][1]  # list of (x, y, angle)
            for i, row in enumerate(coords):
                out_df_rows.append({
                    'id': cur_id, 'n': n, 'square_id': i,
                    'x': float(row[0]), 'y': float(row[1]), 'angle': float(row[2])
                })
                cur_id += 1
        else:
            for _, r in g.iterrows():
                out_df_rows.append({
                    'id': cur_id, 'n': n, 'square_id': int(r['square_id']),
                    'x': float(r['x']), 'y': float(r['y']), 'angle': float(r['angle'])
                })
                cur_id += 1

    out_df = pd.DataFrame(out_df_rows)
    
    # Validate
    from src.tools.validate_submission import validate
    
    # Compute preliminary score
    merged_p = {n: out_df[out_df.n == n].sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
                for n in range(1, 1001)}
    new_L = {n: side(merged_p[n]) for n in range(1, 1001)}
    cur_L = {n: side(cur_p[n]) for n in range(1, 1001)}
    
    # Simple metric (sum of L/sqrt(n) - 1)
    cur_score = sum((cur_L[n] / math.sqrt(n) - 1) for n in range(1, 1001))
    new_score = sum((new_L[n] / math.sqrt(n) - 1) for n in range(1, 1001))
    print(f"\nPreliminary scores: cur={cur_score:.10f}, new={new_score:.10f}")
    print(f"Estimated gain: {cur_score - new_score:.8f}")

    out_name = f"submission_{new_score:.6f}.csv"
    out_path = ROOT / 'output' / out_name
    out_df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # Full validation
    print("\nRunning official metric validation...")
    import subprocess
    val_report = ROOT / 'output' / 'validation_report_stretch2401.json'
    result = subprocess.run(
        [sys.executable, str(ROOT / 'src' / 'tools' / 'validate_submission.py'),
         str(out_path), str(val_report)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    print(result.stdout)
    if result.returncode == 0 and val_report.exists():
        with open(val_report) as f:
            report = json.load(f)
        official = report.get('official_score', '?')
        rejected = report.get('rejected', [])
        print(f"\nOfficial score: {official}")
        print(f"Rejected: {len(rejected)}")
        if len(rejected) == 0 and official != '?':
            official_f = float(official)
            final_name = f"submission_{official_f:.6f}.csv"
            final_path = ROOT / 'output' / final_name
            out_df.to_csv(final_path, index=False)
            out_df.to_csv(ROOT / 'output' / 'submission_final.csv', index=False)
            print(f"\n✅ CERTIFIED SUBMISSION: {final_path}")
            print(f"   Score: {official_f:.10f}")
        else:
            print(f"⚠️  Rejected puzzles: {rejected}")


if __name__ == '__main__':
    main()
