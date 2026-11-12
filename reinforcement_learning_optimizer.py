#!/usr/bin/env python3
"""
Reinforcement Learning Optimizer
- Q-learning for strategy selection
- Policy gradient methods
- Experience replay
- Multi-armed bandit for parameter selection
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish
import time
from collections import deque

class MultiArmedBandit:
    """UCB1 multi-armed bandit for parameter selection"""
    
    def __init__(self, n_arms):
        self.n_arms = n_arms
        self.counts = np.zeros(n_arms)
        self.values = np.zeros(n_arms)
        self.total_count = 0
    
    def select_arm(self, exploration=2.0):
        """Select arm using UCB1 algorithm"""
        if self.total_count < self.n_arms:
            return self.total_count
        
        ucb_values = self.values + exploration * np.sqrt(
            np.log(self.total_count) / (self.counts + 1e-5)
        )
        return np.argmax(ucb_values)
    
    def update(self, arm, reward):
        """Update arm statistics"""
        self.counts[arm] += 1
        self.total_count += 1
        n = self.counts[arm]
        value = self.values[arm]
        self.values[arm] = ((n - 1) / n) * value + (1 / n) * reward

class QLearningOptimizer:
    """Q-learning for optimization strategy selection"""
    
    def __init__(self, n_states=5, n_actions=6):
        self.n_states = n_states
        self.n_actions = n_actions
        self.Q = np.zeros((n_states, n_actions))
        self.alpha = 0.1  # Learning rate
        self.gamma = 0.9  # Discount factor
        self.epsilon = 0.2  # Exploration rate
    
    def discretize_state(self, L, n):
        """Convert continuous state to discrete"""
        # State based on puzzle size
        if n < 100:
            return 0
        elif n < 200:
            return 1
        elif n < 400:
            return 2
        elif n < 700:
            return 3
        else:
            return 4
    
    def select_action(self, state):
        """Epsilon-greedy action selection"""
        if np.random.random() < self.epsilon:
            return np.random.randint(self.n_actions)
        else:
            return np.argmax(self.Q[state])
    
    def update_q(self, state, action, reward, next_state):
        """Q-learning update"""
        best_next_action = np.argmax(self.Q[next_state])
        td_target = reward + self.gamma * self.Q[next_state, best_next_action]
        td_error = td_target - self.Q[state, action]
        self.Q[state, action] += self.alpha * td_error
    
    def get_best_action(self, state):
        """Get best action without exploration"""
        return np.argmax(self.Q[state])

class ExperienceReplay:
    """Store and replay past experiences"""
    
    def __init__(self, capacity=1000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
    
    def add(self, state, action, reward, next_state, packing):
        """Add experience"""
        self.buffer.append((state, action, reward, next_state, packing.copy()))
    
    def sample(self, batch_size=10):
        """Sample random batch"""
        indices = np.random.choice(len(self.buffer), 
                                   min(batch_size, len(self.buffer)), 
                                   replace=False)
        return [self.buffer[i] for i in indices]
    
    def get_best_packings(self, k=5):
        """Get k best packings from replay buffer"""
        if not self.buffer:
            return []
        
        # Sort by reward (negative side length)
        sorted_buffer = sorted(self.buffer, key=lambda x: x[2], reverse=True)
        return [exp[4] for exp in sorted_buffer[:k]]

def execute_action(packing, action, seed):
    """Execute optimization action"""
    actions = {
        0: ('tight_polish', {'rounds': 6, 'max_seconds': 10, 
                            'trust_start': 0.01, 'regularization': 1e-13}),
        1: ('loose_polish', {'rounds': 5, 'max_seconds': 10,
                            'trust_start': 0.04, 'regularization': 1e-11}),
        2: ('aggressive_reclose', {'trust': 0.4, 'tie': 0.35, 
                                   'rounds': 6, 'seconds': 10}),
        3: ('gentle_reclose', {'trust': 0.18, 'tie': 0.22,
                              'rounds': 6, 'seconds': 10}),
        4: ('balanced_reclose', {'trust': 0.25, 'tie': 0.25,
                                'rounds': 5, 'seconds': 10}),
        5: ('random_explore', {'trust': 0.15 + 0.35*np.random.random(),
                              'tie': 0.15 + 0.30*np.random.random(),
                              'rounds': 5, 'seconds': 10})
    }
    
    action_name, params = actions[action]
    
    try:
        if 'polish' in action_name:
            result, _, _ = polish.polish(packing, seed=seed, **params)
        else:
            result, _, _ = reclosure.reclose(packing, seed=seed, **params)
        return result, True
    except:
        return packing, False

def reinforcement_learning_optimize(packing, puzzle_n, n_episodes=40):
    """RL-based optimization"""
    q_learner = QLearningOptimizer()
    replay = ExperienceReplay()
    
    best_pack = packing.copy()
    best_L = pg.side(best_pack)
    
    current_pack = best_pack.copy()
    current_L = best_L
    
    for episode in range(n_episodes):
        # Get state
        state = q_learner.discretize_state(current_L, puzzle_n)
        
        # Select action
        action = q_learner.select_action(state)
        
        # Execute action
        seed = episode * 777
        new_pack, success = execute_action(current_pack, action, seed)
        
        if success:
            new_L = pg.side(new_pack)
            
            # Calculate reward (improvement)
            reward = (current_L - new_L) * 1000  # Scale up for learning
            
            # Get next state
            next_state = q_learner.discretize_state(new_L, puzzle_n)
            
            # Store experience
            replay.add(state, action, reward, next_state, new_pack)
            
            # Update Q-values
            q_learner.update_q(state, action, reward, next_state)
            
            # Update current and best
            if new_L < current_L:
                current_pack = new_pack.copy()
                current_L = new_L
            
            if new_L < best_L:
                best_L = new_L
                best_pack = new_pack.copy()
            
            # Experience replay (learn from past)
            if episode % 5 == 0 and len(replay.buffer) > 10:
                batch = replay.sample(5)
                for s, a, r, ns, _ in batch:
                    q_learner.update_q(s, a, r, ns)
    
    # Ensemble from replay buffer
    best_packings = replay.get_best_packings(k=5)
    if best_packings:
        # Try averaging best packings
        avg_pack = np.mean([p for p in best_packings], axis=0)
        try:
            avg_pack, _, _ = polish.polish(avg_pack, seed=99999,
                                          rounds=5, max_seconds=10,
                                          trust_start=0.02,
                                          regularization=1e-12)
            avg_L = pg.side(avg_pack)
            if avg_L < best_L:
                best_L = avg_L
                best_pack = avg_pack.copy()
        except:
            pass
    
    return best_pack, best_L, q_learner

def bandit_parameter_selection(packing, n_attempts=50):
    """Use multi-armed bandit for parameter selection"""
    
    # Define parameter arms
    param_arms = [
        {'trust': 0.15, 'tie': 0.20},
        {'trust': 0.20, 'tie': 0.25},
        {'trust': 0.25, 'tie': 0.30},
        {'trust': 0.30, 'tie': 0.20},
        {'trust': 0.35, 'tie': 0.25},
        {'trust': 0.40, 'tie': 0.30},
        {'trust': 0.18, 'tie': 0.35},
        {'trust': 0.28, 'tie': 0.18},
    ]
    
    bandit = MultiArmedBandit(len(param_arms))
    
    best_pack = packing.copy()
    best_L = pg.side(best_pack)
    
    for attempt in range(n_attempts):
        # Select arm
        arm = bandit.select_arm(exploration=2.0)
        params = param_arms[arm]
        
        # Try optimization
        seed = attempt * 543
        try:
            result, _, _ = reclosure.reclose(best_pack, seed=seed,
                                            trust=params['trust'],
                                            tie=params['tie'],
                                            rounds=5, seconds=10)
            result_L = pg.side(result)
            
            # Calculate reward
            improvement = best_L - result_L
            reward = improvement * 10000  # Scale up
            
            # Update bandit
            bandit.update(arm, reward)
            
            # Update best
            if result_L < best_L:
                best_L = result_L
                best_pack = result.copy()
        except:
            # Negative reward for failure
            bandit.update(arm, -1.0)
    
    return best_pack, best_L, bandit

def optimize_puzzle_rl(args):
    """RL optimizer for single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d} L_start={pg.side(p_base):.9f}")
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Q-learning
    try:
        print(f"    Running Q-learning...")
        candidate, candidate_L, q_learner = reinforcement_learning_optimize(best_p, n, n_episodes=30)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Q-learning improved: {candidate_L:.9f}")
            
            # Show learned Q-values
            state = q_learner.discretize_state(candidate_L, n)
            best_action = q_learner.get_best_action(state)
            print(f"    Learned best action for state: {best_action}")
    except Exception as e:
        print(f"    Q-learning failed: {e}")
    
    # Strategy 2: Multi-armed bandit
    try:
        print(f"    Running bandit selection...")
        candidate, candidate_L, bandit = bandit_parameter_selection(best_p, n_attempts=40)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Bandit improved: {candidate_L:.9f}")
            
            # Show best arm
            best_arm = np.argmax(bandit.values)
            print(f"    Best arm: {best_arm} (value={bandit.values[best_arm]:.4f})")
    except Exception as e:
        print(f"    Bandit failed: {e}")
    
    # Final polish
    try:
        for seed in range(3):
            candidate, _, _ = polish.polish(best_p, seed=seed*11111,
                                           rounds=7, max_seconds=15,
                                           trust_start=0.018,
                                           regularization=8e-13)
            candidate_L = pg.side(candidate)
            if candidate_L < best_L:
                best_L = candidate_L
                best_p = candidate.copy()
    except:
        pass
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f"  → Final: {best_L:.9f} ★WIN! Δ={improvement:.2e}\n")
        return (n, best_p, best_L, improvement)
    else:
        print(f"  → Final: {best_L:.9f}\n")
        return None

def main():
    print("=" * 80)
    print("REINFORCEMENT LEARNING OPTIMIZER")
    print("=" * 80)
    print("Q-Learning, Multi-Armed Bandits, Experience Replay, Policy Learning")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target wide range
    targets = list(range(100, 600))
    
    print(f"Targeting {len(targets)} puzzles (n=100-600)")
    print(f"RL learns optimal strategies during optimization\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_rl((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} RL improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/rl_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_rl_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {new_score:.12f}")
        print(f"  File: {sub_path}")

if __name__ == '__main__':
    main()
