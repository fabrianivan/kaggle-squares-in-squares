"""Merge newly certified public packings into master submission preserving exact decimal precision."""

import csv
import json
import math
import os
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "reference_sources"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metric"))
import packing_geometry as pg
try:
    import official_metric as metric
except ImportError:
    import metric
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_CSV = BASE_DIR / "output" / "submission_final.csv"

CANDIDATE_FILES = [
    BASE_DIR / "output" / "quench_run1",
    BASE_DIR / "output" / "quench_run2",
    BASE_DIR / "output" / "quench_run3",
    BASE_DIR / "output" / "quench_run4",
    BASE_DIR / "output" / "hop_test",
    BASE_DIR / "data" / "new_sources" / "mdm" / "portfolio.csv",
    BASE_DIR / "data" / "new_sources" / "notebook_outputs" / "submission_merged.csv",
    BASE_DIR / "data" / "new_sources" / "notebook_outputs" / "submission_ours.csv",
    BASE_DIR / "data" / "new_sources" / "private" / "portfolio_bundle" / "submission.csv",
    BASE_DIR / "data" / "new_sources" / "jazivxt" / "submission.csv",
    BASE_DIR / "data" / "new_sources" / "saamhm" / "submission.csv",
    BASE_DIR / "data" / "new_sources" / "saamhm" / "submissionn.csv",
]

def verify_candidate(args):
    n, src_name, old_side, new_side, rows = args
    recs = [
        {"n": str(n), "square_id": str(i), "x": r[0], "y": r[1], "angle": r[2]}
        for i, r in enumerate(rows)
    ]
    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, recs)
    return n, src_name, old_side, new_side, float(L_cert), why, rows

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

    # Discover candidate improvements
    raw_targets = CANDIDATE_FILES.copy()
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            p = Path(arg)
            if p.exists() and p not in raw_targets:
                raw_targets.append(p)

    target_files = []
    for item in raw_targets:
        if not item.exists():
            continue
        if item.is_dir():
            target_files.extend(sorted(item.glob("*.csv")))
        elif item.is_file() and item.suffix == ".csv":
            target_files.append(item)

    best_candidates = {}
    for cpath in target_files:
        if not cpath.exists():
            continue
        print(f"Scanning {cpath.name}...")
        cand_rows = {}
        with open(cpath, newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if "x" not in r or "y" not in r or "angle" not in r or "n" not in r:
                    cand_rows.clear()
                    break
                n = int(r["n"])
                cand_rows.setdefault(n, []).append((r["x"], r["y"], r["angle"]))
        
        for n, rows in cand_rows.items():
            if n not in base_sides or len(rows) != n:
                continue
            arr = np.array([[float(x), float(y), float(a)] for x, y, a in rows], dtype=float)
            s = pg.side(arr)
            if s < base_sides[n] - 1e-8:
                if n not in best_candidates or s < best_candidates[n]["side"]:
                    best_candidates[n] = {
                        "side": s,
                        "src": cpath.name,
                        "rows": rows
                    }

    print(f"\nFound {len(best_candidates)} candidate puzzle improvements:")
    items_to_verify = []
    for n in sorted(best_candidates.keys()):
        cand = best_candidates[n]
        gain = (base_sides[n] - cand["side"]) / math.sqrt(n)
        print(f"  n={n:3d}: {base_sides[n]:.8f} -> {cand['side']:.8f} (gain {gain:.8f}, src={cand['src']})")
        items_to_verify.append((n, cand["src"], base_sides[n], cand["side"], cand["rows"]))

    print(f"\nCertifying {len(items_to_verify)} candidates with official metric...")
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

    # Copy to submission_final.csv and data/submission_best.csv
    import shutil
    shutil.copyfile(out_csv, out_final)
    shutil.copyfile(out_csv, data_best)
    print(f"Updated {out_final}")
    print(f"Updated {data_best}")

    # Write summary json
    summary_path = BASE_DIR / "output" / "improvement_summary_round30.json"
    summary_data = {
        "previous_score": base_score,
        "new_score": new_score,
        "total_gain": tot_gain,
        "improved_puzzles_count": len(accepted),
        "improvements": {
            n: {
                "before": base_sides[n],
                "after": accepted[n]["L_cert"],
                "gain": accepted[n]["gain"],
                "source": accepted[n]["src"]
            }
            for n in sorted(accepted.keys())
        }
    }
    summary_path.write_text(json.dumps(summary_data, indent=2))
    print(f"Summary written to {summary_path}")

if __name__ == "__main__":
    main()
