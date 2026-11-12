"""Intensive multi-restart contact polish on high-leverage puzzles.

For each target puzzle, runs many independent contact polish restarts with
varied trust/regularization params and random angle perturbations.
Certifies any improvement.

    .venv/bin/python -u src/engine/intensive_polish.py \
        --base output/submission_22.204565.csv \
        --workers 8 --seconds 180 \
        --outdir output/intensive_polish_wins
"""
from __future__ import annotations
import argparse, math, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
KIT  = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(ROOT / "src" / "tools"))
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "kirilltym"))
sys.path.insert(0, str(ROOT / "data" / "latest_sync_1900" / "kirilltym"))
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
    p = p.copy(); p[:, 0] -= xlo; p[:, 1] -= ylo
    return p


def optimize_one(job):
    n, p0, seconds, seed = job
    try:
        from cpu_contact_polish import polish
        from cpu_axis_reclosure import reclose
    except ImportError:
        return n, _side(p0), _side(p0), None

    import metric as M

    rng = np.random.default_rng(seed)
    deadline = time.perf_counter() + seconds
    L0 = _side(p0)
    best_L = L0
    best_p = p0.copy()

    def try_polish(p_in, seed_off, trust=0.04, reg=0.0):
        nonlocal best_L, best_p
        p = _normalize(p_in.copy())
        try:
            q_tup = reclose(p, seed=seed + seed_off, trust=trust, tie=0.015,
                            rounds=6, seconds=min(5.0, deadline - time.perf_counter()))
            q = q_tup[0] if isinstance(q_tup, tuple) else q_tup
        except Exception:
            q = p
        if time.perf_counter() < deadline:
            try:
                r_tup = polish(q, rounds=120, seed=seed + seed_off + 1000,
                               max_seconds=min(15.0, deadline - time.perf_counter()),
                               regularization=reg, trust_start=trust)
                r = r_tup[0] if isinstance(r_tup, tuple) else r_tup
            except Exception:
                r = q
        else:
            r = q
        L = _side(r)
        if L < best_L - 1e-9:
            best_L = L
            best_p = r.copy()
        return L

    # Strategy 1: direct polish from base with multiple param sets
    for i, (trust, reg) in enumerate([
        (0.04, 0.0), (0.08, 0.0), (0.15, 0.0),
        (0.04, 1e-4), (0.04, 1e-3), (0.08, 1e-4),
        (0.22, 0.015), (0.40, 0.0), (0.55, 0.0),
    ]):
        if time.perf_counter() > deadline: break
        try_polish(p0, seed_off=i * 7, trust=trust, reg=reg)

    # Strategy 2: small random angle perturbations + polish
    for i in range(30):
        if time.perf_counter() > deadline: break
        p_perturb = p0.copy()
        # Perturb a random subset of squares
        k = max(1, len(p0) // 8)
        idx = rng.choice(len(p0), size=k, replace=False)
        p_perturb[idx, 2] += rng.uniform(-0.08, 0.08, k)
        p_perturb[idx, 0] += rng.normal(0, 0.02, k)
        p_perturb[idx, 1] += rng.normal(0, 0.02, k)
        try_polish(p_perturb, seed_off=100 + i * 3, trust=0.04, reg=0.0)

    # Strategy 3: rotate entire packing by small angle (breaks symmetry differently)
    for da in [0.01, 0.02, 0.05, -0.01, -0.02, -0.05, 0.1, -0.1]:
        if time.perf_counter() > deadline: break
        p_rot = p0.copy()
        p_rot[:, 2] += da
        # Also rotate positions around centroid
        cx, cy = p_rot[:, 0].mean(), p_rot[:, 1].mean()
        cos_da, sin_da = math.cos(da), math.sin(da)
        x_new = cx + cos_da * (p_rot[:, 0] - cx) - sin_da * (p_rot[:, 1] - cy)
        y_new = cy + sin_da * (p_rot[:, 0] - cx) + cos_da * (p_rot[:, 1] - cy)
        p_rot[:, 0] = x_new; p_rot[:, 1] = y_new
        try_polish(p_rot, seed_off=200, trust=0.04, reg=0.0)

    if best_L >= L0 - 1e-9:
        return n, L0, L0, None

    # Certify
    rows = [{"n": str(n), "square_id": str(i),
             "x": repr(float(best_p[i, 0])), "y": repr(float(best_p[i, 1])),
             "angle": repr(float(best_p[i, 2]))} for i in range(n)]
    _, _, L_str, why = M.evaluate_single_puzzle(n, rows)
    if why != "ok" or L_str is None: return n, L0, L0, None
    L_cert = float(L_str)
    if L_cert >= L0 - 1e-9: return n, L0, L0, None
    return n, L0, L_cert, best_p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "output" / "submission_22.204565.csv"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--outdir", default=str(ROOT / "output" / "intensive_polish_wins"))
    ap.add_argument("--seconds", type=float, default=180.0)
    ap.add_argument("--nmin", type=int, default=100)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--max_puzzles", type=int, default=150)
    a = ap.parse_args()

    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.base); df["n"] = df["n"].astype(int)
    bank = {}
    for n_val, g in df.groupby("n"):
        bank[int(n_val)] = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)

    # Target: non-trivial puzzles ranked by weight*(L-K) — most leverage
    targets = []
    for n in range(a.nmin, min(a.nmax + 1, 1001)):
        K = math.isqrt(n); D = n - K*K
        if D == 0 or n not in bank: continue
        from ensemble import side as fside
        L = float(fside(bank[n]))
        if L >= K + 1 - 1e-6: continue
        wt = 1.0 / math.sqrt(n)
        targets.append((n, K, D, L, wt * (L - K)))

    targets.sort(key=lambda x: -x[4])
    targets = targets[:a.max_puzzles]
    print(f"Targets: {len(targets)}", flush=True)
    for n, K, D, L, pri in targets[:10]:
        print(f"  n={n:4d} K={K} D={D:2d} L={L:.6f} priority={pri:.5f}", flush=True)

    jobs = [(n, bank[n], a.seconds, n * 97 + 13) for n, K, D, L, pri in targets]

    t0 = time.time(); wins = 0; total_gain = 0.0
    print(f"\nRunning {len(jobs)} jobs on {a.workers} workers ({a.seconds}s each)...", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(optimize_one, job): job[0] for job in jobs}
        for fut in as_completed(futures):
            n_val = futures[fut]
            try:
                n, L0, L_cert, sq = fut.result()
            except Exception as e:
                print(f"  n={n_val}: ERROR {e}", flush=True); continue
            if sq is not None and L_cert < L0 - 1e-9:
                gain = (L0 - L_cert) / math.sqrt(n)
                total_gain += gain; wins += 1
                with open(outdir / f"{n}.csv", "w") as fh:
                    fh.write("n,square_id,x,y,angle\n")
                    for i in range(n):
                        fh.write(f"{n},{i},{float(sq[i,0])!r},{float(sq[i,1])!r},{float(sq[i,2])!r}\n")
                print(f"  WIN n={n}: {L0:.9f} -> {L_cert:.9f} (gain {gain:.4e}) [total {total_gain:.6f}]", flush=True)

    print(f"\nDone in {time.time()-t0:.0f}s: {wins}/{len(targets)} wins, gain {total_gain:.6f}", flush=True)


if __name__ == "__main__":
    main()
