#!/usr/bin/env python3
"""
Absolute Maximum Effort Optimizer
Every technique, maximum intensity, no holds barred
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg
from src.tools.cpu_axis_reclosure import reclose
from src.tools.cpu_contact_polish import polish

def maximum_effort_puzzle(n, baseline, time_budget=180):
    """Apply every optimization technique we have"""
    best = baseline.copy()
    best_side = pg.side(best)
    start = time.time()
    
    print(f"\n  n={n}: MAXIMUM EFFORT MODE")
    print(f"  Baseline: {best_side:.12f}")
    
    # Phase 1: Rapid multi-start (30% time)
    phase1_time = time_budget * 0.3
    seeds_phase1 = 40
    
    print(f"  Phase 1: {seeds_phase1} rapid multi-starts")
    for i in range(seeds_phase1):
        if time.time() - start > phase1_time:
            break
        
        seed = np.random.randint(1e9)
        
        # Try polish
        try:
            trust = 0.15 + 0.4 * np.random.random()
            reg = 10 ** (-13 + 1.5 * np.random.random())
            cand = polish(best, seed=seed, rounds=4, max_seconds=15,
                         trust_start=trust, regularization=reg)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase1[{i}]: polish → {s:.12f}")
        except:
            pass
        
        # Try reclose
        try:
            trust = 0.15 + 0.35 * np.random.random()
            tie = 0.15 + 0.25 * np.random.random()
            cand = reclose(best, seed=seed+1, trust=trust, tie=tie,
                         rounds=4, seconds=15)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase1[{i}]: reclose → {s:.12f}")
        except:
            pass
    
    # Phase 2: Fine-grained parameter sweep (40% time)
    phase2_start = time.time()
    phase2_time = time_budget * 0.4
    
    print(f"  Phase 2: Fine parameter sweep")
    trust_grid = np.linspace(0.15, 0.5, 15)
    tie_grid = np.linspace(0.15, 0.35, 12)
    reg_grid = [1e-13, 3e-13, 1e-12, 3e-12, 1e-11]
    
    sweep_count = 0
    while time.time() - phase2_start < phase2_time and sweep_count < 60:
        seed = np.random.randint(1e9)
        sweep_count += 1
        
        # Polish with grid search
        try:
            trust = np.random.choice(trust_grid)
            reg = np.random.choice(reg_grid)
            cand = polish(best, seed=seed, rounds=5, max_seconds=20,
                         trust_start=trust, regularization=reg)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase2: polish(t={trust:.3f},r={reg:.1e}) → {s:.12f}")
        except:
            pass
        
        # Reclose with grid search
        try:
            trust = np.random.choice(trust_grid[:10])
            tie = np.random.choice(tie_grid)
            cand = reclose(best, seed=seed+1, trust=trust, tie=tie,
                         rounds=5, seconds=20)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase2: reclose(t={trust:.3f},tie={tie:.3f}) → {s:.12f}")
        except:
            pass
    
    # Phase 3: Intensive refinement (30% time)
    phase3_start = time.time()
    phase3_time = time_budget * 0.3
    
    print(f"  Phase 3: Intensive refinement")
    refine_count = 0
    while time.time() - phase3_start < phase3_time and refine_count < 30:
        seed = np.random.randint(1e9)
        refine_count += 1
        
        # High-precision polish
        try:
            cand = polish(best, seed=seed, rounds=6, max_seconds=25,
                         trust_start=0.22, regularization=1e-13)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase3: refined → {s:.12f}")
        except:
            pass
        
        # Tight reclose
        try:
            cand = reclose(best, seed=seed+1, trust=0.2, tie=0.22,
                         rounds=6, seconds=25)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    Phase3: refined → {s:.12f}")
        except:
            pass
    
    improvement = pg.side(baseline) - best_side
    print(f"  n={n}: FINAL {best_side:.12f} (Δ={improvement:.2e})")
    
    return best, best_side

def main():
    df = pd.read_csv("output/submission_final.csv")
    
    print("=" * 80)
    print("ABSOLUTE MAXIMUM EFFORT OPTIMIZER")
    print("=" * 80)
    print("3-Phase: Rapid Multi-start → Fine Sweep → Intensive Refinement")
    print("Time per puzzle: 3-10 minutes depending on size")
    
    # Target ALL puzzles with adaptive time
    targets = list(range(2, 1001))
    print(f"\nTargeting ALL {len(targets)} puzzles")
    
    packings = {}
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            packings[n] = rows[['x', 'y', 'angle']].values
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        if n not in packings:
            continue
        
        print(f"\n[{idx}/{len(targets)}] =" * 30)
        baseline = packings[n]
        baseline_side = pg.side(baseline)
        
        # Adaptive time budget
        if n < 50:
            time_budget = 600  # 10 min
        elif n < 150:
            time_budget = 360  # 6 min
        elif n < 400:
            time_budget = 240  # 4 min
        else:
            time_budget = 180  # 3 min
        
        best, best_side = maximum_effort_puzzle(n, baseline, time_budget)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"\n  ★★★ WIN FOR n={n}: {improvement:.12e} improvement ★★★")
        
        if idx % 25 == 0:
            elapsed = (time.time() - start_time) / 3600
            rate = idx / elapsed
            remaining = (len(targets) - idx) / rate
            print(f"\n{'='*60}")
            print(f"PROGRESS: {len(wins)} wins in {elapsed:.2f}h")
            print(f"Estimated remaining: {remaining:.2f}h")
            print(f"{'='*60}")
    
    if wins:
        out = f"output/maximum_wins_{len(wins)}.npz"
        np.savez_compressed(out, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            mask = df_new['n'] == n
            df_new.loc[mask, ['x', 'y', 'angle']] = packing
        
        from src.metric.metric import score
        new_score = score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ NEW SUBMISSION: {sub_path}")
        print(f"✓ SCORE: {new_score:.12f}")
    else:
        print("\nNo improvements found (baseline already excellent)")
    
    total = (time.time() - start_time) / 3600
    print(f"\nTotal runtime: {total:.2f} hours")

if __name__ == "__main__":
    main()
