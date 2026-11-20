#!/usr/bin/env python3
"""
Ensemble Meta-Optimizer - Combines multiple optimization strategies
- Portfolio of optimizers
- Meta-learning which optimizer works best
- Automatic strategy selection
- Voting and ensemble methods
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
from collections import defaultdict

class OptimizerPortfolio:
    """Portfolio of different optimization strategies"""
    
    def __init__(self):
        self.optimizers = {
            'tight_polish': self._tight_polish,
            'loose_polish': self._loose_polish,
            'aggressive_reclose': self._aggressive_reclose,
            'gentle_reclose': self._gentle_reclose,
            'balanced': self._balanced,
            'random_explore': self._random_explore
        }
        
        # Track performance
        self.performance = defaultdict(list)
        self.success_rate = defaultdict(float)
    
    def _tight_polish(self, pack, seed):
        return polish.polish(pack, seed=seed, rounds=6, max_seconds=12,
                           trust_start=0.01, regularization=1e-13)
    
    def _loose_polish(self, pack, seed):
        return polish.polish(pack, seed=seed, rounds=5, max_seconds=10,
                           trust_start=0.04, regularization=1e-11)
    
    def _aggressive_reclose(self, pack, seed):
        return reclosure.reclose(pack, seed=seed, trust=0.4, tie=0.35,
                                rounds=6, seconds=12)
    
    def _gentle_reclose(self, pack, seed):
        return reclosure.reclose(pack, seed=seed, trust=0.18, tie=0.22,
                                rounds=6, seconds=12)
    
    def _balanced(self, pack, seed):
        # Two-stage: polish then reclose
        p1, _, _ = polish.polish(pack, seed=seed, rounds=4, max_seconds=8,
                                trust_start=0.02, regularization=1e-12)
        return reclosure.reclose(p1, seed=seed+1, trust=0.25, tie=0.25,
                                rounds=4, seconds=8)
    
    def _random_explore(self, pack, seed):
        np.random.seed(seed)
        trust = 0.15 + 0.35 * np.random.random()
        tie = 0.15 + 0.30 * np.random.random()
        return reclosure.reclose(pack, seed=seed, trust=trust, tie=tie,
                                rounds=5, seconds=10)
    
    def optimize(self, pack, optimizer_name, seed):
        """Run specific optimizer"""
        try:
            result, info, meta = self.optimizers[optimizer_name](pack, seed)
            return result, True
        except:
            return pack, False
    
    def record_performance(self, optimizer_name, improvement):
        """Record how well optimizer performed"""
        self.performance[optimizer_name].append(improvement)
        
        # Update success rate
        successes = sum(1 for imp in self.performance[optimizer_name] if imp > 1e-12)
        total = len(self.performance[optimizer_name])
        self.success_rate[optimizer_name] = successes / total if total > 0 else 0
    
    def get_best_optimizer(self, n=None):
        """Select best optimizer based on past performance"""
        if not self.success_rate:
            return np.random.choice(list(self.optimizers.keys()))
        
        # Weight by success rate and average improvement
        scores = {}
        for name in self.optimizers:
            if self.performance[name]:
                avg_imp = np.mean([max(0, imp) for imp in self.performance[name]])
                success = self.success_rate[name]
                scores[name] = success * 0.7 + avg_imp * 1000 * 0.3
            else:
                scores[name] = 0.1  # Small prior
        
        # Softmax selection with temperature
        T = 0.5
        exp_scores = np.array([np.exp(scores[name]/T) for name in self.optimizers])
        probs = exp_scores / exp_scores.sum()
        
        return np.random.choice(list(self.optimizers.keys()), p=probs)

def ensemble_voting(candidates, method='quality'):
    """Select best from ensemble of candidates"""
    if not candidates:
        return None, float('inf')
    
    # Evaluate all candidates
    evaluated = []
    for pack in candidates:
        try:
            L = pg.side(pack)
            evaluated.append((pack, L))
        except:
            pass
    
    if not evaluated:
        return None, float('inf')
    
    if method == 'best':
        # Simply return best
        return min(evaluated, key=lambda x: x[1])
    
    elif method == 'quality':
        # Weight by inverse side length
        evaluated.sort(key=lambda x: x[1])
        
        # Take top 30% and average
        top_k = max(1, len(evaluated) // 3)
        top_packs = [pack for pack, L in evaluated[:top_k]]
        
        # Weighted average (better solutions get more weight)
        weights = np.array([1/(i+1) for i in range(len(top_packs))])
        weights /= weights.sum()
        
        avg_pack = np.zeros_like(top_packs[0])
        for pack, w in zip(top_packs, weights):
            avg_pack += w * pack
        
        # Quick polish the average
        try:
            avg_pack, _, _ = polish.polish(avg_pack, seed=99999,
                                          rounds=4, max_seconds=8,
                                          trust_start=0.02,
                                          regularization=1e-12)
        except:
            pass
        
        return avg_pack, pg.side(avg_pack)

def meta_learning_optimize(packing, n_attempts=50):
    """Meta-learning: learn which optimizer works best"""
    portfolio = OptimizerPortfolio()
    
    best_pack = packing.copy()
    best_L = pg.side(best_pack)
    
    candidates = [best_pack]
    
    for attempt in range(n_attempts):
        # Select optimizer based on past performance
        if attempt < 12:
            # Exploration phase: try all optimizers
            optimizer_name = list(portfolio.optimizers.keys())[attempt % 6]
        else:
            # Exploitation phase: use best performing
            optimizer_name = portfolio.get_best_optimizer()
        
        # Run optimizer
        seed = attempt * 1234
        result, success = portfolio.optimize(best_pack, optimizer_name, seed)
        
        if success:
            result_L = pg.side(result)
            improvement = best_L - result_L
            
            # Record performance
            portfolio.record_performance(optimizer_name, improvement)
            
            if result_L < best_L:
                best_L = result_L
                best_pack = result.copy()
            
            candidates.append(result)
    
    # Ensemble voting on all candidates
    ensemble_pack, ensemble_L = ensemble_voting(candidates, method='quality')
    
    if ensemble_L < best_L:
        best_L = ensemble_L
        best_pack = ensemble_pack
    
    return best_pack, best_L, portfolio

def adaptive_portfolio(packing, puzzle_n):
    """Adaptive portfolio based on puzzle characteristics"""
    best_pack = packing.copy()
    best_L = pg.side(best_pack)
    
    # Determine puzzle characteristics
    is_small = puzzle_n < 100
    is_medium = 100 <= puzzle_n < 400
    is_large = puzzle_n >= 400
    is_prime = puzzle_n in [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97,
                            101,103,107,109,113,127,131,137,139,149,151,157,163,167,173,179,181,191,193,197,199,
                            211,223,227,229,233,239,241,251,257,263,269,271,277,281,283,293,
                            307,311,313,317,331,337,347,349,353,359,367,373,379,383,389,397,
                            401,409,419,421,431,433,439,443,449,457,461,463,467,479,487,491,499]
    is_square = int(np.sqrt(puzzle_n))**2 == puzzle_n
    
    # Select strategies based on characteristics
    strategies = []
    
    if is_small:
        strategies = ['tight_polish', 'gentle_reclose', 'balanced']
        n_attempts = 30
    elif is_medium:
        strategies = ['loose_polish', 'aggressive_reclose', 'balanced', 'random_explore']
        n_attempts = 40
    else:  # large
        strategies = ['aggressive_reclose', 'random_explore', 'loose_polish']
        n_attempts = 50
    
    if is_prime:
        strategies.append('random_explore')
        n_attempts += 10
    
    if is_square:
        strategies = ['gentle_reclose', 'balanced'] + strategies
    
    # Run selected strategies
    portfolio = OptimizerPortfolio()
    candidates = [best_pack]
    
    for attempt in range(n_attempts):
        strategy = strategies[attempt % len(strategies)]
        seed = attempt * 5678
        
        result, success = portfolio.optimize(best_pack, strategy, seed)
        
        if success:
            result_L = pg.side(result)
            if result_L < best_L:
                best_L = result_L
                best_pack = result.copy()
            
            candidates.append(result)
    
    # Final ensemble
    ensemble_pack, ensemble_L = ensemble_voting(candidates, method='quality')
    
    if ensemble_L < best_L:
        best_L = ensemble_L
        best_pack = ensemble_pack
    
    return best_pack, best_L

def optimize_puzzle_ensemble(args):
    """Ensemble meta-optimizer for single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d} L_start={pg.side(p_base):.9f}")
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Meta-learning
    try:
        candidate, candidate_L, portfolio = meta_learning_optimize(best_p, n_attempts=40)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            
            # Print which optimizer worked best
            best_opt = max(portfolio.success_rate.items(), key=lambda x: x[1])
            print(f"    Meta-learning: {best_opt[0]} performed best (success={best_opt[1]:.2%})")
    except Exception as e:
        print(f"    Meta-learning failed: {e}")
    
    # Strategy 2: Adaptive portfolio
    try:
        candidate, candidate_L = adaptive_portfolio(best_p, n)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Adaptive portfolio improved: {candidate_L:.9f}")
    except Exception as e:
        print(f"    Adaptive portfolio failed: {e}")
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f"  → Final: {best_L:.9f} ★WIN! Δ={improvement:.2e}\n")
        return (n, best_p, best_L, improvement)
    else:
        print(f"  → Final: {best_L:.9f}\n")
        return None

def main():
    print("=" * 80)
    print("ENSEMBLE META-OPTIMIZER")
    print("=" * 80)
    print("Portfolio Selection, Meta-Learning, Adaptive Strategies, Voting")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target all puzzle ranges
    targets = list(range(50, 600))
    
    print(f"Targeting {len(targets)} puzzles (n=50-600)")
    print(f"Using adaptive strategy selection\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_ensemble((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} ensemble improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/ensemble_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_ensemble_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {new_score:.12f}")

if __name__ == '__main__':
    main()
