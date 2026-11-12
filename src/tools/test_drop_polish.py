"""Neighbour drop + contact polish search on active canonical baseline.
Takes packing of n+1, drops one loose boundary square, and runs polish to beat n.
All angles are in RADIANS.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "fresh_sync_0003" / "danil_latest" / "search"))
from contact_polish import polish
from search_geometry import side, normalize, repair
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric

def main():
    base_df = pd.read_csv(ROOT / "output" / "submission_final.csv", dtype=str)
    bank = {}
    for n_str, g in base_df.groupby("n"):
        n = int(n_str)
        g = g.sort_values("square_id").reset_index(drop=True)
        xs = g["x"].astype(float).values
        ys = g["y"].astype(float).values
        rads = g["angle"].astype(float).values  # Already in radians!
        bank[n] = np.column_stack((xs, ys, rads))

    print(f"Loaded {len(bank)} puzzles into memory.")
    
    # Priority targets: n where n+1 is very close in L to n (e.g. side(bank[n+1]) < side(bank[n]) + 0.035)
    candidates_to_try = []
    for n in range(2, 999):
        p_n = bank[n]
        p_next = bank[n+1]
        L_n = side(p_n)
        L_next = side(p_next)
        diff = L_next - L_n
        if diff < 0.035:
            candidates_to_try.append((n, diff, L_n, L_next))

    candidates_to_try.sort(key=lambda x: x[1])
    print(f"Found {len(candidates_to_try)} candidate puzzles where L_{{n+1}} - L_n < 0.035:")
    for n, diff, L_n, L_next in candidates_to_try[:20]:
        print(f"  n={n:3d}: L_n={L_n:.6f}, L_{{n+1}}={L_next:.6f}, diff={diff:.6f}")

    total_gain = 0.0
    improved = []

    for n, diff, L_n, L_next in candidates_to_try[:30]:
        a = normalize(bank[n+1], 0)
        h = (abs(np.cos(a[:, 2])) + abs(np.sin(a[:, 2]))) / 2
        
        boundary = []
        for k in (0, 1):
            boundary.extend(np.argsort(a[:, k] - h)[:3])
            boundary.extend(np.argsort(-(a[:, k] + h))[:3])
            
        d = cKDTree(a[:, :2]).query(a[:, :2], k=min(5, len(a)))[0]
        free = np.argsort(-d[:, 1:].mean(axis=1))[:4]
        drop_ids = list(dict.fromkeys(list(free) + boundary))
        
        print(f"\n--- Testing n={n} (Base L={L_n:.8f}) with {len(drop_ids)} candidate drops from n={n+1} ---")
        best_cand_L = L_n
        best_cand_q = None
        
        for idx, drop_i in enumerate(drop_ids[:8]):
            cand_p = np.delete(a, drop_i, 0)
            cand_p = normalize(cand_p, 0)
            if side(cand_p) > L_n + 0.015:
                continue
            
            q, trace, secs = polish(cand_p, rounds=40, seed=n*100 + drop_i, max_seconds=3)
            if q is not None and side(q) < best_cand_L - 1e-9:
                cand_rows = []
                for sq_i in range(len(q)):
                    cand_rows.append({
                        "id": str(sq_i),
                        "square_id": str(sq_i),
                        "n": str(n),
                        "x": f"{q[sq_i, 0]:.16f}",
                        "y": f"{q[sq_i, 1]:.16f}",
                        "angle": f"{q[sq_i, 2]:.16f}"
                    })
                _, _, c_L, c_ok = metric.evaluate_single_puzzle(n, cand_rows)
                if c_ok == "ok" and float(c_L) < L_n - 1e-9:
                    dL = L_n - float(c_L)
                    gain = dL / (n ** 0.5)
                    print(f"  [Drop #{idx} sq {drop_i}] SUCCESS! L: {L_n:.8f} -> {float(c_L):.8f} | dL={dL:.6e} | gain={gain:.6e}")
                    best_cand_L = float(c_L)
                    best_cand_q = cand_rows
                    improved.append((n, dL, gain, cand_rows))
                    total_gain += gain
                    break

    print(f"\nSearch complete. Total verified improvements: {len(improved)}, total score gain: {total_gain:.9e}")

if __name__ == "__main__":
    main()
