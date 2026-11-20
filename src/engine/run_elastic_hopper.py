"""Driver script for Elastic Contact Basin-Hopping Solver.
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
from src.engine.elastic_contact_hopper import ElasticSolver

def test_puzzles(target_ns: list[int], time_per_n: float = 20.0):
    sub_df = pd.read_csv(os.path.join(ROOT, "output/submission_final.csv"))
    
    print(f"Testing Elastic Contact Hopper on {target_ns}...")
    for n in target_ns:
        puzzle = sub_df[sub_df["n"] == n].sort_values("square_id")
        centers = puzzle[["x", "y"]].values
        angles = puzzle["angle"].values
        
        solver = ElasticSolver(n, seed=42)
        L0 = solver.compute_bounding_side(centers, angles)
        print(f"\n[n={n}] Initial side L0 = {L0:.10f}")
        
        t0 = time.time()
        best_c, best_a, best_L = solver.squeeze_and_hop(centers, angles, time_limit=time_per_n, step_delta=0.0001)
        elapsed = time.time() - t0
        
        delta_L = L0 - best_L
        score_gain = delta_L / np.sqrt(n)
        print(f"[n={n}] Completed in {elapsed:.1f}s: Final L = {best_L:.10f}, Delta L = {delta_L:.6e}, Gain = +{score_gain:.6e}")

if __name__ == "__main__":
    test_puzzles([26, 28, 37], time_per_n=15.0)
