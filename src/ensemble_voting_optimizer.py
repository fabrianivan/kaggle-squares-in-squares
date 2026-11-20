#!/usr/bin/env python3
"""
Ensemble Voting Optimizer
Runs multiple optimization methods and votes on the best result
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from pathlib import Path
import time
from src.tools import packing_geometry as pg
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import multiprocessing as mp

def optimize_method_1(packing, seed, time_limit):
    """Polish with tight parameters"""
    from src.tools.cpu_contact_polish import polish
    return polish(packing, seed=seed, rounds=6, max_seconds=time_limit,
                 trust_start=0.2, regularization=1e-12)

def optimize_method_2(packing, seed, time_limit):
    """Polish with loose parameters"""
    from src.tools.cpu_contact_polish import polish
    return polish(packing, seed=seed, rounds=6, max_seconds=time_limit,
                 trust_start=0.5, regularization=1e-10)

def optimize_method_3(packing, seed, time_limit):
    """Reclose with tight parameters"""
    from src.tools.cpu_axis_reclosure import reclose
    return reclose(packing, seed=seed, trust=0.15, tie=0.2, 
                  rounds=5, seconds=time_limit)

def optimize_method_4(packing, seed, time_limit):
    """Reclose with balanced parameters"""
    from src.tools.cpu_axis_reclosure import reclose
    return reclose(packing, seed=seed, trust=0.3, tie=0.28,
                  rounds=5, seconds=time_limit)

def optimize_method_5(packing, seed, time_limit):
    """Reclose with loose parameters"""
    from src.tools.cpu_axis_reclosure import reclose
    return reclose(packing, seed=seed, trust=0.45, tie=0.35,
                  rounds=5, seconds=time_limit)

def optimize_method_6(packing, seed, time_limit):
    """Polish with medium parameters"""
    from src.tools.cpu_contact_polish import polish
    return polish(packing, seed=seed, rounds=6, max_seconds=time_limit,
                 trust_start=0.35, regularization=5e-12)

METHODS = [
    optimize_method_1,
    optimize_method_2,
    optimize_method_3,
    optimize_method_4,
    optimize_method_5,
    optimize_method_6,
]

def ensemble_optimize_puzzle(n, baseline_packing, num_votes=10, time_per_vote=60):
    """
    Run ensemble optimization: multiple methods compete, best wins
    """
    best = baseline_packing.copy()
    best_side = pg.side(best)
    
    votes = []
    
    for vote_idx in range(num_votes):
        seed = np.random.randint(1e9)
        
        # Each vote: try all methods in parallel, pick best
        vote_results = []
        
        for method_idx, method in enumerate(METHODS):
            try:
                candidate = method(best, seed + method_idx, time_per_vote // len(METHODS))
                side = pg.side(candidate)
                vote_results.append((side, candidate, method_idx))
            except Exception as e:
                continue
        
        if not vote_results:
            continue
        
        # Pick best from this vote
        vote_best_side, vote_best_packing, vote_best_method = min(vote_results, key=lambda x: x[0])
        
        if vote_best_side < best_side:
            best = vote_best_packing
            best_side = vote_best_side
            print(f"  n={n}: Vote {vote_idx+1}/{num_votes}, method {vote_best_method} → {best_side:.12f}")
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("ENSEMBLE VOTING OPTIMIZER")
    print("=" * 80)
    print(f"Baseline: {baseline_path}")
    print(f"Using {len(METHODS)} optimization methods")
    
    # Target diverse puzzles
    targets = (list(range(2, 101)) + 
               list(range(101, 301, 2)) + 
               list(range(301, 601, 5)) +
               list(range(601, 1001, 10)))
    
    print(f"Targeting {len(targets)} puzzles")
    print(f"Each puzzle: {len(METHODS)} methods × 10 votes")
    
    wins = {}
    method_wins = {i: 0 for i in range(len(METHODS))}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['packing']))
        baseline_side = pg.side(baseline_packing)
        
        # More votes for small puzzles
        num_votes = 15 if n < 100 else 10
        time_per_vote = 90 if n < 100 else 60
        
        best, best_side = ensemble_optimize_puzzle(n, baseline_packing, num_votes, time_per_vote)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        else:
            print(f"  No improvement")
        
        if idx % 20 == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed
            remaining = (len(targets) - idx) / rate
            print(f"\n>>> Progress: {len(wins)} wins, {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    # Save results
    if wins:
        out_path = f"output/ensemble_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'packing'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path} (score={new_score:.12f})")
    else:
        print("\nNo improvements found")
    
    print(f"\nTotal time: {(time.time() - start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
