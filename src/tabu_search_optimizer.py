#!/usr/bin/env python3
"""
Tabu Search Optimizer - Avoids revisiting recent solutions using memory
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from collections import deque
from src.tools import packing_geometry as pg

def tabu_search_puzzle(n, baseline_packing, max_iterations=100, tabu_tenure=15):
    """Tabu search with memory to avoid cycling"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    current = best.copy()
    current_side = best_side
    
    # Tabu list stores recent configurations (hashes)
    tabu_list = deque(maxlen=tabu_tenure)
    
    for iteration in range(max_iterations):
        # Generate neighborhood solutions
        candidates = []
        
        # Method 1: Polish with varying parameters
        for trust in [0.2, 0.35, 0.5]:
            try:
                seed = np.random.randint(1e9)
                cand = polish(current, seed=seed, rounds=3, max_seconds=15,
                            trust_start=trust, regularization=1e-11)
                cand_hash = hash(cand.tobytes())
                
                if cand_hash not in tabu_list:
                    candidates.append((cand, cand_hash))
            except:
                pass
        
        # Method 2: Reclose with varying parameters
        for trust, tie in [(0.15, 0.2), (0.3, 0.28), (0.45, 0.35)]:
            try:
                seed = np.random.randint(1e9)
                cand = reclose(current, seed=seed, trust=trust, tie=tie,
                             rounds=3, seconds=15)
                cand_hash = hash(cand.tobytes())
                
                if cand_hash not in tabu_list:
                    candidates.append((cand, cand_hash))
            except:
                pass
        
        if not candidates:
            break
        
        # Select best non-tabu candidate
        candidates_with_sides = [(c, h, pg.side(c)) for c, h in candidates]
        candidates_with_sides.sort(key=lambda x: x[2])
        
        next_solution, next_hash, next_side = candidates_with_sides[0]
        
        # Move to best candidate (even if worse - tabu allows exploration)
        current = next_solution
        current_side = next_side
        tabu_list.append(next_hash)
        
        # Update best if improved
        if current_side < best_side:
            best = current.copy()
            best_side = current_side
            print(f"  n={n}: Tabu iteration {iteration} improved to {best_side:.12f}")
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("TABU SEARCH OPTIMIZER")
    print("=" * 80)
    
    # Target 250 puzzles
    targets = list(range(2, 201)) + list(range(250, 501, 2)) + list(range(600, 801, 5))
    print(f"Targeting {len(targets)} puzzles with tabu search")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['squares']))
        baseline_side = pg.side(baseline_packing)
        
        max_iters = 150 if n < 100 else 100
        best, best_side = tabu_search_puzzle(n, baseline_packing, max_iters)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        
        if idx % 20 == 0:
            print(f">>> {len(wins)} wins, {(time.time()-start_time)/60:.1f}m elapsed")
    
    if wins:
        out_path = f"output/tabu_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'squares'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path}")
    
    print(f"\nTotal: {(time.time()-start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
