"""Generate two-angle pinwheel packing donors for fault-line DP gadget extraction.

For each (w, h) in [4..16] x [4..16] and angle pair (theta1, theta2) with
theta1 in [15°,35°], theta2 in [25°,45°], theta1 < theta2:
 - Place w*h squares in a grid, alternating angles by pattern (checkerboard / rows / blocks)
 - Apply cpu_axis_reclosure + cpu_contact_polish to minimize overhang
 - Keep configs with dm >= 1 that pack in [0, w+f] x [0, h+f] with f < 0.97
 - Extract gadgets via fault_dp.extract and keep high-merit ones

The goal is gadgets with dm/(w+h) high and dm in range 36-61 for small w, h.

    .venv/bin/python src/engine/two_angle_pinwheel_generator.py --workers 8 --output output/two_angle_gadgets.npz
"""
from __future__ import annotations
import argparse
import math
import os
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


def _normalize(p):
    """Translate so bounding box starts at (0,0)."""
    if len(p) == 0:
        return p
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xlo = (p[:, 0] - c - s).min()
    ylo = (p[:, 1] - s + c).min()
    p = p.copy()
    p[:, 0] -= xlo
    p[:, 1] -= ylo
    return p


def _side(p):
    """Bounding box side length."""
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    X = np.concatenate([p[:, 0] + c - s, p[:, 0] - c - s, p[:, 0] - c + s, p[:, 0] + c + s])
    Y = np.concatenate([p[:, 1] + s + c, p[:, 1] - s + c, p[:, 1] - s - c, p[:, 1] + s - c])
    return max(X.max() - X.min(), Y.max() - Y.min())


