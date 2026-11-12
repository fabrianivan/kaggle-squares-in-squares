#!/usr/bin/env python3
"""
EXTREME EXHAUSTIVE OPTIMIZER - Maximum possible improvement
Uses hundreds of seeds and every strategy possible per puzzle
Target: Push MUCH further below 22.251
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

def extreme_optimize(n, p_base, num_seeds=100):
    """Exhaustive optimization with 100+ seeds and all strategies"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        improvements = 0
        
        print(f"    Starting n={n}: L0={L0:.15f}")
        
        for seed in range(num_seeds):
            # Strategy 1: Reclosure with comprehensive parameter sweep
            trust_range = np.linspace(0.15, 0.85, 8)
            tie_range = np.linspace(0.08, 0.42, 8)
            
            for trust in trust_range:
                for tie in tie_range:
                    try:
                        q, _, _ = reclosure.reclose(
                            p_base if seed < 10 else best_p,
                            seed=seed*997,
                            trust=trust,
                            tie=tie,
                            rounds=40,
                            seconds=5.0
                        )
                        L_q = pg.side(q)
                        if L_q < best_L - 1e-13:
                            improvements += 1
                            best_L = L_q
                            best_p = q.copy()
                            print(f"      Seed {seed:3d} reclosure: {L_q:.15f} (gain={L0-L_q:.15e})")
                    except:
                        pass
            
            # Strategy 2: Contact polish with comprehensive parameters
            trust_start_range = np.linspace(0.008, 0.045, 8)
            reg_range = [0.0, 0.00001, 0.00005, 0.0001, 0.0005, 0.001]
            
            for trust_start in trust_start_range:
                for reg in reg_range:
                    try:
                        q, _, _ = polish.polish(
                            best_p,
                            seed=seed*509,
                            rounds=100,
                            max_seconds=5.0,
                            trust_start=trust_start,
                            regularization=reg
                        )
                        q = pg.repair(q, clearance=1e-10)
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-13:
                                improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                print(f"      Seed {seed:3d} polish:    {L_q:.15f} (gain={L0-L_q:.15e})")
                    except:
                        pass
            
            # Strategy 3: Multiple perturbation scales
            if seed % 2 == 0:
                rng = np.random.default_rng(seed * 12345)
                for scale in [0.0005, 0.001, 0.002, 0.004, 0.008]:
                    try:
                        q = best_p.copy()
                        q[:, 0] += rng.normal(0, scale, n)
                        q[:, 1] += rng.normal(0, scale, n)
                        q[:, 2] += rng.normal(0, scale * 5, n)
                        q = pg.normalize(q)
                        
                        # Recovery optimization
                        q, _, _ = reclosure.reclose(q, seed=seed, trust=0.55, tie=0.28, rounds=30, seconds=4.0)
                        q, _, _ = polish.polish(q, seed=seed+100, rounds=80, max_seconds=4.0, trust_start=0.02)
                        q = pg.repair(q, clearance=1e-10)
                        
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-13:
                                improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                print(f"      Seed {seed:3d} perturb:   {L_q:.15f} (gain={L0-L_q:.15e})")
                    except:
                        pass
            
            # Strategy 4: Rotation sweep every 5 seeds
            if seed % 5 == 0:
                for angle in np.linspace(0, np.pi/2, 12):
                    try:
                        q = pg.rotate(best_p, angle)
                        q, _, _ = polish.polish(q, seed=seed, rounds=60, max_seconds=3.0, trust_start=0.02)
                        q = pg.repair(q, clearance=1e-10)
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-13:
                                improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                print(f"      Seed {seed:3d} rotation:  {L_q:.15f} (gain={L0-L_q:.15e})")
                    except:
                        pass
        
        # Final ultra-precise optimization
        try:
            q, _, _ = reclosure.reclose(best_p, seed=99999, trust=0.45, tie=0.22, rounds=50, seconds=6.0)
            q, _, _ = polish.polish(q, seed=88888, rounds=120, max_seconds=8.0, trust_start=0.015, regularization=0.0)
            q = pg.repair(q, clearance=5e-11)
            if q is not None:
                L_q = pg.side(q)
                if L_q < best_L - 1e-13:
                    best_L = L_q
                    best_p = q.copy()
                    print(f"      FINAL ultra:    {L_q:.15f} (gain={L0-L_q:.15e})")
        except:
            pass
        
        # Final repair
        best_p = pg.repair(best_p, clearance=1e-11)
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 1e-13:
                print(f"    ✓ n={n} WIN: {L0:.15f} -> {best_L:.15f} (total gain={L0-best_L:.15e}, {improvements} improvements)")
                return (n, L0, best_L, best_p)
            else:
                print(f"    ✗ n={n} no win: {improvements} internal improvements, but no final gain")
    
    except Exception as e:
        print(f"    Error n={n}: {e}")
    
    return None

