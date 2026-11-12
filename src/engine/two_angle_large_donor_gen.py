"""Generate large two-angle packings as donors for fault-line DP gadget extraction.

The key insight: gadgets with dm in range 36-61 come from LARGE packings (n=300-900)
where a rectangular crop w×h contains n squares with f < FMAX overflow. The dm value
is n - w*h (squares outside the w×h box but inside the [0,w+f]×[0,h+f] box).

This script generates large two-angle pinwheel packings at various angles and sizes,
then feeds them as donors to fault_dp.extract() which finds all useful crops.

Strategy:
- For K in [17,18,...,31] (so n = K^2 + D for D in 36-61), generate K×K and nearby packings
- Use two-angle patterns at (theta1, theta2) pairs found effective
- Optimize with cpu_axis_reclosure + cpu_contact_polish
- Feed all resulting packings to fault_dp.extract()

Usage:
    .venv/bin/python -u src/engine/two_angle_large_donor_gen.py --workers 8 \
        --output output/two_angle_large_donors.npy
"""
from __future__ import annotations
import argparse
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(ROOT / "src" / "tools"))
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "kirilltym"))
sys.path.insert(0, str(ROOT / "data" / "latest_sync_1900" / "kirilltym"))

FMAX = 0.97

# Angle pairs that are known to produce compact two-angle packings
# Drawn from the n=109 packing (23.59°, 28.66°) and nearby values
ANGLE_PAIRS_DEG = [
    (23.59, 28.66),  # the known-good n=109 angles
    (20.0, 30.0),
    (22.0, 28.0),
    (25.0, 32.0),
    (18.0, 27.0),
    (21.0, 31.0),
    (24.0, 29.0),
    (15.0, 35.0),
    (20.0, 25.0),
    (28.0, 35.0),
    (19.0, 29.0),
    (23.0, 33.0),
]

# Patterns for alternating angles
PATTERNS = ["checkerboard", "rows", "cols"]


def _side(p):
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    X = np.concatenate([p[:, 0] + c - s, p[:, 0] - c - s, p[:, 0] - c + s, p[:, 0] + c + s])
    Y = np.concatenate([p[:, 1] + s + c, p[:, 1] - s + c, p[:, 1] - s - c, p[:, 1] + s - c])
    return max(X.max() - X.min(), Y.max() - Y.min())


def _normalize(p):
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xlo = (p[:, 0] - np.abs(c) - np.abs(s)).min()
    ylo = (p[:, 1] - np.abs(s) - np.abs(c)).min()
    p = p.copy()
    p[:, 0] -= xlo
    p[:, 1] -= ylo
    return p


def _init_packing(rows: int, cols: int, theta1: float, theta2: float, pattern: str) -> np.ndarray:
    squares = []
    for i in range(cols):
        for j in range(rows):
            if pattern == "checkerboard":
                angle = theta1 if (i + j) % 2 == 0 else theta2
            elif pattern == "rows":
                angle = theta1 if j % 2 == 0 else theta2
            else:  # cols
                angle = theta1 if i % 2 == 0 else theta2
            squares.append([i + 0.5, j + 0.5, angle])
    return np.array(squares, float)


def _try_large_packing(n_target: int, theta1_deg: float, theta2_deg: float,
                       pattern: str, seconds: float = 60.0, seed: int = 0) -> np.ndarray | None:
    """Try to generate a compact large packing of n_target squares with two angles."""
    try:
        from cpu_axis_reclosure import reclose
        from cpu_contact_polish import polish
    except ImportError:
        return None

    theta1 = math.radians(theta1_deg)
    theta2 = math.radians(theta2_deg)

    # Grid dimensions: try to make roughly square
    cols = int(math.ceil(math.sqrt(n_target)))
    rows = int(math.ceil(n_target / cols))
    # Take exactly n_target squares from the grid
    all_sq = []
    for i in range(cols):
        for j in range(rows):
            if len(all_sq) >= n_target:
                break
            if pattern == "checkerboard":
                angle = theta1 if (i + j) % 2 == 0 else theta2
            elif pattern == "rows":
                angle = theta1 if j % 2 == 0 else theta2
            else:  # cols
                angle = theta1 if i % 2 == 0 else theta2
            all_sq.append([i + 0.5, j + 0.5, angle])
        if len(all_sq) >= n_target:
            break

    p = np.array(all_sq[:n_target], float)
    best_side = _side(p)
    best_p = p.copy()

    t_start = time.perf_counter()

    # Phase 1: axis reclosure
    for attempt in range(4):
        elapsed = time.perf_counter() - t_start
        if elapsed > seconds * 0.6:
            break
        try:
            result = reclose(p, seed=seed + attempt, rounds=10,
                             seconds=min(15.0, seconds * 0.15))
            pr = result[0] if isinstance(result, tuple) else result
        except Exception:
            continue
        s = _side(pr)
        if s < best_side - 1e-12:
            best_side = s
            best_p = pr.copy()
        p = pr

    # Phase 2: contact polish
    p = best_p.copy()
    for attempt in range(3):
        elapsed = time.perf_counter() - t_start
        if elapsed > seconds * 0.95:
            break
        try:
            result = polish(p, rounds=80, seed=seed + attempt,
                            max_seconds=min(20.0, seconds * 0.2))
            pp = result[0] if isinstance(result, tuple) else result
        except Exception:
            continue
        s = _side(pp)
        if s < best_side - 1e-12:
            best_side = s
            best_p = pp.copy()
        p = pp

    # Only keep if strictly better than trivial grid
    K = int(math.ceil(math.sqrt(n_target)))
    if best_side >= K - 1e-9:
        return None  # trivial or worse — no useful gadgets

    return _normalize(best_p)


