#!/usr/bin/env python3
"""
BREAKTHROUGH 6: Reinforcement Learning Optimizer
Q-learning style algorithm that learns optimal action sequences
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure
from collections import defaultdict

print("=" * 80)
print("BREAKTHROUGH 6: REINFORCEMENT LEARNING OPTIMIZER")
print("Learns optimal action sequences through Q-learning")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 201))

# Q-table: state (quality level) -> action (parameter set) -> value
Q = defaultdict(lambda: defaultdict(float))
alpha = 0.1  # Learning rate
gamma = 0.9  # Discount factor
epsilon = 0.2  # Exploration rate

# Define action space (different parameter combinations)
actions = [
    ('ultra_tight_polish', lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.015, regularization=1e-13)),
    ('tight_polish', lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.025, regularization=5e-13)),
    ('medium_polish', lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.035, regularization=1e-12)),
    ('tight_reclose', lambda p, s: reclosure.reclose(p, seed=s, trust=0.18, tie=0.18, rounds=5, seconds=10)),
    ('medium_reclose', lambda p, s: reclosure.reclose(p, seed=s, trust=0.28, tie=0.25, rounds=5, seconds=10)),
    ('loose_reclose', lambda p, s: reclosure.reclose(p, seed=s, trust=0.38, tie=0.32, rounds=5, seconds=10)),
]

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    current = p_base.copy()
    current_L = pg.side(current)
    
    print(f"[{idx}/{len(targets)}] n={n} - RL Agent")
    
    # RL episode
    for episode in range(30):
        state = int(current_L * 100) % 100  # Discretize state
        
        # Choose action (epsilon-greedy)
        if np.random.random() < epsilon:
            action_idx = np.random.randint(len(actions))
        else:
            # Choose best action from Q-table
            action_values = [Q[state][i] for i in range(len(actions))]
            action_idx = np.argmax(action_values)
        
        action_name, action_func = actions[action_idx]
        seed = np.random.randint(1e8)
        
        try:
            next_packing, _, _ = action_func(current, seed)
            next_L = pg.side(next_packing)
            next_state = int(next_L * 100) % 100
            
            # Reward: negative change (we want to minimize)
            reward = (current_L - next_L) * 1000  # Scale up for learning
            
            # Q-learning update
            old_value = Q[state][action_idx]
            next_max = max([Q[next_state][a] for a in range(len(actions))])
            Q[state][action_idx] = old_value + alpha * (reward + gamma * next_max - old_value)
            
            if next_L < current_L:
                current = next_packing
                current_L = next_L
                print(f"  Episode {episode}: {action_name} → {current_L:.12f} (Q={Q[state][action_idx]:.3f})")
        except:
            # Negative reward for failed action
            Q[state][action_idx] -= 0.1
    
    if current_L < pg.side(p_base) - 1e-12:
        wins[n] = current
        print(f"  ★★ RL WIN for n={n}!")

if wins:
    np.savez_compressed(f"output/rl_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 6 (RL): Score {s:.12f}, {len(wins)} wins")