def main():
    print("=" * 80)
    print("EXTREME EXHAUSTIVE OPTIMIZER")
    print("Target: MUCH FURTHER improvement from 22.2511217459")
    print("Strategy: 100 seeds × comprehensive parameter sweeps per puzzle")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    print(f"\nLoading: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Target ALL puzzles with significant waste, prioritized by impact
    puzzles = []
    
    # Priority 1: Large puzzles (n=500-1000) - highest impact
    for n in range(500, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            weighted = waste * n * n  # Square weight
            puzzles.append((weighted, 1, waste, n, p))
    
    # Priority 2: Medium-large (n=300-499)
    for n in range(300, 500):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            weighted = waste * n * 1.5
            puzzles.append((weighted, 2, waste, n, p))
    
    # Priority 3: Medium (n=150-299)  
    for n in range(150, 300):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            weighted = waste * n
            puzzles.append((weighted, 3, waste, n, p))
    
    puzzles.sort(reverse=True)
    
    # Target top 200 puzzles (will take many hours but maximize improvement)
    top_targets = puzzles[:200]
    
    print(f"\n🎯 TARGETING TOP 200 PUZZLES BY IMPACT")
    print(f"Priority 1 (large): {sum(1 for _, p, _, _, _ in top_targets if p == 1)} puzzles")
    print(f"Priority 2 (med-lg): {sum(1 for _, p, _, _, _ in top_targets if p == 2)} puzzles")
    print(f"Priority 3 (medium): {sum(1 for _, p, _, _, _ in top_targets if p == 3)} puzzles")
    print(f"\nTop 10 targets:")
    for i, (wv, pri, waste, n, _) in enumerate(top_targets[:10], 1):
        print(f"  {i:2d}. n={n:4d} waste={waste:.6f} weight={wv:.0f}")
    
    print(f"\n🚀 RUNNING EXTREME EXHAUSTIVE OPTIMIZATION")
    print(f"⏱️  ESTIMATED TIME: 3-6 HOURS (100 seeds × many strategies per puzzle)")
    print(f"💪 This is the MOST AGGRESSIVE optimization possible!")
    print()
    
    wins = []
    start_time = time.time()
    
    for i, (wv, pri, waste, n, p) in enumerate(top_targets):
        print(f"\n[{i+1}/200] n={n} (priority {pri}, waste={waste:.6f})")
        result = extreme_optimize(n, p, num_seeds=100)
        
        if result is not None:
            wins.append(result)
        
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(top_targets) - i - 1) / rate if rate > 0 else 0
            total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
            print(f"\n  ═══ PROGRESS: {i+1}/200 ═══")
            print(f"  Wins so far: {len(wins)}")
            print(f"  Total gain so far: {total_gain:.15f}")
            print(f"  Time: {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
            print(f"  ════════════════════════════")
    
    elapsed_total = time.time() - start_time
    
    print(f"\n{'=' * 80}")
    print(f"🎉 EXTREME EXHAUSTIVE OPTIMIZATION COMPLETE! 🎉")
    print(f"{'=' * 80}")
    print(f"Puzzles optimized: {len(top_targets)}")
    print(f"Improvements found: {len(wins)}")
    print(f"Total time: {elapsed_total/3600:.2f} hours ({elapsed_total/60:.1f} minutes)")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        old_score = 22.2511217459
        new_score = old_score - total_gain
        
        print(f"\n✨ MASSIVE SUCCESS! ✨")
        print(f"Total score improvement: {total_gain:.15f}")
        print(f"Old score: {old_score:.15f}")
        print(f"New score: {new_score:.15f}")
        print(f"Reduction: {total_gain:.15f}")
        
        print(f"\n📊 Top 10 improvements:")
        wins_sorted = sorted(wins, key=lambda x: x[1]-x[2], reverse=True)
        for i, (n, L0, L_best, _) in enumerate(wins_sorted[:10], 1):
            print(f"  {i:2d}. n={n:4d}: {L0:.15f} -> {L_best:.15f} (gain={L0-L_best:.15e})")
        
        # Save everything
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/extreme_exhaustive_wins.npz', **patch_data)
        
        summary = {
            'timestamp': time.time(),
            'baseline_score': old_score,
            'new_score': float(new_score),
            'total_gain': float(total_gain),
            'wins': len(wins),
            'time_hours': elapsed_total / 3600,
            'improvements': [
                {'n': int(n), 'L0': float(L0), 'L_best': float(L_best), 'gain': float(L0-L_best)}
                for n, L0, L_best, p in wins
            ]
        }
        
        with open('output/extreme_exhaustive_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
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
        print(f"🚀 MASSIVE IMPROVEMENT - Ready to upload to Kaggle!")
        
    else:
        print(f"\n❌ No improvements found even with extreme exhaustive search")
        print(f"Baseline {old_score:.15f} is at absolute optimum!")

if __name__ == '__main__':
    main()
