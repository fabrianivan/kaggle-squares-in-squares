"""Merge az0519 22.2401 stretch + danil latest into our best submission, with 14-core mpmath certification."""
import math
import subprocess
import sys
import time
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric
from ensemble import side

BASELINE = ROOT / "output" / "submission_22.233798.csv"

SOURCES = [
    ("stretch_2401", ROOT / "data" / "fresh_sync_today" / "stretch_2401" / "submission.csv"),
    ("danil_merged",  ROOT / "data" / "fresh_sync_today" / "danil_latest" / "submission_merged.csv"),
    ("danil_sub",     ROOT / "data" / "fresh_sync_today" / "danil_latest" / "submission.csv"),
    ("danil_ours",    ROOT / "data" / "fresh_sync_today" / "danil_latest" / "submission_ours.csv"),
]


def load_sides_and_rows(csv_path):
    df = pd.read_csv(csv_path)
    sides = {}
    rows_map = {}
    for n, g in df.groupby("n"):
        g2 = g.sort_values("square_id")
        x = g2["x"].to_numpy(float)
        y = g2["y"].to_numpy(float)
        t = g2["angle"].to_numpy(float)
        c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
        xc = np.vstack([x + c - s, x - c - s, x - c + s, x + c + s])
        yc = np.vstack([y + s + c, y - s + c, y - s - c, y + s - c])
        L = max(xc.max() - xc.min(), yc.max() - yc.min())
        sides[int(n)] = L
        rows_map[int(n)] = [
            {"n": str(int(n)), "square_id": str(int(r["square_id"])),
             "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])}
            for _, r in g2.iterrows()
        ]
    return sides, rows_map


def certify_worker(args):
    n, rows_dict_list = args
    sys.path.insert(0, str(ROOT / "src" / "metric"))
    import metric as m
    _, sc, L_str, why = m.evaluate_single_puzzle(n, rows_dict_list)
    if why == "ok" and L_str is not None:
        return n, float(L_str), L_str, rows_dict_list
    return n, None, None, why


def main():
    print("=" * 60)
    print("🚀 Certify New Public Stretch Wins → Merged Submission")
    print("=" * 60)

    base_sides, base_rows = load_sides_and_rows(BASELINE)
    base_score = sum(base_sides[n] / math.sqrt(n) - 1 for n in base_sides)
    print(f"Baseline: {BASELINE.name}")
    print(f"Baseline approx score: {base_score:.10f}\n")

    # Find best win per n across all sources
    best_wins = {}   # n -> (source, cand_L, rows_dict_list)
    for name, path in SOURCES:
        if not path.exists():
            print(f"  Skip {name} (not found)")
            continue
        sides, rows_map = load_sides_and_rows(path)
        wins = 0
        for n in range(1, 1001):
            if n in sides:
                sc = base_sides.get(n, 999)
                sn = sides[n]
                if sn < sc - 1e-9:
                    if n not in best_wins or sn < best_wins[n][1]:
                        best_wins[n] = (name, sn, rows_map[n])
                        wins += 1
        print(f"  {name}: {wins} new wins found")

    print(f"\nTotal unique winning puzzles: {len(best_wins)}")
    if not best_wins:
        print("No wins. Stopping.")
        return

    # Certify all via 14-core mpmath
    print(f"\nCertifying {len(best_wins)} candidates with 14 cores (mpmath)...")
    certified = {}
    t0 = time.time()
    jobs = [(n, best_wins[n][2]) for n in sorted(best_wins)]
    with ProcessPoolExecutor(max_workers=14) as pool:
        futures = {pool.submit(certify_worker, job): job[0] for job in jobs}
        for f in as_completed(futures):
            n = futures[f]
            n_ret, L_cert, L_str, status = f.result()
            sc = base_sides[n]
            if L_cert is not None and L_cert < sc - 1e-9:
                gain = sc - L_cert
                print(f"  ✅ n={n:4d}: {sc:.9f} → {L_cert:.9f} (gain={gain:+.6e}, src={best_wins[n][0]})", flush=True)
                certified[n] = (L_cert, best_wins[n][2])
            else:
                print(f"  ❌ n={n:4d}: {status}", flush=True)

    dt = time.time() - t0
    print(f"\nCertification complete in {dt:.1f}s. {len(certified)}/{len(best_wins)} certified.")

    if not certified:
        print("No certified wins. Stopping.")
        return

    # Assemble new submission
    print("\nAssembling new submission...")
    out_rows = []
    cur_id = 0
    for n in range(1, 1001):
        if n in certified:
            for row in certified[n][1]:
                out_rows.append({
                    "id": cur_id, "n": n, "square_id": int(row["square_id"]),
                    "x": row["x"], "y": row["y"], "angle": row["angle"]
                })
                cur_id += 1
        else:
            for row in base_rows[n]:
                out_rows.append({
                    "id": cur_id, "n": n, "square_id": int(row["square_id"]),
                    "x": row["x"], "y": row["y"], "angle": row["angle"]
                })
                cur_id += 1

    out_df = pd.DataFrame(out_rows)
    assert len(out_df) == 500500, f"Wrong row count: {len(out_df)}"
    
    # Compute preliminary score
    merged_sides = {}
    for n, g in out_df.groupby("n"):
        g2 = g.sort_values("square_id")
        x = g2["x"].to_numpy(float)
        y = g2["y"].to_numpy(float)
        t = g2["angle"].to_numpy(float)
        c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
        xc = np.vstack([x + c - s, x - c - s, x - c + s, x + c + s])
        yc = np.vstack([y + s + c, y - s + c, y - s - c, y + s - c])
        merged_sides[int(n)] = max(xc.max() - xc.min(), yc.max() - yc.min())

    new_approx_score = sum(merged_sides[n] / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"\nApprox score: baseline={base_score:.10f}, new={new_approx_score:.10f}")
    print(f"Approx gain:  {base_score - new_approx_score:.10f}")

    # Save provisional
    prov_path = ROOT / "output" / f"submission_stretch2401_merged.csv"
    out_df.to_csv(prov_path, index=False)
    print(f"\nProvisional save: {prov_path}")

    # Official validation
    print("\nRunning official metric validation (this takes a few minutes)...")
    val_report = ROOT / "output" / "validation_report_stretch2401.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"),
         str(prov_path), str(val_report)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    print(result.stdout[-2000:])
    if result.returncode == 0 and val_report.exists():
        with open(val_report) as f:
            report = json.load(f)
        official = report.get("official_score", "?")
        rejected = report.get("rejected", [])
        rows_ok = report.get("rows", 0)
        print(f"\nOfficial score: {official}")
        print(f"Rows: {rows_ok} | Rejected: {len(rejected)}")
        if len(rejected) == 0 and official != "?":
            official_f = float(official)
            final_name = f"submission_{official_f:.6f}.csv"
            final_path = ROOT / "output" / final_name
            out_df.to_csv(final_path, index=False)
            out_df.to_csv(ROOT / "output" / "submission_final.csv", index=False)
            print(f"\n🎉 CERTIFIED SUBMISSION: {final_path}")
            print(f"   Official Score: {official_f:.10f}")
            print(f"   Gain vs baseline: {22.233798 - official_f:.8f}")


if __name__ == "__main__":
    main()
