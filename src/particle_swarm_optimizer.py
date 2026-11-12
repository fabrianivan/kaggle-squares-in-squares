#!/usr/bin/env python3
"""
PARTICLE SWARM OPTIMIZER - Swarm intelligence approach
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg

def particle_swarm_optimize(n, p_base, n_particles=40, iterations=200):
    """Particle swarm optimization"""
    try:
        L0 = pg.side(p_base)
        rng = np.random.default_rng(n * 17)
        
        # Initialize particles
        particles = []
        velocities = []
        personal_best = []
        personal_best_L = []
        
        for i in range(n_particles):
            p = p_base.copy()
            if i > 0:
                p[:, 0] += rng.normal(0, 0.005, n)
                p[:, 1] += rng.normal(0, 0.005, n)
                p[:, 2] += rng.normal(0, 0.02, n)
                p = pg.normalize(p)
            particles.append(p)
            velocities.append(np.zeros_like(p))
            personal_best.append(p.copy())
            personal_best_L.append(pg.side(p))
        
        global_best = p_base.copy()
        global_best_L = L0
        
        w = 0.7  # Inertia
        c1 = 1.5  # Cognitive
        c2 = 1.5  # Social
        
        for iter in range(iterations):
            for i in range(n_particles):
                # Update velocity
                r1, r2 = rng.random(2)
                velocities[i] = (w * velocities[i] + 
                               c1 * r1 * (personal_best[i] - particles[i]) +
                               c2 * r2 * (global_best - particles[i]))
                
                # Update position
                particles[i] = particles[i] + velocities[i]
                particles[i] = pg.normalize(particles[i])
                particles[i] = pg.repair(particles[i], clearance=1e-10)
                
                if particles[i] is not None:
                    try:
                        L = pg.side(particles[i])
                        
                        if L < personal_best_L[i]:
                            personal_best[i] = particles[i].copy()
                            personal_best_L[i] = L
                            
                            if L < global_best_L - 1e-11:
                                global_best = particles[i].copy()
                                global_best_L = L
                    except:
                        pass
            
            if (iter + 1) % 50 == 0:
                print(f"    PSO iter {iter+1}: best_L={global_best_L:.12f}")
        
        if global_best_L < L0 - 1e-11:
            return (n, L0, global_best_L, global_best)
    except:
        pass
    return None

def main():
    print("="*80)
    print("PARTICLE SWARM OPTIMIZER")
    print("="*80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    # Target specific range
    puzzles = []
    for n in range(450, 751, 10):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            puzzles.append((n, p))
    
    print(f"\nTargeting {len(puzzles)} puzzles with particle swarm\n")
    
    wins = []
    for i, (n, p) in enumerate(puzzles):
        print(f"[{i+1}/{len(puzzles)}] PSO on n={n}...")
        result = particle_swarm_optimize(n, p)
        if result is not None:
            wins.append(result)
            print(f"  ✓ WIN!")
    
    print(f"\nParticle swarm: {len(wins)} wins")
    if wins:
        np.savez('output/pso_wins.npz', **{str(n): p for n, _, _, p in wins})

if __name__ == '__main__':
    main()
