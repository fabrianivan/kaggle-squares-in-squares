"""14-Core Basin Hopping Search Tool (Fixed & Automated).

Based on the official `hop_search.py` engine from Alex Chilton / evand.
Fixes:
- Strict 4-corner bounding box translation (ensures no wall boundary violation at start)
- Angle normalization modulo 90 degrees
- Float64 dilation (1 + 1e-12) and official metric interval arithmetic certification
- Dispatches across 14 cores
- Automatically updates submission and validates.
"""

import math
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))
sys.path.insert(0, str(ROOT / "src" / "metric"))

import metric
from ensemble import side, certify

PACKER = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "packer")
SUBMISSION_PATH = str(ROOT / "output" / "submission_22.246775.csv")
WORK_DIR = ROOT / "output" / "hop_work"

def corners(sq):
    x, y, t = sq[:, 0], sq[:, 1], sq[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    return (
        np.r_[x + c - s, x - c - s, x - c + s, x + c + s],
        np.r_[y + s + c, y - s + c, y - s - c, y + s - c],
    )

def hop_worker(job):
    n, sq, minutes, seed = job
    sq = sq.copy()
    X, Y = corners(sq)
    L0 = side(sq)
    sq[:, 0] -= X.min()
    sq[:, 1] -= Y.min()

    with tempfile.TemporaryDirectory() as td:
        p_start = os.path.join(td, f"start_{n}_{seed}.txt")
        p_best = os.path.join(td, f"best_{n}_{seed}.txt")

        with open(p_start, "w") as f:
            f.write(f"{n} {L0 + 1e-12:.17f}\n")
            for x, y, t in sq:
                f.write(f"{x:.17f} {y:.17f} {math.degrees(t) % 90.0:.15f}\n")

        t0 = time.time()
        cmd = [
            PACKER, "hop",
            "--in", p_start,
            "--seed", str(seed),
            "--iters", "1000000000",
            "--out", p_best,
            "--quiet"
        ]
        try:
            subprocess.run(cmd, timeout=minutes * 60, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            pass

        if not os.path.exists(p_best):
            return n, seed, L0, L0, "no output", time.time() - t0, None

        rows = [l.split() for l in open(p_best) if l.strip() and not l.startswith("#")][1:]
        if not rows:
            return n, seed, L0, L0, "empty best", time.time() - t0, None

        new = np.array([[float(a), float(b), math.radians(float(c))] for a, b, c, *_ in rows])
        L1 = side(new)
        if L1 >= L0 - 1e-9:
            return n, seed, L0, L1, "no gain", time.time() - t0, None

        # Dilation by 1 + 1e-12 about center to ensure interval arithmetic certification
        cx = (new[:, 0].min() + new[:, 0].max()) / 2.0
        cy = (new[:, 1].min() + new[:, 1].max()) / 2.0
        new[:, 0] = cx + (new[:, 0] - cx) * (1.0 + 1e-12)
        new[:, 1] = cy + (new[:, 1] - cy) * (1.0 + 1e-12)

        r = certify(n, new)
        if r is None or r[0] >= L0 - 1e-9:
            return n, seed, L0, L1, "not certified", time.time() - t0, None

        return n, seed, L0, r[0], "CERTIFIED", time.time() - t0, r[2]

def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    num_workers = 14
    minutes_per_puzzle = 1.0  # 1 min per worker per puzzle

    # High-impact target puzzles with room to improve
    targets = [
        329, 331, 325, 367, 366, 362, 326, 369, 401, 363, 408, 449, 442, 402,
        51, 53, 55, 50, 41, 39, 29, 28
    ]

    print("============================================================")
    print("🚀 14-Core Parallel Basin Hopping Search (Fixed)")
    print(f"Workers: {num_workers} | Budget: {minutes_per_puzzle}m per job | Puzzles: {len(targets)}")
    print(f"Baseline: {SUBMISSION_PATH}")
    print("============================================================\n", flush=True)

    df = pd.read_csv(SUBMISSION_PATH)
    all_wins = {}

    for n in targets:
        g = df[df.n == int(n)]
        if len(g) != n:
            continue
        sq0 = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
        L0 = side(sq0)
        print(f"\n--- Optimizing n={n} (current L={L0:.9f}) across {num_workers} workers ---", flush=True)

        jobs = [(n, sq0, minutes_per_puzzle, seed * 101 + n * 7) for seed in range(1, num_workers + 1)]
        best_n_win = None

        with Pool(num_workers) as pool:
            for res in pool.imap_unordered(hop_worker, jobs):
                p_n, seed, orig_L, new_L, status, elapsed, text = res
                if status == "CERTIFIED" and new_L < L0 - 1e-9:
                    gain = (L0 - new_L) / math.sqrt(n)
                    print(f"  🎉 Worker {seed:2d}: {orig_L:.9f} -> {new_L:.9f} ({status}, gain: {gain:.4e}) in {elapsed:.1f}s!", flush=True)
                    if best_n_win is None or new_L < best_n_win[0]:
                        best_n_win = (new_L, text)
                else:
                    print(f"     Worker {seed:2d}: {status} ({elapsed:.1f}s)", flush=True)

        if best_n_win is not None:
            all_wins[n] = best_n_win
            print(f">>> PUZZLE n={n} IMPROVED: L={L0:.9f} -> {best_n_win[0]:.9f} <<<", flush=True)

    print("\n" + "=" * 60)
    print(f"Basin hopping campaign completed. Total improved puzzles: {len(all_wins)}")

    if all_wins:
        print("Merging all certified basin hopping improvements into new submission...")
        base_df = pd.read_csv(SUBMISSION_PATH, dtype=str)
        updates_dict = {n: text for n, (_, text) in all_wins.items()}

        rows_list = []
        cur_id = 0
        for n_str, g in base_df.groupby("n", sort=False):
            n = int(n_str)
            if n in updates_dict:
                for i, (a, b, t) in enumerate(updates_dict[n]):
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(i), "x": str(a), "y": str(b), "angle": str(t)})
                    cur_id += 1
            else:
                for _, r in g.sort_values("square_id", key=lambda c: c.astype(int)).iterrows():
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                    cur_id += 1

        new_df = pd.DataFrame(rows_list)
        out_csv = ROOT / "output" / "submission_hop_improved.csv"
        new_df.to_csv(out_csv, index=False)
        print(f"Saved candidate submission to {out_csv}")

        val_json = ROOT / "output" / "validation_report_hop.json"
        val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json)]
        subprocess.run(val_cmd, check=True)
        print(f"Validation complete! Report saved to {val_json}")

if __name__ == "__main__":
    main()
