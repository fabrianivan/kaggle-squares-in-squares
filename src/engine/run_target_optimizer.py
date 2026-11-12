"""High-leverage target optimizer using proprietary EnhancedOriginalOptimizer.

Targets high-excess, high-weight medium puzzles where continuous relaxation and
analytical SAT Jacobians can discover tighter packings.
"""

from __future__ import annotations
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

def optimize_puzzles(target_ns: list[int], time_budget_per_puzzle: float = 30.0):
    sub_df = pd.read_csv(os.path.join(ROOT, "output/submission_final.csv"))
    
    print(f"Starting targeted optimization on {len(target_ns)} puzzles: {target_ns}")
    optimizer = EnhancedOriginalOptimizer(guard=1e-11, seed=42)
    
    improved = {}
    
    for n in target_ns:
        puzzle = sub_df[sub_df["n"] == n].sort_values("square_id")
        centers = puzzle[["x", "y"]].values
        angles = puzzle["angle"].values
        
        state0 = PackingState(n, centers, angles)
        state0.normalize_to_box()
        s0 = state0.compute_bounding_side()
        
        t0 = time.time()
        print(f"\n[n={n}] Initial side: {s0:.12f} (Excess: {s0/np.sqrt(n)-1:.6f})")
        
        opt_state = optimizer.optimize_puzzle(state0, max_cycles=25, time_budget=time_budget_per_puzzle)
        elapsed = time.time() - t0
        
        # Verify offline certification
        valid, cert_L, reason = opt_state.certify_official()
        print(f"[n={n}] Result in {elapsed:.1f}s: L={opt_state.s:.12f}, Valid={valid}, Reason={reason}")
        
        if valid and opt_state.s < s0 - 1e-10:
            delta_L = s0 - opt_state.s
            score_gain = delta_L / np.sqrt(n)
            print(f"  >>> IMPROVEMENT FOUND! Delta L = {delta_L:.10e}, Score Gain = +{score_gain:.10e}")
            improved[n] = (opt_state, delta_L, score_gain)
        else:
            print(f"  No improvement or strictly equivalent (Delta = {s0 - opt_state.s:.2e})")
            
    print(f"\nOptimization complete. Found improvements on {len(improved)} puzzles.")
    return improved

if __name__ == "__main__":
    targets = [55, 68, 51, 53, 39, 41]
    optimize_puzzles(targets, time_budget_per_puzzle=20.0)
