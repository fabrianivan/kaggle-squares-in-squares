"""Jitter-Relax / Loosen-Squeeze Solver for high-excess irregular puzzles.
Aims to find sub-millimeter contractions to beat Rank 94.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "fresh_sync_0003" / "danil_latest" / "search"))
from contact_polish import polish
from search_geometry import side, normalize, repair
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric

def true_L(g):
    xs_val = g["x"].astype(float).values
    ys_val = g["y"].astype(float).values
    angs = g["angle"].astype(float).values
    c = np.cos(angs)
    s = np.sin(angs)
    h = 0.5
    dx1, dy1 = h * c - h * s, h * s + h * c
    dx2, dy2 = -h * c - h * s, -h * s + h * c
    all_x = np.concatenate([xs_val + dx1, xs_val + dx2, xs_val - dx1, xs_val - dx2])
    all_y = np.concatenate([ys_val + dy1, ys_val + dy2, ys_val - dy1, ys_val - dy2])
    return max(np.max(all_x) - np.min(all_x), np.max(all_y) - np.min(all_y))

def run_jitter_search(target_ns, trials_per_puzzle=40):
    base_df = pd.read_csv(ROOT / "output" / "submission_final.csv", dtype=str)
    
    print(f"Starting Jitter-Relax Search on {len(target_ns)} puzzles: {target_ns}")
    total_gain = 0.0
    improvements = {}

    for n in target_ns:
        g = base_df[base_df["n"] == str(n)].sort_values("square_id").reset_index(drop=True)
        xs = g["x"].astype(float).values
        ys = g["y"].astype(float).values
        rads = g["angle"].astype(float).values
        p = np.column_stack((xs, ys, rads))
        
        # Verify initial
        records = g.to_dict("records")
        _, _, b_L_str, b_ok = metric.evaluate_single_puzzle(n, records)
        if b_ok != "ok":
            print(f"Skipping n={n}: invalid initial {b_ok}")
            continue
        base_L = float(b_L_str)
        best_L = base_L
        best_q = None
        
        print(f"\n==================================================")
        print(f"Puzzle n={n:3d} | Base Certified L = {base_L:.10f}")
        print(f"==================================================")
        
        t0 = time.time()
        rng = np.random.default_rng(n * 2026)
        
        # Trial 0: pure contact polish on unmodified configuration
        q, trace, _ = polish(p.copy(), rounds=60, seed=n, max_seconds=4)
        if q is not None and side(q) < best_L - 1e-9:
            # Verify with metric
            q_rows = [{
                "id": str(i), "square_id": str(i), "n": str(n),
                "x": f"{q[i, 0]:.16f}", "y": f"{q[i, 1]:.16f}", "angle": f"{q[i, 2]:.16f}"
            } for i in range(len(q))]
            _, _, c_L, c_ok = metric.evaluate_single_puzzle(n, q_rows)
            if c_ok == "ok" and float(c_L) < best_L - 1e-9:
                dL = best_L - float(c_L)
                gain = dL / (n ** 0.5)
                print(f"  [Direct Polish] SQUEEZED! L: {best_L:.10f} -> {float(c_L):.10f} | dL={dL:.6e} | gain={gain:.6e}")
                best_L = float(c_L)
                best_q = q_rows
                
        # Jitter trials
        for trial in range(1, trials_per_puzzle + 1):
            if time.time() - t0 > 30: # Max 30 seconds per puzzle
                break
                
            p_trial = p.copy()
            # Loosen scale
            scale = 1.0 + rng.uniform(0.0005, 0.005)
            p_trial[:, :2] *= scale
            
            # Identify internal squares vs boundary squares
            h = (abs(np.cos(p_trial[:, 2])) + abs(np.sin(p_trial[:, 2]))) / 2
            L_curr = side(p_trial)
            dist_to_wall = np.minimum(
                np.minimum(p_trial[:, 0] - h, L_curr - (p_trial[:, 0] + h)),
                np.minimum(p_trial[:, 1] - h, L_curr - (p_trial[:, 1] + h))
            )
            # Squares not hard against the wall have more freedom
            internal_mask = dist_to_wall > 0.05
            
            # Add spatial & angular jitter to internal squares
            n_internal = np.sum(internal_mask)
            if n_internal > 0:
                p_trial[internal_mask, 0] += rng.normal(0, 0.008, size=n_internal)
                p_trial[internal_mask, 1] += rng.normal(0, 0.008, size=n_internal)
                p_trial[internal_mask, 2] += rng.normal(0, 0.025, size=n_internal)
                
            # Add slight global jitter to all squares
            p_trial[:, :2] += rng.normal(0, 0.002, size=(n, 2))
            
            # Repair collisions
            p_rep = repair(p_trial, clearance=1e-10)
            if p_rep is None:
                continue
                
            # Run contact polish
            q, trace, _ = polish(p_rep, rounds=50, seed=trial, max_seconds=2)
            if q is not None and side(q) < best_L - 1e-9:
                q_rows = [{
                    "id": str(i), "square_id": str(i), "n": str(n),
                    "x": f"{q[i, 0]:.16f}", "y": f"{q[i, 1]:.16f}", "angle": f"{q[i, 2]:.16f}"
                } for i in range(len(q))]
                _, _, c_L, c_ok = metric.evaluate_single_puzzle(n, q_rows)
                if c_ok == "ok" and float(c_L) < best_L - 1e-9:
                    dL = best_L - float(c_L)
                    gain = dL / (n ** 0.5)
                    print(f"  [Trial #{trial:2d}] SQUEEZED! L: {best_L:.10f} -> {float(c_L):.10f} | dL={dL:.6e} | gain={gain:.6e}")
                    best_L = float(c_L)
                    best_q = q_rows

        if best_q is not None:
            improvements[n] = (best_L, best_q)
            total_gain += (base_L - best_L) / (n ** 0.5)

        print(f"Puzzle n={n} finished in {time.time()-t0:.2f}s | Result: {best_L:.10f}")

    print(f"\n==================================================")
    print(f"Jitter Search Summary: {len(improvements)} puzzles improved")
    print(f"Total potential score reduction: {total_gain:.10e}")
    print(f"==================================================")

if __name__ == "__main__":
    targets = [51, 53, 55, 68, 66, 67, 69, 70, 71, 83, 84, 85, 86, 87, 88, 89]
    run_jitter_search(targets, trials_per_puzzle=30)
