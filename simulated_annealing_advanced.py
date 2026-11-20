#!/usr/bin/env python3
"""
Advanced Simulated Annealing with Multiple Enhancements
- Adaptive temperature scheduling
- Multiple cooling schedules (exponential, logarithmic, linear)
- Reheating when stuck
- Population-based parallel annealing
- Boltzmann acceptance with momentum
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

class AdaptiveSimulatedAnnealing:
    """Advanced SA with adaptive temperature control"""
    
    def __init__(self, T_start=10.0, T_end=0.001, cooling_rate=0.95):
        self.T_start = T_start
        self.T_end = T_end
        self.cooling_rate = cooling_rate
        self.T = T_start
        
        self.best_energy = float('inf')
        self.current_energy = float('inf')
        self.stagnation_counter = 0
        self.acceptance_rate = []
    
    def cool_exponential(self, iteration):
        """Exponential cooling"""
        self.T = self.T_start * (self.cooling_rate ** iteration)
    
    def cool_logarithmic(self, iteration):
        """Logarithmic cooling (slower)"""
        self.T = self.T_start / (1 + np.log(1 + iteration))
    
    def cool_cauchy(self, iteration):
        """Cauchy cooling"""
        self.T = self.T_start / (1 + iteration)
    
    def cool_adaptive(self, iteration, acceptance_rate):
        """Adaptive cooling based on acceptance rate"""
        if acceptance_rate > 0.3:
            # Cool faster if accepting too many
            self.T *= 0.90
        elif acceptance_rate < 0.05:
            # Cool slower if accepting too few
            self.T *= 0.98
        else:
            # Normal cooling
            self.T *= self.cooling_rate
        
        # Ensure minimum temperature
        self.T = max(self.T, self.T_end)
    
    def should_accept(self, new_energy, current_energy):
        """Metropolis criterion with momentum"""
        if new_energy < current_energy:
            return True
        
        delta_E = new_energy - current_energy
        prob = np.exp(-delta_E / self.T)
        
        return np.random.random() < prob
    
    def reheat(self):
        """Reheat when stuck in local minimum"""
        self.T = min(self.T * 5.0, self.T_start * 0.5)
        print(f"      Reheating to T={self.T:.4f}", flush=True)

def parallel_annealing(packing, n_chains=5, n_steps=150):
    """Run multiple SA chains in parallel"""
    chains = []
    
    for chain_id in range(n_chains):
        sa = AdaptiveSimulatedAnnealing(
            T_start=5.0 + chain_id * 2.0,  # Different starting temperatures
            T_end=0.001,
            cooling_rate=0.95 - chain_id * 0.01
        )
        
        current_pack = packing.copy()
        current_L = pg.side(current_pack)
        
        best_pack = current_pack.copy()
        best_L = current_L
        
        chains.append({
            'sa': sa,
            'current': current_pack,
            'current_L': current_L,
            'best': best_pack,
            'best_L': best_L,
            'acceptances': 0,
            'attempts': 0
        })
    
    # Run all chains
    for step in range(n_steps):
        for chain in chains:
            sa = chain['sa']
            
            # Generate neighbor
            seed = step * 100 + chains.index(chain)
            
            # Alternate between methods
            if step % 3 == 0:
                try:
                    neighbor, _, _ = polish.polish(chain['current'], seed=seed,
                                                   rounds=4, max_seconds=8,
                                                   trust_start=0.01 + 0.03*np.random.random(),
                                                   regularization=10**(-13 + 2*np.random.random()))
                except:
                    neighbor = chain['current']
            else:
                try:
                    trust = 0.15 + 0.3 * np.random.random()
                    tie = 0.15 + 0.25 * np.random.random()
                    neighbor, _, _ = reclosure.reclose(chain['current'], seed=seed,
                                                       trust=trust, tie=tie,
                                                       rounds=4, seconds=8)
                except:
                    neighbor = chain['current']
            
            try:
                neighbor_L = pg.side(neighbor)
            except:
                continue
            
            # Acceptance decision
            chain['attempts'] += 1
            if sa.should_accept(neighbor_L, chain['current_L']):
                chain['current'] = neighbor
                chain['current_L'] = neighbor_L
                chain['acceptances'] += 1
                
                if neighbor_L < chain['best_L']:
                    chain['best'] = neighbor.copy()
                    chain['best_L'] = neighbor_L
            
            # Cool down
            acceptance_rate = chain['acceptances'] / max(1, chain['attempts'])
            if step % 10 == 0:
                sa.cool_adaptive(step, acceptance_rate)
            else:
                sa.cool_exponential(step)
            
            # Reheat if stuck
            if step % 50 == 0 and step > 0:
                if chain['acceptances'] < 5:  # Very few acceptances in last 50 steps
                    sa.reheat()
                    chain['acceptances'] = 0
                    chain['attempts'] = 0
    
    # Return best from all chains
    best_chain = min(chains, key=lambda c: c['best_L'])
    return best_chain['best'], best_chain['best_L']

def hybrid_sa_local_search(packing, n_iterations=100):
    """SA combined with intensive local search"""
    sa = AdaptiveSimulatedAnnealing(T_start=8.0, T_end=0.001, cooling_rate=0.96)
    
    current_pack = packing.copy()
    current_L = pg.side(current_pack)
    
    best_pack = current_pack.copy()
    best_L = current_L
    
    acceptance_count = 0
    
    for iteration in range(n_iterations):
        # Generate neighbor with SA
        seed = iteration * 456
        
        # Multiple perturbation strategies
        strategy = iteration % 4
        
        if strategy == 0:
            # Small perturbation + polish
            neighbor = current_pack.copy()
            noise_scale = 0.02 * (sa.T / sa.T_start)
            neighbor[:, :2] += np.random.randn(*neighbor[:, :2].shape) * noise_scale
            
            try:
                neighbor, _, _ = polish.polish(neighbor, seed=seed,
                                              rounds=5, max_seconds=10,
                                              trust_start=0.015,
                                              regularization=1e-12)
            except:
                pass
        
        elif strategy == 1:
            # Aggressive reclose
            try:
                trust = 0.2 + 0.3 * (sa.T / sa.T_start)
                neighbor, _, _ = reclosure.reclose(current_pack, seed=seed,
                                                  trust=trust, tie=0.25,
                                                  rounds=5, seconds=10)
            except:
                neighbor = current_pack
        
        elif strategy == 2:
            # Rotation + optimization
            angle = np.random.uniform(0, np.pi/4)
            neighbor = current_pack.copy()
            neighbor[:, 2] += angle
            
            try:
                neighbor, _, _ = reclosure.reclose(neighbor, seed=seed,
                                                  trust=0.22, tie=0.22,
                                                  rounds=4, seconds=8)
            except:
                pass
        
        else:
            # Random exploration
            try:
                trust = 0.15 + 0.35 * np.random.random()
                tie = 0.15 + 0.3 * np.random.random()
                neighbor, _, _ = reclosure.reclose(current_pack, seed=seed,
                                                  trust=trust, tie=tie,
                                                  rounds=4, seconds=8)
            except:
                neighbor = current_pack
        
        try:
            neighbor_L = pg.side(neighbor)
        except:
            continue
        
        # Acceptance
        if sa.should_accept(neighbor_L, current_L):
            current_pack = neighbor
            current_L = neighbor_L
            acceptance_count += 1
            
            if neighbor_L < best_L:
                best_L = neighbor_L
                best_pack = neighbor.copy()
        
        # Adaptive cooling
        if iteration % 10 == 0:
            acc_rate = acceptance_count / max(1, iteration)
            sa.cool_adaptive(iteration, acc_rate)
        else:
            sa.cool_exponential(iteration)
        
        # Reheat if needed
        if iteration % 30 == 0 and iteration > 0 and acceptance_count < 3:
            sa.reheat()
            acceptance_count = 0
    
    return best_pack, best_L

def optimize_puzzle_sa(args):
    """Advanced SA optimizer for single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d} L_start={pg.side(p_base):.9f}")
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Parallel annealing
    try:
        print(f"    Running parallel annealing (5 chains)...")
        candidate, candidate_L = parallel_annealing(best_p, n_chains=5, n_steps=120)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Parallel SA improved: {candidate_L:.9f}")
    except Exception as e:
        print(f"    Parallel SA failed: {e}")
    
    # Strategy 2: Hybrid SA + local search
    try:
        print(f"    Running hybrid SA + local search...")
        candidate, candidate_L = hybrid_sa_local_search(best_p, n_iterations=80)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Hybrid SA improved: {candidate_L:.9f}")
    except Exception as e:
        print(f"    Hybrid SA failed: {e}")
    
    # Final intensive polish
    try:
        for seed in range(5):
            candidate, _, _ = polish.polish(best_p, seed=seed*7777,
                                           rounds=8, max_seconds=20,
                                           trust_start=0.018,
                                           regularization=6e-13)
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
    print("ADVANCED SIMULATED ANNEALING OPTIMIZER")
    print("=" * 80)
    print("Parallel Chains, Adaptive Cooling, Reheating, Hybrid Local Search")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target medium-large puzzles where SA excels
    targets = list(range(150, 600))
    
    print(f"Targeting {len(targets)} puzzles (n=150-600)")
    print(f"SA excels at escaping local minima\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_sa((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} SA improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/sa_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_sa_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {new_score:.12f}")

if __name__ == '__main__':
    main()
