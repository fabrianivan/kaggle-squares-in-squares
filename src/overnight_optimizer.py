#!/usr/bin/env python3
"""
Overnight Optimizer - Exhaustive search for microscopic improvements
Runs multiple passes with different strategies over many hours
"""
import sys
import json
import math
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def intensive_optimize(args):
    """Intensive optimization with many random seeds and strategies"""
    n, p_base, job_id = args
    L0 = pg.side(p_base)
    best_L = L0
    best_p = None
    
    # Strategy 1: Reclosure with many seeds and parameter variations
    for seed_offset in range(50):  # 50 different seeds
        seed = job_id * 1000 + seed_offset
        
        for trust, tie in [(0.2, 0.1), (0.3, 0.15), (0.4, 0.2), (0.5, 0.25)]:
            try:
                q, _, _ = reclosure.reclose(
                    p_base, seed=seed, trust=trust, tie=tie,
                    rounds=25, seconds=4.0
                )
                
                # Polish the result
                q, _, _ = polish.polish(
                    q, seed=seed+7, rounds=60, max_seconds=4.0,
                    trust_start=0.018, regularization=0.0
                )
                
                q = pg.repair(q, clearance=1.2e-9)
                if q is not None:
                    L = pg.side(q)
                    if L < best_L - 1e-12:
                        best_L = L
                        best_p = q.copy()
            except:
                pass
    
    # Strategy 2: Perturbation + polish with many attempts
    rng = np.random.default_rng(job_id * 13337)
    for attempt in range(30):
        try:
            p_pert = p_base.copy()
            scale = 0.003 * (0.5 + 0.5 * attempt / 30)  # Varying scales
            p_pert[:, 0] += rng.normal(0, scale, n)
            p_pert[:, 1] += rng.normal(0, scale, n)
            p_pert[:, 2] += rng.normal(0, scale * 3, n)
            p_pert = pg.normalize(p_pert)
            
            # Polish
            q, _, _ = polish.polish(
                p_pert, seed=job_id*2000+attempt, rounds=70, max_seconds=4.0,
                trust_start=0.02, regularization=0.0
            )
            q = pg.repair(q, clearance=1.2e-9)
            
            if q is not None:
                L = pg.side(q)
                if L < best_L - 1e-12:
                    best_L = L
                    best_p = q.copy()
        except:
            pass
    
    # Strategy 3: Try optimal rotation of best result
    if best_p is not None and best_L < L0 - 1e-12:
        try:
            q_rot, _ = pg.optimal_rotation(best_p)
            L_rot = pg.side(q_rot)
            if L_rot < best_L - 1e-12:
                best_L = L_rot
                best_p = q_rot.copy()
        except:
            pass
    
    if best_p is not None and best_L < L0 - 1e-12:
        gain = (L0 - best_L) / math.sqrt(n)
        return (n, L0, best_L, best_p, gain)
    
    return None

