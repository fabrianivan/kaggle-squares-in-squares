"""Fault-line DP with a finer quantisation of the free tip lengths.

The seam test in fault_dp keeps only a 6-bin floor of each gadget's free tip lengths (Ybr / Xtl) and compares the
*bin's lower edge* against the next gadget's overhang. That floor can sit up to 0.3 below the true tip length, so
chains that really do fit are rejected and the DP settles for a larger f. Refining the bins keeps the test
conservative -- it still compares against a lower bound -- while admitting those chains, and every composition is
still certified by the official interval metric before it is kept.

    .venv/bin/python -u src/engine/fine_bin_dp.py [--step 0.05] [--workers 6] [--nmin 100]
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))

import fault_dp as F  # noqa: E402
from ensemble import side  # noqa: E402

OUT = ROOT / "output"
BASE_CSV = OUT / "submission_22.233377.csv"


def set_bins(thr) -> None:
    """Install a bin grid for the free tip lengths in both extract() and run_dp()."""
    F.THR = np.asarray(thr, dtype=float)
    F.NB = len(F.THR)


def make_bins(step: float) -> np.ndarray:
    return np.round(np.arange(0.0, 1.0, step), 10)


def _chunk(args):
    thr, donors, base_di = args
    set_bins(thr)
    G = F.extract(donors)
    if len(G):
        G[:, 6] += base_di
    return G


def dominance_prune(G: np.ndarray) -> np.ndarray:
    """Drop gadgets beaten on f by one that is no wider, no taller, holds as many extras and has longer tips."""
    qb = np.maximum(np.searchsorted(F.THR, G[:, 4], side="right") - 1, 0)
    qt = np.maximum(np.searchsorted(F.THR, G[:, 5], side="right") - 1, 0)
    M = np.full((F.WMAX + 2, F.WMAX + 2, F.DMAX + 2, F.NB, F.NB), np.inf)
    for (w, h, d, f), b, t in zip(G[:, :4], qb, qt):
        M[int(w), int(h), int(d), b, t] = min(M[int(w), int(h), int(d), b, t], f)
    for ax in (0, 1):
        M = np.minimum.accumulate(M, axis=ax)
    for ax in (2, 3, 4):
        M = np.flip(np.minimum.accumulate(np.flip(M, axis=ax), axis=ax), axis=ax)
    keep = G[:, 3] <= M[G[:, 0].astype(int), G[:, 1].astype(int), G[:, 2].astype(int), qb, qt] + 1e-15
    return G[keep]


def load_donors():
    cur = F.load_csv(str(BASE_CSV))
    cd = np.load(OUT / "cached_donors.npz")
    base_donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
    cur_donors = [cur[n] for n in sorted(cur) if n >= 325]
    res = dict(np.load(OUT / "all_quenched_gadgets_combined.npz"))
    q_sqs = [res[k] for k in res if not k.endswith("_before")]
    return base_donors + cur_donors + q_sqs, cur


def extract_fine(donors, thr, workers: int) -> np.ndarray:
    size = math.ceil(len(donors) / workers)
    jobs = [(thr, donors[i:i + size], i) for i in range(0, len(donors), size)]
    F.log(f"fine extract: {len(donors)} donors, {len(thr)} bins, {len(jobs)} workers")
    t0 = time.time()
    parts = []
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        for i, G in enumerate(pool.map(_chunk, jobs)):
            parts.append(G)
            F.log(f"  chunk {i+1}/{len(jobs)}: {len(G)} gadgets ({time.time()-t0:.0f}s)")
    G = np.concatenate([p for p in parts if len(p)])
    F.log(f"fine extract: {len(G)} gadgets before global prune")
    G = dominance_prune(G)
    F.log(f"fine extract: {len(G)} gadgets after global prune in {time.time()-t0:.0f}s")
    return G


def evaluate(G, donors, cur, nmin, nmax, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    F.log("running DP on the fine-bin library...")
    t0 = time.time()
    dp, PG, PM, PQ = F.run_dp(G)
    F.log(f"DP done in {time.time()-t0:.0f}s")

    total, wins, uncert = 0.0, [], []
    for n in range(nmin, nmax + 1):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G, K, D)
        if f is None or K + f + 2 * F.E >= L0 - 1e-9:
            continue
        try:
            sq = F.compose(K, D, f, links, G, donors)
        except AssertionError as e:
            F.log(f"n={n}: compose failed ({e})")
            continue
        r = F.certify_ladder(n, sq)
        if r is None or r[0] >= L0 - 1e-12:
            uncert.append((n, L0, K + f))
            continue
        d = (L0 - r[0]) / math.sqrt(n)
        total += d
        wins.append((n, L0, r[0], d))
        with open(outdir / f"{n}.csv", "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {d:.3e} | running total {total:.6f}")

    F.log(f"DONE: {len(wins)} certified wins, total gain {total:.6f}; {len(uncert)} candidates failed certification")
    return wins, uncert


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--nmin", type=int, default=100)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--outdir", default=str(OUT / "fine_bin_wins"))
    a = ap.parse_args()

    thr = make_bins(a.step)
    set_bins(thr)
    donors, cur = load_donors()
    cache = OUT / f"fine_G_step{a.step}.npy"
    if cache.exists():
        G = np.load(cache)
        F.log(f"reusing {cache.name}: {len(G)} gadgets")
    else:
        G = extract_fine(donors, thr, a.workers)
        np.save(cache, G)
    evaluate(G, donors, cur, a.nmin, a.nmax, Path(a.outdir))


if __name__ == "__main__":
    main()
