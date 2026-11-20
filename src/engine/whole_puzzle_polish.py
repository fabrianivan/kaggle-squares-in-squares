"""Squeeze each finished packing as a whole with fq, instead of only its gadgets.

A ladder composition is assembled from a cropped gadget plus two rigid lattice continents, so the finished packing
can still hold slack that no gadget-level move can see: the continents are locked to the integer lattice even
where the fault leaves room. This runs evand's fq over the entire packing (square mode) from several loosen/kick
settings, and keeps a result only when the official interval metric certifies a strictly smaller side.

    .venv/bin/python -u src/engine/whole_puzzle_polish.py --workers 7 --rounds 6 --nmin 100
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(ROOT / "src" / "engine"))

from ensemble import certify, side  # noqa: E402
from fq_pool import FQPool  # noqa: E402

OUT = ROOT / "output"


def load_base(path: Path):
    df = pd.read_csv(path)
    out = {}
    for n, g in df.groupby("n"):
        g = g.sort_values("square_id")
        out[int(n)] = g[["x", "y", "angle"]].to_numpy(float)
    return out


def polish_one(pool: FQPool, n: int, sq: np.ndarray, rounds: int, deadline: float):
    """Best fq result for one puzzle, or None. Tries a rigid squeeze then progressively looser/kicked restarts."""
    L0 = side(sq)
    best, Lbest = None, L0
    settings = [
        "--finish --loosen 1.0",
        "--finish --loosen 1.0005",
        "--finish --loosen 1.002 --kick 0.002",
        "--finish --loosen 1.005 --kick 0.005",
        "--finish --loosen 1.0 --round-r0 0.05",
        "--finish --loosen 1.01 --kick 0.01 --round-r0 0.1",
    ]
    seed_sq = sq
    for r in range(rounds):
        args = settings[r % len(settings)] + f" --deadline {deadline:.1f} --seed {r+1}"
        L, cand, info = pool.quench(seed_sq, extra_args=args, timeout=deadline * 3 + 20)
        if L is None or cand is None or len(cand) != n or not np.isfinite(L):
            continue
        if L < Lbest - 1e-13:
            best, Lbest = cand, L
            seed_sq = cand
    return best, Lbest, L0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(OUT / "submission_22.233377.csv"))
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--deadline", type=float, default=8.0)
    ap.add_argument("--nmin", type=int, default=100)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--outdir", default=str(OUT / "polish_wins"))
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = load_base(Path(a.base))
    targets = []
    for n in range(a.nmin, a.nmax + 1):
        if n not in base:
            continue
        k = math.isqrt(n)
        if k * k == n:                                   # a perfect square is already exact
            continue
        L0 = side(base[n])
        if L0 >= math.ceil(math.sqrt(n)) - 1e-12:        # a grid packing has no slack fq can find
            continue
        targets.append(n)
    print(f"polishing {len(targets)} puzzles with {a.workers} fq workers, "
          f"{a.rounds} rounds x {a.deadline}s", flush=True)

    pool = FQPool(num_workers=a.workers)
    wins, t0, done = {}, time.time(), 0
    lock = __import__("threading").Lock()

    def work(n):
        nonlocal done
        cand, L, L0 = polish_one(pool, n, base[n], a.rounds, a.deadline)
        with lock:
            done += 1
            if done % 25 == 0:
                print(f"  [{done}/{len(targets)}] {time.time()-t0:.0f}s, {len(wins)} raw wins", flush=True)
        if cand is None or L >= L0 - 1e-13:
            return
        r = certify(n, cand)
        if r is None:
            c = (cand[:, :2].min(0) + cand[:, :2].max(0)) / 2
            for eps in (1e-12, 1e-11):
                s2 = cand.copy()
                s2[:, :2] = c + (cand[:, :2] - c) * (1 + eps)
                r = certify(n, s2)
                if r:
                    break
        if r is None or r[0] >= L0 - 1e-13:
            return
        with lock:
            wins[n] = (L0, r[0])
        with open(outdir / f"{n}.csv", "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
        print(f"  CERTIFIED n={n}: {L0:.9f} -> {r[0]:.9f}  gain {(L0-r[0])/math.sqrt(n):.3e}", flush=True)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, targets))
    pool.close()

    total = sum((a_ - b) / math.sqrt(n) for n, (a_, b) in wins.items())
    print(f"\nDONE {len(wins)} certified wins, total gain {total:.9f} in {time.time()-t0:.0f}s", flush=True)
    (OUT / "polish_summary.json").write_text(json.dumps(
        {str(n): dict(L0=v[0], L=v[1]) for n, v in sorted(wins.items())}, indent=1))


if __name__ == "__main__":
    main()
