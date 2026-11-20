#!/usr/bin/env python3
"""
Quantum-Inspired Optimizer - Using advanced quantum computing concepts
- Quantum annealing simulation
- Superposition of states
- Quantum tunneling for escaping local minima
- Entanglement-inspired correlation optimization
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
from scipy.optimize import differential_evolution

class QuantumState:
    """Represents a quantum superposition of packing states"""
    def __init__(self, n_states=10):
        self.states = []
        self.amplitudes = []
        self.n_states = n_states
    
    def add_state(self, packing, amplitude):
        """Add a state to the superposition"""
        self.states.append(packing.copy())
        self.amplitudes.append(amplitude)
        
        # Keep only top n_states
        if len(self.states) > self.n_states:
            # Sort by amplitude (probability)
            idx = np.argsort(self.amplitudes)[-self.n_states:]
            self.states = [self.states[i] for i in idx]
            self.amplitudes = [self.amplitudes[i] for i in idx]
            
            # Renormalize
            total = sum(self.amplitudes)
            self.amplitudes = [a/total for a in self.amplitudes]
    
    def collapse(self):
        """Collapse to a single state (measurement)"""
        if not self.states:
            return None
        probs = np.array(self.amplitudes)
        probs = probs / probs.sum()
        idx = np.random.choice(len(self.states), p=probs)
        return self.states[idx].copy()
    
    def interfere(self):
        """Create interference pattern (weighted combination)"""
        if not self.states:
            return None
        
        # Weighted average of all states
        total_amp = sum(self.amplitudes)
        result = np.zeros_like(self.states[0])
        
        for state, amp in zip(self.states, self.amplitudes):
            result += state * (amp / total_amp)
        
        return result

def quantum_annealing(packing, n_steps=200, T_start=10.0, T_end=0.001):
    """Simulate quantum annealing process"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    current_p = best_p.copy()
    current_L = best_L
    
    for step in range(n_steps):
        # Temperature schedule (exponential decay)
        T = T_start * (T_end / T_start) ** (step / n_steps)
        
        # Quantum fluctuation strength (decreases with temperature)
        quantum_strength = T / T_start
        
        # Generate multiple candidate states (quantum superposition)
        n_candidates = max(3, int(10 * quantum_strength))
        candidates = []
        
        for _ in range(n_candidates):
            # Add quantum noise
            noise_scale = quantum_strength * 0.1
            candidate = current_p.copy()
            candidate[:, :2] += np.random.randn(*candidate[:, :2].shape) * noise_scale
            candidate[:, 2] += np.random.randn(len(candidate)) * noise_scale * 0.5
            
            try:
                # Optimize candidate
                if np.random.random() < 0.5:
                    candidate, _, _ = polish.polish(candidate, seed=np.random.randint(1e7),
                                                   rounds=4, max_seconds=8,
                                                   trust_start=0.01 + 0.03*np.random.random(),
                                                   regularization=10**(-13 + 2*np.random.random()))
                else:
                    candidate, _, _ = reclosure.reclose(candidate, seed=np.random.randint(1e7),
                                                       trust=0.15 + 0.25*np.random.random(),
                                                       tie=0.15 + 0.25*np.random.random(),
                                                       rounds=4, seconds=8)
                
                candidates.append(candidate)
            except:
                pass
        
        if not candidates:
            continue
        
        # Find best candidate
        best_candidate = min(candidates, key=lambda p: pg.side(p))
        candidate_L = pg.side(best_candidate)
        
        # Quantum tunneling: accept with probability even if worse
        delta_E = candidate_L - current_L
        
        if delta_E < 0:
            # Always accept improvements
            accept = True
        else:
            # Quantum tunneling probability
            tunnel_prob = np.exp(-delta_E / T)
            accept = np.random.random() < tunnel_prob
        
        if accept:
            current_p = best_candidate
            current_L = candidate_L
            
            if current_L < best_L:
                best_L = current_L
                best_p = current_p.copy()
    
    return best_p, best_L

