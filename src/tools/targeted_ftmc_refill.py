"""Targeted Centered FTMC Refill with Exact SAT Certification.

Loads current submission_final.csv, performs centered scaling of the tilted core,
solves L-BFGS-B relaxation on core, applies HiGHS MILP refill for upright squares,
polishes contacts, and certifies with the official metric before accepting.
"""

import math
import time
import json
import argparse
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "src" / "tools"))
sys.path.insert(0, str(BASE_DIR / "src" / "metric"))

import packing_geometry as pg
import metric
from cpu_round21_refill import refill, check
from cpu_contact_polish import polish


def core_energy(z, shape, L, anchor=None, tether=0.0):
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
    if anchor is not None and tether > 0:
        v = p - anchor
        E += tether * np.sum(v * v)
        g += 2 * tether * v
    return float(E), g.ravel()


def try_refill_puzzle(n, p_orig, depth, seed=42, mode=0):
    start = time.monotonic()
    rng = np.random.default_rng(seed)
    L0 = pg.side(p_orig)
    L = L0 - depth
    
    a = (p_orig[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4
    tilt = abs(a) > 0.018
    core = p_orig[tilt].copy()
    oldU = p_orig[~tilt].copy()
    
    if not (2 <= len(core) <= 250):
        return None, f"invalid core size: {len(core)}"
        
    # Centered scaling fix
    core[:, :2] = (core[:, :2] - L0 * 0.5) * (L - 1.0) / (L0 - 1.0) + L * 0.5
    
    if mode == 1:
        core[:, :2] += rng.normal(0, 0.005, core[:, :2].shape)
        core[:, 2] += rng.normal(0, 0.003, len(core))
    elif mode == 2:
        core[:, :2] += rng.normal(0, 0.015, core[:, :2].shape)
        core[:, 2] += rng.normal(0, 0.008, len(core))

    anchor = core.copy()
    trust = 0.05 if mode == 0 else (0.12 if mode == 1 else 0.25)
    bounds = [
        (x - trust, x + trust) if j < 2 else (x - 0.1, x + 0.1)
        for row in core
        for j, x in enumerate(row)
    ]
    
    for reg in [1e-5, 1e-8, 0.0]:
        fit = minimize(
            core_energy,
            core.ravel(),
            args=(core.shape, L, anchor, reg),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": 120, "ftol": 1e-15, "gtol": 1e-9, "maxls": 30},
        )
        core = fit.x.reshape(core.shape)
        if time.monotonic() - start > 10:
            break
            
    E, _ = core_energy(core.ravel(), core.shape, L)
    if E > 1e-12:
        return None, f"core relaxation failed (E={E:.2e})"
        
    # Build candidate upright positions
    extra = np.vstack(
        [
            oldU + np.array([dx, dy, 0.0])
            for dx, dy in [(0, 0), (-depth, 0), (0, -depth), (-depth, -depth), (-depth/2, -depth/2)]
        ]
    )
    
    q, r = refill(L, L, core, n, extra=extra, seconds=0.6, soft=min(0.004, depth * 0.5))
    if q is None:
        return None, f"refill failed (needed={r.get('needed')}, found={r.get('found')})"
        
    # Polish and repair
    q, tr, sec = polish(q, rounds=25, max_seconds=3, seed=seed, trust_start=0.01)
    q = pg.repair(q, clearance=2e-9)
    if q is None:
        return None, "repair failed"
        
    new_L = pg.side(q)
    if new_L >= L0 - 1e-8:
        return None, f"not smaller ({new_L:.8f} vs {L0:.8f})"
        
    # Official SAT certification
    recs = [
        {"n": str(n), "square_id": str(i), "x": f"{row[0]:.16f}", "y": f"{row[1]:.16f}", "angle": f"{row[2]:.16f}"}
        for i, row in enumerate(q)
    ]
    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, recs)
    if status and float(L_cert) < L0 - 1e-8:
        return q, f"WIN: L0={L0:.8f} -> L_cert={float(L_cert):.8f} (gain={(L0 - float(L_cert))/math.sqrt(n):.8f})"
    else:
        return None, f"certification rejected: {why}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", nargs="+", type=int, default=[106, 104, 108, 102, 105, 103])
    args = parser.parse_args()
    
    print("Loading baseline...")
    bank = pg.load_bank(str(BASE_DIR / "output" / "submission_final.csv"))
    
    for n in args.targets:
        p0 = bank[n]
        L0 = pg.side(p0)
        print(f"\n--- Testing n={n} (L0={L0:.8f}) ---")
        for depth in [0.0001, 0.0002, 0.0005, 0.001, 0.002]:
            for mode in [0, 1]:
                cand, msg = try_refill_puzzle(n, p0, depth=depth, seed=12345 + int(depth*1e6), mode=mode)
                print(f"  depth={depth:.5f}, mode={mode}: {msg}")
                if cand is not None:
                    print(f"  >>> SUCCESS on n={n}! <<<")
                    break
            if cand is not None:
                break

if __name__ == "__main__":
    main()

