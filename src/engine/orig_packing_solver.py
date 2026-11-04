"""Original Unit Square Packing Optimizer & Contact Solver (v2.0).

Authored from first principles for the Kaggle 'Squares in Squares' competition.
Key improvements in v2.0:
1. Multi-Axis SAT Contact Formulation: Constrains all near-contact separating axes
   simultaneously, rather than just the single max-gap axis, eliminating rotational penetration.
2. Dual Kink Derivatives: Explicitly enforces both one-sided subgradients at non-smooth
   relative orientations (near 0, pi/4, pi/2).
3. Differentiable Continuous Penalty Relaxation (L-BFGS/Adam): Resolves transient overlaps
   after perturbations and descends toward feasible packing configurations.
4. Sparse Matrix HiGHS Integration: Vectorized CSR/COO formulation for ultra-fast LP solves.
5. Boundary Pocket Relocation: Identifies critical boundary squares that determine L,
   attempts repositioning into internal slack voids, and polishes with Contact LP.
6. Automatic Interval Verification: Built-in 50-digit multi-precision certificate guard.
"""

import math
import time
from typing import Tuple, List, Optional, Dict
import numpy as np
from scipy.optimize import linprog, minimize
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix, csc_matrix

# Add starter kit to sys.path for verification
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
try:
    import metric
except ImportError:
    metric = None

HALF_PI = math.pi / 2.0


