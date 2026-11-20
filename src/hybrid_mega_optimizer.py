#!/usr/bin/env python3
"""
HYBRID MEGA OPTIMIZER
Combines ALL best techniques in sequence per puzzle
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def hybrid_mega_optimize(n, p_base):
    """Apply ALL techniques in optimal sequence"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        rng = np.random.default_rng(n)
        
        # Phase 1: Aggressive reclosure sweep
        for seed in range(20):
            for trust in [0.25, 0.4, 0.55, 0.7]:
                for tie in [0.15, 0.25]:
                    try:
                        q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie, rounds=30, seconds=2.5)
                        if pg.side(q) < best_L - 1e-11:
                            best_L = pg.side(q)
                            best_p = q.copy()
                    except:
                        pass
        
        # Phase 2: Intensive polish
        for seed in range(15):
            for trust_start in [0.012, 0.02, 0.028]:
                try:
                    q, _, _ = polish.polish(best_p, seed=seed, rounds=70, max_seconds=3.0, trust_start=trust_start)
                    q = pg.repair(q, clearance=1e-10)
                    if q is not None and pg.side(q) < best_L - 1e-11:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        # Phase 3: Perturbation + recovery
        for trial in range(10):
            scale = 0.002 * (1 + trial/10)
            q = best_p.copy()
            q[:, 0] += rng.normal(0, scale, n)
            q[:, 1] += rng.normal(0, scale, n)
            q[:, 2] += rng.normal(0, scale * 3, n)
            q = pg.normalize(q)
            
            try:
                q, _, _ = reclosure.reclose(q, seed=trial, trust=0.5, tie=0.25, rounds=25, seconds=2.0)
                q, _, _ = polish.polish(q, seed=trial, rounds=50, max_seconds=2.0, trust_start=0.02)
                q = pg.repair(q, clearance=1e-10)
                if q is not None and pg.side(q) < best_L - 1e-11:
                    best_L = pg.side(q)
                    best_p = q.copy()
            except:
                pass
        
        # Phase 4: Final ultra-precision
        try:
            best_p, _, _ = reclosure.reclose(best_p, seed=9999, trust=0.45, tie=0.22, rounds=40, seconds=4.0)
            best_p, _, _ = polish.polish(best_p, seed=9999, rounds=100, max_seconds=5.0, trust_start=0.015)
            best_p = pg.repair(best_p, clearance=5e-11)
        except:
            pass
        
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 1e-11:
                return (n, L0, best_L, best_p)
    except:
        pass
    return None

def main():
    print("="*80)
    print("HYBRID MEGA OPTIMIZER - All techniques combined")
    print("="*80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    # Target highest-value puzzles not heavily covered
    puzzles = []
    for n in range(750, 1001, 2):  # Every other large puzzle
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            puzzles.append((waste * n * n, n, p))
    
    puzzles.sort(reverse=True)
    targets = puzzles[:80]
    
    print(f"\nTargeting {len(targets)} high-value puzzles\n")
    
    wins = []
    for i, (_, n, p) in enumerate(targets):
        print(f"[{i+1}/{len(targets)}] Hybrid mega on n={n}...")
        result = hybrid_mega_optimize(n, p)
        if result is not None:
            wins.append(result)
            print(f"  ✓ WIN: {result[1]:.12f} -> {result[2]:.12f}")
    
    print(f"\nHybrid mega: {len(wins)} wins")
    if wins:
        np.savez('output/hybrid_wins.npz', **{str(n): p for n, _, _, p in wins})
        with open('output/hybrid_summary.json', 'w') as f:
            json.dump({'wins': len(wins), 'total_gain': float(sum(L0-L for n,L0,L,p in wins))}, f)

if __name__ == '__main__':
    main()