def entanglement_optimize(packing1, packing2):
    """Optimize using entanglement-inspired correlation"""
    n = len(packing1)
    
    # Create entangled state (correlation between two packings)
    # Take positions from packing1, angles from packing2
    entangled1 = packing1.copy()
    entangled1[:, 2] = packing2[:, 2]
    
    # Take positions from packing2, angles from packing1
    entangled2 = packing2.copy()
    entangled2[:, 2] = packing1[:, 2]
    
    # Weighted combinations
    alpha_values = [0.3, 0.5, 0.7]
    candidates = [packing1, packing2, entangled1, entangled2]
    
    for alpha in alpha_values:
        mixed = alpha * packing1 + (1 - alpha) * packing2
        candidates.append(mixed)
    
    # Optimize all candidates
    best_p = packing1
    best_L = pg.side(packing1)
    
    for candidate in candidates:
        try:
            # Quick polish
            optimized, _, _ = polish.polish(candidate, seed=np.random.randint(1e7),
                                           rounds=3, max_seconds=6,
                                           trust_start=0.02,
                                           regularization=1e-12)
            L = pg.side(optimized)
            if L < best_L:
                best_L = L
                best_p = optimized.copy()
        except:
            pass
    
    return best_p, best_L

def optimize_puzzle_quantum(args):
    """Quantum-inspired optimization for a single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d}", end="", flush=True)
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Quantum annealing
    try:
        candidate, candidate_L = quantum_annealing(best_p, n_steps=150, T_start=5.0, T_end=0.001)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f" Q→{best_L:.9f}", end="", flush=True)
    except:
        pass
    
    # Strategy 2: Quantum state superposition
    try:
        quantum_state = QuantumState(n_states=8)
        
        # Generate diverse states
        for i in range(20):
            # Random perturbation
            perturbed = best_p.copy()
            scale = 0.05 * (1 - i/20)
            perturbed[:, :2] += np.random.randn(*perturbed[:, :2].shape) * scale
            
            try:
                if i % 2 == 0:
                    perturbed, _, _ = polish.polish(perturbed, seed=i*1000,
                                                    rounds=3, max_seconds=5,
                                                    trust_start=0.015,
                                                    regularization=1e-12)
                else:
                    perturbed, _, _ = reclosure.reclose(perturbed, seed=i*1000,
                                                        trust=0.2, tie=0.2,
                                                        rounds=3, seconds=5)
                
                # Add to superposition with amplitude based on quality
                L = pg.side(perturbed)
                amplitude = np.exp(-(L - original_L) * 100)
                quantum_state.add_state(perturbed, amplitude)
            except:
                pass
        
        # Collapse and optimize
        collapsed = quantum_state.collapse()
        if collapsed is not None:
            collapsed, _, _ = polish.polish(collapsed, seed=12345,
                                           rounds=5, max_seconds=10,
                                           trust_start=0.02,
                                           regularization=5e-13)
            collapsed_L = pg.side(collapsed)
            if collapsed_L < best_L:
                best_L = collapsed_L
                best_p = collapsed.copy()
                print(f" S→{best_L:.9f}", end="", flush=True)
        
        # Interference pattern
        interfered = quantum_state.interfere()
        if interfered is not None:
            try:
                interfered, _, _ = reclosure.reclose(interfered, seed=54321,
                                                     trust=0.25, tie=0.22,
                                                     rounds=5, seconds=10)
                interfered_L = pg.side(interfered)
                if interfered_L < best_L:
                    best_L = interfered_L
                    best_p = interfered.copy()
                    print(f" I→{best_L:.9f}", end="", flush=True)
            except:
                pass
    except:
        pass
    
    # Strategy 3: Entanglement with rotated version
    try:
        # Create second packing by rotating
        packing2 = best_p.copy()
        packing2[:, 2] += np.pi/4
        packing2, _, _ = reclosure.reclose(packing2, seed=99999,
                                          trust=0.2, tie=0.2,
                                          rounds=3, seconds=5)
        
        candidate, candidate_L = entanglement_optimize(best_p, packing2)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f" E→{best_L:.9f}", end="", flush=True)
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
    print("QUANTUM-INSPIRED OPTIMIZER")
    print("=" * 80)
    print("Advanced techniques: Quantum Annealing, Superposition, Tunneling, Entanglement")
    print("=" * 80 + "\n")
    
    # Load best submission
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target puzzles strategically
    # Focus on medium-large puzzles where quantum methods excel
    targets = list(range(200, 700))
    
    print(f"Targeting {len(targets)} puzzles (n=200-700)")
    print(f"Quantum methods work best on complex mid-size problems\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_quantum((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} quantum improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/quantum_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_quantum_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ NEW SUBMISSION")
        print(f"  Score: {new_score:.12f}")
        print(f"  File: {sub_path}")
        print(f"  Quantum wins: {len(wins)}")

if __name__ == '__main__':
    main()
