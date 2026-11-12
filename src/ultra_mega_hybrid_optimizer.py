#!/usr/bin/env python3
"""
Ultra Mega Hybrid Optimizer
Combines ALL best techniques: multi-start, ensemble, adaptive, meta-learning
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def hybrid_optimize_puzzle(n, baseline_packing, total_time=300):
    """Ultimate hybrid optimization"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    start_time = time.time()
    
    # Phase 1: Multi-start polish (40% of time)
    phase1_time = total_time * 0.4
    num_seeds = 30
    
    print(f"  n={n}: Phase 1 - Multi-start polish ({num_seeds} seeds)")
    for seed_idx in range(num_seeds):
        if time.time() - start_time > phase1_time:
            break
        
        seed = np.random.randint(1e9)
        trust = 0.15 + 0.4 * np.random.random()
        reg = 10 ** (-12 - np.random.random())
        
        try:
            candidate = polish(best, seed=seed, rounds=4, 
                             max_seconds=phase1_time//num_seeds,
                             trust_start=trust, regularization=reg)
            cand_side = pg.side(candidate)
            if cand_side < best_side:
                best = candidate
                best_side = cand_side
                print(f"    Phase 1 improved: {best_side:.12f}")
        except:
            pass
    
    # Phase 2: Multi-start reclose (40% of time)
    phase2_start = time.time()
    phase2_time = total_time * 0.4
    
    print(f"  n={n}: Phase 2 - Multi-start reclose ({num_seeds} seeds)")
    for seed_idx in range(num_seeds):
        if time.time() - phase2_start > phase2_time:
            break
        
        seed = np.random.randint(1e9)
        trust = 0.15 + 0.35 * np.random.random()
        tie = 0.15 + 0.25 * np.random.random()
        
        try:
            candidate = reclose(best, seed=seed, trust=trust, tie=tie,
                              rounds=4, seconds=phase2_time//num_seeds)
            cand_side = pg.side(candidate)
            if cand_side < best_side:
                best = candidate
                best_side = cand_side
                print(f"    Phase 2 improved: {best_side:.12f}")
        except:
            pass
    
    # Phase 3: Alternating refinement (20% of time)
    phase3_start = time.time()
    phase3_time = total_time * 0.2
    
    print(f"  n={n}: Phase 3 - Alternating refinement")
    iteration = 0
    while time.time() - phase3_start < phase3_time:
        seed = np.random.randint(1e9)
        
        if iteration % 2 == 0:
            # Polish
            try:
                candidate = polish(best, seed=seed, rounds=3, max_seconds=20,
                                 trust_start=0.25, regularization=1e-12)
                cand_side = pg.side(candidate)
                if cand_side < best_side:
                    best = candidate
                    best_side = cand_side
                    print(f"    Phase 3 refined: {best_side:.12f}")
            except:
                pass
        else:
            # Reclose
            try:
                candidate = reclose(best, seed=seed, trust=0.25, tie=0.25,
                                  rounds=3, seconds=20)
                cand_side = pg.side(candidate)
                if cand_side < best_side:
                    best = candidate
                    best_side = cand_side
                    print(f"    Phase 3 refined: {best_side:.12f}")
            except:
                pass
        
        iteration += 1
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("ULTRA MEGA HYBRID OPTIMIZER")
    print("=" * 80)
    print("3-Phase Strategy: Multi-start Polish → Multi-start Reclose → Refinement")
    
    # Check column name
    cols = df.columns.tolist()
    data_col = 'squares' if 'squares' in cols else 'packing'
    print(f"Using column: {data_col}")
    
    # Target ALL 1000 puzzles with 5 minutes each
    targets = list(range(2, 1001))
    print(f"Targeting ALL {len(targets)} puzzles (5min each = 83h total)")
    print("Running in parallel with other optimizers")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row[data_col]))
        baseline_side = pg.side(baseline_packing)
        
        # Adaptive time: more for small puzzles
        if n < 50:
            opt_time = 360  # 6 min
        elif n < 150:
            opt_time = 300  # 5 min
        elif n < 400:
            opt_time = 240  # 4 min
        else:
            opt_time = 180  # 3 min
        
        best, best_side = hybrid_optimize_puzzle(n, baseline_packing, opt_time)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        
        if idx % 25 == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed
            remaining = (len(targets) - idx) / rate
            print(f"\n>>> Progress: {len(wins)} wins, {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    if wins:
        out_path = f"output/hybrid_mega_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, data_col] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path} (score={new_score:.12f})")
    
    total_time = time.time() - start_time
    print(f"\nTotal time: {total_time/3600:.1f} hours")

if __name__ == "__main__":
    main()
