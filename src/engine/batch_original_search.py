"""Batch runner for our Enhanced Original Optimizer.

Scans puzzles with high excess or irregular structures, applies:
1. Pure Multi-Axis Contact LP Squeeze
2. Target Continuous Penalty Relaxation
3. Slack-Directed Void Basin Hopping
4. Official Multi-Precision Verification
Dynamically logs any certified wins.
"""

import os
import sys
import time
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))

import metric
from src.engine.orig_packing_solver import PackingState, EnhancedOriginalOptimizer

def run_batch(candidate_ns, time_per_n=15.0):
    sub_path = os.path.join(ROOT, "output/submission_final.csv")
    sub_df = pd.read_csv(sub_path, dtype=str)
    
    optimizer = EnhancedOriginalOptimizer(guard=1e-11, seed=42)
    total_gain = 0.0
    wins = []

    print(f"Starting batch search across {len(candidate_ns)} puzzles with our original optimizer...")
    print(f"Time budget per puzzle: {time_per_n}s\n")

    for n in candidate_ns:
        g = sub_df[sub_df["n"] == str(n)].sort_values("square_id", key=lambda c: c.astype(int))
        if len(g) != n:
            continue

        centers = np.array([[float(r["x"]), float(r["y"])] for _, r in g.iterrows()])
        angles = np.array([float(r["angle"]) for _, r in g.iterrows()])

        state = PackingState(n, centers, angles)
        state.normalize_to_box()
        L0 = state.s

        t0 = time.time()
        best = optimizer.optimize_puzzle(state, max_cycles=15, time_budget=time_per_n)
        elapsed = time.time() - t0

        if best.s < L0 - 1e-10:
            ok, L_cert, reason = best.certify_official()
            if ok and L_cert < L0 - 1e-10:
                gain = (L0 - L_cert) / np.sqrt(n)
                total_gain += gain
                wins.append((n, L0, L_cert, gain))
                print(f"*** [n={n:4d}] CERTIFIED IMPROVEMENT! L: {L0:.10f} -> {L_cert:.10f}, Gain: {gain:.10e} (in {elapsed:.1f}s) ***")
            else:
                print(f"    [n={n:4d}] Side decreased in LP ({L0:.8f} -> {best.s:.8f}) but uncertified ({reason})")
        else:
            print(f"    [n={n:4d}] Rigid minimum at L={L0:.8f} ({elapsed:.1f}s)")

    print(f"\nBatch search finished. Total certified wins: {len(wins)}, total gain: {total_gain:.10e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        targets = [int(x) for x in sys.argv[1:]]
    else:
        # Default targets: prominent non-grid puzzles
        targets = [11, 17, 18, 19, 26, 27, 28, 29, 37, 38, 39, 40, 41, 50, 51, 52, 53, 54, 55, 66, 67, 68, 69]
    run_batch(targets, time_per_n=8.0)
