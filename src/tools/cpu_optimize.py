"""CPU local-search optimizer for the Squares-in-Squares packings.

For each target puzzle, runs a cascade of trust-region LP searches (axis
re-closure + free-angle contact polish) plus optimal global rotation, across
several random seeds, and keeps the tightest feasible result.

Wins are written as a per-puzzle ``.npz`` patch (key = str(n), value = (n,3)
float64 array) that can be folded into the union submission via
``portfolio_union.build_portfolio(patch_path=...)``.

All certification uses the pinned official metric (interval SAT), so only
provably-feasible improvements are kept.

Usage (run from workspace root):
    python src/tools/cpu_optimize.py --seconds 480 --workers 6
"""

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "reference_sources"))

import numpy as np  # noqa: E402
import packing_geometry as pg  # noqa: E402
import cpu_axis_reclosure as reclose_mod  # noqa: E402
import cpu_contact_polish as polish_mod  # noqa: E402

BASE = TOOLS.parent.parent


def grid(n):
    k = math.ceil(math.sqrt(n))
    return np.array([(i % k + 0.5, i // k + 0.5, 0.0) for i in range(n)])


def side(p):
    return pg.side(p)


def optimize_one(job):
    """One optimization job. Returns (n, L0, L_best, q) where q is None if no win."""
    n, p_base, seed, seconds = job
    L0 = side(p_base)
    best_q = None
    best_L = L0
    deadline = time.perf_counter() + seconds

    # --- Strategy 1: cascade reclose (varying trust/tie) then polish -----------
    for trust, tie in [(0.22, 0.015), (0.4, 0.06), (0.55, 0.12), (0.7, 0.2)]:
        if time.perf_counter() > deadline:
            break
        q, _, _ = reclose_mod.reclose(
            p_base, seed=seed, trust=trust, tie=tie,
            rounds=8, seconds=min(3.0, max(0.5, deadline - time.perf_counter())),
        )
        if side(q) < best_L - 1e-9:
            best_q, best_L = q, side(q)
        # polish the reclose result
        q, _, _ = polish_mod.polish(
            q, seed=seed + 7, rounds=45, max_seconds=2.5,
            trust_start=0.02, regularization=0.0,
        )
        q = pg.repair(q, clearance=1.5e-9)
        if q is not None and side(q) < best_L - 1e-9:
            best_q, best_L = q, side(q)

    # --- Strategy 2: perturbation + polish (escape local minima) ---------------
    rng = np.random.default_rng(seed + 31)
    for trial in range(4):
        if time.perf_counter() > deadline:
            break
        pp = p_base.copy()
        sc = 0.02 * (1.0 - 0.18 * trial)
        pp[:, 0] += rng.normal(0, sc, n)
        pp[:, 1] += rng.normal(0, sc, n)
        pp[:, 2] += rng.normal(0, sc * 0.3, n)
        pp = pg.normalize(pp)
        q, _, _ = polish_mod.polish(
            pp, seed=seed + 100 + trial, rounds=45, max_seconds=2.0,
            trust_start=0.03, regularization=0.0,
        )
        q = pg.repair(q, clearance=1.5e-9)
        if q is not None and side(q) < best_L - 1e-9:
            best_q, best_L = q, side(q)

    # --- Strategy 3: optimal global rotation on the best so far ---------------
    if best_q is not None and best_L < L0 - 1e-9:
        try:
            q_rot, _ = pg.optimal_rotation(best_q)
            if side(q_rot) < best_L - 1e-9:
                best_q, best_L = q_rot, side(q_rot)
        except Exception:
            pass

    return n, L0, best_L, best_q


def certify(n, q):
    """Return certified L (mpmath) or None if infeasible, via the pinned metric."""
    import official_metric as metric
    rows = [
        {
            "n": str(n), "square_id": str(i),
            "x": format(float(q[i, 0]), ".17g"),
            "y": format(float(q[i, 1]), ".17g"),
            "angle": format(float(q[i, 2]), ".17g"),
        }
        for i in range(len(q))
    ]
    _, _score, L_text, reason = metric.evaluate_single_puzzle(n, rows)
    return float(L_text) if reason == "ok" and L_text is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=str(BASE / "output" / "submission_union.csv"))
    ap.add_argument("--patch-out", default=str(BASE / "output" / "cpu_patch.npz"))
    ap.add_argument("--seconds", type=float, default=480.0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--per-puzzle-seconds", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=400)
    args = ap.parse_args()

    print(f"Loading baseline bank: {args.baseline}")
    import pandas as pd
    bank = {n: grid(n) for n in range(1, 1001)}
    df = pd.read_csv(args.baseline, float_precision="round_trip")
    for n, g in df.groupby("n"):
        n = int(n)
        bank[n] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    # Target sub-grid puzzles (room to compress); prioritize larger excess.
    targets = []
    for n in range(1, 1001):
        L = side(bank[n])
        ceil_grid = math.ceil(math.sqrt(n))
        if L < ceil_grid - 1e-6:  # already beats grid -> non-trivial packing
            excess = L - math.sqrt(n)
            targets.append((n, excess))
    targets.sort(key=lambda t: t[1], reverse=True)
    targets = [n for n, _ in targets[: args.top]]
    print(f"Targets: {len(targets)} sub-grid puzzles (top {args.top})")
    print(f"First 10: {targets[:10]}")

    # Build jobs: a few seeds per target.
    jobs = []
    for n in targets:
        for seed_off in range(3):
            jobs.append((n, bank[n], n * 10000 + seed_off, args.per_puzzle_seconds))
    print(f"Total jobs: {len(jobs)}  workers={args.workers}  budget={args.seconds:.0f}s")

    start = time.perf_counter()
    wins = {}  # n -> certified L (float)
    win_arr = {}  # n -> q array
    done = 0
    deadline = start + args.seconds

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(optimize_one, j): j[0] for j in jobs}
        for f in as_completed(futures):
            if time.perf_counter() > deadline:
                # cancel remaining
                for ff in futures:
                    ff.cancel()
            try:
                n, L0, Lbest, q = f.result()
            except Exception as e:
                n = futures[f]
                L0, Lbest, q = side(bank[n]), side(bank[n]), None
                print(f"  n={n}: job error {e!r}")
            done += 1
            if q is not None and Lbest < L0 - 1e-8:
                cur = side(bank[n])
                if Lbest < cur - 1e-8:
                    # Certify with the pinned official metric.
                    L_cert = certify(n, q)
                    if L_cert is not None and L_cert < cur - 1e-8:
                        prev = wins.get(n, math.inf)
                        if L_cert < prev - 1e-10:
                            wins[n] = L_cert
                            win_arr[n] = q
                            gain = (cur - L_cert) / math.sqrt(n)
                            print(
                                f"  WIN n={n:4d}: {cur:.10f} -> {L_cert:.10f} "
                                f"(gain {gain:.10f})  [{done}/{len(jobs)}]",
                                flush=True,
                            )
            if done % 50 == 0:
                el = time.perf_counter() - start
                print(f"  progress {done}/{len(jobs)} jobs, {len(wins)} wins, {el:.0f}s",
                      flush=True)
            if time.perf_counter() > deadline:
                break

    # Save patch npz.
    Path(args.patch_out).parent.mkdir(parents=True, exist_ok=True)
    if win_arr:
        pg.save_bank(args.patch_out, win_arr)
    total_gain = sum((side(bank[n]) - wins[n]) / math.sqrt(n) for n in wins)
    print(f"\n=== DONE: {len(wins)} certified wins, est. gain {total_gain:.10f} ===")
    print(f"patch: {args.patch_out}")
    # Persist a small manifest.
    Path(BASE / "output" / "cpu_wins.json").write_text(json.dumps(
        {str(n): {"cert_L": wins[n], "gain": (side(bank[n]) - wins[n]) / math.sqrt(n)}
         for n in wins}, indent=2))


if __name__ == "__main__":
    main()