def _init_packing(w: int, h: int, theta1: float, theta2: float, pattern: str = "checkerboard") -> np.ndarray:
    """Create initial w*h packing with two angles."""
    squares = []
    for i in range(w):
        for j in range(h):
            if pattern == "checkerboard":
                angle = theta1 if (i + j) % 2 == 0 else theta2
            elif pattern == "rows":
                angle = theta1 if j % 2 == 0 else theta2
            elif pattern == "cols":
                angle = theta1 if i % 2 == 0 else theta2
            elif pattern == "blocks":
                bsize = max(1, min(w, h) // 2)
                angle = theta1 if (i // bsize + j // bsize) % 2 == 0 else theta2
            else:
                angle = theta1
            squares.append([i + 0.5, j + 0.5, angle])
    return np.array(squares, float)


def _overhang(p: np.ndarray, w: int, h: int) -> float:
    """Max overhang beyond [0,w]x[0,h]."""
    t = p[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    xhi = (p[:, 0] + np.abs(c) + np.abs(s))
    yhi = (p[:, 1] + np.abs(s) + np.abs(c))
    return float(max(0.0, xhi.max() - w, yhi.max() - h))


def _try_config(w: int, h: int, theta1: float, theta2: float, pattern: str,
                seconds: float = 30.0, seed: int = 42) -> dict | None:
    """Try to generate a donor packing at two angles. Returns None if no improvement found."""
    try:
        from cpu_axis_reclosure import reclose
        from cpu_contact_polish import polish
    except ImportError:
        return None

    p = _init_packing(w, h, theta1, theta2, pattern)
    best_f = _overhang(p, w, h)
    best_p = p.copy()

    t_start = time.perf_counter()
    # Phase 1: axis reclosure
    for attempt in range(5):
        if time.perf_counter() - t_start > seconds * 0.5:
            break
        try:
            result = reclose(p, seed=seed + attempt, rounds=8, seconds=min(6.0, seconds * 0.1))
            pr = result[0] if isinstance(result, tuple) else result
        except Exception:
            continue
        f = _overhang(pr, w, h)
        if f < best_f - 1e-12:
            best_f = f
            best_p = pr.copy()
        p = pr

    # Phase 2: contact polish
    p = best_p.copy()
    for attempt in range(3):
        if time.perf_counter() - t_start > seconds * 0.9:
            break
        try:
            result = polish(p, rounds=60, seed=seed + attempt, max_seconds=min(10.0, seconds * 0.15))
            pp = result[0] if isinstance(result, tuple) else result
        except Exception:
            continue
        f = _overhang(pp, w, h)
        if f < best_f - 1e-12:
            best_f = f
            best_p = pp.copy()
        p = pp

    if best_f >= FMAX:
        return None

    p = _normalize(best_p)
    return {"w": w, "h": h, "theta1": theta1, "theta2": theta2, "pattern": pattern,
            "f": best_f, "n": w * h, "packing": p}


def _job(args):
    """Worker job: try all patterns for a (w,h,theta1,theta2) config."""
    w, h, theta1, theta2, seconds, seed = args
    results = []
    for pattern in ["checkerboard", "rows", "cols", "blocks"]:
        r = _try_config(w, h, theta1, theta2, pattern, seconds=seconds, seed=seed)
        if r is not None:
            results.append(r)
    return results


def generate_configs(wmin=4, wmax=12, hmin=4, hmax=12,
                     theta1_min_deg=15.0, theta1_max_deg=35.0,
                     theta2_min_deg=25.0, theta2_max_deg=45.0,
                     theta_step_deg=2.0):
    """Generate all (w, h, theta1, theta2) combinations to try."""
    configs = []
    steps = []
    t = theta1_min_deg
    while t <= theta1_max_deg + 1e-9:
        steps.append(round(t, 3))
        t += theta_step_deg
    theta1_list = [math.radians(d) for d in steps]
    theta2_list = [math.radians(d) for d in steps if d >= theta2_min_deg - 1e-9]
    for w in range(wmin, wmax + 1):
        for h in range(hmin, hmax + 1):
            for t1 in theta1_list:
                for t2 in theta2_list:
                    if t2 > t1 + math.radians(1.0):
                        configs.append((w, h, t1, t2))
    return configs


def extract_gadgets_from_donors(donors: list, fmax: float = FMAX) -> np.ndarray:
    """Extract gadgets from a list of donor packings using fault_dp.extract."""
    import fault_dp as F
    orig_fmax = F.FMAX
    F.FMAX = fmax
    try:
        G = F.extract(donors)
    finally:
        F.FMAX = orig_fmax
    return G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wmin", type=int, default=4)
    ap.add_argument("--wmax", type=int, default=14)
    ap.add_argument("--hmin", type=int, default=4)
    ap.add_argument("--hmax", type=int, default=14)
    ap.add_argument("--theta1_min", type=float, default=15.0, help="min theta1 in degrees")
    ap.add_argument("--theta1_max", type=float, default=35.0, help="max theta1 in degrees")
    ap.add_argument("--theta2_min", type=float, default=25.0, help="min theta2 in degrees")
    ap.add_argument("--theta2_max", type=float, default=45.0, help="max theta2 in degrees")
    ap.add_argument("--theta_step", type=float, default=2.0, help="angle step in degrees")
    ap.add_argument("--seconds_per_config", type=float, default=30.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", default=str(ROOT / "output" / "two_angle_gadgets.npz"))
    ap.add_argument("--donors-output", default=str(ROOT / "output" / "two_angle_donors.npz"))
    a = ap.parse_args()

    configs = generate_configs(
        wmin=a.wmin, wmax=a.wmax, hmin=a.hmin, hmax=a.hmax,
        theta1_min_deg=a.theta1_min, theta1_max_deg=a.theta1_max,
        theta2_min_deg=a.theta2_min, theta2_max_deg=a.theta2_max,
        theta_step_deg=a.theta_step,
    )
    print(f"Total configs to try: {len(configs)}", flush=True)

    jobs = [(w, h, t1, t2, a.seconds_per_config, i * 13)
            for i, (w, h, t1, t2) in enumerate(configs)]

    t0 = time.time()
    donors = []
    done = 0

    print(f"Starting {a.workers} workers...", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(_job, job): job for job in jobs}
        for fut in as_completed(futures):
            done += 1
            try:
                results = fut.result()
                for r in results:
                    donors.append(r["packing"])
                if done % 100 == 0 or results:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    print(f"  [{done}/{len(configs)}] {elapsed:.0f}s donors={len(donors)} rate={rate:.1f}/s",
                          flush=True)
                    if results:
                        for r in results:
                            print(f"    w={r['w']} h={r['h']} "
                                  f"theta1={math.degrees(r['theta1']):.1f}° "
                                  f"theta2={math.degrees(r['theta2']):.1f}° "
                                  f"pat={r['pattern']} f={r['f']:.4f}", flush=True)
            except Exception as e:
                pass

    print(f"\nCollected {len(donors)} donor packings in {time.time()-t0:.0f}s", flush=True)

    if not donors:
        print("No donors found! Check theta ranges and optimization.", flush=True)
        sys.exit(1)

    # Save donors
    donor_dict = {f"d_{i}": sq for i, sq in enumerate(donors)}
    np.savez(a.donors_output, **donor_dict)
    print(f"Saved {len(donors)} donors to {a.donors_output}", flush=True)

    # Extract gadgets
    print("Extracting gadgets...", flush=True)
    G = extract_gadgets_from_donors(donors)
    np.save(a.output.replace(".npz", ".npy"), G)
    print(f"Extracted {len(G)} gadgets", flush=True)

    # Also save as npz with metadata
    high_d = G[(G[:, 2] >= 36) & (G[:, 2] <= 61)] if len(G) else np.zeros((0, 8))
    print(f"Gadgets in D=36-61: {len(high_d)}", flush=True)
    if len(G) > 0:
        print(f"Max dm: {G[:,2].max():.0f}", flush=True)
        merit = G[:, 2] / (G[:, 0] + G[:, 1])
        print(f"Max merit: {merit.max():.3f}", flush=True)

    np.savez(a.output, gadgets=G)
    print(f"Done! Gadgets saved to {a.output}", flush=True)


if __name__ == "__main__":
    main()
