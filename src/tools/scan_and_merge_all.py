"""Scan all CSV files in data/new_sources and any other candidates,
find any puzzle with better side length, certify with official metric,
and generate an improved submission.
"""

import csv
import math
import os
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metric"))
import packing_geometry as pg
import metric

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_CSV = BASE_DIR / "output" / "submission_22.251122.csv"

def verify_candidate(args):
    n, src_name, old_side, new_side, rows = args
    recs = [
        {"n": str(n), "square_id": str(i), "x": r[0], "y": r[1], "angle": r[2]}
        for i, r in enumerate(rows)
    ]
    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, recs)
    return n, src_name, old_side, new_side, float(L_cert) if L_cert is not None else 0.0, why, rows

def main():
    print(f"Loading baseline from {BASELINE_CSV}...")
    baseline_rows = {}
    base_sides = {}
    with open(BASELINE_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            n = int(r["n"])
            baseline_rows.setdefault(n, []).append((r["x"], r["y"], r["angle"]))

    for n, rows in baseline_rows.items():
        arr = np.array([[float(x), float(y), float(a)] for x, y, a in rows], dtype=float)
        base_sides[n] = pg.side(arr)

    base_score = sum(base_sides[n] / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"Current baseline score: {base_score:.12f}")

    sources_dir = BASE_DIR / "data" / "new_sources"
    all_csvs = sorted(list(sources_dir.rglob("*.csv")))
    print(f"Discovered {len(all_csvs)} CSV files in {sources_dir}")

    best_candidates = {}

    for cpath in all_csvs:
        try:
            # Check file size: ignore tiny or metadata files
            if cpath.stat().st_size < 100_000:
                continue

            with open(cpath, newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not {"n", "x", "y", "angle"}.issubset(set(reader.fieldnames)):
                    continue

                cand_rows = {}
                for r in reader:
                    try:
                        n = int(r["n"])
                        cand_rows.setdefault(n, []).append((r["x"], r["y"], r["angle"]))
                    except:
                        pass

            wins_in_file = 0
            for n, rows in cand_rows.items():
                if len(rows) != n:
                    continue
                arr = np.array([[float(x), float(y), float(a)] for x, y, a in rows], dtype=float)
                s = pg.side(arr)
                if s < base_sides[n] - 1e-7:
                    if n not in best_candidates or s < best_candidates[n]["side"]:
                        best_candidates[n] = {
                            "side": s,
                            "src": cpath.relative_to(BASE_DIR).as_posix(),
                            "rows": rows
                        }
                        wins_in_file += 1
            if wins_in_file > 0:
                print(f"  -> Found {wins_in_file} potential better packings in {cpath.name}")
        except Exception as e:
            # print(f"Error reading {cpath}: {e}")
            pass

    print(f"\nTotal potential candidate puzzle improvements: {len(best_candidates)}")
    if not best_candidates:
        print("No candidates beat current baseline.")
        return

    items_to_verify = []
    for n in sorted(best_candidates.keys()):
        cand = best_candidates[n]
        gain = (base_sides[n] - cand["side"]) / math.sqrt(n)
        print(f"  n={n:3d}: {base_sides[n]:.8f} -> {cand['side']:.8f} (gain {gain:.8f}, src={cand['src']})")
        items_to_verify.append((n, cand["src"], base_sides[n], cand["side"], cand["rows"]))

    print(f"\nCertifying {len(items_to_verify)} candidates with official mpmath interval metric...")
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(verify_candidate, item) for item in items_to_verify]
        results = [f.result() for f in as_completed(futures)]

    accepted = {}
    for n, src, old_s, new_s, L_cert, why, rows in results:
        if why == "ok" and L_cert < old_s - 1e-9:
            gain = (old_s - L_cert) / math.sqrt(n)
            accepted[n] = {
                "L_cert": L_cert,
                "gain": gain,
                "src": src,
                "rows": rows
            }
            print(f"  [CERTIFIED] n={n:3d}: gain={gain:.10f} ({src})")
        else:
            print(f"  [REJECTED]  n={n:3d}: why={why}")

    tot_gain = sum(v["gain"] for v in accepted.values())
    new_score = base_score - tot_gain
    print(f"\nTotal certified improvements: {len(accepted)} / {len(items_to_verify)}")
    print(f"Total verified gain: {tot_gain:.10f}")
    print(f"New score: {new_score:.12f}")

    if not accepted:
        print("No accepted improvements. Exiting.")
        return

    # Write new master submission
    out_csv = BASE_DIR / "output" / f"submission_{new_score:.6f}.csv"
    out_final = BASE_DIR / "output" / "submission_final.csv"
    data_best = BASE_DIR / "data" / "submission_best.csv"

    row_count = 0
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "n", "square_id", "x", "y", "angle"])
        for n in range(1, 1001):
            rows = accepted[n]["rows"] if n in accepted else baseline_rows[n]
            for sid, (x, y, a) in enumerate(rows):
                writer.writerow([row_count, n, sid, x, y, a])
                row_count += 1

    assert row_count == 500500, f"Expected 500500 rows, got {row_count}"
    print(f"\nWritten {row_count} rows to {out_csv}")

    import shutil
    shutil.copyfile(out_csv, out_final)
    shutil.copyfile(out_csv, data_best)
    print(f"Updated {out_final}")
    print(f"Updated {data_best}")

    # Certify full submission
    print("\nRunning complete metric certification on final submission...")
    from metric.metric import score as run_metric_score
    df_sub = metric.pd.read_csv(out_csv)
    df_sol = metric.pd.DataFrame({"n": list(range(1, 1001))})
    full_score = run_metric_score(df_sol, df_sub, "id")
    print(f"\n>>> FULL OFFICIAL SCORE CERTIFIED: {full_score:.12f} <<<")

if __name__ == "__main__":
    main()
