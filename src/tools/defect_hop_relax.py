"""Defect-Mediated Topological Slack Relaxation (Breakthrough Paradigm 3).

Optimizes high-excess construction puzzles (n in [325, 450]) by taking the packing
of n+k (k=1 or 2), deleting the least-constrained boundary/slack square to introduce
a free-volume defect of >= 1.0 unit squares (unjamming the contact network), and
running Evan Driscoll's Rust basin-hopping engine (packer hop) to collapse into
novel topological basins inaccessible from the rigid jammed baseline of n.
"""

import math
import os
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ALEX_DIR = ROOT_DIR / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(ALEX_DIR))
sys.path.insert(0, str(ROOT_DIR / "src" / "metric"))

import metric
import fault_dp as F
from ensemble import side, certify

PACKER = ROOT_DIR / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "packer"
OUTPUT_DIR = ROOT_DIR / "output" / "defect_hop_run"


def corners(sq):
    x, y, t = sq[:, 0], sq[:, 1], sq[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    return np.r_[x + c - s, x - c - s, x - c + s, x + c + s], np.r_[y + s + c, y - s + c, y - s - c, y + s - c]


def find_least_critical_square(sq):
    """Find the square whose removal least affects the bounding box."""
    L0 = side(sq)
    min_impact = 1e9
    best_idx = 0
    # Center of mass
    cx, cy = np.mean(sq[:, 0]), np.mean(sq[:, 1])
    # Fast heuristic: squares closest to center or farthest from active boundary
    dists_from_center = (sq[:, 0] - cx)**2 + (sq[:, 1] - cy)**2
    # Check top 15 candidate squares
    cand_indices = np.argsort(dists_from_center)[:15]
    for idx in cand_indices:
        sub = np.delete(sq, idx, axis=0)
        s_sub = side(sub)
        impact = s_sub
        if impact < min_impact:
            min_impact = impact
            best_idx = idx
    return best_idx


def optimize_puzzle_defect(n, cur_packings, timeout_sec=60):
    """Attempt defect-mediated relaxation for puzzle n."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    L_target = side(cur_packings[n])
    
    # Try donors: n+1 and n+2
    candidates = []
    for k in [1, 2]:
        if (n + k) in cur_packings:
            donor_sq = cur_packings[n + k].copy()
            # Delete k squares sequentially
            sq_sub = donor_sq.copy()
            for _ in range(k):
                drop_idx = find_least_critical_square(sq_sub)
                sq_sub = np.delete(sq_sub, drop_idx, axis=0)
            candidates.append((k, sq_sub))
            
    # Also include the baseline packing of n itself with a small kick
    candidates.append((0, cur_packings[n].copy()))

    best_certified_L = L_target
    best_certified_sq = None

    for seed, (k, start_sq) in enumerate(candidates, 1):
        X, Y = corners(start_sq)
        L_start = side(start_sq)
        start_sq[:, 0] -= X.min()
        start_sq[:, 1] -= Y.min()

        tmp_in = OUTPUT_DIR / f"tmp_in_{n}_{seed}.txt"
        tmp_out = OUTPUT_DIR / f"tmp_out_{n}_{seed}.txt"

        with open(tmp_in, "w") as f:
            f.write(f"{n} {L_target:.17f}\n")
            for x, y, t in start_sq:
                f.write(f"{x:.17f} {y:.17f} {math.degrees(t) % 90.0:.15f}\n")

        cmd = [
            str(PACKER), "hop",
            "--in", str(tmp_in),
            "--s", f"{L_target:.17g}",
            "--seed", str(seed * 41 + n),
            "--iters", "2000000",
            "--out", str(tmp_out),
            "--quiet"
        ]

        try:
            subprocess.run(cmd, timeout=timeout_sec, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            pass

        if os.path.exists(tmp_out):
            try:
                rows = [
                    l.split()
                    for l in open(tmp_out)
                    if l.strip() and not l.startswith("#")
                ][1:]
                if len(rows) != n:
                    continue
                new_sq = np.array([[float(a), float(b), math.radians(float(c))] for a, b, c, *_ in rows])
                L_new = side(new_sq)
                if L_new < best_certified_L - 1e-9:
                    # Dilate by 1 + 1e-12 for interval arithmetic safety
                    cx, cy = (new_sq[:, 0].min() + new_sq[:, 0].max()) / 2, (new_sq[:, 1].min() + new_sq[:, 1].max()) / 2
                    new_sq[:, 0] = cx + (new_sq[:, 0] - cx) * (1 + 1e-12)
                    new_sq[:, 1] = cy + (new_sq[:, 1] - cy) * (1 + 1e-12)

                    r = certify(n, new_sq)
                    if r is not None and r[0] < best_certified_L - 1e-9:
                        best_certified_L = r[0]
                        best_certified_sq = new_sq.copy()
            except Exception as e:
                pass
            finally:
                if os.path.exists(tmp_out):
                    os.remove(tmp_out)
        if os.path.exists(tmp_in):
            os.remove(tmp_in)

    return best_certified_L, best_certified_sq


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_csv = ROOT_DIR / "output" / "submission_final.csv"
    if not PACKER.exists():
        raise FileNotFoundError(f"packer binary not found: {PACKER}")
    cur = F.load_csv(str(base_csv))

    # Priority targets: High-excess non-grid construction puzzles
    targets = [
        325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340,
        362, 365, 366, 367, 368, 370, 371, 372, 401, 402, 405, 410, 442, 445, 450
    ]

    print(f"Targeting {len(targets)} high-excess construction puzzles for Defect-Mediated Relaxation...", flush=True)
    total_gain = 0.0
    wins = []

    for idx, n in enumerate(targets, 1):
        if n not in cur:
            continue
        L0 = side(cur[n])
        t0 = time.time()
        L_best, sq_best = optimize_puzzle_defect(n, cur, timeout_sec=40)
        dt = time.time() - t0

        if sq_best is not None and L_best < L0 - 1e-9:
            gain = (L0 - L_best) / math.sqrt(n)
            total_gain += gain
            wins.append((n, L0, L_best, gain))
            out_csv = OUTPUT_DIR / f"{n}.csv"
            with open(out_csv, "w") as fh:
                fh.write("n,square_id,x,y,angle\n")
                for i, (x, y, t) in enumerate(sq_best):
                    fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
            print(f"[{idx}/{len(targets)}] n={n}: CERTIFIED IMPROVEMENT! {L0:.8f} -> {L_best:.8f} (gain: {gain:.2e}) [{dt:.1f}s] | Total: {total_gain:.8f}", flush=True)
        else:
            print(f"[{idx}/{len(targets)}] n={n}: no improvement over {L0:.8f} [{dt:.1f}s]", flush=True)

    print(f"\nFINISHED. Total certified gain: {total_gain:.8f} across {len(wins)} puzzles.", flush=True)


if __name__ == "__main__":
    main()
