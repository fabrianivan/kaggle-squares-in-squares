#!/usr/bin/env python3
"""
FINAL PUSH OPTIMIZER - Systematic optimization of all high-value puzzles
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def optimize_puzzle(n, p_base, num_seeds=15):
    """Optimize a single puzzle with multiple seeds and strategies"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        # Try multiple seeds with different parameter combinations
        for seed in range(num_seeds):
            # Strategy 1: Reclosure with varying trust
            for trust_mult in [0.8, 1.0, 1.2]:
                try:
                    q, _, _ = reclosure.reclose(
                        p_base, 
                        seed=seed*37, 
                        trust=0.35*trust_mult, 
                        tie=0.18*trust_mult,
                        rounds=25, 
                        seconds=3.0
                    )
                    if pg.side(q) < best_L - 1e-11:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
            
            # Strategy 2: Polish best so far
            try:
                q, _, _ = polish.polish(
                    best_p, 
                    seed=seed*53, 
                    rounds=60, 
                    max_seconds=3.0,
                    trust_start=0.02, 
                    regularization=0.0
                )
                q = pg.repair(q, clearance=1e-9)
                if q is not None and pg.side(q) < best_L - 1e-11:
                    best_L = pg.side(q)
                    best_p = q.copy()
            except:
                pass
        
        # Final repair
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
    print("FINAL PUSH OPTIMIZER")
    print("=" * 80)
    
    # Load baseline
    baseline_path = 'output/submission_final.csv'
    print(f"\nLoading: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Calculate waste for all puzzles
    puzzles = []
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            # Weighted value: waste * n (larger n worth more)
            weighted = waste * n
            puzzles.append((weighted, waste, n, p))
    
    # Sort by weighted value and target top 150
    puzzles.sort(reverse=True)
    top_puzzles = puzzles[:150]
    
    print(f"\nTargeting top 150 puzzles by weighted value (waste × n)")
    print(f"Top 10: {[(n, f'{w:.6f}') for _, w, n, _ in top_puzzles[:10]]}")
    print(f"\nStarting sequential optimization (no multiprocessing issues)...")
    print()
    
    wins = []
    start_time = time.time()
    
    for i, (_, waste, n, p) in enumerate(top_puzzles):
        result = optimize_puzzle(n, p, num_seeds=15)
        
        if result is not None:
            n, L0, L_best, p_best = result
            gain = L0 - L_best
            wins.append(result)
            print(f"✓ WIN #{len(wins):3d} - n={n:4d}: {L0:.12f} -> {L_best:.12f} (gain={gain:.12f})")
        
        # Progress every 10 puzzles
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(top_puzzles) - i - 1) / rate if rate > 0 else 0
            print(f"  Progress: {i+1}/{len(top_puzzles)} ({100*(i+1)/len(top_puzzles):.1f}%) - "
                  f"{len(wins)} wins - {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    print(f"\n{'=' * 80}")
    print(f"OPTIMIZATION COMPLETE!")
    print(f"{'=' * 80}")
    print(f"Puzzles optimized: {len(top_puzzles)}")
    print(f"Improvements found: {len(wins)}")
    print(f"Total time: {(time.time() - start_time)/60:.1f} minutes")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        avg_gain_per_puzzle = total_gain / 1000
        new_score = 22.251602 - total_gain
        
        print(f"\n✨ SUCCESS! ✨")
        print(f"Total score improvement: {total_gain:.12f}")
        print(f"Average per puzzle: {avg_gain_per_puzzle:.12f}")
        print(f"Old score: 22.251602407995")
        print(f"New score: {new_score:.12f}")
        print(f"Score reduction: {total_gain:.12f}")
        
        # Save wins
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/final_push_wins.npz', **patch_data)
        
        # Save summary
        summary = {
            'timestamp': time.time(),
            'wins': len(wins),
            'total_gain': float(total_gain),
            'old_score': 22.251602407995,
            'new_score': float(new_score),
            'improvements': [
                {
                    'n': int(n),
                    'L0': float(L0),
                    'L_best': float(L_best),
                    'gain': float(L0 - L_best)
                }
                for n, L0, L_best, p in wins
            ]
        }
        
        with open('output/final_push_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📁 Files created:")
        print(f"  - output/final_push_wins.npz (winning packings)")
        print(f"  - output/final_push_summary.json (detailed summary)")
        
        # Create improved submission
        print(f"\n🔧 Creating improved submission...")
        df_new = df.copy()
        
        for n, _, _, p_new in wins:
            mask = df_new['n'] == n
            sorted_indices = df_new[mask].sort_values('square_id').index
            for i, idx in enumerate(sorted_indices):
                df_new.loc[idx, 'x'] = p_new[i, 0]
                df_new.loc[idx, 'y'] = p_new[i, 1]
                df_new.loc[idx, 'angle'] = p_new[i, 2]
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        df_new.to_csv(output_path, index=False, float_format='%.50f')
        
        print(f"\n✅ NEW SUBMISSION CREATED: {output_path}")
        print(f"\n🚀 Ready to upload to Kaggle!")
        
    else:
        print("\n❌ No improvements found in this optimization run")
        print("The current solution is already extremely well-optimized!")
        print("Consider:")
        print("  - Running optimization for longer (overnight)")
        print("  - Targeting different puzzle ranges")
        print("  - Using different optimization strategies")

if __name__ == '__main__':
    main()
