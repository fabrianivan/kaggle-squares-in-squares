"""Bounded CPU tilted-core compression/refill; FTMC architecture credited to
Chris Deotte, finite candidate refill adapted from lightningv08 public V22.
New experiment: numpy analytic SAT quench with per-square trust bounds on CPU.
No CUDA/MPS imports, no publication, two local workers, explicit time budget.
"""

import os

for k in [
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "MKL_NUM_THREADS",
]:
    os.environ[k] = "1"
import math, time, json, argparse
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from concurrent.futures import ProcessPoolExecutor, as_completed
from packing_geometry import load_bank, side, repair, normalize, save_bank, min_gap
from cpu_round21_refill import refill, check
from cpu_contact_polish import polish


def energy(z, shape, L, anchor=None, tether=0.0):
    p = z.reshape(shape)
    n = len(p)
    a = p[:, 2]
    c = np.cos(a)
    s = np.sin(a)
    h = (abs(c) + abs(s)) / 2
    pairs = cKDTree(p[:, :2]).query_pairs(1.6, output_type="ndarray")
    g = np.zeros_like(p)
    E = 0.0
    if len(pairs):
        i, j = pairs.T
        d = p[j, :2] - p[i, :2]
        ux = np.column_stack((c[i], -s[i], c[j], -s[j]))
        uy = np.column_stack((s[i], c[i], s[j], c[j]))
        proj = d[:, 0, None] * ux + d[:, 1, None] * uy
        ranks = abs(proj)
        k = ranks.argmax(1)
        rr = np.arange(len(i))
        sg = np.where(proj[rr, k] >= 0, 1.0, -1.0)
        vx = sg * ux[rr, k]
        vy = sg * uy[rr, k]
        rot = -d[:, 0] * vy + d[:, 1] * vx
        delta = a[j] - a[i]
        cd = np.cos(delta)
        sd = np.sin(delta)
        rad = (1 + abs(cd) + abs(sd)) / 2
        dr = (-sd * np.sign(cd) + cd * np.sign(sd)) / 2
        v = np.maximum(rad - ranks[rr, k] + 2e-8, 0)
        E += np.dot(v, v)
        w = 2 * v
        np.add.at(g[:, 0], i, w * vx)
        np.add.at(g[:, 1], i, w * vy)
        np.add.at(g[:, 0], j, -w * vx)
        np.add.at(g[:, 1], j, -w * vy)
        np.add.at(g[:, 2], i, w * (-dr - np.where(k < 2, rot, 0)))
        np.add.at(g[:, 2], j, w * (dr - np.where(k >= 2, rot, 0)))
    dh = (-s * np.sign(c) + c * np.sign(s)) / 2
    for dim in [0, 1]:
        low = np.maximum(h - p[:, dim] + 2e-8, 0)
        high = np.maximum(p[:, dim] + h - (L[dim] if np.ndim(L) else L) + 2e-8, 0)
        E += np.dot(low, low) + np.dot(high, high)
        g[:, dim] += 2 * (high - low)
        g[:, 2] += 2 * (low + high) * dh
    if anchor is not None and tether:
        v = p - anchor
        E += tether * np.sum(v * v)
        g += 2 * tether * v
    return float(E), g.ravel()