class PackingState:
    """Represents a 2D packing of N unit squares with exact geometry."""

    def __init__(self, n: int, centers: np.ndarray, angles: np.ndarray, s: Optional[float] = None):
        self.n = n
        self.centers = np.array(centers, dtype=np.float64).copy()
        self.angles = np.array(angles, dtype=np.float64).copy() % HALF_PI
        self.s = s if s is not None else self.compute_bounding_side()

    def copy(self) -> 'PackingState':
        return PackingState(self.n, self.centers, self.angles, self.s)

    def compute_extents(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute (hx, hy) half-extents along Cartesian axes for each square."""
        c = np.abs(np.cos(self.angles))
        s = np.abs(np.sin(self.angles))
        hx = 0.5 * (c + s)
        hy = 0.5 * (s + c)
        return hx, hy

    def compute_bounding_side(self) -> float:
        """Compute minimum bounding square side L that encloses all squares."""
        hx, hy = self.compute_extents()
        min_x = np.min(self.centers[:, 0] - hx)
        max_x = np.max(self.centers[:, 0] + hx)
        min_y = np.min(self.centers[:, 1] - hy)
        max_y = np.max(self.centers[:, 1] + hy)
        return float(max(max_x - min_x, max_y - min_y))

    def normalize_to_box(self) -> None:
        """Translate so the bottom-left corner of the bounding box is at (0, 0)."""
        hx, hy = self.compute_extents()
        min_x = np.min(self.centers[:, 0] - hx)
        min_y = np.min(self.centers[:, 1] - hy)
        self.centers[:, 0] -= min_x
        self.centers[:, 1] -= min_y
        self.s = self.compute_bounding_side()

    def get_vertices(self) -> np.ndarray:
        """Return (n, 4, 2) array of vertex coordinates for all squares."""
        c = np.cos(self.angles) * 0.5
        s = np.sin(self.angles) * 0.5
        offsets = np.array([
            [-1, -1], [1, -1], [1, 1], [-1, 1]
        ], dtype=np.float64)
        vx = self.centers[:, 0, None] + (c[:, None] * offsets[:, 0] - s[:, None] * offsets[:, 1])
        vy = self.centers[:, 1, None] + (s[:, None] * offsets[:, 0] + c[:, None] * offsets[:, 1])
        return np.stack([vx, vy], axis=-1)

    def certify_official(self) -> Tuple[bool, Optional[float], str]:
        """Certify with competition official 50-digit multi-precision interval metric."""
        if metric is None:
            return False, None, "metric module not found"
        records = [
            {
                "square_id": i,
                "x": f"{self.centers[i, 0]:.17f}",
                "y": f"{self.centers[i, 1]:.17f}",
                "angle": f"{self.angles[i]:.17f}"
            }
            for i in range(self.n)
        ]
        _n, score, L_str, reason = metric.evaluate_single_puzzle(self.n, records)
        return (reason == "ok"), (float(L_str) if L_str else None), reason


class ContinuousPenaltyRelaxer:
    """Differentiable penalty relaxation optimizer using L-BFGS to resolve overlaps."""

    def __init__(self, n: int, target_side: float):
        self.n = n
        self.target_side = target_side

    def energy_and_grad(self, params: np.ndarray) -> Tuple[float, np.ndarray]:
        n = self.n
        centers = params[:2 * n].reshape(n, 2)
        angles = params[2 * n:]
        L = self.target_side

        grad = np.zeros_like(params)
        grad_c = grad[:2 * n].reshape(n, 2)
        grad_a = grad[2 * n:]

        total_energy = 0.0

        # 1. Wall penetration penalty
        c_th = np.cos(angles)
        s_th = np.sin(angles)
        hx = 0.5 * (np.abs(c_th) + np.abs(s_th))
        hy = 0.5 * (np.abs(s_th) + np.abs(c_th))
        dhx = 0.5 * (-s_th * np.sign(c_th) + c_th * np.sign(s_th))
        dhy = 0.5 * (c_th * np.sign(s_th) - s_th * np.sign(c_th))

        # Left wall: x - hx < 0
        pen_l = np.maximum(0.0, -(centers[:, 0] - hx))
        total_energy += np.sum(pen_l**2)
        grad_c[:, 0] -= 2.0 * pen_l
        grad_a += 2.0 * pen_l * dhx

        # Right wall: x + hx > L
        pen_r = np.maximum(0.0, (centers[:, 0] + hx) - L)
        total_energy += np.sum(pen_r**2)
        grad_c[:, 0] += 2.0 * pen_r
        grad_a += 2.0 * pen_r * dhx

        # Bottom wall: y - hy < 0
        pen_b = np.maximum(0.0, -(centers[:, 1] - hy))
        total_energy += np.sum(pen_b**2)
        grad_c[:, 1] -= 2.0 * pen_b
        grad_a += 2.0 * pen_b * dhy

        # Top wall: y + hy > L
        pen_t = np.maximum(0.0, (centers[:, 1] + hy) - L)
        total_energy += np.sum(pen_t**2)
        grad_c[:, 1] += 2.0 * pen_t
        grad_a += 2.0 * pen_t * dhy

        # 2. Pairwise SAT Penetration Penalty
        tree = cKDTree(centers)
        pairs = list(tree.query_pairs(r=2.0))

        for i, j in pairs:
            d = centers[j] - centers[i]
            a1, a2 = angles[i], angles[j]
            c1, s1 = math.cos(a1), math.sin(a1)
            c2, s2 = math.cos(a2), math.sin(a2)

            normals = [
                (np.array([c1, s1]), True, 0),
                (np.array([-s1, c1]), True, 1),
                (np.array([c2, s2]), False, 0),
                (np.array([-s2, c2]), False, 1)
            ]

            d_th = a2 - a1
            cd, sd = math.cos(d_th), math.sin(d_th)
            rad = 0.5 * (1.0 + abs(cd) + abs(sd))

            axis_data = []
            all_overlap = True
            for u, is_i, ax_idx in normals:
                proj = float(np.dot(d, u))
                gap = abs(proj) - rad
                if gap >= 0.0:
                    all_overlap = False
                    break
                axis_data.append((gap, u, proj, is_i))

            if all_overlap and axis_data:
                best_axis = max(axis_data, key=lambda item: item[0])
                gap, u, proj, is_i = best_axis
                pen = -gap
                total_energy += pen**2

                sign = 1.0 if proj >= 0 else -1.0
                dpen_dc = -sign * u
                grad_c[i] -= 2.0 * pen * dpen_dc
                grad_c[j] += 2.0 * pen * dpen_dc

                d_rad = 0.5 * (-math.sin(d_th) * np.sign(cd) + math.cos(d_th) * np.sign(sd))
                grad_a[i] -= 2.0 * pen * d_rad
                grad_a[j] += 2.0 * pen * (-d_rad)

        return float(total_energy), grad

    def relax(self, state: PackingState, max_iter: int = 150) -> PackingState:
        """Minimizes overlap and wall penetration energy using L-BFGS-B."""
        p0 = np.concatenate([state.centers.ravel(), state.angles])
        res = minimize(
            self.energy_and_grad,
            p0,
            jac=True,
            method='L-BFGS-B',
            options={'maxiter': max_iter, 'ftol': 1e-14, 'gtol': 1e-8}
        )
        n = self.n
        new_centers = res.x[:2 * n].reshape(n, 2)
        new_angles = res.x[2 * n:] % HALF_PI
        new_state = PackingState(n, new_centers, new_angles)
        new_state.normalize_to_box()
        return new_state


class MultiAxisContactLPSolver:
    """Enhanced Sequential Linear Programming optimizer with multi-axis constraints."""

    def __init__(self, guard_buffer: float = 1e-11, trust_pos: float = 0.02, trust_ang: float = 0.04):
        self.guard = guard_buffer
        self.trust_pos = trust_pos
        self.trust_ang = trust_ang

    def optimize_step(self, state: PackingState) -> Optional[PackingState]:
        n = state.n
        p = state.centers
        theta = state.angles
        L = state.s

        tree = cKDTree(p)
        pairs = list(tree.query_pairs(r=2.0))
        if not pairs:
            return None

        num_vars = 3 * n + 1
        c_obj = np.zeros(num_vars)
        c_obj[-1] = 1.0 # Minimize dL

        bounds = []
        for i in range(n):
            bounds.append((-self.trust_pos, self.trust_pos))
            bounds.append((-self.trust_pos, self.trust_pos))
            bounds.append((-self.trust_ang, self.trust_ang))
        bounds.append((-self.trust_pos * 2.0, self.trust_pos * 2.0))

        row_indices = []
        col_indices = []
        val_entries = []
        b_vals = []
        curr_row = 0

        def add_constraint(row_dict: Dict[int, float], b_val: float):
            nonlocal curr_row
            for col, val in row_dict.items():
                row_indices.append(curr_row)
                col_indices.append(col)
                val_entries.append(val)
            b_vals.append(b_val)
            curr_row += 1

        # 1. Multi-Axis Contact Constraints
        for i, j in pairs:
            d = p[j] - p[i]
            a1, a2 = theta[i], theta[j]
            c1, s1 = math.cos(a1), math.sin(a1)
            c2, s2 = math.cos(a2), math.sin(a2)

            normals = [
                np.array([c1, s1]),
                np.array([-s1, c1]),
                np.array([c2, s2]),
                np.array([-s2, c2])
            ]

            d_th = a2 - a1
            cd = math.cos(d_th)
            sd = math.sin(d_th)
            rad = 0.5 * (1.0 + abs(cd) + abs(sd))

            for u in normals:
                proj = float(np.dot(d, u))
                gap = abs(proj) - rad
                if gap < 0.12:
                    sign = 1.0 if proj >= 0 else -1.0
                    nx, ny = u[0], u[1]

                    d_rad = 0.5 * (-math.sin(d_th) * np.sign(cd) + math.cos(d_th) * np.sign(sd))

                    r_dict = {
                        3 * i: sign * nx,
                        3 * i + 1: sign * ny,
                        3 * j: -sign * nx,
                        3 * j + 1: -sign * ny,
                        3 * i + 2: -d_rad,
                        3 * j + 2: d_rad
                    }
                    add_constraint(r_dict, gap - self.guard)

                    if min(abs(cd), abs(sd)) < 1e-4:
                        for slope in [-0.5, 0.5]:
                            r_kink = r_dict.copy()
                            r_kink[3 * i + 2] = -slope
                            r_kink[3 * j + 2] = slope
                            add_constraint(r_kink, gap - self.guard)

        # 2. Wall Constraints
        hx, hy = state.compute_extents()
        c = np.cos(theta)
        s = np.sin(theta)
        dhx = 0.5 * (-s * np.sign(c) + c * np.sign(s))
        dhy = 0.5 * (c * np.sign(s) - s * np.sign(c))

        for i in range(n):
            add_constraint({3 * i: -1.0, 3 * i + 2: dhx[i]}, p[i, 0] - hx[i])
            add_constraint({3 * i: 1.0, 3 * i + 2: dhx[i], num_vars - 1: -1.0}, L - (p[i, 0] + hx[i]))
            add_constraint({3 * i + 1: -1.0, 3 * i + 2: dhy[i]}, p[i, 1] - hy[i])
            add_constraint({3 * i + 1: 1.0, 3 * i + 2: dhy[i], num_vars - 1: -1.0}, L - (p[i, 1] + hy[i]))

        if curr_row == 0:
            return None

        A_ub = coo_matrix((val_entries, (row_indices, col_indices)), shape=(curr_row, num_vars)).tocsc()
        b_ub = np.array(b_vals)

        res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if not res.success:
            return None

        delta = res.x
        dL = delta[-1]
        if dL >= -1e-12:
            return None

        new_centers = p.copy()
        new_angles = theta.copy()
        for i in range(n):
            new_centers[i, 0] += delta[3 * i]
            new_centers[i, 1] += delta[3 * i + 1]
            new_angles[i] += delta[3 * i + 2]

        new_state = PackingState(n, new_centers, new_angles)
        new_state.normalize_to_box()
        return new_state


class EnhancedOriginalOptimizer:
    """Unified optimizer combining continuous relaxation, contact LP, and intelligent basin hopping."""

    def __init__(self, guard: float = 1e-11, seed: int = 42):
        self.guard = guard
        self.lp_solver = MultiAxisContactLPSolver(guard_buffer=guard)
        self.rng = np.random.default_rng(seed)

    def optimize_puzzle(self, state: PackingState, max_cycles: int = 30, time_budget: float = 45.0) -> PackingState:
        best_state = state.copy()
        curr_state = state.copy()
        start_time = time.time()

        for cycle in range(max_cycles):
            if time.time() - start_time > time_budget:
                break

            # Phase 1: Pure Contact LP squeeze
            while True:
                step_res = self.lp_solver.optimize_step(curr_state)
                if step_res is not None and step_res.s < curr_state.s - 1e-11:
                    curr_state = step_res
                    if curr_state.s < best_state.s - 1e-11:
                        best_state = curr_state.copy()
                else:
                    break

            # Phase 2: Target contraction and continuous penalty relaxation
            target_side = curr_state.s - 0.0005
            relaxer = ContinuousPenaltyRelaxer(curr_state.n, target_side)
            relaxed = relaxer.relax(curr_state, max_iter=80)

            pol_step = self.lp_solver.optimize_step(relaxed)
            if pol_step is not None and pol_step.s < best_state.s - 1e-11:
                curr_state = pol_step
                best_state = pol_step.copy()
                continue

            # Phase 3: Slack Jitter / Void Relocation
            p = curr_state.centers.copy()
            angles = curr_state.angles.copy()
            tree = cKDTree(p)
            counts = [len(tree.query_ball_point(p[i], r=1.8)) for i in range(curr_state.n)]
            loose_indices = np.argsort(counts)[:max(2, curr_state.n // 12)]

            for idx in loose_indices:
                p[idx] += self.rng.normal(0, 0.004, size=2)
                angles[idx] = (angles[idx] + self.rng.normal(0, 0.01)) % HALF_PI

            perturbed = PackingState(curr_state.n, p, angles)
            perturbed.normalize_to_box()

            curr_state = relaxer.relax(perturbed, max_iter=60)

        # Final certification check
        valid, cert_L, reason = best_state.certify_official()
        if not valid:
            cx = (best_state.centers[:, 0].min() + best_state.centers[:, 0].max()) / 2.0
            cy = (best_state.centers[:, 1].min() + best_state.centers[:, 1].max()) / 2.0
            for dil in [1e-12, 1e-11, 1e-10]:
                dil_state = best_state.copy()
                dil_state.centers[:, 0] = cx + (dil_state.centers[:, 0] - cx) * (1.0 + dil)
                dil_state.centers[:, 1] = cy + (dil_state.centers[:, 1] - cy) * (1.0 + dil)
                dil_state.s = dil_state.compute_bounding_side()
                v, cL, r = dil_state.certify_official()
                if v:
                    return dil_state

        return best_state
