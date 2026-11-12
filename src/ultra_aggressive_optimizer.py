#!/usr/bin/env python3
"""
ULTRA AGGRESSIVE OPTIMIZER - Push beyond 22.2511217459
Uses the most aggressive strategies with maximum exploration
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

def ultra_aggressive_optimize(n, p_base, num_attempts=30):
    """Most aggressive optimization possible"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        # Strategy 1: Extreme reclosure with very high trust/tie
        for seed in range(num_attempts):
            for trust, tie in [(0.3, 0.15), (0.45, 0.22), (0.6, 0.3), (0.75, 0.38)]:
                try:
                    q, _, _ = reclosure.reclose(
                        p_base, 
                        seed=seed*101, 
                        trust=trust, 
                        tie=tie,
                        rounds=30, 
                        seconds=4.0
                    )
                    if pg.side(q) < best_L - 1e-12:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
            
            # Strategy 2: Aggressive polish on current best
            for trust_start in [0.012, 0.018, 0.025, 0.032]:
                for reg in [0.0, 0.00005, 0.0002]:
                    try:
                        q, _, _ = polish.polish(
                            best_p, 
                            seed=seed*73, 
                            rounds=80, 
                            max_seconds=4.0,
                            trust_start=trust_start, 
                            regularization=reg
                        )
                        q = pg.repair(q, clearance=5e-10)
                        if q is not None and pg.side(q) < best_L - 1e-12:
                            best_L = pg.side(q)
                            best_p = q.copy()
                    except:
                        pass
            
            # Strategy 3: Large perturbations + recovery
            if seed % 3 == 0:
                try:
                    rng = np.random.default_rng(seed * 1000)
                    q = best_p.copy()
                    scale = 0.003 * (1 + seed / num_attempts)
                    q[:, 0] += rng.normal(0, scale, n)
                    q[:, 1] += rng.normal(0, scale, n)
                    q[:, 2] += rng.normal(0, scale * 4, n)
                    q = pg.normalize(q)
                    
                    # Aggressive recovery
                    q, _, _ = reclosure.reclose(q, seed=seed, trust=0.5, tie=0.25, rounds=25, seconds=3.0)
                    q, _, _ = polish.polish(q, seed=seed+50, rounds=60, max_seconds=3.0, trust_start=0.02)
                    q = pg.repair(q, clearance=5e-10)
                    
                    if q is not None and pg.side(q) < best_L - 1e-12:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        # Final ultra-precise repair
        best_p = pg.repair(best_p, clearance=3e-10)
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 1e-12:
                return (n, L0, best_L, best_p)
    
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return None

def main():
    print("=" * 80)
    print("ULTRA AGGRESSIVE OPTIMIZER")
    print("Baseline: 22.2511217459 → Target: < 22.251")
    print("=" * 80)
    
    # Load new baseline
    baseline_path = 'output/submission_22.251122.csv'
    print(f"\nLoading new baseline: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Target strategy: Focus on largest puzzles (highest impact)
    # n=700-1000 have the most impact on score
    puzzles = []
    for n in range(700, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            weighted_value = waste * n * n  # Square weight for large puzzles
            puzzles.append((weighted_value, waste, n, p))
    
    # Also add medium high-value puzzles
    for n in range(400, 700):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            weighted_value = waste * n * 1.5
            puzzles.append((weighted_value, waste, n, p))
    
    puzzles.sort(reverse=True)
    top_targets = puzzles[:100]  # Top 100 highest-impact puzzles
    
    print(f"\nTargeting top 100 highest-impact puzzles")
    print(f"Top 10: {[(n, f'waste={w:.6f}', f'weight={wv:.0f}') for wv, w, n, _ in top_targets[:10]]}")
    print(f"\nRunning ULTRA AGGRESSIVE optimization (30 attempts × multiple strategies per puzzle)")
    print(f"Estimated time: 40-60 minutes\n")
    
    wins = []
    start_time = time.time()
    
    for i, (wv, waste, n, p) in enumerate(top_targets):
        result = ultra_aggressive_optimize(n, p, num_attempts=30)
        
        if result is not None:
            n, L0, L_best, p_best = result
            gain = L0 - L_best
            wins.append(result)
            print(f"✓ WIN #{len(wins):3d} - n={n:4d}: {L0:.15f} -> {L_best:.15f} (gain={gain:.15f})")
        
        if (i + 1) % 5 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(top_targets) - i - 1) / rate if rate > 0 else 0
            print(f"  Progress: {i+1}/100 ({(i+1)}%) - {len(wins)} wins - "
                  f"{elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    elapsed_total = time.time() - start_time
    
    print(f"\n{'=' * 80}")
    print(f"ULTRA AGGRESSIVE OPTIMIZATION COMPLETE!")
    print(f"{'=' * 80}")
    print(f"Puzzles optimized: {len(top_targets)}")
    print(f"Improvements found: {len(wins)}")
    print(f"Total time: {elapsed_total/60:.1f} minutes")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        old_score = 22.2511217459
        new_score = old_score - total_gain
        
        print(f"\n🎉 SUCCESS! 🎉")
        print(f"Total score improvement: {total_gain:.15f}")
        print(f"Old score: {old_score:.15f}")
        print(f"New score: {new_score:.15f}")
        print(f"Reduction: {total_gain:.15f}")
        
        # Save wins
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/ultra_aggressive_wins.npz', **patch_data)
        
        # Save summary
        summary = {
            'timestamp': time.time(),
            'baseline_score': old_score,
            'new_score': float(new_score),
            'total_gain': float(total_gain),
            'wins': len(wins),
            'improvements': [
                {'n': int(n), 'L0': float(L0), 'L_best': float(L_best), 'gain': float(L0-L_best)}
                for n, L0, L_best, p in wins
            ]
        }
        
        with open('output/ultra_aggressive_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📁 Saved:")
        print(f"  - output/ultra_aggressive_wins.npz")
        print(f"  - output/ultra_aggressive_summary.json")
        
        # Create new submission
        print(f"\n🔧 Creating new submission...")
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
        print(f"📊 NEW SCORE: {new_score:.15f}")
        print(f"\n🚀 Ready to upload to Kaggle!")
        
    else:
        print(f"\n❌ No improvements found")
        print(f"Baseline {old_score:.15f} is already extremely well-optimized!")

if __name__ == '__main__':
    main()