def main():
    print("=" * 80)
    print("OVERNIGHT EXHAUSTIVE OPTIMIZER")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Configuration
    N_WORKERS = 8
    PASSES = 3  # Multiple passes through the puzzle set
    
    # Load baseline
    baseline_path = 'output/submission_final.csv'
    print(f"\nLoading baseline: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Calculate initial score
    bank = {}
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            bank[n] = g[['x', 'y', 'angle']].to_numpy(float)
    
    initial_score = sum(pg.side(bank[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"Initial score: {initial_score:.12f}")
    
    # Target selection: all puzzles, prioritized by potential
    targets = []
    for n in range(1, 1001):
        L = pg.side(bank[n])
        waste = L / math.sqrt(n) - 1
        # Weight: larger puzzles and higher waste
        weight = waste * math.sqrt(n)
        targets.append((weight, n, bank[n]))
    
    targets.sort(reverse=True)
    
    # Use top 300 for detailed optimization
    optimization_targets = targets[:300]
    print(f"\nTargeting {len(optimization_targets)} puzzles over {PASSES} passes")
    print(f"Top 10: {[n for _, n, _ in optimization_targets[:10]]}")
    print(f"Workers: {N_WORKERS}")
    
    all_wins = {}
    
    for pass_num in range(1, PASSES + 1):
        print(f"\n{'=' * 80}")
        print(f"PASS {pass_num}/{PASSES}")
        print(f"{'=' * 80}")
        
        jobs = []
        for job_id, (weight, n, p) in enumerate(optimization_targets):
            # Use current best (may have been improved in previous pass)
            current_p = all_wins.get(n, (None, None, p))[2]
            jobs.append((n, current_p, job_id + pass_num * 10000))
        
        wins_this_pass = 0
        total_gain = 0.0
        
        start_time = time.time()
        completed = 0
        
        with ProcessPoolExecutor(max_workers=N_WORKERS) as executor:
            futures = {executor.submit(intensive_optimize, job): job for job in jobs}
            
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                
                if result is not None:
                    n, L0, L_best, p_best, gain = result
                    
                    # Check if this is better than any previous win for this puzzle
                    if n not in all_wins or L_best < all_wins[n][1] - 1e-12:
                        all_wins[n] = (L0, L_best, p_best, gain)
                        wins_this_pass += 1
                        total_gain += gain
                        print(f"  ✓ n={n:4d}: {L0:.12f} → {L_best:.12f} (gain={gain:.12f})")
                
                # Progress update every 20 jobs
                if completed % 20 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed
                    remaining = (len(jobs) - completed) / rate if rate > 0 else 0
                    print(f"  Progress: {completed}/{len(jobs)} ({completed*100//len(jobs)}%) | "
                          f"Wins: {wins_this_pass} | "
                          f"ETA: {remaining/60:.1f} min")
        
        pass_time = time.time() - start_time
        print(f"\nPass {pass_num} complete: {wins_this_pass} new/improved wins in {pass_time/60:.1f} min")
    
    # Final results
    print(f"\n{'=' * 80}")
    print("OPTIMIZATION COMPLETE")
    print(f"{'=' * 80}")
    print(f"Total unique puzzle improvements: {len(all_wins)}")
    
    if all_wins:
        total_gain = sum(gain for _, _, _, gain in all_wins.values())
        print(f"Total score gain: {total_gain:.12f}")
        print(f"New score: {initial_score - total_gain:.12f}")
        
        # Save wins
        patch_data = {str(n): p for n, (L0, L_best, p, gain) in all_wins.items()}
        np.savez('output/overnight_wins.npz', **patch_data)
        print(f"\nWins saved to: output/overnight_wins.npz")
        
        # Create improved submission using portfolio_union
        print("\nBuilding improved submission...")
        sys.path.insert(0, 'src/tools')
        from portfolio_union import build_portfolio
        
        summary = build_portfolio(
            source_paths={'baseline': baseline_path},
            leader_name='baseline',
            output_path='output/submission_overnight_improved.csv',
            patch_path='output/overnight_wins.npz'
        )
        
        final_score = summary['score']
        print(f"\nFinal submission score: {final_score:.12f}")
        print(f"Improvement: {initial_score - final_score:.12f}")
        print(f"Saved to: output/submission_overnight_improved.csv")
        
        # Save detailed log
        log = {
            'start_time': datetime.now().isoformat(),
            'initial_score': initial_score,
            'final_score': final_score,
            'improvement': initial_score - final_score,
            'wins_count': len(all_wins),
            'wins': [
                {
                    'n': n,
                    'L0': float(L0),
                    'L_best': float(L_best),
                    'gain': float(gain)
                }
                for n, (L0, L_best, _, gain) in sorted(all_wins.items())
            ]
        }
        
        with open('output/overnight_log.json', 'w') as f:
            json.dump(log, f, indent=2)
        
        print("\nTop 20 improvements:")
        wins_sorted = sorted(all_wins.items(), key=lambda x: x[1][3], reverse=True)
        for i, (n, (L0, L_best, _, gain)) in enumerate(wins_sorted[:20], 1):
            print(f"  {i:2d}. n={n:4d}: gain={gain:.12f} ({L0:.8f} → {L_best:.8f})")
    else:
        print("No improvements found - solution is at local optimum")
    
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