def _job(args):
    n_target, theta1_deg, theta2_deg, pattern, seconds, seed = args
    packing = _try_large_packing(n_target, theta1_deg, theta2_deg, pattern, seconds, seed)
    if packing is not None:
        return {
            "n": n_target, "theta1": theta1_deg, "theta2": theta2_deg,
            "pattern": pattern, "side": float(_side(packing)),
            "packing": packing,
        }
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seconds_per_job", type=float, default=90.0)
    ap.add_argument("--output", default=str(ROOT / "output" / "two_angle_large_donors.npy"))
    ap.add_argument("--nmin", type=int, default=290,
                    help="min n for donor packings (K=17 => n=289+)")
    ap.add_argument("--nmax", type=int, default=965,
                    help="max n for donor packings (K=31 => n=961+)")
    ap.add_argument("--nstep", type=int, default=10,
                    help="step between target n values")
    a = ap.parse_args()

    # Generate all (n, theta1, theta2, pattern) combinations to try
    n_values = list(range(a.nmin, a.nmax + 1, a.nstep))
    jobs = []
    for n_target in n_values:
        for theta1_deg, theta2_deg in ANGLE_PAIRS_DEG:
            for pattern in PATTERNS:
                seed = (n_target * 1000 + int(theta1_deg * 10) + int(theta2_deg * 10))
                jobs.append((n_target, theta1_deg, theta2_deg, pattern, a.seconds_per_job, seed))

    print(f"Total jobs: {len(jobs)} ({len(n_values)} n values × {len(ANGLE_PAIRS_DEG)} angle pairs × {len(PATTERNS)} patterns)")
    print(f"Workers: {a.workers}, seconds/job: {a.seconds_per_job}")
    print(f"Expected runtime: ~{len(jobs) * a.seconds_per_job / a.workers / 60:.0f} minutes", flush=True)

    t0 = time.time()
    donors = []
    done = 0

    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(_job, job): job for job in jobs}
        for fut in as_completed(futures):
            done += 1
            try:
                result = fut.result()
                if result is not None:
                    donors.append(result["packing"])
                    elapsed = time.time() - t0
                    K = int(math.ceil(math.sqrt(result["n"])))
                    D = result["n"] - K * K
                    print(f"  [{done}/{len(jobs)}] {elapsed:.0f}s n={result['n']} K={K} D={D} "
                          f"t1={result['theta1']:.1f}° t2={result['theta2']:.1f}° "
                          f"pat={result['pattern']} side={result['side']:.4f} "
                          f"(trivial={K:.0f}) donors={len(donors)}", flush=True)
            except Exception as e:
                pass
            if done % 50 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  progress: [{done}/{len(jobs)}] {elapsed:.0f}s donors={len(donors)} rate={rate:.1f}/s",
                      flush=True)

    print(f"\nCollected {len(donors)} donor packings in {time.time()-t0:.0f}s", flush=True)

    if not donors:
        print("No donors found! All packings stayed at trivial grid.", flush=True)
        sys.exit(1)

    # Save donors
    donor_dict = {f"d_{i}": sq for i, sq in enumerate(donors)}
    np.savez(a.output.replace(".npy", "_donors.npz"), **donor_dict)
    print(f"Saved {len(donors)} donors to {a.output.replace('.npy', '_donors.npz')}", flush=True)

    # Extract gadgets via fault_dp
    sys.path.insert(0, str(KIT))
    import fault_dp as F
    F.log = print
    print("Extracting gadgets from donors...", flush=True)
    G = F.extract(donors)
    if len(G) == 0:
        print("No gadgets extracted!", flush=True)
        sys.exit(1)

    np.save(a.output, G)
    print(f"Extracted {len(G)} gadgets", flush=True)

    # Report D=36-61 coverage
    dm_vals = G[:, 2].astype(int)
    print(f"dm range: {dm_vals.min()} - {dm_vals.max()}", flush=True)
    for lo, hi in [(1, 10), (11, 20), (21, 35), (36, 50), (51, 61)]:
        count = ((dm_vals >= lo) & (dm_vals <= hi)).sum()
        print(f"  D={lo}-{hi}: {count} gadgets", flush=True)

    print(f"\nDone! Gadgets saved to {a.output}", flush=True)


if __name__ == "__main__":
    main()
