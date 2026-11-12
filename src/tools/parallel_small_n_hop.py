"""14-Core Parallel Basin Hopping for High-Headroom Small Puzzles.

Runs multi-seed descending basin hopping using `packer hop` across all 14 cores
on puzzles where a small reduction in side length delivers outsized competition score gains.
Automatically validates and certifies any discovered improvements.
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
import fault_dp as F
from ensemble import side, certify

PACKER = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "packer")
SUBMISSION_PATH = str(ROOT / "output" / "submission_22.248338.csv")

def worker_hop(job):
    n, seed, s0, sq, iters, temp, amp, descend = job
    with tempfile.TemporaryDirectory() as td:
        p_in = os.path.join(td, "in.txt")
        p_out = os.path.join(td, "out.txt")
        with open(p_in, "w") as fh:
            fh.write(f"{len(sq)} {s0 + 1e-9:.17f}\n")
            for x, y, t in sq:
                fh.write(f"{x:.17f} {y:.17f} {math.degrees(t):.15f}\n")

        cmd = [
            PACKER, "hop",
            "--in", p_in,
            "--s", str(s0 + 1e-9),
            "--seed", str(seed),
            "--iters", str(iters),
            "--temp", str(temp),
            "--amp", str(amp),
            "--descend", str(descend),
            "--out", p_out,
            "--quiet"
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
            if os.path.exists(p_out):
                lines = open(p_out).read().splitlines()
                cand = np.array([[float(v) for v in r.split()] for r in lines[1:] if r.strip()])
                if len(cand) == len(sq) and np.isfinite(cand).all():
                    cand[:, 2] = np.radians(cand[:, 2])
                    sc = side(cand)
                    if sc < s0 - 1e-9:
                        ok, sc_cert, text = certify(n, cand)
                        if ok and sc_cert < s0 - 1e-9:
                            return n, seed, sc_cert, text
        except Exception:
            pass
    return n, seed, s0, None

def optimize_puzzle(n, num_workers=14, iters=3000, temp=0.25, amp=1.0, descend=1e-5):
    cur = F.load_csv(SUBMISSION_PATH)
    sq = cur[n].copy()
    s0 = side(sq)
    print(f"\n============================================================")
    print(f"🎯 Optimizing Puzzle n={n} | Current Side L={s0:.12f}")
    print(f"Workers: {num_workers} | Iters/worker: {iters} | Total iters: {num_workers * iters}")
    print(f"============================================================", flush=True)

    jobs = [(n, seed, s0, sq, iters, temp, amp, descend) for seed in range(1, num_workers + 1)]
    t0 = time.time()

    best_win = None
    with Pool(num_workers) as pool:
        for res in pool.imap_unordered(worker_hop, jobs):
            p_n, seed, sc, text = res
            if text is not None and sc < s0 - 1e-9:
                gain = (s0 - sc) / math.sqrt(n)
                print(f"🎉 Worker seed={seed:2d} FOUND IMPROVEMENT: {s0:.12f} -> {sc:.12f} (score gain: {gain:.4e})!", flush=True)
                if best_win is None or sc < best_win[0]:
                    best_win = (sc, text)
            else:
                print(f"   Worker seed={seed:2d} finished (no gain)", flush=True)

    print(f"Puzzle n={n} search completed in {time.time() - t0:.1f}s.")
    return best_win

def main():
    target_puzzles = [51, 53, 55, 50, 41, 39, 29, 28]
    print("🚀 14-Core Parallel Small-N Basin Hopping Campaign Started.")
    
    total_wins = []
    for n in target_puzzles:
        win = optimize_puzzle(n, num_workers=14, iters=4000)
        if win is not None:
            total_wins.append((n, win[0], win[1]))

    if total_wins:
        print(f"\nApplying {len(total_wins)} certified puzzle wins...")
        base_df = pd.read_csv(SUBMISSION_PATH, dtype=str)
        updates_dict = {n: text for n, _, text in total_wins}

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
        out_csv = ROOT / "output" / "submission_small_n_improved.csv"
        new_df.to_csv(out_csv, index=False)
        print(f"Saved candidate submission to {out_csv}")

        val_json = ROOT / "output" / "validation_report_small_n.json"
        val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json)]
        subprocess.run(val_cmd, check=True)
        print(f"Validation complete! Report saved to {val_json}")
    else:
        print("\nNo small puzzle improvement found in this parameter regime.")

if __name__ == "__main__":
    main()
