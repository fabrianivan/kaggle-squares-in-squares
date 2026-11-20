#!/usr/bin/env python3
"""
MEGA OPTIMIZER - Exhaustive multi-strategy improvement system
Runs multiple optimization strategies in parallel for maximum improvement potential
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

def ultra_optimize_puzzle(args):
    """Ultra-aggressive optimization with 50+ strategies per puzzle"""
    n, p_base, seed = args
    
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        # Strategy 1: Multiple reclosure passes with varying parameters
        for trust in [0.15, 0.25, 0.35, 0.45, 0.55, 0.65]:
            for tie in [0.05, 0.1, 0.15, 0.2, 0.25]:
                try:
                    q, _, _ = reclosure.reclose(p_base, seed=seed, trust=trust, tie=tie, rounds=25, seconds=4.0)
                    if pg.side(q) < best_L - 1e-11:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        # Strategy 2: Contact polish with many parameter combinations
        for trust_start in [0.01, 0.015, 0.02, 0.025, 0.03]:
            for reg in [0.0, 0.0001, 0.001, 0.01]:
                try:
                    q, _, _ = polish.polish(best_p, seed=seed+1000, rounds=70, max_seconds=4.0, 
                                           trust_start=trust_start, regularization=reg)
                    q = pg.repair(q, clearance=1e-9)
                    if q is not None and pg.side(q) < best_L - 1e-11:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        # Strategy 3: Random perturbations + local optimization
        rng = np.random.default_rng(seed + 5000)
        for trial in range(50):
            try:
                q = best_p.copy()
                scale = 0.001 * (1 + trial / 50)
                q[:, 0] += rng.normal(0, scale, n)
                q[:, 1] += rng.normal(0, scale, n)
                q[:, 2] += rng.normal(0, scale * 3, n)
                q = pg.normalize(q)
                
                # Quick polish on perturbation
                q, _, _ = polish.polish(q, seed=seed+trial, rounds=30, max_seconds=2.0, trust_start=0.02)
                q = pg.repair(q, clearance=1e-9)
                
                if q is not None and pg.side(q) < best_L - 1e-11:
                    best_L = pg.side(q)
                    best_p = q.copy()
            except:
                pass
        
        # Strategy 4: Rotation sweep
        for angle in np.linspace(0, np.pi/2, 20):
            try:
                q = pg.rotate(best_p, angle)
                q, _, _ = polish.polish(q, seed=seed+2000, rounds=20, max_seconds=1.5, trust_start=0.02)
                q = pg.repair(q, clearance=1e-9)
                if q is not None and pg.side(q) < best_L - 1e-11:
                    best_L = pg.side(q)
                    best_p = q.copy()
            except:
                pass
        
        # Strategy 5: Final optimal rotation
        if best_L < L0 - 1e-11:
            try:
                q_rot, _ = pg.optimal_rotation(best_p)
                if pg.side(q_rot) < best_L - 1e-11:
                    best_L = pg.side(q_rot)
                    best_p = q_rot.copy()
            except:
                pass
        
        # Final verification
        best_p = pg.repair(best_p, clearance=1.5e-9)
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 1e-11:
                return (n, L0, best_L, best_p)
    
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return None

def main():
    print("=" * 80)
    print("MEGA OPTIMIZER - Exhaustive Multi-Strategy System")
    print("=" * 80)
    
    # Load current best
    baseline_path = 'output/submission_final.csv'
    print(f"\nLoading baseline: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Calculate waste for each puzzle
    puzzles = []
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            # Weight by n (larger puzzles worth more)
            weighted_value = waste * n
            puzzles.append((weighted_value, waste, n, p))
    
    # Sort by weighted value (waste * n) to target high-impact puzzles
    puzzles.sort(reverse=True)
    
    # Target top 200 puzzles
    targets = [(n, p, i*13) for i, (_, _, n, p) in enumerate(puzzles[:200])]
    
    print(f"\nTargeting top 200 high-value puzzles")
    print(f"Top 10 by weighted value: {[(n, f'waste={w:.6f}') for _, w, n, _ in puzzles[:10]]}")
    print(f"\nRunning ultra-optimization with ~150 strategies per puzzle...")
    print(f"This will take 2-4 hours. Progress will be reported.\n")
    
    # Run optimization
    wins = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(ultra_optimize_puzzle, args): args for args in targets}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            
            if result is not None:
                n, L0, L_best, p_best = result
                gain = L0 - L_best
                wins.append(result)
                print(f"✓ WIN n={n:4d}: {L0:.12f} -> {L_best:.12f} (gain={gain:.12f})")
            
            # Progress report every 20 puzzles
            if completed % 20 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed
                remaining = (len(targets) - completed) / rate if rate > 0 else 0
                print(f"  Progress: {completed}/{len(targets)} ({100*completed/len(targets):.1f}%) "
                      f"- {len(wins)} wins - {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    print(f"\n{'=' * 80}")
    print(f"MEGA OPTIMIZATION COMPLETE!")
    print(f"{'=' * 80}")
    print(f"Total puzzles optimized: {len(targets)}")
    print(f"Improvements found: {len(wins)}")
    print(f"Total time: {(time.time() - start_time)/60:.1f} minutes")
    
    if wins:
        # Calculate total improvement
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        avg_gain = total_gain / 1000  # Average per puzzle
        
        print(f"\nTotal score improvement: {total_gain:.12f}")
        print(f"Average improvement per puzzle: {avg_gain:.12f}")
        print(f"New estimated score: {22.251602 - total_gain:.12f}")
        
        # Save improvements
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/mega_wins.npz', **patch_data)
        print(f"\nWins saved to: output/mega_wins.npz")
        
        # Save summary
        summary = {
            'wins': len(wins),
            'total_gain': float(total_gain),
            'improvements': [
                {'n': int(n), 'L0': float(L0), 'L_best': float(L_best), 'gain': float(L0-L_best)}
                for n, L0, L_best, p in wins
            ]
        }
        
        with open('output/mega_wins_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Summary saved to: output/mega_wins_summary.json")
        
        # Create improved submission
        print(f"\nMerging improvements into submission...")
        for n, _, _, p_new in wins:
            mask = df['n'] == n
            for i, square_id in enumerate(df[mask].sort_values('square_id').index):
                df.loc[square_id, 'x'] = p_new[i, 0]
                df.loc[square_id, 'y'] = p_new[i, 1]
                df.loc[square_id, 'angle'] = p_new[i, 2]
        
        output_path = f'output/submission_mega_improved_{22.251602-total_gain:.6f}.csv'
        df.to_csv(output_path, index=False, float_format='%.50f')
        print(f"New submission saved: {output_path}")
        
    else:
        print("\n⚠ No improvements found in this optimization run")
        print("The current solution is extremely well-optimized!")

if __name__ == '__main__':
    main()
