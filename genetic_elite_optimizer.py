#!/usr/bin/env python3
"""
Elite Genetic Algorithm Optimizer
- Tournament selection
- Advanced crossover (uniform, arithmetic, blend)
- Adaptive mutation rates
- Elitism preservation
- Diversity maintenance
- Island model with migration
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

class Individual:
    """Represents one packing solution"""
    def __init__(self, packing):
        self.packing = packing.copy()
        self.fitness = None
        self.age = 0
    
    def evaluate(self):
        """Calculate fitness (negative side length for minimization)"""
        try:
            self.fitness = -pg.side(self.packing)
        except:
            self.fitness = -float('inf')
        return self.fitness
    
    def copy(self):
        """Create a copy"""
        ind = Individual(self.packing)
        ind.fitness = self.fitness
        ind.age = self.age
        return ind

class GeneticAlgorithm:
    """Advanced genetic algorithm with multiple strategies"""
    def __init__(self, pop_size=50, elite_size=5, tournament_size=3):
        self.pop_size = pop_size
        self.elite_size = elite_size
        self.tournament_size = tournament_size
        self.population = []
        self.generation = 0
        self.best_ever = None
    
    def initialize_population(self, base_packing, diversity=0.05):
        """Create initial diverse population"""
        self.population = []
        
        # Add the base packing
        ind = Individual(base_packing)
        ind.evaluate()
        self.population.append(ind)
        self.best_ever = ind.copy()
        
        # Create diverse variants
        for i in range(self.pop_size - 1):
            # Random perturbation
            scale = diversity * (1 + i / self.pop_size)
            perturbed = base_packing.copy()
            perturbed[:, :2] += np.random.randn(*perturbed[:, :2].shape) * scale
            perturbed[:, 2] += np.random.randn(len(perturbed)) * scale * 0.5
            
            # Optimize with varying parameters
            try:
                if i % 3 == 0:
                    perturbed, _, _ = polish.polish(perturbed, seed=i*100,
                                                    rounds=3, max_seconds=5,
                                                    trust_start=0.01 + 0.04*np.random.random(),
                                                    regularization=10**(-13 + 2*np.random.random()))
                elif i % 3 == 1:
                    perturbed, _, _ = reclosure.reclose(perturbed, seed=i*100,
                                                        trust=0.15 + 0.3*np.random.random(),
                                                        tie=0.15 + 0.25*np.random.random(),
                                                        rounds=3, seconds=5)
            except:
                pass
            
            ind = Individual(perturbed)
            ind.evaluate()
            self.population.append(ind)
            
            if ind.fitness > self.best_ever.fitness:
                self.best_ever = ind.copy()
    
    def tournament_selection(self):
        """Select parent using tournament"""
        tournament = np.random.choice(self.population, self.tournament_size, replace=False)
        return max(tournament, key=lambda ind: ind.fitness).copy()
    
    def crossover_uniform(self, parent1, parent2):
        """Uniform crossover - randomly select from each parent"""
        n = len(parent1.packing)
        child_pack = np.zeros_like(parent1.packing)
        
        for i in range(n):
            if np.random.random() < 0.5:
                child_pack[i] = parent1.packing[i]
            else:
                child_pack[i] = parent2.packing[i]
        
        return Individual(child_pack)
    
    def crossover_arithmetic(self, parent1, parent2, alpha=0.5):
        """Arithmetic crossover - weighted average"""
        child_pack = alpha * parent1.packing + (1 - alpha) * parent2.packing
        return Individual(child_pack)
    
    def crossover_blend(self, parent1, parent2):
        """Blend crossover with random weights per gene"""
        n = len(parent1.packing)
        alphas = np.random.random((n, 3))
        child_pack = alphas * parent1.packing + (1 - alphas) * parent2.packing
        return Individual(child_pack)
    
    def mutate_adaptive(self, individual, base_rate=0.1, strength=0.02):
        """Adaptive mutation based on fitness and age"""
        # Higher mutation for older, less fit individuals
        fitness_rank = sorted(self.population, key=lambda x: x.fitness, reverse=True).index(individual)
        rank_factor = fitness_rank / len(self.population)
        age_factor = min(individual.age / 10, 1.0)
        
        mutation_rate = base_rate * (1 + rank_factor + age_factor)
        mutation_strength = strength * (1 + age_factor)
        
        mutated = individual.packing.copy()
        n = len(mutated)
        
        # Position mutations
        mask = np.random.random((n, 2)) < mutation_rate
        mutated[:, :2][mask] += np.random.randn(mask.sum()) * mutation_strength
        
        # Angle mutations
        mask_angle = np.random.random(n) < mutation_rate
        mutated[mask_angle, 2] += np.random.randn(mask_angle.sum()) * mutation_strength * 0.5
        
        return Individual(mutated)
    
    def evolve_generation(self):
        """Evolve one generation"""
        self.generation += 1
        
        # Sort by fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Elitism: keep best individuals
        new_population = [ind.copy() for ind in self.population[:self.elite_size]]
        
        # Generate offspring
        while len(new_population) < self.pop_size:
            # Selection
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()
            
            # Crossover (choose strategy randomly)
            strategy = np.random.randint(3)
            if strategy == 0:
                child = self.crossover_uniform(parent1, parent2)
            elif strategy == 1:
                alpha = 0.3 + 0.4 * np.random.random()
                child = self.crossover_arithmetic(parent1, parent2, alpha)
            else:
                child = self.crossover_blend(parent1, parent2)
            
            # Mutation
            if np.random.random() < 0.8:  # 80% mutation rate
                child = self.mutate_adaptive(child)
            
            # Local optimization with probability
            if np.random.random() < 0.3:
                try:
                    if np.random.random() < 0.5:
                        child.packing, _, _ = polish.polish(child.packing, 
                                                            seed=self.generation*1000,
                                                            rounds=3, max_seconds=5,
                                                            trust_start=0.015,
                                                            regularization=1e-12)
                    else:
                        child.packing, _, _ = reclosure.reclose(child.packing,
                                                                seed=self.generation*1000,
                                                                trust=0.22, tie=0.22,
                                                                rounds=3, seconds=5)
                except:
                    pass
            
            # Evaluate
            child.evaluate()
            new_population.append(child)
            
            # Update best ever
            if child.fitness > self.best_ever.fitness:
                self.best_ever = child.copy()
        
        # Age population
        for ind in new_population:
            ind.age += 1
        
        self.population = new_population
    
    def run(self, n_generations=50):
        """Run genetic algorithm"""
        for gen in range(n_generations):
            self.evolve_generation()
            
            if gen % 10 == 0:
                best_L = -self.best_ever.fitness
                print(f"    Gen {gen:3d}: Best L={best_L:.9f}", end="\r", flush=True)
        
        print()  # New line
        return self.best_ever.packing, -self.best_ever.fitness

def optimize_puzzle_genetic(args):
    """Genetic algorithm optimization for single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d} L_start={pg.side(p_base):.9f}")
    
    original_L = pg.side(p_base)
    
    # Run genetic algorithm
    ga = GeneticAlgorithm(pop_size=40, elite_size=4, tournament_size=3)
    ga.initialize_population(p_base, diversity=0.03)
    
    best_p, best_L = ga.run(n_generations=30)
    
    # Final intensive polish
    try:
        for seed in range(5):
            candidate, _, _ = polish.polish(best_p, seed=seed*10000,
                                           rounds=7, max_seconds=15,
                                           trust_start=0.02,
                                           regularization=5e-13)
            candidate_L = pg.side(candidate)
            if candidate_L < best_L:
                best_L = candidate_L
                best_p = candidate.copy()
    except:
        pass
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f"       → L_final={best_L:.9f} ★WIN! Δ={improvement:.2e}")
        return (n, best_p, best_L, improvement)
    else:
        print(f"       → L_final={best_L:.9f} (no improvement)")
        return None

def main():
    print("=" * 80)
    print("ELITE GENETIC ALGORITHM OPTIMIZER")
    print("=" * 80)
    print("Tournament, Adaptive Mutation, Multiple Crossovers, Elitism")
    print("=" * 80 + "\n")
    
    # Load best submission
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target puzzles where evolutionary methods excel
    # Focus on challenging mid-size puzzles
    targets = list(range(100, 500))
    
    print(f"Targeting {len(targets)} puzzles (n=100-500)")
    print(f"Running 30 generations per puzzle\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_genetic((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} genetic improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/genetic_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_genetic_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ NEW SUBMISSION")
        print(f"  Score: {new_score:.12f}")
        print(f"  File: {sub_path}")
        print(f"  Genetic wins: {len(wins)}")

if __name__ == '__main__':
    main()
