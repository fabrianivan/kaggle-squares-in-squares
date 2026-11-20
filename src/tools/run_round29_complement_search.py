"""Bounded CPU contact search on newly complementary public donor witnesses.
All numerical optimizers are previously reviewed local CPU helpers. No GPU/MPS.
"""

import os

for k in [
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "MKL_NUM_THREADS",
]:
    os.environ[k] = "1"
import argparse, time, json, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from scipy.optimize import minimize
from packing_geometry import load_bank, normalize, side, repair, save_bank
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish
from run_round21_core_refill import energy
from cpu_round21_project import project


def worker(job):
    n, p, seed, arm = job
    t = time.monotonic()
    L0 = side(p)
    rng = np.random.default_rng(seed)
    r = dict(n=n, seed=seed, arm=arm, before=L0, accepted=False, gain=0.0)
    if arm == 0:
        q, trace, _ = reclose(
            p, seed=seed, trust=0.55, tie=0.28, rounds=10, seconds=1.0
        )
        r["kind"] = "contact_control"
        r["iterations"] = len(trace)
    else:
        q = normalize(p)
        depth = [0.0003, 0.001, 0.004, 0.012, 0.03, 0.06][((arm - 1) // 4) % 6]
        L = L0 - depth
        q[:, :2] = 0.5 + (q[:, :2] - 0.5) * (L - 1) / (L0 - 1)
        mode = (arm - 1) % 4
        r.update(
            kind=["compression", "coherent_fault", "local_hinge", "rectangular_return"][
                mode
            ],
            depth=depth,
        )
        if mode == 1:
            # Coherent opposite translation on each side of a seeded cut.
            a = rng.uniform(0, np.pi)
            u = np.array([np.cos(a), np.sin(a)])
            v = np.array([-u[1], u[0]])
            x = p[:, :2] @ u
            cut = np.quantile(x, rng.uniform(0.3, 0.7))
            q[:, :2] += np.sign(x - cut)[:, None] * v * 0.025
            q[:, 2] += rng.normal(0, 0.002, len(q))
        elif mode == 2:
            angle = abs((p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4)
            pool = np.flatnonzero(angle > 0.002)
            pivot = p[rng.choice(pool) if len(pool) else rng.integers(n), :2]
            ids = np.argsort(((p[:, :2] - pivot) ** 2).sum(1))[: min(n, 30)]
            delta = rng.choice([-1, 1]) * 0.012
            c, s = np.cos(delta), np.sin(delta)
            q[ids, :2] = (q[ids, :2] - pivot) @ np.array([[c, s], [-s, c]]) + pivot
            q[ids, 2] += delta
        bounds = [
            (x - 0.25, x + 0.25) if j < 2 else (x - 0.12, x + 0.12)
            for row in q
            for j, x in enumerate(row)
        ]
        if mode == 3:
            # A rectangular excursion changes wall contacts before restoring a square.
            # Only the existing gradient-checked SAT energy is used; no size relaxation.
            stretch = rng.choice([-1.0, 1.0]) * max(0.005, min(0.08, depth * 3))
            box = np.array([L + stretch, L - stretch])
            q[:, :2] = 0.5 + (q[:, :2] - 0.5) * (box - 1) / (L - 1)
            fit0 = minimize(
                energy,
                q.ravel(),
                args=(q.shape, box, None, 0.0),
                method="L-BFGS-B",
                jac=True,
                bounds=bounds,
                options={
                    "maxiter": 650,
                    "ftol": 1e-17,
                    "gtol": 1e-11,
                    "maxls": 30,
                    "maxcor": 25,
                },
            )
            q = fit0.x.reshape(q.shape)
            r["excursion_iterations"] = int(fit0.nit)
            r["stretch"] = float(stretch)
        fit = minimize(
            energy,
            q.ravel(),
            args=(q.shape, L, None, 0.0),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={
                "maxiter": 1100,
                "ftol": 1e-17,
                "gtol": 1e-11,
                "maxls": 30,
                "maxcor": 25,
            },
        )
        q = fit.x.reshape(q.shape)
        E, _ = energy(q.ravel(), q.shape, L)
        r.update(energy=E, iterations=int(fit.nit))
        q = project(q, L0 - 1e-7, trust=0.16, seconds=1.0) if E < 0.02 else None
    if q is not None and (side(p) - side(q)) / math.sqrt(n) > 1e-8:
        q, tr, _ = polish(q, seed=seed, rounds=35, max_seconds=2.0, trust_start=0.012)
        q = repair(q, clearance=2e-9)
        if q is not None and (side(p) - side(q)) / math.sqrt(n) > 1e-8:
            r.update(
                accepted=True, after=side(q), gain=(side(p) - side(q)) / math.sqrt(n)
            )
    r["seconds"] = time.monotonic() - t
    return q if r["accepted"] else None, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    start = time.monotonic()
    b = load_bank("artifacts/round29_submission.csv")
    s = json.load(open("artifacts/round29_summary.json"))
    scan = json.load(open("artifacts/round29_union_scan.json"))
    targets = list(
        dict.fromkeys(
            [r["n"] for r in scan["wins"]]
            + [r["n"] for r in scan["new_leader_changes"][:60]]
        )
    )
    h = []
    wins = {}
    seq = 0
    visits = {n: 0 for n in targets}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        active = {}

        def add():
            nonlocal seq
            n = targets[seq % len(targets)]
            arm = visits[n]
            visits[n] += 1
            seq += 1
            active[ex.submit(worker, (n, b[n], 291026000 + seq * 32749, arm))] = n

        for _ in range(a.workers):
            add()
        while active:
            f = next(as_completed(active))
            active.pop(f)
            try:
                q, r = f.result()
            except Exception as e:
                q = None
                r = {"error": repr(e)}
            h.append(r)
            if q is not None and side(q) < side(b[r["n"]]):
                b[r["n"]] = q
                wins[str(r["n"])] = q
                print(json.dumps(r), flush=True)
            if len(h) % 10 == 0 or q is not None:
                save_bank("artifacts/round29_cpu_packings.npz", wins)
                Path("artifacts/round29_cpu_history.json").write_text(
                    json.dumps(h, indent=2)
                )
                print(
                    "trials",
                    len(h),
                    "wins",
                    len(wins),
                    "elapsed",
                    round(time.monotonic() - start),
                    flush=True,
                )
            if time.monotonic() - start < a.seconds and seq < len(targets) * 25:
                add()
    save_bank("artifacts/round29_cpu_packings.npz", wins)
    Path("artifacts/round29_cpu_history.json").write_text(json.dumps(h, indent=2))


if __name__ == "__main__":
    main()
