"""Seed-extension optimizer: improve puzzles by using n-1 as a warm-start.

Novel strategy: for each puzzle n, the best known packing for n-1 squares is a
near-feasible warm start — we just need to fit one more square. We try inserting
the extra square at many candidate positions (voids, boundary, and random), then
optimize with reclose + polish.

This is structurally different from the existing approaches:
- Not random init (uses the best known n-1 packing)
- Not gadget DP (direct coordinate optimization)
- Not whole-packing quench (targeted insertion + local opt)

Also tries: take the n+1 packing and remove the worst-fitting square (inverse),
giving a different warm start.

Usage:
    .venv/bin/python -u src/engine/seed_extension_optimizer.py \\
        --base output/submission_22.206715.csv \\
        --workers 8 --seconds 90 \\
        --outdir output/seed_ext_wins
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
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "kirilltym"))
sys.path.insert(0, str(ROOT / "data" / "latest_sync_1900" / "kirilltym"))
sys.path.insert(0, str(ROOT / "src" / "metric"))


def _side(p: np.ndarray) -> float:
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    X = np.concatenate([p[:, 0] + c - s, p[:, 0] - c - s, p[:, 0] - c + s, p[:, 0] + c + s])
    Y = np.concatenate([p[:, 1] + s + c, p[:, 1] - s + c, p[:, 1] - s - c, p[:, 1] + s - c])
    return float(max(X.max() - X.min(), Y.max() - Y.min()))


def _normalize(p: np.ndarray) -> np.ndarray:
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xlo = (p[:, 0] - np.abs(c) - np.abs(s)).min()
    ylo = (p[:, 1] - np.abs(s) - np.abs(c)).min()
    p = p.copy()
    p[:, 0] -= xlo
    p[:, 1] -= ylo
    return p


def _find_void_positions(p: np.ndarray, n_candidates: int = 20, seed: int = 0) -> list:
    """Find candidate positions for inserting a new square into existing packing.

    Strategy 1: grid scan of the bounding box, pick top void positions.
    Strategy 2: positions near existing squares' boundaries.
    Strategy 3: random positions within bounding box.
    """
    rng = np.random.default_rng(seed)
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xlo = (p[:, 0] - np.abs(c) - np.abs(s)).min()
    xhi = (p[:, 0] + np.abs(c) + np.abs(s)).max()
    ylo = (p[:, 1] - np.abs(s) - np.abs(c)).min()
    yhi = (p[:, 1] + np.abs(s) + np.abs(c)).max()

    L = max(xhi - xlo, yhi - ylo)
    candidates = []

    # Strategy 1: grid scan for voids
    # Place centers of potential new square on a fine grid, check overlap
    grid_step = max(0.5, L / 15.0)
    for gx in np.arange(xlo + 0.5, xhi + 1.5, grid_step):
        for gy in np.arange(ylo + 0.5, yhi + 1.5, grid_step):
            # Check distance to nearest existing square center
            dists = np.sqrt((p[:, 0] - gx)**2 + (p[:, 1] - gy)**2)
            if dists.min() > 0.9:  # likely a void
                candidates.append((gx, gy))

    # Strategy 2: near existing square boundaries (offset by ~1 unit)
    for i in range(len(p)):
        for dx, dy in [(1.05, 0), (0, 1.05), (-1.05, 0), (0, -1.05),
                        (0.75, 0.75), (-0.75, 0.75), (0.75, -0.75), (-0.75, -0.75)]:
            nx, ny = p[i, 0] + dx, p[i, 1] + dy
            dists = np.sqrt((p[:, 0] - nx)**2 + (p[:, 1] - ny)**2)
            if dists.min() > 0.85:
                candidates.append((nx, ny))

    # Strategy 3: random positions
    for _ in range(n_candidates):
        rx = rng.uniform(xlo, xhi + 1.0)
        ry = rng.uniform(ylo, yhi + 1.0)
        dists = np.sqrt((p[:, 0] - rx)**2 + (p[:, 1] - ry)**2)
        if dists.min() > 0.85:
            candidates.append((rx, ry))

    return candidates[:n_candidates * 3]


def _insert_square(p: np.ndarray, x: float, y: float, angle: float) -> np.ndarray:
    """Insert a new square at (x, y, angle) into packing p."""
    new_sq = np.array([[x, y, angle]], float)
    return np.concatenate([p, new_sq], axis=0)


def optimize_one(job: tuple) -> tuple:
    """Optimize one puzzle using seed-extension. Returns (n, L0, L_best, best_sq) or (n, L0, L0, None)."""
    n, p_seed, L_target, seconds, seed = job

    try:
        from cpu_axis_reclosure import reclose
        from cpu_contact_polish import polish
    except ImportError:
        return n, _side(p_seed), _side(p_seed), None

    import metric as M

    rng = np.random.default_rng(seed)
    deadline = time.perf_counter() + seconds
    best_p = None
    best_L = L_target  # only keep improvements below this

    def try_packing(p_init: np.ndarray, seed_off: int = 0) -> float:
        nonlocal best_p, best_L
        p = _normalize(p_init.copy())
        cur_L = _side(p)

        # Phase 1: fast axis reclosure
        for trust, tie, rnds in [(0.22, 0.015, 6), (0.40, 0.06, 6)]:
            if time.perf_counter() > deadline:
                return cur_L
            try:
                q_tup = reclose(p, seed=seed + seed_off, trust=trust, tie=tie,
                                rounds=rnds, seconds=min(5.0, deadline - time.perf_counter()))
                q = q_tup[0] if isinstance(q_tup, tuple) else q_tup
            except Exception:
                continue
            L = _side(q)
            if L < best_L - 1e-9:
                best_L = L
                best_p = q.copy()
            if L < cur_L:
                p = q
                cur_L = L

        # Phase 2: contact polish
        if time.perf_counter() < deadline:
            try:
                q_tup = polish(p, rounds=60, seed=seed + seed_off + 50,
                               max_seconds=min(8.0, deadline - time.perf_counter()))
                q = q_tup[0] if isinstance(q_tup, tuple) else q_tup
                L = _side(q)
                if L < best_L - 1e-9:
                    best_L = L
                    best_p = q.copy()
                if L < cur_L:
                    p = q
                    cur_L = L
            except Exception:
                pass

        return cur_L

    # Insert extra square at candidate positions with various angles
    candidate_positions = _find_void_positions(p_seed[:-1] if len(p_seed) > 1 else p_seed,
                                               n_candidates=25, seed=seed)

    angles_to_try = [0.0, math.pi / 4, math.radians(23.6), math.radians(28.7),
                     math.radians(15.0), math.radians(35.0)]

    off = 0
    for x, y in candidate_positions:
        if time.perf_counter() > deadline:
            break
        for angle in angles_to_try:
            if time.perf_counter() > deadline:
                break
            p_init = _insert_square(p_seed, x, y, angle)
            try_packing(p_init, seed_off=off)
            off += 1

    # Also try: start from the full n-packing with random perturbations
    for _ in range(5):
        if time.perf_counter() > deadline:
            break
        p_perturbed = p_seed.copy()
        p_perturbed[:, :2] += rng.normal(0, 0.05, (len(p_seed), 2))
        p_perturbed[:, 2] += rng.normal(0, 0.05, len(p_seed))
        try_packing(p_perturbed, seed_off=off)
        off += 1

    if best_p is None:
        return n, L_target, L_target, None

    # Certify
    rows = [{"n": str(n), "square_id": str(i),
             "x": repr(float(best_p[i, 0])),
             "y": repr(float(best_p[i, 1])),
             "angle": repr(float(best_p[i, 2]))}
            for i in range(n)]
    _, _, L_str, why = M.evaluate_single_puzzle(n, rows)
    if why != "ok" or L_str is None:
        return n, L_target, L_target, None
    L_cert = float(L_str)
    if L_cert >= L_target - 1e-9:
        return n, L_target, L_target, None
    return n, L_target, L_cert, best_p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "output" / "submission_22.206715.csv"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--outdir", default=str(ROOT / "output" / "seed_ext_wins"))
    ap.add_argument("--seconds", type=float, default=90.0, help="seconds per puzzle")
    ap.add_argument("--nmin", type=int, default=2)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--max_puzzles", type=int, default=200,
                    help="max number of puzzles to try (highest leverage first)")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load base submission
    df = pd.read_csv(a.base)
    df["n"] = df["n"].astype(int)
    bank: dict[int, np.ndarray] = {}
    for n_val, g in df.groupby("n"):
        bank[int(n_val)] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    # Identify target puzzles and score them by leverage
    # A puzzle is a good target if:
    # 1. n-1 is in the bank (we have a warm start)
    # 2. Current L is close to K+1 (near-trivial, high improvement potential)
    # Weight = improvement_potential * score_weight = (gap_to_trivial_or_1) / sqrt(n)
    targets = []
    for n in range(max(2, a.nmin), min(a.nmax + 1, 1001)):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        if n not in bank:
            continue
        L_cur = _side(bank[n])
        # Score weight
        w = 1.0 / math.sqrt(n)
        trivial = float(K + 1)
        gap_to_trivial = trivial - L_cur

        # Only include if n-1 is in the bank AND is sub-grid (non-trivial)
        # Seed-extension only gives a good warm start when n-1 is already compact
        if n - 1 not in bank:
            continue
        L_seed = _side(bank[n - 1])
        K_seed = math.isqrt(n - 1)
        if L_seed >= K_seed + 1 - 1e-6:
            continue  # n-1 is trivial, no useful warm start

        # Priority: high weight × how poor the current packing is
        if D >= 1 and L_cur > K + 0.5:
            priority = w * (1.0 - gap_to_trivial / max(trivial - K, 0.01))
            targets.append((n, K, D, L_cur, gap_to_trivial, priority))

    # Sort by priority (highest leverage first)
    targets.sort(key=lambda x: -x[5])
    targets = targets[:a.max_puzzles]

    print(f"Target puzzles: {len(targets)} (max {a.max_puzzles})", flush=True)
    for n, K, D, L, gap, pri in targets[:10]:
        print(f"  n={n} K={K} D={D} L={L:.6f} gap={gap:.4f} priority={pri:.4f}", flush=True)

    # Build jobs — use n-1 packing as seed where available, else use current packing
    jobs = []
    for n, K, D, L_cur, gap, pri in targets:
        if n - 1 in bank:
            # Extend the n-1 packing
            seed_packing = bank[n - 1]
            # We need to add 1 square — _find_void_positions will handle placement
            # Pass the n-1 packing; optimize_one will search for where to insert
        else:
            seed_packing = bank[n]
        jobs.append((n, seed_packing, L_cur, a.seconds, n * 31 + 7))

    t0 = time.time()
    wins = 0
    total_gain = 0.0

    print(f"\nRunning {len(jobs)} jobs on {a.workers} workers...", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(optimize_one, job): job[0] for job in jobs}
        for fut in as_completed(futures):
            n_val = futures[fut]
            try:
                n, L0, L_cert, sq = fut.result()
            except Exception as e:
                print(f"  n={n_val}: ERROR {e}", flush=True)
                continue

            if sq is not None and L_cert < L0 - 1e-9:
                gain = (L0 - L_cert) / math.sqrt(n)
                total_gain += gain
                wins += 1
                # Write win CSV
                with open(outdir / f"{n}.csv", "w") as fh:
                    fh.write("n,square_id,x,y,angle\n")
                    for i in range(n):
                        fh.write(f"{n},{i},{float(sq[i,0])!r},{float(sq[i,1])!r},{float(sq[i,2])!r}\n")
                print(f"  WIN n={n}: {L0:.8f} -> {L_cert:.8f} (gain {gain:.4e}) "
                      f"[total {total_gain:.6f}]", flush=True)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s: {wins}/{len(targets)} wins, "
          f"total gain {total_gain:.6f}", flush=True)


if __name__ == "__main__":
    main()
