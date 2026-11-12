#!/usr/bin/env python3
"""
FAST TRACK OPTIMIZER - Quick wins on medium-sized puzzles (n=150-500)
These puzzles are complex enough to have room for improvement but small enough to optimize quickly
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def fast_optimize(args):
    """Quick but thorough optimization"""
    n, p_base, seed = args
    
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        # Fast reclosure sweep
        for trust, tie in [(0.2, 0.1), (0.35, 0.15), (0.5, 0.2), (0.65, 0.25)]:
            q, _, _ = reclosure.reclose(p_base, seed=seed, trust=trust, tie=tie, rounds=20, seconds=2.5)
            if pg.side(q) < best_L - 1e-11:
                best_L = pg.side(q)
                best_p = q.copy()
        
        # Fast polish
        for trust_start in [0.015, 0.025]:
            q, _, _ = polish.polish(best_p, seed=seed+500, rounds=50, max_seconds=2.5, 
                                   trust_start=trust_start, regularization=0.0)
            q = pg.repair(q, clearance=1e-9)
            if q is not None and pg.side(q) < best_L - 1e-11:
                best_L = pg.side(q)
                best_p = q.copy()
        
        # Perturbation trials
        rng = np.random.default_rng(seed + 2000)
        for trial in range(20):
            q = best_p.copy()
            q[:, 0] += rng.normal(0, 0.0015, n)
            q[:, 1] += rng.normal(0, 0.0015, n)
            q[:, 2] += rng.normal(0, 0.005, n)
            q = pg.normalize(q)
            q, _, _ = polish.polish(q, seed=seed+trial, rounds=25, max_seconds=1.5, trust_start=0.02)
            q = pg.repair(q, clearance=1e-9)
            if q is not None and pg.side(q) < best_L - 1e-11:
                best_L = pg.side(q)
                best_p = q.copy()
        
        # Final repair
        best_p = pg.repair(best_p, clearance=1.5e-9)
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 1e-11:
                return (n, L0, best_L, best_p)
    
    except Exception as e:
        pass
    
    return None

def main():
    print("=" * 80)
    print("FAST TRACK OPTIMIZER - Medium Puzzle Quick Wins (n=150-500)")
    print("=" * 80)
    
    baseline_path = 'output/submission_final.csv'
    print(f"\nLoading: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Target medium-sized puzzles (n=150 to 500) - good optimization potential
    puzzles = []
    for n in range(150, 501):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            puzzles.append((waste, n, p))
    
    puzzles.sort(reverse=True)
    targets = [(n, p, i*17) for i, (waste, n, p) in enumerate(puzzles)]
    
    print(f"\nTargeting {len(targets)} medium puzzles (n=150-500)")
    print(f"Top 10 by waste: {[n for _, n, _ in puzzles[:10]]}")
    print(f"\nRunning fast optimization (~30-60 min)...\n")
    
    wins = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fast_optimize, args): args for args in targets}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            
            if result is not None:
                n, L0, L_best, p_best = result
                gain = L0 - L_best
                wins.append(result)
                print(f"✓ WIN n={n:4d}: {L0:.12f} -> {L_best:.12f} (gain={gain:.12f})")
            
            if completed % 30 == 0:
                elapsed = time.time() - start_time
                print(f"  Progress: {completed}/{len(targets)} - {len(wins)} wins - {elapsed/60:.1f}m elapsed")
    
    print(f"\n{'=' * 80}")
    print(f"FAST TRACK COMPLETE: {len(wins)} improvements found")
    print(f"Time: {(time.time() - start_time)/60:.1f} minutes")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        print(f"Total gain: {total_gain:.12f}")
        
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/fast_track_wins.npz', **patch_data)
        
        summary = {
            'wins': len(wins),
            'total_gain': float(total_gain),
            'improvements': [{'n': int(n), 'gain': float(L0-L_best)} for n, L0, L_best, p in wins]
        }
        with open('output/fast_track_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Saved: output/fast_track_wins.npz")
    else:
        print("\nNo improvements found - solution already optimal for this range!")

if __name__ == '__main__':
    main()
