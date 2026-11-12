#!/usr/bin/env python3
"""
BREAKTHROUGH 4: Momentum-Based Optimizer
Tracks improvement direction and accelerates in successful directions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish

print("=" * 80)
print("BREAKTHROUGH ALGORITHM 4: MOMENTUM OPTIMIZATION")
print("Learns from improvement history and accelerates in good directions")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 201))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    current = p_base.copy()
    current_L = pg.side(current)
    
    print(f"[{idx}/{len(targets)}] n={n}")
    
    # Track which parameters lead to improvements
    param_momentum = {'trust': 0.03, 'reg_exp': -12.5}
    momentum_velocity = {'trust': 0, 'reg_exp': 0}
    learning_rate = 0.1
    momentum_coef = 0.9
    
    for iteration in range(50):
        seed = np.random.randint(1e8)
        
        # Try current parameters
        trust = max(0.01, min(0.07, param_momentum['trust']))
        reg = 10 ** param_momentum['reg_exp']
        
        try:
            candidate, _, _ = polish.polish(current, seed=seed, rounds=5, 
                                           max_seconds=10,
                                           trust_start=trust,
                                           regularization=reg)
            candidate_L = pg.side(candidate)
            
            if candidate_L < current_L:
                improvement = current_L - candidate_L
                current = candidate
                current_L = candidate_L
                
                # Update momentum in direction of improvement
                # Increase trust slightly if this worked
                momentum_velocity['trust'] = (momentum_coef * momentum_velocity['trust'] + 
                                             learning_rate * 0.005)
                momentum_velocity['reg_exp'] = (momentum_coef * momentum_velocity['reg_exp'] + 
                                               learning_rate * 0.2)
                
                print(f"  [{iteration}] Improved → {current_L:.12f}, trust={trust:.4f}")
            else:
                # Try opposite direction
                momentum_velocity['trust'] = (momentum_coef * momentum_velocity['trust'] - 
                                             learning_rate * 0.002)
                momentum_velocity['reg_exp'] = (momentum_coef * momentum_velocity['reg_exp'] - 
                                               learning_rate * 0.1)
            
            # Update parameters with momentum
            param_momentum['trust'] += momentum_velocity['trust']
            param_momentum['reg_exp'] += momentum_velocity['reg_exp']
            param_momentum['reg_exp'] = max(-14, min(-11, param_momentum['reg_exp']))
            
        except:
            pass
    
    if current_L < pg.side(p_base) - 1e-12:
        wins[n] = current
        print(f"  ★★ n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/momentum_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 4: Score {s:.12f}, {len(wins)} wins")
