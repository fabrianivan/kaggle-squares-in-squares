#!/usr/bin/env python3
"""
NUCLEAR OPTIMIZER - ABSOLUTE MAXIMUM EFFORT
500 seeds per puzzle, every possible strategy, ultra-long runtime
TARGET: Drop score to 22.24X or below!
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def nuclear_optimize(n, p_base, num_seeds=500):
    """NUCLEAR-LEVEL optimization - 500 seeds with ALL strategies"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        total_improvements = 0
        best_seed = -1
        
        print(f"\n╔═══════════════════════════════════════════════════════════════╗")
        print(f"║ NUCLEAR OPTIMIZATION: n={n:4d}                                  ║")
        print(f"║ Starting L: {L0:.15f}                      ║")
        print(f"║ Target: Find ANY improvement with 500 seeds!                 ║")
        print(f"╚═══════════════════════════════════════════════════════════════╝")
        
        for seed in range(num_seeds):
            seed_start = time.time()
            seed_improvements = 0
            
            # PHASE 1: Ultra-comprehensive reclosure (10x10 grid)
            trust_grid = np.linspace(0.1, 0.9, 10)
            tie_grid = np.linspace(0.05, 0.45, 10)
            
            for i, trust in enumerate(trust_grid):
                for j, tie in enumerate(tie_grid):
                    try:
                        q, _, _ = reclosure.reclose(
                            p_base if seed < 20 else best_p,
                            seed=seed*1009 + i*10 + j,
                            trust=trust,
                            tie=tie,
                            rounds=50,
                            seconds=6.0
                        )
                        L_q = pg.side(q)
                        if L_q < best_L - 1e-14:
                            seed_improvements += 1
                            total_improvements += 1
                            best_L = L_q
                            best_p = q.copy()
                            best_seed = seed
                            print(f"    🎯 Seed {seed:3d} reclosure[{i},{j}]: {L_q:.15f} ▼{L0-L_q:.2e}")
                    except:
                        pass
            
            # PHASE 2: Ultra-comprehensive polish (12x8 grid)
            trust_start_grid = np.linspace(0.005, 0.05, 12)
            reg_grid = [0.0, 0.000001, 0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.002]
            
            for i, trust_start in enumerate(trust_start_grid):
                for j, reg in enumerate(reg_grid):
                    try:
                        q, _, _ = polish.polish(
                            best_p,
                            seed=seed*503 + i*8 + j,
                            rounds=120,
                            max_seconds=6.0,
                            trust_start=trust_start,
                            regularization=reg
                        )
                        q = pg.repair(q, clearance=5e-12)
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-14:
                                seed_improvements += 1
                                total_improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                best_seed = seed
                                print(f"    🎯 Seed {seed:3d} polish[{i},{j}]:    {L_q:.15f} ▼{L0-L_q:.2e}")
                    except:
                        pass
            
            # PHASE 3: Multi-scale perturbations (10 scales)
            if seed % 3 == 0:
                rng = np.random.default_rng(seed * 98765)
                scales = np.logspace(-3.5, -1.5, 10)  # 0.0003 to 0.03
                
                for scale in scales:
                    try:
                        q = best_p.copy()
                        q[:, 0] += rng.normal(0, scale, n)
                        q[:, 1] += rng.normal(0, scale, n)
                        q[:, 2] += rng.normal(0, scale * 6, n)
                        q = pg.normalize(q)
                        
                        # Aggressive recovery
                        q, _, _ = reclosure.reclose(q, seed=seed, trust=0.6, tie=0.3, rounds=40, seconds=5.0)
                        q, _, _ = polish.polish(q, seed=seed+200, rounds=100, max_seconds=5.0, trust_start=0.018, regularization=0.0)
                        q = pg.repair(q, clearance=5e-12)
                        
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-14:
                                seed_improvements += 1
                                total_improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                best_seed = seed
                                print(f"    🎯 Seed {seed:3d} perturb[{scale:.1e}]: {L_q:.15f} ▼{L0-L_q:.2e}")
                    except:
                        pass
            
            # PHASE 4: Rotation sweep (every 4 seeds, 20 angles)
            if seed % 4 == 0:
                for angle in np.linspace(0, np.pi/2, 20):
                    try:
                        q = pg.rotate(best_p, angle)
                        q, _, _ = polish.polish(q, seed=seed, rounds=80, max_seconds=4.0, trust_start=0.02, regularization=0.0)
                        q = pg.repair(q, clearance=5e-12)
                        if q is not None:
                            L_q = pg.side(q)
                            if L_q < best_L - 1e-14:
                                seed_improvements += 1
                                total_improvements += 1
                                best_L = L_q
                                best_p = q.copy()
                                best_seed = seed
                                print(f"    🎯 Seed {seed:3d} rotation[{angle:.3f}]: {L_q:.15f} ▼{L0-L_q:.2e}")
                    except:
                        pass
            
            # PHASE 5: Simulated annealing (every 10 seeds)
            if seed % 10 == 0:
                rng = np.random.default_rng(seed * 54321)
                current = best_p.copy()
                current_L = best_L
                T = 0.05
                
                for sa_iter in range(100):
                    scale = T * 0.01
                    candidate = current.copy()
                    candidate[:, 0] += rng.normal(0, scale, n)
                    candidate[:, 1] += rng.normal(0, scale, n)
                    candidate[:, 2] += rng.normal(0, scale * 3, n)
                    candidate = pg.normalize(candidate)
                    candidate = pg.repair(candidate, clearance=5e-12)
                    
                    if candidate is not None:
                        L_cand = pg.side(candidate)
                        delta = L_cand - current_L
                        
                        if delta < 0 or rng.random() < np.exp(-delta / (T * current_L)):
                            current = candidate
                            current_L = L_cand
                            
                            if L_cand < best_L - 1e-14:
                                seed_improvements += 1
                                total_improvements += 1
                                best_L = L_cand
                                best_p = candidate.copy()
                                best_seed = seed
                                print(f"    🎯 Seed {seed:3d} SA[{sa_iter:3d}]:      {L_cand:.15f} ▼{L0-L_cand:.2e}")
                    
                    T *= 0.95
            
            # Progress report every 10 seeds
            if (seed + 1) % 10 == 0:
                elapsed = time.time() - seed_start
                if seed_improvements > 0:
                    print(f"    ✓ Seed {seed:3d} complete: {seed_improvements} improvements in {elapsed:.1f}s")
                elif (seed + 1) % 50 == 0:
                    print(f"    ○ Seeds {seed-49:3d}-{seed:3d}: {total_improvements} total improvements so far")
        
        # FINAL PHASE: Ultra-precise optimization on best result
        print(f"\n    ═══ FINAL ULTRA-PRECISION PASS ═══")
        for final_seed in range(10):
            try:
                q, _, _ = reclosure.reclose(best_p, seed=999000+final_seed, trust=0.48, tie=0.24, rounds=60, seconds=8.0)
                q, _, _ = polish.polish(q, seed=888000+final_seed, rounds=150, max_seconds=10.0, trust_start=0.012, regularization=0.0)
                q = pg.repair(q, clearance=1e-12)
                if q is not None:
                    L_q = pg.side(q)
                    if L_q < best_L - 1e-14:
                        best_L = L_q
                        best_p = q.copy()
                        print(f"    🎯 FINAL {final_seed}: {L_q:.15f} ▼{L0-L_q:.2e}")
            except:
                pass
        
        # Ultra-final repair
        best_p = pg.repair(best_p, clearance=1e-13)
        if best_p is not None:
            best_L = pg.side(best_p)
            
            if best_L < L0 - 1e-14:
                gain = L0 - best_L
                print(f"\n╔═══════════════════════════════════════════════════════════════╗")
                print(f"║ ✨ NUCLEAR SUCCESS! n={n:4d}                                  ║")
                print(f"║ L0:      {L0:.15f}                      ║")
                print(f"║ L_best:  {best_L:.15f}                      ║")
                print(f"║ GAIN:    {gain:.15e}                              ║")
                print(f"║ Improvements found: {total_improvements:4d} | Best seed: {best_seed:3d}        ║")
                print(f"╚═══════════════════════════════════════════════════════════════╝")
                return (n, L0, best_L, best_p)
            else:
                print(f"\n    ✗ n={n}: {total_improvements} internal improvements, no final gain")
    
    except Exception as e:
        print(f"    ✗ Error n={n}: {e}")
    
    return None

