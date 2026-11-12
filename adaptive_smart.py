#!/usr/bin/env python3
"""
ADAPTIVE SMART - Advanced optimizer with learning and adaptation
Strategy: Learns from successful attempts and adapts parameters dynamically
Features:
- Success tracking per puzzle size
- Adaptive parameter adjustment
- Smart seed generation
- Strategy ranking based on historical success
Runtime: ~3-4 hours
"""
import sys
import math
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import pandas as pd
import numpy as np
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

def compute_score(df):
    """Compute overall score manually"""
    total = 0.0
    for n in range(1, 1001):
        p = df[df['n'] == n][['x', 'y', 'angle']].values
        if len(p) == n:
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def optimize_adaptive():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"ADAPTIVE SMART - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Success tracking
    strategy_success = defaultdict(lambda: {'wins': 0, 'attempts': 0, 'total_improvement': 0.0})
    size_class_success = defaultdict(lambda: {'best_trust': 0.3, 'best_reg': 1e-12, 'best_tie': 0.2})
    
    # Target puzzles with smart selection
    target_puzzles = list(range(20, 401))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        # Determine size class for adaptive parameters
        if puzzle_n < 50:
            size_class = 'tiny'
        elif puzzle_n < 150:
            size_class = 'small'
        elif puzzle_n < 300:
            size_class = 'medium'
        else:
            size_class = 'large'
        
        # Get learned parameters for this size class
        learned = size_class_success[size_class]
        base_trust = learned['best_trust']
        base_reg = learned['best_reg']
        base_tie = learned['best_tie']
        
        print(f"Puzzle {puzzle_n} [{size_class}]: starting {current_side:.10f}, using trust={base_trust:.3f}", flush=True)
        
        # 100 adaptive attempts with strategy ranking
        strategies = list(range(15))
        strategy_weights = [1.0 + strategy_success[i]['wins'] * 0.5 for i in strategies]
        
        for attempt in range(100):
            # Sample strategy based on success weights
            strategy = np.random.choice(strategies, p=np.array(strategy_weights)/sum(strategy_weights))
            seed = 8000 + attempt * 31 + puzzle_n
            
            # Adapt parameters based on attempt number
            progress = attempt / 100.0
            trust_var = (0.5 - progress) * 0.15  # More exploration early
            reg_var = (0.5 - progress) * 1e-11
            
            try:
                if strategy == 0:
                    # Adaptive precision polish
                    trust = base_trust * 0.5 + np.random.uniform(-trust_var, trust_var)
                    reg = base_reg * 0.5 + np.random.uniform(-reg_var, reg_var)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=35,
                                            trust_start=max(0.01, trust), 
                                            regularization=max(1e-14, reg))
                
                elif strategy == 1:
                    # Adaptive reclosure
                    trust = base_trust + np.random.uniform(-trust_var*2, trust_var*2)
                    tie = base_tie + np.random.uniform(-0.05, 0.05)
                    candidate, _, _ = reclosure.reclose(p, seed=seed, 
                                                trust=np.clip(trust, 0.2, 0.58),
                                                tie=np.clip(tie, 0.14, 0.26),
                                                rounds=8, seconds=35)
                
                elif strategy == 2:
                    # Smart combo based on size
                    if puzzle_n < 100:
                        temp, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=20,
                                           trust_start=0.03, regularization=5e-13)
                        candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.42,
                                                    tie=0.19, rounds=6, seconds=20)
                    else:
                        temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.45,
                                                tie=0.18, rounds=6, seconds=20)
                        candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=8, max_seconds=20,
                                                trust_start=0.025, regularization=4e-13)
                
                elif strategy == 3:
                    # Temperature-based exploration
                    temperature = 1.0 - progress  # Cool down over time
                    trust = base_trust + np.random.normal(0, temperature * 0.1)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=30,
                                            trust_start=np.clip(trust*0.6, 0.015, 0.08),
                                            regularization=base_reg * (0.5 + temperature))
                
                elif strategy == 4:
                    # Multi-scale approach
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=0.06, regularization=1e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=6, max_seconds=15,
                                        trust_start=0.03, regularization=5e-12)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                            trust_start=0.018, regularization=2e-13)
                
                elif strategy == 5:
                    # Momentum-based (use recent success)
                    if strategy_success[strategy]['wins'] > 0:
                        boost = 1.2
                    else:
                        boost = 0.9
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=int(14*boost), max_seconds=int(38*boost),
                                            trust_start=base_trust*0.4, regularization=base_reg*0.3)
                
                elif strategy == 6:
                    # Ensemble approach - try multiple, keep best
                    candidates = []
                    for subseed in [seed, seed+100, seed+200]:
                        temp, _, _ = polish.polish(p, seed=subseed, rounds=7, max_seconds=15,
                                           trust_start=0.04, regularization=6e-12)
                        candidates.append(temp)
                    candidate = min(candidates, key=lambda x: pg.side(x))
                
                elif strategy == 7:
                    # Alternating intensive
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=18,
                                       trust_start=0.035, regularization=4e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.4, 
                                            tie=0.20, rounds=6, seconds=18)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=8, max_seconds=18,
                                        trust_start=0.022, regularization=3e-13)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.35,
                                                tie=0.22, rounds=6, seconds=18)
                
                elif strategy == 8:
                    # Random search in good region
                    trust = np.random.uniform(0.015, 0.05)
                    reg = np.random.uniform(1e-13, 1e-11)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=np.random.randint(8, 16),
                                            max_seconds=np.random.randint(25, 40),
                                            trust_start=trust, regularization=reg)
                
                elif strategy == 9:
                    # High exploration reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, 
                                                trust=np.random.uniform(0.35, 0.55),
                                                tie=np.random.uniform(0.16, 0.24),
                                                rounds=np.random.randint(6, 10),
                                                seconds=35)
                
                elif strategy == 10:
                    # Precision ladder
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=12,
                                       trust_start=0.08, regularization=2e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=5, max_seconds=12,
                                        trust_start=0.04, regularization=8e-12)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=12,
                                        trust_start=0.025, regularization=3e-12)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=5, max_seconds=12,
                                            trust_start=0.015, regularization=8e-13)
                
                elif strategy == 11:
                    # Balanced mega
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.44, tie=0.19, rounds=5, seconds=15)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=6, max_seconds=15,
                                       trust_start=0.032, regularization=5e-12)
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.38, tie=0.21, rounds=5, seconds=15)
                
                elif strategy == 12:
                    # Ultra precision
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=18, max_seconds=45,
                                            trust_start=0.012, regularization=5e-14)
                
                elif strategy == 13:
                    # Extreme reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.56, tie=0.145,
                                                rounds=12, seconds=48)
                
                else:  # strategy == 14
                    # Adaptive hybrid
                    if puzzle_n % 2 == 0:
                        temp, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=25,
                                           trust_start=base_trust*0.6, regularization=base_reg)
                        candidate, _, _ = reclosure.reclose(temp, seed=seed+1, 
                                                    trust=base_trust*1.3, tie=base_tie,
                                                    rounds=7, seconds=25)
                    else:
                        temp, _, _ = reclosure.reclose(p, seed=seed, trust=base_trust*1.4, 
                                                tie=base_tie, rounds=7, seconds=25)
                        candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=9, max_seconds=25,
                                                trust_start=base_trust*0.5, regularization=base_reg*0.8)
                
                cand_side = pg.side(candidate)
                
                # Track strategy performance
                strategy_success[strategy]['attempts'] += 1
                
                if cand_side < best_side - 1e-11:
                    improvement = current_side - cand_side
                    best_side = cand_side
                    best_p = candidate.copy()
                    
                    # Update strategy success
                    strategy_success[strategy]['wins'] += 1
                    strategy_success[strategy]['total_improvement'] += improvement
                    
                    # Update learned parameters for size class
                    # (Exponential moving average)
                    alpha = 0.3
                    if strategy in [0, 3, 4, 8]:  # Polish-based strategies
                        size_class_success[size_class]['best_trust'] = \
                            alpha * base_trust * 0.6 + (1-alpha) * size_class_success[size_class]['best_trust']
                        size_class_success[size_class]['best_reg'] = \
                            alpha * base_reg * 0.5 + (1-alpha) * size_class_success[size_class]['best_reg']
                    elif strategy in [1, 9, 13]:  # Reclosure-based
                        size_class_success[size_class]['best_trust'] = \
                            alpha * base_trust * 1.2 + (1-alpha) * size_class_success[size_class]['best_trust']
                        size_class_success[size_class]['best_tie'] = \
                            alpha * base_tie * 0.95 + (1-alpha) * size_class_success[size_class]['best_tie']
                    
                    print(f"  → WIN attempt {attempt} [strategy {strategy}]: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
                    
                    # Update strategy weights for better selection
                    strategy_weights[strategy] += 0.5
            
            except Exception as e:
                print(f"  Strategy {strategy} failed: {e}", flush=True)
                continue
        
        if best_side < current_side - 1e-11:
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f}", flush=True)
    
    # Save if improved
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"ADAPTIVE SMART COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"\nLearned parameters by size class:")
        for size_class, params in size_class_success.items():
            print(f"  {size_class}: trust={params['best_trust']:.4f}, reg={params['best_reg']:.2e}, tie={params['best_tie']:.3f}")
        print(f"\nTop 5 strategies by wins:")
        sorted_strategies = sorted(strategy_success.items(), 
                                   key=lambda x: x[1]['wins'], reverse=True)[:5]
        for strat_id, stats in sorted_strategies:
            if stats['attempts'] > 0:
                win_rate = stats['wins'] / stats['attempts'] * 100
                print(f"  Strategy {strat_id}: {stats['wins']} wins / {stats['attempts']} attempts ({win_rate:.1f}%), total Δ={stats['total_improvement']:.2e}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_adaptive()
