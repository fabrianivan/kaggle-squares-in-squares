#!/usr/bin/env python3
"""
Rapid Score Boost - Fast and effective optimizer
Using proven techniques with correct function names
"""

import numpy as np
import pandas as pd
from pathlib import Path
import time
import multiprocessing as mp
from scipy.optimize import differential_evolution

import sys
sys.path.append('src')
from tools.packing_geometry import side, rotate, normalize
from tools.cpu_axis_reclosure import axis_reclosure_cpu
from tools.cpu_contact_polish import contact_polish

def multi_angle_optimize(n, solution):
    """Try multiple rotation angles and find the best"""
    best_solution = solution.copy()
    best_score = side(solution)
    
    # Try 16 rotation angles
    for angle in np.linspace(0, np.pi/2, 16):
        try:
            rotated = rotate(solution, angle)
            rotated_score = side(rotated)
            
            if rotated_score < best_score:
                best_score = rotated_score
                best_solution = rotated.copy()
        except:
            pass
    
    return best_solution, best_score

def multi_param_polish(solution):
    """Try multiple parameter combinations for axis reclosure"""
    best_solution = solution.copy()
    best_score = side(solution)
    
    # Parameter sweep
    params = [
        (0.18, 0.22, 1e-11),
        (0.25, 0.18, 5e-12),
        (0.15, 0.28, 1e-11),
        (0.22, 0.25, 8e-12),
        (0.20, 0.20, 1e-11),
        (0.17, 0.30, 1e-11),
        (0.30, 0.15, 5e-12),
        (0.16, 0.24, 1e-11),
    ]
    
    for trust, tie, reg in params:
        try:
            candidate = axis_reclosure_cpu(best_solution, trust=trust, tie=tie, reg=reg)
            candidate_score = side(candidate)
            
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    return best_solution, best_score

def contact_polish_multi(solution):
    """Multiple rounds of contact polish with different settings"""
    best_solution = solution.copy()
    best_score = side(solution)
    
    for rounds in [3, 5, 7]:
        for reg in [1e-11, 5e-12, 1e-10]:
            try:
                candidate = contact_polish(best_solution, rounds=rounds, reg=reg)
                candidate_score = side(candidate)
                
                if candidate_score < best_score:
                    best_score = candidate_score
                    best_solution = candidate.copy()
            except:
                pass
    
    return best_solution, best_score

def combined_optimization(solution):
    """Combine all optimization strategies"""
    best_solution = solution.copy()
    best_score = side(solution)
    
    # Multi-pass optimization
    for iteration in range(3):
        # Step 1: Multi-angle
        candidate, candidate_score = multi_angle_optimize(len(solution), best_solution)
        if candidate_score < best_score:
            best_score = candidate_score
            best_solution = candidate.copy()
        
        # Step 2: Multi-param polish
        candidate, candidate_score = multi_param_polish(best_solution)
        if candidate_score < best_score:
            best_score = candidate_score
            best_solution = candidate.copy()
        
        # Step 3: Contact polish
        candidate, candidate_score = contact_polish_multi(best_solution)
        if candidate_score < best_score:
            best_score = candidate_score
            best_solution = candidate.copy()
    
    return best_solution, best_score

def optimize_puzzle_worker(args):
    """Worker function for parallel optimization"""
    n, solution = args
    
    original_score = side(solution)
    
    try:
        best_solution, best_score = combined_optimization(solution)
        improvement = original_score - best_score
        
        if improvement > 1e-9:
            return (n, best_solution, best_score, improvement)
    except Exception as e:
        pass
    
    return None

def main():
    print("=" * 80)
    print("RAPID SCORE BOOST")
    print("=" * 80)
    print("Multi-angle + Multi-parameter + Contact Polish")
    print("=" * 80)
    
    # Load baseline
    baseline_files = sorted(Path('output').glob('submission_*.csv'))
    if not baseline_files:
        baseline_files = sorted(Path('artifacts').glob('round29_submission.csv'))
    
    if not baseline_files:
        print("Error: No baseline found")
        return
    
    baseline_file = baseline_files[-1]
    print(f"\nBaseline: {baseline_file.name}")
    
    df = pd.read_csv(baseline_file)
    
    # Calculate current score using simple method
    def simple_score(df):
        total = 0.0
        for n in range(1, 1001):
            puzzle_df = df[df['n'] == n]
            solution = puzzle_df[['x', 'y', 'angle']].values
            L = side(solution)
            total += L / np.sqrt(n) - 1
        return total
    
    current_score = simple_score(df)
    print(f"Current score: {current_score:.9f}")
    print(f"Target: < 22.11")
    
    # Focus on high-impact puzzles (n >= 100)
    target_ns = list(range(100, 1001))
    print(f"\nTargeting {len(target_ns)} puzzles (n >= 100)")
    print(f"Using {mp.cpu_count()} CPU cores")
    
    # Prepare work
    args_list = []
    for n in target_ns:
        puzzle_df = df[df['n'] == n]
        solution = puzzle_df[['x', 'y', 'angle']].values
        args_list.append((n, solution))
    
    # Parallel optimization
    print("\nOptimizing...")
    start_time = time.time()
    
    wins = {}
    total_improvement = 0.0
    
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(optimize_puzzle_worker, args_list)
    
    # Collect improvements
    for result in results:
        if result is not None:
            n, solution, score, improvement = result
            wins[n] = solution
            total_improvement += improvement
            print(f"✓ n={n:4d}: improved by {improvement:.9f} → {score:.9f}")
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"Optimization complete in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} improvements")
    print(f"Total improvement: {total_improvement:.9f}")
    
    estimated_score = current_score - total_improvement
    print(f"\nEstimated new score: {estimated_score:.9f}")
    print(f"Improvement: {current_score - estimated_score:.9f}")
    
    # Save results
    if wins:
        timestamp = int(time.time())
        
        # Save wins file
        wins_file = Path('output') / f'rapid_wins_{timestamp}.npz'
        wins_file.parent.mkdir(exist_ok=True)
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved wins: {wins_file}")
        
        # Create new submission
        new_df = df.copy()
        for n, solution in wins.items():
            mask = new_df['n'] == n
            new_df.loc[mask, ['x', 'y', 'angle']] = solution
        
        submission_file = Path('output') / f'submission_rapid_{estimated_score:.6f}.csv'
        new_df.to_csv(submission_file, index=False)
        print(f"Saved submission: {submission_file}")
        
        # Verify
        actual_score = simple_score(new_df)
        print(f"\n✓ Verified score: {actual_score:.9f}")
        print(f"✓ Actual improvement: {current_score - actual_score:.9f}")
        
        # Save summary
        summary = {
            'baseline_file': str(baseline_file),
            'baseline_score': float(current_score),
            'new_score': float(actual_score),
            'improvement': float(current_score - actual_score),
            'puzzles_improved': len(wins),
            'time_minutes': elapsed / 60,
            'timestamp': timestamp
        }
        
        import json
        summary_file = Path('output') / f'rapid_summary_{timestamp}.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Saved summary: {summary_file}")
    else:
        print("\nNo improvements found - baseline is already excellent!")
    
    print("\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)

if __name__ == '__main__':
    main()
