#!/usr/bin/env python3
"""
BREAKTHROUGH 8: Adversarial Search
Two competing agents: one tries to improve, other tries to challenge
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

print("=" * 80)
print("BREAKTHROUGH 8: ADVERSARIAL SEARCH")
print("Two competing agents: Optimizer vs Challenger")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best = p_base.copy()
    best_L = pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n} - Adversarial Search")
    
    # Alternating game: Optimizer vs Challenger
    for round in range(15):
        # Optimizer turn: try to improve best
        optimizer_improved = False
        for _ in range(3):
            seed = np.random.randint(1e8)
            trust = 0.015 + 0.04 * np.random.random()
            reg = 10 ** (-13 + np.random.random())
            
            try:
                candidate, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=10,
                                               trust_start=trust, regularization=reg)
                if pg.side(candidate) < best_L:
                    best = candidate
                    best_L = pg.side(candidate)
                    optimizer_improved = True
                    print(f"  Round {round}: Optimizer improved → {best_L:.12f}")
                    break
            except:
                pass
        
        # Challenger turn: try to find vulnerabilities
        # Uses different method (reclose) to explore different solution space
        challenger_improved = False
        for _ in range(3):
            seed = np.random.randint(1e8)
            trust = 0.2 + 0.3 * np.random.random()
            tie = 0.2 + 0.2 * np.random.random()
            
            try:
                candidate, _, _ = reclosure.reclose(best, seed=seed, trust=trust, tie=tie,
                                                   rounds=5, seconds=10)
                if pg.side(candidate) < best_L:
                    best = candidate
                    best_L = pg.side(candidate)
                    challenger_improved = True
                    print(f"  Round {round}: Challenger improved → {best_L:.12f}")
                    break
            except:
                pass
        
        # If neither improved, increase exploration
        if not (optimizer_improved or challenger_improved):
            # Random perturbation to escape
            for _ in range(2):
                seed = np.random.randint(1e8)
                trust = 0.01 + 0.06 * np.random.random()
                reg = 10 ** (-14 + 2 * np.random.random())
                try:
                    candidate, _, _ = polish.polish(best, seed=seed, rounds=4, max_seconds=8,
                                                   trust_start=trust, regularization=reg)
                    if pg.side(candidate) < best_L:
                        best = candidate
                        best_L = pg.side(candidate)
                except:
                    pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best
        print(f"  ★★ Adversarial WIN for n={n}!")

if wins:
    np.savez_compressed(f"output/adversarial_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 8 (Adversarial): Score {s:.12f}, {len(wins)} wins")
