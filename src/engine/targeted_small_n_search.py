"""Targeted Small-to-Medium N Optimization using Original First-Principles Solver.

Focuses on high-impact puzzles where 1/sqrt(n) is largest (n in 11..100).
Applies multi-axis SAT LP, continuous penalty relaxation, and rotation sweeps.
Every improvement is verified with official interval arithmetic (reason == 'ok').
"""

import os
import sys
import time
import math
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orig_packing_solver import PackingState, ContinuousPenaltyRelaxer, MultiAxisContactLPSolver

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

HALF_PI = math.pi / 2.0


def load_puzzle(submission_path: str, n: int) -> PackingState:
    df = pd.read_csv(submission_path)
    sub = df[df['n'] == n].copy()
    sub['square_id'] = sub['square_id'].astype(int)
    sub = sub.sort_values('square_id')
    centers = sub[['x', 'y']].values.astype(np.float64)
    angles = sub['angle'].values.astype(np.float64)
    state = PackingState(n, centers, angles)
    v, _, _ = state.certify_official()
    if not v:
        state.normalize_to_box()
    return state


def optimize_puzzle_deep(state: PackingState, time_budget: float = 30.0, seed: int = 42) -> PackingState:
    best_state = state.copy()
    valid0, L_cert0, reason0 = state.certify_official()
    best_L = L_cert0 if valid0 else state.s

    lp_solver = MultiAxisContactLPSolver(guard_buffer=1e-11, trust_pos=0.03, trust_ang=0.05)
    rng = np.random.default_rng(seed)

    # 1. First attempt: Direct Contact LP contraction
    curr = state.copy()
    for _ in range(25):
        nxt = lp_solver.optimize_step(curr)
        if nxt is not None and nxt.s < curr.s - 1e-11:
            curr = nxt
            v, cL, r = curr.certify_official()
            if v and cL < best_L - 1e-11:
                best_L = cL
                best_state = curr.copy()
        else:
            break

    t0 = time.time()
    round_idx = 0

    while time.time() - t0 < time_budget:
        round_idx += 1

        # Determine target contraction
        step_delta = 0.0002 * (1.0 + (round_idx % 4) * 0.5)
        target_L = best_state.s - step_delta

        # Perturbation: select random subset of squares (slack or boundary)
        p = best_state.centers.copy()
        a = best_state.angles.copy()

        # Mode A: Subtle shake on angles
        if round_idx % 3 == 0:
            a += rng.normal(0, 0.02, size=state.n)
        # Mode B: Shake positions of 20% loose squares
        elif round_idx % 3 == 1:
            indices = rng.choice(state.n, size=max(2, state.n // 5), replace=False)
            p[indices] += rng.normal(0, 0.015, size=(len(indices), 2))
            a[indices] += rng.normal(0, 0.04, size=len(indices))
        # Mode C: Corner/boundary compress
        else:
            hx, hy = best_state.compute_extents()
            near_wall = (
                (p[:, 0] - hx < 0.1) |
                (best_state.s - (p[:, 0] + hx) < 0.1) |
                (p[:, 1] - hy < 0.1) |
                (best_state.s - (p[:, 1] + hy) < 0.1)
            )
            wall_indices = np.where(near_wall)[0]
            if len(wall_indices) > 0:
                pick = rng.choice(wall_indices, size=min(len(wall_indices), max(1, len(wall_indices) // 3)), replace=False)
                a[pick] = (a[pick] + rng.choice([0.0, math.pi/4, math.pi/8, -math.pi/8]) + rng.normal(0, 0.01, size=len(pick))) % HALF_PI

        perturbed = PackingState(state.n, p, a)
        perturbed.normalize_to_box()

        # Differentiable Penalty Relaxation
        relaxer = ContinuousPenaltyRelaxer(state.n, target_side=target_L, overlap_weight=1e6)
        relaxed = relaxer.relax(perturbed, max_iter=70)

        # Contact LP squeeze
        squeezed = relaxed
        for _ in range(15):
            nxt = lp_solver.optimize_step(squeezed)
            if nxt is not None and nxt.s < squeezed.s - 1e-11:
                squeezed = nxt
            else:
                break

        # Check official certification
        valid, cert_L, reason = squeezed.certify_official()
        if valid and cert_L < best_L - 1e-11:
            print(f"  [+] IMPROVEMENT round {round_idx}: L {best_L:.9f} -> {cert_L:.9f} (dL = {best_L - cert_L:.2e})")
            best_L = cert_L
            best_state = squeezed.copy()

    return best_state


def main():
    target_puzzles = [11, 18, 19, 26, 27, 28, 29, 37, 38, 39, 41, 51, 55, 68, 70, 71, 85, 86, 87]
    base_csv = os.path.join(ROOT, "data/submission_best.csv")
    out_dir = os.path.join(ROOT, "tmp/orig_improvements")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Starting targeted search on {len(target_puzzles)} high-impact puzzles...")
    total_gain = 0.0
    improvements = []

    for n in target_puzzles:
        state0 = load_puzzle(base_csv, n)
        v0, L0, r0 = state0.certify_official()
        print(f"\n--- Puzzle n={n} (weight = {1.0/math.sqrt(n):.4f}) Starting L0={L0:.9f} ---")

        opt_state = optimize_puzzle_deep(state0, time_budget=15.0, seed=n * 1337)
        v1, L1, r1 = opt_state.certify_official()

        if v1 and L1 < L0 - 1e-11:
            gain = (L0 - L1) / math.sqrt(n)
            total_gain += gain
            improvements.append((n, L0, L1, gain))
            print(f"*** CONFIRMED GAIN for n={n}: {L0:.9f} -> {L1:.9f} (gain: {gain:.2e}) ***")

            # Save puzzle CSV
            out_file = os.path.join(out_dir, f"{n}.csv")
            with open(out_file, "w") as f:
                f.write("n,square_id,x,y,angle\n")
                for i in range(n):
                    f.write(f"{n},{i},{float(opt_state.centers[i, 0])!r},{float(opt_state.centers[i, 1])!r},{float(opt_state.angles[i])!r}\n")
        else:
            print(f"Puzzle n={n}: no improvement found (best L={L1:.9f})")

    print(f"\n==========================================")
    print(f"Targeted search completed. Total verified gain: {total_gain:.8e}")
    print(f"Puzzles improved: {[x[0] for x in improvements]}")


if __name__ == "__main__":
    main()
