#!/usr/bin/env python3
"""
Advanced Gradient Descent Optimizer
- Adam optimizer with momentum
- Learning rate scheduling
- Gradient clipping
- Multi-scale optimization (coarse to fine)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import time

class AdamOptimizer:
    """Adam optimizer for packing coordinates"""
    def __init__(self, learning_rate=0.01, beta1=0.9, beta2=0.999, epsilon=1e-8):
        self.lr = learning_rate
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.m = None  # First moment
        self.v = None  # Second moment
        self.t = 0     # Time step
    
    def initialize(self, shape):
        """Initialize moment vectors"""
        self.m = np.zeros(shape)
        self.v = np.zeros(shape)
        self.t = 0
    
    def step(self, gradient):
        """Apply Adam update"""
        self.t += 1
        
        # Update biased first moment estimate
        self.m = self.beta1 * self.m + (1 - self.beta1) * gradient
        
        # Update biased second raw moment estimate
        self.v = self.beta2 * self.v + (1 - self.beta2) * (gradient ** 2)
        
        # Compute bias-corrected first moment estimate
        m_hat = self.m / (1 - self.beta1 ** self.t)
        
        # Compute bias-corrected second raw moment estimate
        v_hat = self.v / (1 - self.beta2 ** self.t)
        
        # Update parameters
        update = self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
        
        return update

def compute_numerical_gradient(packing, epsilon=1e-6):
    """Compute numerical gradient of side length w.r.t. positions"""
    n = len(packing)
    gradient = np.zeros_like(packing)
    
    current_L = pg.side(packing)
    
    # Gradient for positions (x, y)
    for i in range(n):
        for j in range(2):  # x and y
            perturbed = packing.copy()
            perturbed[i, j] += epsilon
            L_plus = pg.side(perturbed)
            gradient[i, j] = (L_plus - current_L) / epsilon
    
    # Gradient for angles (more carefully)
    for i in range(n):
        perturbed = packing.copy()
        perturbed[i, 2] += epsilon
        L_plus = pg.side(perturbed)
        gradient[i, 2] = (L_plus - current_L) / epsilon
    
    return gradient

def multiscale_optimization(packing, scales=[0.1, 0.05, 0.02, 0.01]):
    """Optimize from coarse to fine scale"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    for scale in scales:
        # Initialize Adam optimizer for this scale
        adam = AdamOptimizer(learning_rate=scale)
        adam.initialize(best_p.shape)
        
        # Gradient descent steps
        for step in range(20):
            # Compute gradient
            gradient = compute_numerical_gradient(best_p, epsilon=scale*0.01)
            
            # Clip gradient to prevent explosion
            max_norm = 10.0
            grad_norm = np.linalg.norm(gradient)
            if grad_norm > max_norm:
                gradient = gradient * (max_norm / grad_norm)
            
            # Apply Adam update
            update = adam.step(gradient)
            
            # Update packing
            candidate = best_p - update  # Subtract because we minimize
            
            # Project to valid range if needed
            candidate[:, :2] = np.clip(candidate[:, :2], -50, 50)
            candidate[:, 2] = np.mod(candidate[:, 2], 2*np.pi)
            
            # Evaluate
            try:
                candidate_L = pg.side(candidate)
                if candidate_L < best_L:
                    best_L = candidate_L
                    best_p = candidate.copy()
            except:
                break  # Invalid packing
    
    return best_p, best_L

def cyclical_learning_rate_optimize(packing, n_cycles=5):
    """Use cyclical learning rate (triangular schedule)"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    lr_min, lr_max = 0.001, 0.1
    steps_per_cycle = 50
    
    adam = AdamOptimizer()
    adam.initialize(best_p.shape)
    
    for cycle in range(n_cycles):
        for step in range(steps_per_cycle):
            # Triangular learning rate schedule
            progress = step / steps_per_cycle
            if progress < 0.5:
                lr = lr_min + (lr_max - lr_min) * (progress * 2)
            else:
                lr = lr_max - (lr_max - lr_min) * ((progress - 0.5) * 2)
            
            adam.lr = lr
            
            # Compute and apply gradient
            gradient = compute_numerical_gradient(best_p, epsilon=0.001)
            grad_norm = np.linalg.norm(gradient)
            if grad_norm > 5.0:
                gradient = gradient * (5.0 / grad_norm)
            
            update = adam.step(gradient)
            candidate = best_p - update
            
            try:
                candidate_L = pg.side(candidate)
                if candidate_L < best_L:
                    best_L = candidate_L
                    best_p = candidate.copy()
            except:
                pass
    
    return best_p, best_L

def optimize_puzzle_gradient(args):
    """Gradient-based optimization for a single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d}", end="", flush=True)
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Multiscale optimization
    try:
        candidate, candidate_L = multiscale_optimization(best_p)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f" M→{best_L:.9f}", end="", flush=True)
            
            # Polish the result
            best_p, _, _ = polish.polish(best_p, seed=123, rounds=5, max_seconds=10,
                                         trust_start=0.02, regularization=1e-12)
            best_L = pg.side(best_p)
            print(f" P→{best_L:.9f}", end="", flush=True)
    except:
        pass
    
    # Strategy 2: Cyclical learning rate
    try:
        candidate, candidate_L = cyclical_learning_rate_optimize(best_p, n_cycles=3)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f" C→{best_L:.9f}", end="", flush=True)
            
            # Polish
            best_p, _, _ = polish.polish(best_p, seed=456, rounds=5, max_seconds=10,
                                         trust_start=0.015, regularization=1e-12)
            best_L = pg.side(best_p)
            print(f" P→{best_L:.9f}", end="", flush=True)
    except:
        pass
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f" ★WIN! Δ={improvement:.2e}")
        return (n, best_p, best_L, improvement)
    else:
        print()
        return None

def main():
    print("=" * 80)
    print("GRADIENT DESCENT OPTIMIZER")
    print("=" * 80)
    print("Adam, Multiscale, Cyclical LR, Gradient Clipping")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target smaller-medium puzzles where gradient methods work well
    targets = list(range(50, 400))
    
    print(f"Targeting {len(targets)} puzzles (n=50-400)\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_gradient((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} gradient improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/gradient_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_gradient_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {new_score:.12f}")

if __name__ == '__main__':
    main()