def task(job):
    n, p, seed, depth, mode = job
    start = time.monotonic()
    rng = np.random.default_rng(seed)
    L0 = side(p)
    L = L0 - depth
    a = (p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4
    tilt = abs(a) > 0.018
    core = p[tilt].copy()
    oldU = p[~tilt].copy()
    report = dict(
        n=n,
        seed=seed,
        depth=depth,
        mode=mode,
        core=len(core),
        before=L0,
        accepted=False,
        gain=0.0,
    )
    if not 2 <= len(core) <= 200:
        return None, report
    core[:, :2] *= (L - 1) / (L0 - 1)
    if mode:
        core[:, :2] += rng.normal(0, 0.015 if mode == 1 else 0.04, core[:, :2].shape)
        core[:, 2] += rng.normal(0, 0.008 if mode == 1 else 0.025, len(core))
    anchor = core.copy()
    trust = 0.15 if mode < 2 else 0.3
    bounds = [
        (x - trust, x + trust) if j < 2 else (x - 0.15, x + 0.15)
        for row in core
        for j, x in enumerate(row)
    ]
    for reg in [1e-4, 1e-7, 0.0]:
        fit = minimize(
            energy,
            core.ravel(),
            args=(core.shape, L, anchor, reg),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": 110, "ftol": 1e-15, "gtol": 1e-9, "maxls": 30},
        )
        core = fit.x.reshape(core.shape)
        if time.monotonic() - start > 12:
            break
    E, _ = energy(core.ravel(), core.shape, L)
    report["energy"] = E
    if E > 1e-12:
        report["seconds"] = time.monotonic() - start
        return None, report
    extra = np.vstack(
        [
            oldU + np.array([dx, dy, 0.0])
            for dx, dy in [(0, 0), (-depth, 0), (0, -depth), (-depth, -depth)]
        ]
    )
    q, r = refill(
        L, L, core, n, extra=extra, seconds=0.25, soft=min(0.006, depth * 0.3)
    )
    report["refill"] = r
    if q is not None:
        # Repair near-feasible refill with the full sparse CPU penalty model first.
        full_anchor = q.copy()
        bounds = [
            (x - 0.2, x + 0.2) if j < 2 else (x - 0.06, x + 0.06)
            for row in q
            for j, x in enumerate(row)
        ]
        fit = minimize(
            energy,
            q.ravel(),
            args=(q.shape, L, full_anchor, 0.0),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": 180, "ftol": 1e-15, "gtol": 1e-9, "maxls": 30},
        )
        q = fit.x.reshape(q.shape)
        q = repair(q, clearance=2e-9)
        if q is not None and side(q) < L0 - 1e-7:
            q, tr, sec = polish(
                q, rounds=35, max_seconds=5, seed=seed, trust_start=0.02
            )
            q = repair(q, clearance=2e-9)
            if q is not None and side(q) < L0 - 1e-7:
                report.update(
                    accepted=True,
                    after=side(q),
                    gain=(L0 - side(q)) / math.sqrt(n),
                    gap=min_gap(q),
                )
    report["seconds"] = time.monotonic() - start
    return q if report["accepted"] else None, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    start = time.monotonic()
    b = load_bank("artifacts/round20_final_submission.csv")
    hist = []
    wins = {}
    print("refill check", check(), flush=True)
    candidates = [
        n
        for n, p in b.items()
        if 100 <= n <= 1000
        and side(p) < math.ceil(math.sqrt(n)) - 1e-6
        and np.sum(abs((p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4) > 0.018) <= 200
    ]

    # Prefer numerical non-45-degree geometries and smaller expensive cores.
    def priority(n):
        p = b[n]
        a = abs((p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4)
        a = a[a > 1e-5]
        return (float(np.mean(abs(a - np.pi / 4))) > 0.005, 1 / math.sqrt(n))

    candidates.sort(key=priority, reverse=True)
    jobs = [
        (n, b[n], 261024 + n + arm * 19937, depth, mode)
        for arm, (depth, mode) in enumerate(
            [(0.003, 0), (0.012, 0), (0.025, 1), (0.006, 2), (0.06, 2)]
        )
        for n in candidates
    ]
    print("targets", len(candidates), "jobs", len(jobs), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        active = {}
        it = iter(jobs)

        def add():
            try:
                j = next(it)
            except StopIteration:
                return False
            active[ex.submit(task, j)] = j[0]
            return True

        for _ in range(args.workers):
            add()
        while active:
            f = next(as_completed(active))
            active.pop(f)
            try:
                q, r = f.result()
            except Exception as e:
                q = None
                r = {"error": repr(e)}
            hist.append(r)
            if q is not None and side(q) < side(b[r["n"]]):
                b[r["n"]] = q
                wins[r["n"]] = q
                print(json.dumps(r), flush=True)
            if len(hist) % 10 == 0 or q is not None:
                save_bank("artifacts/round21_core_packings.npz", b)
                Path("artifacts/round21_core_history.json").write_text(
                    json.dumps(hist, indent=2)
                )
                print(
                    "progress",
                    len(hist),
                    "wins",
                    len(wins),
                    "seconds",
                    round(time.monotonic() - start),
                    flush=True,
                )
            if time.monotonic() - start < args.seconds:
                add()
    save_bank("artifacts/round21_core_packings.npz", b)
    Path("artifacts/round21_core_history.json").write_text(json.dumps(hist, indent=2))


if __name__ == "__main__":
    main()
