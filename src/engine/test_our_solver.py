"""Test script for EnhancedOriginalOptimizer v2.0."""

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

def test_puzzles(target_ns=[28, 51, 68]):
    sub_df = pd.read_csv(os.path.join(ROOT, "output/submission_final.csv"))
    optimizer = EnhancedOriginalOptimizer(guard=1e-11, seed=42)

    for n in target_ns:
        puzzle = sub_df[sub_df["n"] == n].sort_values("square_id")
        centers = puzzle[["x", "y"]].values
        angles = puzzle["angle"].values

        state = PackingState(n, centers, angles)
        state.normalize_to_box()

        print(f"\n==========================================")
        print(f"Testing Enhanced Optimizer on n={n}:")
        print(f"  Starting L0: {state.s:.12f}")

        t0 = time.time()
        best = optimizer.optimize_puzzle(state, max_cycles=10, time_budget=10.0)
        elapsed = time.time() - t0

        print(f"  Completed in {elapsed:.2f}s, Final side: {best.s:.12f}")
        delta = state.s - best.s
        print(f"  Delta L: {delta:.10e}")
        
        ok, L_cert, reason = best.certify_official()
        print(f"  Official Metric Cert: ok={ok}, L={L_cert}, reason={reason}")

if __name__ == "__main__":
    ns = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else [28, 51]
    test_puzzles(ns)
