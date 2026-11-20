#!/usr/bin/env python3
"""
Quantum-Inspired Optimizer
Uses parallel universes (multiple simultaneous packings) with quantum tunneling (big jumps)
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from pathlib import Path
import time
from src.tools import packing_geometry as pg

def quantum_tunnel(packing, temperature):
    """Quantum tunneling: make a big random perturbation"""
    p = packing.copy()
    n = len(p)
    
    # Select random subset to perturb
    num_perturb = max(2, int(n * temperature * 0.3))
    indices = np.random.choice(n, num_perturb, replace=False)
    
    # Big random moves
    p[indices, :2] += np.random.randn(num_perturb, 2) * temperature * 0.5
    p[indices, 2] += np.random.randn(num_perturb) * temperature * 90  # rotation
    
    return pg.normalize(pg.repair(p))

def quantum_optimize_puzzle(n, baseline_packing, num_universes=20, max_iterations=5000):
    """
    Maintain multiple parallel packings (universes) and let them evolve independently
    Periodically tunnel between them
    """
    from src.tools.cpu_contact_polish import polish
    from src.tools.cpu_axis_reclosure import reclose
    
    # Initialize parallel universes
    universes = []
    for i in range(num_universes):
        if i == 0:
            universes.append(baseline_packing.copy())
        else:
            # Create variants
            p = baseline_packing.copy()
            # Add small random perturbations
            p[:, :2] += np.random.randn(n, 2) * 0.01
            p[:, 2] += np.random.randn(n) * 5
            universes.append(pg.normalize(pg.repair(p)))
    
    best_ever = baseline_packing.copy()
    best_side = pg.side(best_ever)
    
    print(f"  n={n}: Starting {num_universes} parallel universes")
    
    for iteration in range(max_iterations // num_universes):
        # Temperature schedule (for quantum tunneling)
        temperature = 1.0 * (1 - iteration / (max_iterations / num_universes))
        
        for u_idx in range(num_universes):
            universe = universes[u_idx]
            
            # Decide: polish, reclose, or quantum tunnel
            action = np.random.random()
            
            if action < 0.4:  # 40% polish
                try:
                    universe = polish(universe, seed=np.random.randint(1e9), 
                                    rounds=2, max_seconds=5, 
                                    trust_start=0.2 + 0.3*np.random.random(),
                                    regularization=1e-11 * (0.1 + 0.9*np.random.random()))
                except:
                    pass
            elif action < 0.7:  # 30% reclose
                try:
                    universe = reclose(universe, seed=np.random.randint(1e9),
                                     trust=0.15 + 0.4*np.random.random(),
                                     tie=0.15 + 0.3*np.random.random(),
                                     rounds=2, seconds=5)
                except:
                    pass
            else:  # 30% quantum tunnel
                universe = quantum_tunnel(universe, temperature)
            
            universes[u_idx] = universe
            
            # Check if this universe found something better
            side = pg.side(universe)
            if side < best_side:
                best_ever = universe.copy()
                best_side = side
                print(f"  n={n}: Universe {u_idx} improved to {best_side:.12f} (iter {iteration})")
        
        # Periodically: merge best universes (quantum entanglement)
        if iteration % 20 == 0 and iteration > 0:
            # Sort universes by quality
            sides = [pg.side(u) for u in universes]
            best_idx = np.argmin(sides)
            
            # Replace worst half with variations of best half
            sorted_indices = np.argsort(sides)
            for i in range(num_universes // 2):
                worst_idx = sorted_indices[-(i+1)]
                best_source_idx = sorted_indices[i % (num_universes // 2)]
                
                # Create variant
                universes[worst_idx] = universes[best_source_idx].copy()
                universes[worst_idx][:, :2] += np.random.randn(n, 2) * 0.02
                universes[worst_idx][:, 2] += np.random.randn(n) * 10
                universes[worst_idx] = pg.normalize(pg.repair(universes[worst_idx]))
    
    return best_ever, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("QUANTUM-INSPIRED OPTIMIZER")
    print("=" * 80)
    print(f"Baseline: {baseline_path}")
    
    # Target 150 puzzles with quantum approach
    targets = list(range(2, 151)) + list(range(200, 401, 2)) + list(range(500, 701, 5))
    print(f"Targeting {len(targets)} puzzles with quantum optimization")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['packing']))
        baseline_side = pg.side(baseline_packing)
        
        # More universes for small puzzles
        num_universes = 30 if n < 100 else 20
        max_iterations = 8000 if n < 100 else 5000
        
        best, best_side = quantum_optimize_puzzle(n, baseline_packing, num_universes, max_iterations)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        else:
            print(f"  No improvement for n={n}")
        
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            print(f">>> {len(wins)} wins so far, {elapsed/60:.1f}m elapsed")
    
    # Save results
    if wins:
        out_path = f"output/quantum_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'packing'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path} (score={new_score:.12f})")
    else:
        print("\nNo improvements found")
    
    print(f"\nTotal time: {(time.time() - start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
