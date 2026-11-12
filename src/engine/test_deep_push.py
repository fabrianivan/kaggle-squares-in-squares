"""Deep push test on irregular puzzles using our original engine."""

import os
import sys
import time
import math
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))

import metric
from src.engine.orig_packing_solver import PackingState, MultiAxisContactLPSolver, ContinuousPenaltyRelaxer

def test_deep_push(target_n=51, num_trials=30):
    sub_df = pd.read_csv(os.path.join(ROOT, "output/submission_final.csv"), dtype=str)
    g = sub_df[sub_df["n"] == str(target_n)].sort_values("square_id", key=lambda c: c.astype(int))
    
    centers = np.array([[float(r["x"]), float(r["y"])] for _, r in g.iterrows()])
    angles = np.array([float(r["angle"]) for _, r in g.iterrows()])
    
    base_state = PackingState(target_n, centers, angles)
    base_state.normalize_to_box()
    L0 = base_state.s
    print(f"\n[n={target_n}] Base L0: {L0:.12f}")
    
    lp_solver = MultiAxisContactLPSolver(guard_buffer=1e-11)
    rng = np.random.default_rng(42)
    
    best_state = base_state.copy()
    
    # Try different target reductions: 1e-4, 3e-4, 5e-4, 1e-3
    for trial in range(num_trials):
        step_down = (trial + 1) * 3e-5
        target_side = L0 - step_down
        
        # Scale coordinates toward center
        cx, cy = L0 / 2.0, L0 / 2.0
        scale = target_side / L0
        
        cand_p = cx + (base_state.centers - cx) * scale
        cand_a = base_state.angles.copy()
        
        # Add slight stochastic noise to loose squares
        if trial > 0:
            noise_idx = rng.integers(0, target_n, size=min(4, target_n))
            cand_p[noise_idx] += rng.normal(0, 0.003, size=(len(noise_idx), 2))
            cand_a[noise_idx] = (cand_a[noise_idx] + rng.normal(0, 0.005)) % (math.pi / 2.0)
            
        cand_state = PackingState(target_n, cand_p, cand_a)
        cand_state.normalize_to_box()
        
        # Relax with continuous penalty
        relaxer = ContinuousPenaltyRelaxer(target_n, target_side)
        relaxed = relaxer.relax(cand_state, max_iter=100)
        
        # Polish with LP solver
        for _ in range(5):
            pol = lp_solver.optimize_step(relaxed)
            if pol is not None and pol.s < relaxed.s - 1e-11:
                relaxed = pol
            else:
                break
                
        if relaxed.s < best_state.s - 1e-10:
            ok, cert_L, reason = relaxed.certify_official()
            if not ok:
                # Try center dilation
                cx = (relaxed.centers[:, 0].min() + relaxed.centers[:, 0].max()) / 2.0
                cy = (relaxed.centers[:, 1].min() + relaxed.centers[:, 1].max()) / 2.0
                for factor in [1e-12, 5e-12, 1e-11, 5e-11, 1e-10]:
                    d_p = cx + (relaxed.centers - cx) * (1.0 + factor)
                    d_state = PackingState(target_n, d_p, relaxed.angles)
                    d_state.normalize_to_box()
                    ok, cert_L, reason = d_state.certify_official()
                    if ok:
                        relaxed = d_state
                        break

            if ok and cert_L < L0 - 1e-10:
                gain = (L0 - cert_L) / np.sqrt(target_n)
                print(f"*** TRIAL {trial}: CERTIFIED SQUEEZE! L: {L0:.10f} -> {cert_L:.10f}, Gain: {gain:.10e} ***")
                best_state = relaxed
                return best_state
            else:
                print(f"Trial {trial}: Side {relaxed.s:.10f} < L0, but uncertified: {reason}")
                
    delta = L0 - best_state.s
    print(f"[n={target_n}] Completed. Final Delta L: {delta:.10e}")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 51
    test_deep_push(n)
