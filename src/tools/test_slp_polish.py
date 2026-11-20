"""Test free-angle Sequential Sparse LP polish on selected puzzles from submission_final.csv.
"""
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import time

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "fresh_sync_0003" / "danil_latest" / "search"))
from contact_polish import polish
from search_geometry import side, normalize, repair
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric

def test_puzzles(ns):
    base_df = pd.read_csv(ROOT / "output" / "submission_final.csv", dtype=str)
    
    total_gain = 0.0
    improved = []
    
    for n in ns:
        g = base_df[base_df["n"] == str(n)].sort_values("square_id").reset_index(drop=True)
        # Parse into numpy array (x, y, angle_rad)
        xs = g["x"].astype(float).values
        ys = g["y"].astype(float).values
        rads = np.radians(g["angle"].astype(float).values)
        p = np.column_stack((xs, ys, rads))
        
        # Verify baseline with official metric
        b_records = g.to_dict("records")
        _, _, b_L, b_ok = metric.evaluate_single_puzzle(n, b_records)
        if b_ok != "ok":
            print(f"Skipping n={n}: baseline invalid ({b_ok})")
            continue
        base_L_val = float(b_L)
        
        print(f"\n--- Testing n={n} (Base certified L={base_L_val:.8f}) ---")
        t0 = time.time()
        
        best_p = p.copy()
        best_L = base_L_val
        
        for seed in [0, 42, 99]:
            q, trace, secs = polish(p.copy(), rounds=35, seed=seed, max_seconds=10)
            if q is not None:
                # Convert back to dict and verify with official metric
                # Scale angles back to degrees
                q_deg = np.degrees(q[:, 2]) % 360.0
                cand_rows = []
                for i in range(len(q)):
                    cand_rows.append({
                        "id": str(i),
                        "square_id": str(i),
                        "n": str(n),
                        "x": f"{q[i, 0]:.16f}",
                        "y": f"{q[i, 1]:.16f}",
                        "angle": f"{q_deg[i]:.16f}"
                    })
                _, _, c_L, c_ok = metric.evaluate_single_puzzle(n, cand_rows)
                if c_ok == "ok" and float(c_L) < best_L - 1e-10:
                    dL = best_L - float(c_L)
                    gain = dL / (n ** 0.5)
                    print(f"  [Seed {seed}] Squeezed! L: {best_L:.8f} -> {float(c_L):.8f} | dL={dL:.6e} | gain={gain:.6e}")
                    best_L = float(c_L)
                    best_p = q.copy()
                    improved.append((n, dL, gain))
                    total_gain += gain
        
        print(f"n={n} finished in {time.time()-t0:.2f}s | Current best L={best_L:.8f}")

    print(f"\nTotal improved: {len(improved)}, total gain: {total_gain:.9e}")

if __name__ == "__main__":
    # Test on puzzles that have room for boundary relaxation
    test_ns = [11, 17, 18, 19, 26, 27, 28, 29, 37, 38, 39, 41, 42, 50, 52, 55, 60, 65, 70, 75, 80, 85, 90, 95]
    test_puzzles(test_ns)
