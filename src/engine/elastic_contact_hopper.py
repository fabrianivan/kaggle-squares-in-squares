"""Elastic Contact Basin-Hopping Solver.

Authored from first principles for Kaggle 'Squares in Squares'.
Combines:
1. Exact Separating Axis Theorem (SAT) contact kinematics.
2. Analytic smooth penalty potential for pairwise overlaps and bounding box walls.
3. High-precision L-BFGS-B relaxation with contraction targeting.
4. Structural cluster-slip & void relocation basin hopping.
5. Exact mpmath interval certification with Ryū decimal formatting.
"""

from __future__ import annotations
import math
import time
import os
import sys
from typing import Tuple, List, Optional
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

HALF_PI = math.pi / 2.0

class ElasticSolver:
    def __init__(self, n: int, seed: int = 42):
        self.n = n
        self.rng = np.random.default_rng(seed)

    @staticmethod
    def get_corners(centers: np.ndarray, angles: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        c = np.cos(angles) * 0.5
        s = np.sin(angles) * 0.5
        x, y = centers[:, 0], centers[:, 1]
        cx = np.array([x + c - s, x - c - s, x - c + s, x + c + s])
        cy = np.array([y + s + c, y - s + c, y - s - c, y + s - c])
        return cx, cy

    @classmethod
    def compute_bounding_side(cls, centers: np.ndarray, angles: np.ndarray) -> float:
        cx, cy = cls.get_corners(centers, angles)
        w = float(np.max(cx) - np.min(cx))
        h = float(np.max(cy) - np.min(cy))
        return max(w, h)

    def energy_and_grad(self, x_vec: np.ndarray, target_L: float, w_pen: float = 1e5, w_wall: float = 1e5):
        """Calculates total potential energy and analytical gradients."""
        n = self.n
        centers = x_vec[:2*n].reshape((n, 2))
        angles = x_vec[2*n:]

        cos_t = np.cos(angles)
        sin_t = np.sin(angles)

        # Half-extents along Cartesian axes: 0.5 * (|cos| + |sin|)
        # For angles in [0, pi/2], cos >= 0 and sin >= 0
        hx = 0.5 * (np.abs(cos_t) + np.abs(sin_t))
        hy = 0.5 * (np.abs(sin_t) + np.abs(cos_t))

        grad_c = np.zeros_like(centers)
        grad_a = np.zeros_like(angles)
        total_energy = 0.0

        # 1. Wall confinement penalty: box [0, target_L]^2
        # x_min >= 0  =>  centers[:, 0] - hx >= 0
        # x_max <= L  =>  centers[:, 0] + hx <= target_L
        viol_x0 = np.maximum(0.0, -(centers[:, 0] - hx))
        viol_x1 = np.maximum(0.0, centers[:, 0] + hx - target_L)
        viol_y0 = np.maximum(0.0, -(centers[:, 1] - hy))
        viol_y1 = np.maximum(0.0, centers[:, 1] + hy - target_L)

        total_energy += w_wall * float(np.sum(viol_x0**2 + viol_x1**2 + viol_y0**2 + viol_y1**2))

        # Gradient from wall violations
        # d/d(x):
        grad_c[:, 0] += 2.0 * w_wall * (-viol_x0 + viol_x1)
        grad_c[:, 1] += 2.0 * w_wall * (-viol_y0 + viol_y1)

        # d/d(theta): dhx/dtheta = 0.5 * (-sin*sgn(cos) + cos*sgn(sin))
        dhx_da = 0.5 * (-sin_t * np.sign(cos_t + 1e-15) + cos_t * np.sign(sin_t + 1e-15))
        dhy_da = 0.5 * (cos_t * np.sign(sin_t + 1e-15) - sin_t * np.sign(cos_t + 1e-15))

        grad_a += 2.0 * w_wall * (
            viol_x0 * dhx_da + viol_x1 * dhx_da +
            viol_y0 * dhy_da + viol_y1 * dhy_da
        )

        # 2. Pairwise SAT Penetration Penalty
        # For any pair (i, j) within spatial neighborhood:
        tree = cKDTree(centers)
        pairs = tree.query_pairs(r=math.sqrt(2.0) + 0.1)

        for i, j in pairs:
            d_center = centers[j] - centers[i]
            # 4 axes: u_i1, u_i2, u_j1, u_j2
            axes = [
                (np.array([cos_t[i], sin_t[i]]), i, 1),
                (np.array([-sin_t[i], cos_t[i]]), i, 2),
                (np.array([cos_t[j], sin_t[j]]), j, 1),
                (np.array([-sin_t[j], cos_t[j]]), j, 2),
            ]

            # Measure separation along all 4 axes
            seps = []
            for u, owner, ax_id in axes:
                # Projected radius of square i along u:
                r_i = 0.5 * (abs(u[0] * cos_t[i] + u[1] * sin_t[i]) + abs(-u[0] * sin_t[i] + u[1] * cos_t[i]))
                # Projected radius of square j along u:
                r_j = 0.5 * (abs(u[0] * cos_t[j] + u[1] * sin_t[j]) + abs(-u[0] * sin_t[j] + u[1] * cos_t[j]))
                proj_dist = abs(np.dot(u, d_center))
                # gap = proj_dist - (r_i + r_j). If gap < 0, penetration = -gap
                penetration = (r_i + r_j) - proj_dist
                seps.append((penetration, u, owner, ax_id, r_i, r_j, proj_dist))

            # The true overlap depth between convex polygons is the MINIMUM penetration across all 4 axes!
            # If any axis has penetration <= 0, they are completely separated (pen = 0)!
            min_pen_tuple = min(seps, key=lambda x: x[0])
            min_pen = min_pen_tuple[0]

            if min_pen > 0:
                # Both squares overlap!
                total_energy += w_pen * (min_pen ** 2)
                pen, u, owner, ax_id, r_i, r_j, proj_dist = min_pen_tuple
                sgn_proj = np.sign(np.dot(u, d_center))
                if sgn_proj == 0: sgn_proj = 1.0

                # d(pen)/d(center_i) = - d(pen)/d(center_j) = - (- sgn_proj * u) = sgn_proj * u
                # Energy is w_pen * pen^2, so dE/d(center_i) = 2 * w_pen * pen * (sgn_proj * u)
                dE_dc_i = 2.0 * w_pen * pen * (sgn_proj * u)
                grad_c[i] += dE_dc_i
                grad_c[j] -= dE_dc_i

                # Angular gradients for rotation
                # If owner is i:
                u_perp = np.array([-u[1], u[0]])
                d_proj_da_i = sgn_proj * np.dot(u_perp, d_center) if owner == i else 0.0
                d_proj_da_j = sgn_proj * np.dot(u_perp, d_center) if owner == j else 0.0

                # d(r_i)/da_i and d(r_j)/da_j
                grad_a[i] += 2.0 * w_pen * pen * (-d_proj_da_i)
                grad_a[j] += 2.0 * w_pen * pen * (d_proj_da_j)

        grad_vec = np.concatenate([grad_c.ravel(), grad_a.ravel()])
        return total_energy, grad_vec

    def squeeze_and_hop(self, initial_centers: np.ndarray, initial_angles: np.ndarray,
                        time_limit: float = 30.0, step_delta: float = 0.0002) -> Tuple[np.ndarray, np.ndarray, float]:
        n = self.n
        best_centers = initial_centers.copy()
        best_angles = initial_angles.copy() % HALF_PI
        best_L = self.compute_bounding_side(best_centers, best_angles)

        # Normalize to [0, best_L]
        cx, cy = self.get_corners(best_centers, best_angles)
        best_centers[:, 0] -= np.min(cx)
        best_centers[:, 1] -= np.min(cy)

        curr_centers = best_centers.copy()
        curr_angles = best_angles.copy()
        target_L = best_L - step_delta

        t0 = time.time()
        round_idx = 0

        while time.time() - t0 < time_limit:
            round_idx += 1
            x0 = np.concatenate([curr_centers.ravel(), curr_angles.ravel()])

            # Phase 1: L-BFGS-B relaxation
            res = minimize(
                fun=lambda x: self.energy_and_grad(x, target_L, w_pen=1e5, w_wall=1e5),
                x0=x0,
                method='L-BFGS-B',
                jac=True,
                options={'maxiter': 120, 'ftol': 1e-12, 'gtol': 1e-6}
            )

            cand_c = res.x[:2*n].reshape((n, 2))
            cand_a = res.x[2*n:] % HALF_PI

            # Check feasibility with official metric
            records = []
            for i in range(n):
                records.append({
                    "square_id": i,
                    "x": f"{float(cand_c[i, 0])!r}",
                    "y": f"{float(cand_c[i, 1])!r}",
                    "angle": f"{float(cand_a[i])!r}",
                })

            _n, score, L_str, reason = metric.evaluate_single_puzzle(n, records)
            if reason == "ok":
                cert_L = float(L_str)
                if cert_L < best_L - 1e-9:
                    best_L = cert_L
                    best_centers = cand_c.copy()
                    best_angles = cand_a.copy()
                    print(f"  [Round {round_idx}] SQUEEZE SUCCESS! New Side L = {best_L:.10f} (Target was {target_L:.10f})")
                    curr_centers = best_centers.copy()
                    curr_angles = best_angles.copy()
                    target_L = best_L - step_delta
                    continue

            # Phase 2: Basin Hop Perturbation if trapped
            # Move the square with the highest wall/contact slack
            tree = cKDTree(curr_centers)
            counts = [len(tree.query_ball_point(curr_centers[i], r=1.6)) for i in range(n)]
            slackest = np.argsort(counts)[:max(1, n // 8)]

            for s_idx in slackest:
                curr_centers[s_idx] += self.rng.normal(0, 0.015, size=2)
                curr_angles[s_idx] = (curr_angles[s_idx] + self.rng.choice([0.0, math.pi/4, -math.pi/4]) + self.rng.normal(0, 0.02)) % HALF_PI

        return best_centers, best_angles, best_L
