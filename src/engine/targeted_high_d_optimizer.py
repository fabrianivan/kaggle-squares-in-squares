"""Targeted optimizer for trivial D=36-61 puzzles.

These puzzles (K^2 + D where D in [36,61]) currently have trivial grid packings (L=K+1).
Strategy:
1. For each trivial puzzle n=K^2+D, find the nearest non-trivial puzzle for this K
   (the 'seed') which has L < K+1. Use that as a seed.
2. Add the extra D - D_seed squares to the packing.
3. Apply cpu_axis_reclosure + cpu_contact_polish to compress to L < K+1.
4. Also try two-angle initial configurations (theta1/theta2 search).
5. Certify any improvement with the official metric.

    .venv/bin/python src/engine/targeted_high_d_optimizer.py \
        --base output/submission_22.216100.csv \
        --workers 8 \
        --outdir output/high_d_wins \
        --seconds 120
"""
from __future__ import annotations
import argparse
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
TOOLS = ROOT / "src" / "tools"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "src" / "metric"))


def _side(p):
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    X = np.concatenate([p[:, 0] + c - s, p[:, 0] - c - s, p[:, 0] - c + s, p[:, 0] + c + s])
    Y = np.concatenate([p[:, 1] + s + c, p[:, 1] - s + c, p[:, 1] - s - c, p[:, 1] + s - c])
    return float(max(X.max() - X.min(), Y.max() - Y.min()))


def _normalize(p):
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xlo = (p[:, 0] - np.abs(c) - np.abs(s)).min()
    ylo = (p[:, 1] - np.abs(s) - np.abs(c)).min()
    p = p.copy()
    p[:, 0] -= xlo
    p[:, 1] -= ylo
    return p


