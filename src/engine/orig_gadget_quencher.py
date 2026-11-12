"""Original Gadget Quencher & Overhang Squeezer.

Authored from first principles for Kaggle 'Squares in Squares'.
Formulates the gadget overhang minimization problem:
    min f
    s.t. squares are non-overlapping (exact SAT) and contained in [0, w + f] x [0, h + f].
Uses Sequential Linear Programming (SLP) with exact analytical SAT Jacobians and kink subgradients.
"""

from __future__ import annotations
import math
import time
from typing import Tuple, List, Optional, Dict
import numpy as np
from scipy.optimize import linprog
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix

HALF_PI = math.pi / 2.0

class OriginalGadgetQuencher:
    def __init__(self, w: int, h: int, guard_buffer: float = 1e-11, trust_pos: float = 0.015, trust_ang: float = 0.03):
        self.w = w
        self.h = h
        self.guard = guard_buffer
        self.trust_pos = trust_pos
        self.trust_ang = trust_ang

    @staticmethod
    def compute_bounds(centers: np.ndarray, angles: np.ndarray):
        c = np.cos(angles) * 0.5
        s = np.sin(angles) * 0.5
        x, y = centers[:, 0], centers[:, 1]
        cx = np.array([x + c - s, x - c - s, x - c + s, x + c + s])
        cy = np.array([y + s + c, y - s + c, y - s - c, y + s - c])
        xlo, xhi = np.min(cx, axis=0), np.max(cx, axis=0)
        ylo, yhi = np.min(cy, axis=0), np.max(cy, axis=0)
        return xlo, xhi, ylo, yhi

    def compute_overhang(self, centers: np.ndarray, angles: np.ndarray) -> float:
        xlo, xhi, ylo, yhi = self.compute_bounds(centers, angles)
        w_span = float(np.max(xhi) - np.min(xlo))
        h_span = float(np.max(yhi) - np.min(ylo))
        return max(w_span - self.w, h_span - self.h, 0.0)

    def optimize_step(self, centers: np.ndarray, angles: np.ndarray, f_curr: float, contract_only: bool = True) -> Optional[Tuple[np.ndarray, np.ndarray, float, float]]:
        n = len(centers)
        p = centers.copy()
        theta = angles.copy() % HALF_PI

        # Normalize gadget to origin
        xlo, xhi, ylo, yhi = self.compute_bounds(p, theta)
        p[:, 0] -= np.min(xlo)
        p[:, 1] -= np.min(ylo)

        tree = cKDTree(p)
        pairs = list(tree.query_pairs(r=2.0))

        # Variables: dx_i, dy_i, dth_i for each square (3n), plus df (1 var)
        num_vars = 3 * n + 1
        c_obj = np.zeros(num_vars)
        c_obj[-1] = 1.0  # minimize df

        bounds = []
        for i in range(n):
            bounds.append((-self.trust_pos, self.trust_pos))
            bounds.append((-self.trust_pos, self.trust_pos))
            bounds.append((-self.trust_ang, self.trust_ang))
        if contract_only:
            bounds.append((-self.trust_pos * 2.0, 0.0))  # df <= 0 (contraction only)
        else:
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

        # 1. Exact Multi-Axis SAT Contact Constraints
        for i, j in pairs:
            d = p[j] - p[i]
            a1, a2 = theta[i], theta[j]
            c1, s1 = math.cos(a1), math.sin(a1)
            c2, s2 = math.cos(a2), math.sin(a2)

            normals = [
                (np.array([c1, s1]), True, 0),
                (np.array([-s1, c1]), True, 1),
                (np.array([c2, s2]), False, 0),
                (np.array([-s2, c2]), False, 1)
            ]

            d_th = a2 - a1
            cd = math.cos(d_th)
            sd = math.sin(d_th)
            rad = 0.5 * (1.0 + abs(cd) + abs(sd))

            axis_gaps = []
            for u, is_i, ax_idx in normals:
                proj = float(np.dot(d, u))
                gap = abs(proj) - rad
                axis_gaps.append((gap, u, is_i, ax_idx, proj))

            # The true separating axis is the one with the MAXIMUM gap!
            max_gap = max(g[0] for g in axis_gaps)
            if max_gap > 0.15:
                continue  # Not in close contact

            for gap, u, is_i, ax_idx, proj in axis_gaps:
                if gap >= max_gap - 1e-3:
                    sign = 1.0 if proj >= 0 else -1.0
                    nx, ny = u[0], u[1]

                    d_rad_ddth = 0.5 * (-math.sin(d_th) * np.sign(cd) + math.cos(d_th) * np.sign(sd))
                    if is_i:
                        u_perp = np.array([-s1, c1]) if ax_idx == 0 else np.array([-c1, -s1])
                        dgap_da1 = sign * float(np.dot(d, u_perp)) + d_rad_ddth
                        dgap_da2 = -d_rad_ddth
                    else:
                        u_perp = np.array([-s2, c2]) if ax_idx == 0 else np.array([-c2, -s2])
                        dgap_da1 = -d_rad_ddth
                        dgap_da2 = sign * float(np.dot(d, u_perp)) + d_rad_ddth

                    r_dict = {
                        3 * i: sign * nx,
                        3 * i + 1: sign * ny,
                        3 * j: -sign * nx,
                        3 * j + 1: -sign * ny,
                        3 * i + 2: -dgap_da1,
                        3 * j + 2: -dgap_da2
                    }
                    add_constraint(r_dict, gap - self.guard)

                    # Kink subgradients at orthogonal / diagonal alignments
                    if min(abs(cd), abs(sd)) < 1e-4:
                        for slope in [-0.5, 0.5]:
                            if is_i:
                                k_da1 = sign * float(np.dot(d, u_perp)) + slope
                                k_da2 = -slope
                            else:
                                k_da1 = -slope
                                k_da2 = sign * float(np.dot(d, u_perp)) + slope
                            r_kink = r_dict.copy()
                            r_kink[3 * i + 2] = -k_da1
                            r_kink[3 * j + 2] = -k_da2
                            add_constraint(r_kink, gap - self.guard)

        # 2. Wall Constraints for Rectangle [0, w + f] x [0, h + f]
        c = np.cos(theta)
        s = np.sin(theta)
        hx = 0.5 * (np.abs(c) + np.abs(s))
        hy = 0.5 * (np.abs(s) + np.abs(c))
        dhx = 0.5 * (-s * np.sign(c) + c * np.sign(s))
        dhy = 0.5 * (c * np.sign(s) - s * np.sign(c))

        W_target = self.w + f_curr
        H_target = self.h + f_curr

        for i in range(n):
            # Left wall: x_i - hx >= 0  =>  -dx - dhx*dth <= x_i - hx
            add_constraint({3 * i: -1.0, 3 * i + 2: dhx[i]}, p[i, 0] - hx[i])
            # Right wall: x_i + hx <= W + df  =>  dx + dhx*dth - df <= W - (x_i + hx)
            add_constraint({3 * i: 1.0, 3 * i + 2: dhx[i], num_vars - 1: -1.0}, W_target - (p[i, 0] + hx[i]))
            # Bottom wall: y_i - hy >= 0  =>  -dy - dhy*dth <= y_i - hy
            add_constraint({3 * i + 1: -1.0, 3 * i + 2: dhy[i]}, p[i, 1] - hy[i])
            # Top wall: y_i + hy <= H + df  =>  dy + dhy*dth - df <= H - (y_i + hy)
            add_constraint({3 * i + 1: 1.0, 3 * i + 2: dhy[i], num_vars - 1: -1.0}, H_target - (p[i, 1] + hy[i]))

        if curr_row == 0:
            return None

        # Add elastic L1 penalty slack variables
        total_vars = num_vars + curr_row
        c_obj_elastic = np.zeros(total_vars)
        c_obj_elastic[num_vars - 1] = 1.0  # df
        c_obj_elastic[num_vars:] = 1e5  # penalty on constraint violations

        elastic_bounds = list(bounds)
        for k in range(curr_row):
            elastic_bounds.append((0.0, None))
            row_indices.append(k)
            col_indices.append(num_vars + k)
            val_entries.append(-1.0)

        A_ub = coo_matrix((val_entries, (row_indices, col_indices)), shape=(curr_row, total_vars)).tocsc()
        b_ub = np.array(b_vals)

        res = linprog(c_obj_elastic, A_ub=A_ub, b_ub=b_ub, bounds=elastic_bounds, method='highs')
        if not res.success:
            return None

        delta = res.x[:num_vars]
        slacks = res.x[num_vars:]
        max_slack = float(np.max(slacks)) if len(slacks) > 0 else 0.0

        new_centers = p.copy()
        new_angles = theta.copy()
        for i in range(n):
            new_centers[i, 0] += delta[3 * i]
            new_centers[i, 1] += delta[3 * i + 1]
            new_angles[i] += delta[3 * i + 2]

        new_f = self.compute_overhang(new_centers, new_angles)
        return new_centers, new_angles, new_f, max_slack

    def quench(self, initial_centers: np.ndarray, initial_angles: np.ndarray, max_rounds: int = 35) -> Tuple[np.ndarray, np.ndarray, float, bool]:
        curr_c = initial_centers.copy()
        curr_a = initial_angles.copy()
        f_best = self.compute_overhang(curr_c, curr_a)
        best_feasible_c = curr_c.copy()
        best_feasible_a = curr_a.copy()
        found_feasible = False

        # Phase 1: Relax and settle contact topology
        for _ in range(max(1, max_rounds // 2)):
            res = self.optimize_step(curr_c, curr_a, f_best, contract_only=False)
            if res is None:
                break
            new_c, new_a, new_f, max_slack = res
            curr_c, curr_a = new_c, new_a
            if max_slack < 1e-11:
                found_feasible = True
                f_best = min(f_best, new_f)

        # Phase 2: Strictly contract walls
        for _ in range(max(1, max_rounds // 2)):
            res = self.optimize_step(curr_c, curr_a, f_best, contract_only=True)
            if res is None:
                break
            new_c, new_a, new_f, max_slack = res
            curr_c, curr_a = new_c, new_a

            if max_slack < 1e-11:
                found_feasible = True
                if new_f <= f_best:
                    f_best = new_f
                    best_feasible_c = curr_c.copy()
                    best_feasible_a = curr_a.copy()

        return best_feasible_c, best_feasible_a, f_best, found_feasible

    def quench_with_hops(self, initial_centers: np.ndarray, initial_angles: np.ndarray,
                         time_budget: float = 30.0, seed: int = 42) -> Tuple[np.ndarray, np.ndarray, float]:
        """Loosen-and-kick basin hopping with exact SLP contact squeezing."""
        rng = np.random.default_rng(seed)
        best_c, best_a, best_f, feasible = self.quench(initial_centers, initial_angles, max_rounds=25)
        f_start = best_f

        t0 = time.time()
        k = 0
        while time.time() - t0 < time_budget:
            k += 1
            cand_c = best_c.copy()
            cand_a = best_a.copy()

            # Loosen and kick
            loosen = 1.0 + 0.005 * ((k % 3) + 1)
            mean_c = np.mean(cand_c, axis=0)
            cand_c = mean_c + (cand_c - mean_c) * loosen
            cand_c += rng.normal(0, 0.004 * ((k % 2) + 1), size=cand_c.shape)
            cand_a = (cand_a + rng.normal(0, 0.01 * ((k % 2) + 1), size=len(cand_a))) % HALF_PI

            res_c, res_a, f_cand, is_feas = self.quench(cand_c, cand_a, max_rounds=25)
            if is_feas and f_cand < best_f - 1e-11:
                print(f"  >>> GADGET OVERHANG IMPROVED! Round {k}: f={f_cand:.8f} (Gain={f_start - f_cand:.6e})")
                best_c, best_a, best_f = res_c, res_a, f_cand

        return best_c, best_a, best_f
