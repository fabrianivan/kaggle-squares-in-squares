#!/usr/bin/env python3
"""
Mathematical Properties Optimizer
Exploits theoretical properties of optimal square packings:
- Symmetry groups and crystallographic constraints
- Number-theoretic patterns (perfect squares have special structure)
- Boundary minimization (squares should touch container edges)
- Contact graph optimization (maximize touching pairs)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import json
import time
import multiprocessing as mp
from scipy.optimize import minimize, differential_evolution
from scipy.spatial import ConvexHull, Delaunay

import sys
sys.path.append('src')
from tools.packing_geometry import side_length, rotate_solution
from tools.cpu_axis_reclosure import axis_reclosure_cpu
from tools.cpu_contact_polish import contact_polish

class SymmetryExploiter:
    """Exploit symmetry groups to find better packings"""
    
    def detect_symmetry(self, solution):
        """Detect if packing has rotational or reflection symmetry"""
        centers = solution[:, :2]
        center_of_mass = np.mean(centers, axis=0)
        
        # Test for 90-degree rotational symmetry
        centered = centers - center_of_mass
        rotated_90 = np.column_stack([-centered[:, 1], centered[:, 0]])
        
        # Check if rotation matches original (approximately)
        from scipy.spatial import cKDTree
        tree = cKDTree(centered)
        distances, _ = tree.query(rotated_90)
        
        has_90_symmetry = np.mean(distances) < 0.01
        
        return has_90_symmetry
    
    def enforce_symmetry(self, solution, symmetry_type='4-fold'):
        """Enforce specific symmetry on packing"""
        n = len(solution)
        centers = solution[:, :2]
        center_of_mass = np.mean(centers, axis=0)
        
        if symmetry_type == '4-fold':
            # For 4-fold symmetry, divide into 4 groups
            # and replicate first group with 90° rotations
            group_size = n // 4
            
            if group_size > 0:
                # Take first quadrant
                template = solution[:group_size].copy()
                template[:, :2] -= center_of_mass
                
                # Generate 4 symmetric copies
                result = []
                for angle in [0, np.pi/2, np.pi, 3*np.pi/2]:
                    rotated = template.copy()
                    cos_a, sin_a = np.cos(angle), np.sin(angle)
                    x, y = rotated[:, 0], rotated[:, 1]
                    rotated[:, 0] = cos_a * x - sin_a * y
                    rotated[:, 1] = sin_a * x + cos_a * y
                    rotated[:, 2] += angle
                    result.append(rotated)
                
                symmetric_sol = np.vstack(result[:min(4, n//group_size)])
                symmetric_sol[:, :2] += center_of_mass
                
                # Fill remaining with original
                if len(symmetric_sol) < n:
                    remaining = solution[len(symmetric_sol):].copy()
                    symmetric_sol = np.vstack([symmetric_sol, remaining])
                
                return symmetric_sol[:n]
        
        return solution

class BoundaryOptimizer:
    """Optimize squares touching container boundary"""
    
    def identify_boundary_squares(self, solution):
        """Find squares that should touch the boundary"""
        L = side_length(solution)
        centers = solution[:, :2]
        
        # Squares close to edges (within 1.1 of boundary)
        boundary_mask = (
            (np.abs(centers[:, 0]) > L/2 - 1.1) |
            (np.abs(centers[:, 1]) > L/2 - 1.1)
        )
        
        return np.where(boundary_mask)[0]
    
    def snap_to_boundary(self, solution):
        """Snap boundary squares exactly to edges"""
        L = side_length(solution)
        boundary_indices = self.identify_boundary_squares(solution)
        
        new_solution = solution.copy()
        
        for idx in boundary_indices:
            x, y = new_solution[idx, :2]
            
            # Snap to nearest edge
            if abs(x) > abs(y):
                # Snap to left/right edge
                new_solution[idx, 0] = np.sign(x) * (L/2 - 0.5)
            else:
                # Snap to top/bottom edge
                new_solution[idx, 1] = np.sign(y) * (L/2 - 0.5)
        
        return new_solution

class ContactGraphOptimizer:
    """Maximize number of touching square pairs"""
    
    def build_contact_graph(self, solution):
        """Build graph of touching squares"""
        n = len(solution)
        centers = solution[:, :2]
        angles = solution[:, 2]
        
        contacts = []
        
        for i in range(n):
            for j in range(i+1, n):
                # Calculate distance between centers
                dist = np.linalg.norm(centers[i] - centers[j])
                
                # If approximately sqrt(2) apart, they touch
                if abs(dist - np.sqrt(2)) < 0.01:
                    contacts.append((i, j))
        
        return contacts
    
    def optimize_contacts(self, solution, target_contacts=None):
        """Optimize to increase contact count"""
        n = len(solution)
        
        def contact_loss(flat_sol):
            """Loss = negative number of contacts"""
            sol = flat_sol.reshape(-1, 3)
            contacts = self.build_contact_graph(sol)
            # Also penalize container size
            L = side_length(sol)
            return -len(contacts) + 0.1 * L
        
        # Optimize
        flat_sol = solution.flatten()
        bounds = [(-20, 20)] * (n * 2) + [(0, 2*np.pi)] * n
        
        result = minimize(
            contact_loss,
            flat_sol,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 100}
        )
        
        if result.success:
            return result.x.reshape(-1, 3)
        else:
            return solution

class NumberTheoreticOptimizer:
    """Exploit patterns for special n values"""
    
    def is_perfect_square(self, n):
        """Check if n is a perfect square"""
        sqrt_n = int(np.sqrt(n))
        return sqrt_n * sqrt_n == n
    
    def is_prime(self, n):
        """Check if n is prime"""
        if n < 2:
            return False
        for i in range(2, int(np.sqrt(n)) + 1):
            if n % i == 0:
                return False
        return True
    
    def optimize_perfect_square(self, n, solution):
        """Special optimization for n = k²"""
        k = int(np.sqrt(n))
        
        # Create perfect grid
        grid_solution = np.zeros((n, 3))
        idx = 0
        for i in range(k):
            for j in range(k):
                grid_solution[idx, 0] = i - k/2 + 0.5
                grid_solution[idx, 1] = j - k/2 + 0.5
                grid_solution[idx, 2] = 0
                idx += 1
        
        grid_score = side_length(grid_solution)
        original_score = side_length(solution)
        
        if grid_score < original_score:
            return grid_solution
        else:
            return solution
    
    def optimize_prime(self, n, solution):
        """Special optimization for prime n"""
        # Primes often have spiral-like optimal packings
        # Create Ulam spiral arrangement
        spiral_solution = self.create_spiral(n)
        
        # Compact it
        try:
            spiral_solution = contact_polish(spiral_solution, rounds=5, reg=1e-11)
            spiral_score = side_length(spiral_solution)
            original_score = side_length(solution)
            
            if spiral_score < original_score:
                return spiral_solution
        except:
            pass
        
        return solution
    
    def create_spiral(self, n):
        """Create Ulam spiral packing"""
        solution = np.zeros((n, 3))
        x, y = 0.0, 0.0
        dx, dy = 1, 0
        steps_in_direction = 1
        steps_taken = 0
        direction_changes = 0
        
        for i in range(n):
            solution[i] = [x, y, 0]
            
            x += dx
            y += dy
            steps_taken += 1
            
            if steps_taken == steps_in_direction:
                # Change direction (right -> up -> left -> down -> repeat)
                dx, dy = -dy, dx
                direction_changes += 1
                steps_taken = 0
                
                if direction_changes % 2 == 0:
                    steps_in_direction += 1
        
        return solution

class DensityGradientOptimizer:
    """Optimize using density gradients (pack tighter in center)"""
    
    def compute_local_density(self, solution):
        """Compute local density around each square"""
        from scipy.spatial import cKDTree
        
        centers = solution[:, :2]
        tree = cKDTree(centers)
        
        # Find 10 nearest neighbors
        distances, _ = tree.query(centers, k=11)
        
        # Local density = 1 / mean distance to neighbors
        local_density = 1.0 / np.mean(distances[:, 1:], axis=1)
        
        return local_density
    
    def optimize_density_gradient(self, solution, iterations=50):
        """Move squares toward high-density regions"""
        best_solution = solution.copy()
        best_score = side_length(solution)
        
        for iteration in range(iterations):
            density = self.compute_local_density(best_solution)
            centers = best_solution[:, :2]
            
            # Move each square toward density gradient
            for i in range(len(solution)):
                # Find neighbors
                from scipy.spatial import cKDTree
                tree = cKDTree(centers)
                distances, neighbor_idx = tree.query(centers[i], k=6)
                
                # Compute gradient direction
                neighbor_densities = density[neighbor_idx[1:]]
                neighbor_positions = centers[neighbor_idx[1:]]
                
                # Weighted average toward high-density neighbors
                weights = neighbor_densities / np.sum(neighbor_densities)
                target = np.average(neighbor_positions, axis=0, weights=weights)
                
                # Move slightly toward target
                alpha = 0.05 * (1 - iteration / iterations)
                new_pos = (1 - alpha) * centers[i] + alpha * target
                
                # Update
                test_solution = best_solution.copy()
                test_solution[i, :2] = new_pos
                
                try:
                    test_solution = axis_reclosure_cpu(test_solution, trust=0.2, tie=0.2, reg=1e-11)
                    test_score = side_length(test_solution)
                    
                    if test_score < best_score:
                        best_score = test_score
                        best_solution = test_solution.copy()
                except:
                    pass
        
        return best_solution

def optimize_puzzle_mathematical(args):
    """Mathematical properties-based optimization"""
    puzzle_idx, n, solution = args
    
    original_score = side_length(solution)
    best_solution = solution.copy()
    best_score = original_score
    
    # Initialize optimizers
    symmetry_opt = SymmetryExploiter()
    boundary_opt = BoundaryOptimizer()
    contact_opt = ContactGraphOptimizer()
    number_opt = NumberTheoreticOptimizer()
    density_opt = DensityGradientOptimizer()
    
    # Apply techniques based on problem structure
    
    # 1. Number-theoretic optimization
    if number_opt.is_perfect_square(n):
        try:
            candidate = number_opt.optimize_perfect_square(n, best_solution)
            candidate_score = side_length(candidate)
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    if number_opt.is_prime(n) and n > 20:
        try:
            candidate = number_opt.optimize_prime(n, best_solution)
            candidate_score = side_length(candidate)
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    # 2. Boundary optimization
    try:
        candidate = boundary_opt.snap_to_boundary(best_solution)
        candidate = axis_reclosure_cpu(candidate, trust=0.2, tie=0.25, reg=1e-11)
        candidate_score = side_length(candidate)
        if candidate_score < best_score:
            best_score = candidate_score
            best_solution = candidate.copy()
    except:
        pass
    
    # 3. Density gradient optimization
    try:
        candidate = density_opt.optimize_density_gradient(best_solution, iterations=30)
        candidate_score = side_length(candidate)
        if candidate_score < best_score:
            best_score = candidate_score
            best_solution = candidate.copy()
    except:
        pass
    
    # 4. Symmetry exploitation (for larger puzzles)
    if n >= 40 and n % 4 == 0:
        try:
            candidate = symmetry_opt.enforce_symmetry(best_solution, '4-fold')
            candidate = contact_polish(candidate, rounds=5, reg=1e-11)
            candidate_score = side_length(candidate)
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    # 5. Final multi-parameter polish
    for trust, tie, reg in [
        (0.18, 0.22, 1e-11),
        (0.25, 0.18, 5e-12),
        (0.15, 0.28, 1e-11),
        (0.22, 0.25, 8e-12)
    ]:
        try:
            candidate = axis_reclosure_cpu(best_solution, trust=trust, tie=tie, reg=reg)
            candidate_score = side_length(candidate)
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    # 6. Multiple rotation attempts
    for angle in np.linspace(0, np.pi/2, 12):
        try:
            candidate = rotate_solution(best_solution, angle)
            candidate = contact_polish(candidate, rounds=4, reg=1e-11)
            candidate_score = side_length(candidate)
            if candidate_score < best_score:
                best_score = candidate_score
                best_solution = candidate.copy()
        except:
            pass
    
    improvement = original_score - best_score
    
    if improvement > 1e-9:
        return (puzzle_idx, n, best_solution, best_score, improvement)
    else:
        return None

def main():
    print("=" * 80)
    print("MATHEMATICAL PROPERTIES OPTIMIZER")
    print("=" * 80)
    print("Exploiting: Symmetry, Number Theory, Contact Graphs, Density Gradients")
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
    
    # Calculate current score
    from tools.metric import score_submission
    current_score = score_submission(df)
    print(f"Current score: {current_score:.9f}")
    
    # Target all puzzles
    target_ns = list(range(1, 1001))
    print(f"\nTargeting all {len(target_ns)} puzzles")
    print(f"Using {mp.cpu_count()} CPU cores")
    
    # Prepare arguments
    args_list = []
    for n in target_ns:
        puzzle_df = df[df['n'] == n]
        solution = puzzle_df[['x', 'y', 'phi']].values
        args_list.append((len(args_list), n, solution))
    
    # Parallel optimization
    print("\nOptimizing...")
    start_time = time.time()
    
    wins = {}
    total_improvement = 0.0
    
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(optimize_puzzle_mathematical, args_list)
    
    # Collect improvements
    for result in results:
        if result is not None:
            puzzle_idx, n, solution, score, improvement = result
            wins[n] = solution
            total_improvement += improvement
            print(f"✓ n={n}: improved by {improvement:.9f} → {score:.9f}")
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"Optimization complete in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} improvements")
    print(f"Total improvement: {total_improvement:.9f}")
    
    estimated_score = current_score - total_improvement
    print(f"\nEstimated new score: {estimated_score:.9f}")
    
    # Save wins
    if wins:
        timestamp = int(time.time())
        wins_file = Path('output') / f'mathematical_wins_{timestamp}.npz'
        wins_file.parent.mkdir(exist_ok=True)
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved wins: {wins_file}")
        
        # Create new submission
        new_df = df.copy()
        for n, solution in wins.items():
            mask = new_df['n'] == n
            new_df.loc[mask, ['x', 'y', 'phi']] = solution
        
        submission_file = Path('output') / f'submission_mathematical_{estimated_score:.6f}.csv'
        new_df.to_csv(submission_file, index=False)
        print(f"Saved submission: {submission_file}")
        
        # Verify
        actual_score = score_submission(new_df)
        print(f"\n✓ Verified score: {actual_score:.9f}")
        print(f"✓ Actual improvement: {current_score - actual_score:.9f}")
    else:
        print("\nNo improvements found")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