def _grid_packing(n: int) -> np.ndarray:
    """Simple grid packing for n squares."""
    K = math.ceil(math.sqrt(n))
    return np.array([(i % K + 0.5, i // K + 0.5, 0.0) for i in range(n)], float)


def _two_angle_init(n: int, K: int, D: int, theta1: float, theta2: float,
                    seed: int = 0) -> np.ndarray:
    """Initialize n=K^2+D squares with two-angle pinwheel configuration."""
    rng = np.random.default_rng(seed)
    squares = []
    # Fill K rows x K cols with two angles alternating
    for i in range(K):
        for j in range(K):
            angle = theta1 if (i + j) % 2 == 0 else theta2
            squares.append([i + 0.5, j + 0.5, angle])
    # Add D extra squares in the upper-right region
    # Start from corner and work inward
    extra_angle = theta1
    for i in range(K, K + math.ceil(D / K) + 2):
        for j in range(K):
            if len(squares) >= n:
                break
            squares.append([i + 0.5, j + 0.5, extra_angle])
            extra_angle = theta2 if extra_angle == theta1 else theta1
        if len(squares) >= n:
            break
    p = np.array(squares[:n], float)
    # Small random perturbation to help optimizer escape symmetry
    p[:, :2] += rng.uniform(-0.02, 0.02, (n, 2))
    return p


def _extend_packing(base_sq: np.ndarray, n_target: int,
                    theta1: float = 0.0, theta2: float = math.pi / 4) -> np.ndarray:
    """Extend a base packing by adding extra squares near its boundary."""
    n_base = len(base_sq)
    n_add = n_target - n_base
    if n_add <= 0:
        return base_sq[:n_target]
    
    # Find the bounding box of existing packing
    t = base_sq[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xhi = (base_sq[:, 0] + np.abs(c) + np.abs(s)).max()
    yhi = (base_sq[:, 1] + np.abs(s) + np.abs(c)).max()
    
    # Place extra squares along the right and top edges
    extra = []
    angle = theta2
    # Try right edge first
    x_new = xhi + 0.6
    for j in range(n_add * 2):
        y_new = 0.5 + j
        if y_new < yhi + 1:
            extra.append([x_new, y_new, angle])
            angle = theta1 if angle == theta2 else theta2
    # Then top edge
    y_new = yhi + 0.6
    for i in range(n_add * 2):
        x_new2 = 0.5 + i
        if x_new2 < xhi + 1:
            extra.append([x_new2, y_new, angle])
            angle = theta1 if angle == theta2 else theta2
    
    extra = np.array(extra[:n_add], float)
    return np.concatenate([base_sq, extra], axis=0)


def optimize_one(job: tuple) -> tuple:
    """Optimize one puzzle. Returns (n, L0, L_best, best_sq) or (n, L0, L0, None)."""
    n, p_base, seconds, seed = job

    from cpu_axis_reclosure import reclose
    from cpu_contact_polish import polish
    from packing_geometry import repair

    L0 = _side(p_base)
    K = math.isqrt(n)
    target_L = float(K + 1) - 1e-9  # beat the trivial grid

    best_p = p_base.copy()
    best_L = L0
    deadline = time.perf_counter() + seconds
    D = n - K * K

    def try_optimize(p_init, seed_off=0):
        nonlocal best_p, best_L
        p = _normalize(p_init.copy())

        # Phase 1: axis reclosure with various trust params
        for trust, tie in [(0.22, 0.015), (0.40, 0.06), (0.55, 0.12), (0.70, 0.20)]:
            if time.perf_counter() > deadline:
                return
            try:
                q, _, _ = reclose(p, seed=seed + seed_off, trust=trust, tie=tie,
                                  rounds=8, seconds=min(4.0, deadline - time.perf_counter()))
            except Exception:
                continue
            L = _side(q)
            if L < best_L - 1e-12:
                best_L = L
                best_p = q.copy()
            if L < best_L + 0.1:
                p = q  # use as starting point for polish

        # Phase 2: contact polish
        if time.perf_counter() < deadline:
            try:
                q, _, _ = polish(p, seed=seed + seed_off + 5, rounds=80,
                                 max_seconds=min(10.0, deadline - time.perf_counter()))
                if repair(q, clearance=1.5e-9) is not None:
                    q = repair(q, clearance=1.5e-9)
                L = _side(q)
                if L < best_L - 1e-12:
                    best_L = L
                    best_p = q.copy()
            except Exception:
                pass

    # Try 1: start from provided base
    try_optimize(p_base, seed_off=0)

    # Try 2: two-angle inits with different angle pairs
    angle_pairs = [
        (math.radians(23.6), math.radians(28.7)),
        (math.radians(20.0), math.radians(30.0)),
        (math.radians(25.0), math.radians(35.0)),
        (math.radians(22.0), math.radians(27.0)),
        (math.radians(18.0), math.radians(26.0)),
    ]
    for i, (t1, t2) in enumerate(angle_pairs):
        if time.perf_counter() > deadline:
            break
        p_init = _two_angle_init(n, K, D, t1, t2, seed=seed + i * 100)
        try_optimize(p_init, seed_off=i + 1)

    if best_L >= target_L:
        return n, L0, best_L, None

    return n, L0, best_L, best_p


def certify_packing(n: int, sq: np.ndarray) -> float | None:
    """Certify a packing with the official metric. Returns certified L or None."""
    import metric
    rows = [{"n": str(n), "square_id": str(i), "x": repr(float(sq[i, 0])),
             "y": repr(float(sq[i, 1])), "angle": repr(float(sq[i, 2]))}
            for i in range(len(sq))]
    _, _, L, why = metric.evaluate_single_puzzle(n, rows)
    if why == "ok" and L is not None:
        return float(L)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "output" / "submission_22.216100.csv"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--outdir", default=str(ROOT / "output" / "high_d_wins"))
    ap.add_argument("--seconds", type=float, default=120.0,
                    help="seconds per puzzle")
    ap.add_argument("--nmin", type=int, default=1)
    ap.add_argument("--nmax", type=int, default=1000)
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load base submission
    df = pd.read_csv(a.base)
    df["n"] = df["n"].astype(int)
    bank = {}
    for n_val, g in df.groupby("n"):
        n = int(n_val)
        bank[n] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    # Find trivial puzzles in D=36-61 range
    targets = []
    for n in range(a.nmin, min(a.nmax + 1, 1001)):
        K = math.isqrt(n)
        D = n - K * K
        if D < 36 or D > 61:
            continue
        if n not in bank:
            bank[n] = _grid_packing(n)
        L = _side(bank[n])
        if L >= K + 1 - 1e-9:  # trivial
            targets.append(n)

    print(f"Trivial D=36-61 targets: {len(targets)}", flush=True)
    if not targets:
        print("Nothing to do!", flush=True)
        return

    # Sort by K (smaller K first, easier to crack)
    targets.sort(key=lambda n: math.isqrt(n))

    # Build jobs
    jobs = [(n, bank[n], a.seconds, n * 17) for n in targets]

    t0 = time.time()
    wins = 0
    total_gain = 0.0

    print(f"Running {len(jobs)} jobs on {a.workers} workers...", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(optimize_one, job): job[0] for job in jobs}
        for fut in as_completed(futures):
            n_val = futures[fut]
            try:
                n, L0, L_best, sq = fut.result()
            except Exception as e:
                print(f"  n={n_val}: ERROR {e}", flush=True)
                continue

            if sq is not None and L_best < L0 - 1e-9:
                # Certify
                L_cert = certify_packing(n, sq)
                if L_cert is not None and L_cert < L0 - 1e-9:
                    gain = (L0 - L_cert) / math.sqrt(n)
                    total_gain += gain
                    wins += 1
                    # Write win CSV
                    with open(outdir / f"{n}.csv", "w") as fh:
                        fh.write("n,square_id,x,y,angle\n")
                        for i, (x, y, t) in enumerate(sq):
                            fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
                    print(f"  WIN n={n}: {L0:.6f} -> {L_cert:.6f} (gain {gain:.4e}) "
                          f"[total {total_gain:.6f}]", flush=True)
                else:
                    print(f"  n={n}: local {L_best:.6f} but cert failed/no improvement "
                          f"(L0={L0:.6f})", flush=True)
            else:
                pass  # Stay silent on no improvement

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s: {wins}/{len(targets)} wins, "
          f"total gain {total_gain:.6f}", flush=True)


if __name__ == "__main__":
    main()