def main():
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║                      NUCLEAR OPTIMIZER                                 ║")
    print("║                   ABSOLUTE MAXIMUM EFFORT                              ║")
    print("║                                                                        ║")
    print("║  Strategy: 500 seeds × comprehensive grids × multiple strategies      ║")
    print("║  Target: Drop score SIGNIFICANTLY below 22.25                         ║")
    print("║  Runtime: 6-12 HOURS (worth it for maximum improvement!)              ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    
    baseline_path = 'output/submission_22.251122.csv'
    print(f"\n📁 Loading baseline: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Target ONLY the highest-impact puzzles
    puzzles = []
    
    # Ultra-priority: n=800-1000 (massive impact)
    for n in range(800, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            impact = waste * n * n * n  # Cubic weight!
            puzzles.append((impact, waste, n, p))
    
    # High priority: n=600-799
    for n in range(600, 800):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            impact = waste * n * n * 1.5
            puzzles.append((impact, waste, n, p))
    
    # Medium priority: n=400-599
    for n in range(400, 600):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            impact = waste * n * n
            puzzles.append((impact, waste, n, p))
    
    puzzles.sort(reverse=True)
    top_targets = puzzles[:150]  # Top 150 HIGHEST-IMPACT puzzles
    
    print(f"\n🎯 TARGETING TOP 150 HIGHEST-IMPACT PUZZLES")
    print(f"   Ranges: n=400-1000")
    print(f"\n📊 Top 10 targets:")
    for i, (impact, waste, n, _) in enumerate(top_targets[:10], 1):
        print(f"   {i:2d}. n={n:4d} | waste={waste:.6f} | impact={impact:.0f}")
    
    print(f"\n╔═══════════════════════════════════════════════════════════════════════╗")
    print(f"║ 🚀 STARTING NUCLEAR OPTIMIZATION                                      ║")
    print(f"║                                                                        ║")
    print(f"║ Per puzzle:                                                            ║")
    print(f"║   • 500 seeds (not 10-100, but 500!)                                  ║")
    print(f"║   • 10×10 reclosure grid = 100 combinations per seed                  ║")
    print(f"║   • 12×8 polish grid = 96 combinations per seed                       ║")
    print(f"║   • 10 perturbation scales                                            ║")
    print(f"║   • 20 rotation angles (every 4 seeds)                                ║")
    print(f"║   • 100 SA iterations (every 10 seeds)                                ║")
    print(f"║   • Final ultra-precision pass                                        ║")
    print(f"║                                                                        ║")
    print(f"║ Expected time: 6-12 HOURS                                             ║")
    print(f"║ Expected improvement: 0.001-0.005+ (MASSIVE!)                         ║")
    print(f"╚═══════════════════════════════════════════════════════════════════════╝")
    
    input(f"\n⚠️  This will take 6-12 HOURS. Press ENTER to start...")
    
    wins = []
    start_time = time.time()
    
    print(f"\n{'='*75}")
    print(f"OPTIMIZATION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*75}\n")
    
    for i, (impact, waste, n, p) in enumerate(top_targets):
        print(f"\n{'█'*75}")
        print(f"PUZZLE {i+1}/150 | n={n} | waste={waste:.6f} | impact={impact:.0f}")
        print(f"{'█'*75}")
        
        result = nuclear_optimize(n, p, num_seeds=500)
        
        if result is not None:
            wins.append(result)
        
        if (i + 1) % 5 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(top_targets) - i - 1) / rate if rate > 0 else 0
            total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
            
            print(f"\n{'═'*75}")
            print(f"PROGRESS CHECKPOINT: {i+1}/150 puzzles complete")
            print(f"Wins: {len(wins)} | Total gain: {total_gain:.15f}")
            print(f"Time: {elapsed/3600:.2f}h elapsed | ~{remaining/3600:.2f}h remaining")
            print(f"{'═'*75}\n")
    
    elapsed_total = time.time() - start_time
    
    print(f"\n╔═══════════════════════════════════════════════════════════════════════╗")
    print(f"║              🎉 NUCLEAR OPTIMIZATION COMPLETE! 🎉                      ║")
    print(f"╚═══════════════════════════════════════════════════════════════════════╝")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Puzzles optimized: {len(top_targets)}")
    print(f"Improvements found: {len(wins)}")
    print(f"Total time: {elapsed_total/3600:.2f} hours")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        old_score = 22.2511217459
        new_score = old_score - total_gain
        
        print(f"\n✨✨✨ MASSIVE SUCCESS! ✨✨✨")
        print(f"Old score:       {old_score:.15f}")
        print(f"New score:       {new_score:.15f}")
        print(f"Total gain:      {total_gain:.15f}")
        print(f"Score reduction: {(total_gain/old_score)*100:.4f}%")
        
        # Save
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/nuclear_wins.npz', **patch_data)
        
        summary = {
            'timestamp': time.time(),
            'baseline_score': old_score,
            'new_score': float(new_score),
            'total_gain': float(total_gain),
            'wins': len(wins),
            'time_hours': elapsed_total / 3600,
            'seeds_per_puzzle': 500,
            'improvements': [
                {'n': int(n), 'L0': float(L0), 'L_best': float(L_best), 'gain': float(L0-L_best)}
                for n, L0, L_best, p in wins
            ]
        }
        
        with open('output/nuclear_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Create submission
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
        
        print(f"\n✅ NEW SUBMISSION: {output_path}")
        print(f"🚀 READY TO DOMINATE KAGGLE! 🚀")

if __name__ == '__main__':
    main()
