"""Rebuild the gadget library with freshly harvested packings as donors, then rerun the fault-line DP.

A public file whose total score is worse than ours can still contain a *crop* that beats every gadget we hold: the
DP only needs w x h + dm squares with a small overhang, not a good whole packing. So every harvested packing is
fed in as a donor, the gadget table is re-extracted in parallel, and the DP is asked for a cheaper chain for each
(K, D). Only compositions the official interval metric certifies below our current side are written out.

    .venv/bin/python -u src/engine/dp_with_harvest.py --dirs data/harvest_1106 --workers 8
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))

import fault_dp as F  # noqa: E402
from ensemble import side  # noqa: E402

OUT = ROOT / "output"
COLS = ("n", "square_id", "x", "y", "angle")


def packings_in(path: Path):
    """Sub-grid packings in a CSV: {n: squares}. Anything at or above the grid side is useless as a donor."""
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if not set(COLS) <= set(df.columns):
        return {}
    df = df[list(COLS)].apply(pd.to_numeric, errors="coerce").dropna()
    out = {}
    for n, g in df.groupby("n"):
        n = int(n)
        if not 1 <= n <= 3500 or len(g) != n:
            continue
        sq = g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
        if side(sq) < math.ceil(math.sqrt(n)) - 1e-9:
            out[n] = sq
    return out


def set_limits(fmax, thr):
    """Gadget overhang cap and tip-length bins, installed in this process (workers get them per job)."""
    F.FMAX = float(fmax)
    F.THR = np.asarray(thr, float)
    F.NB = len(F.THR)


def _chunk(args):
    donors, base_di, fmax, thr = args
    set_limits(fmax, thr)
    G = F.extract(donors)
    if len(G):
        G[:, 6] += base_di
    return G


def extract_parallel(donors, workers, fmax, thr):
    size = math.ceil(len(donors) / workers)
    jobs = [(donors[i:i + size], i, fmax, thr) for i in range(0, len(donors), size)]
    t0 = time.time()
    parts = []
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        for i, G in enumerate(pool.map(_chunk, jobs)):
            parts.append(G)
            F.log(f"  chunk {i+1}/{len(jobs)}: {len(G)} gadgets ({time.time()-t0:.0f}s)")
    G = np.concatenate([p for p in parts if len(p)])
    F.log(f"{len(G)} gadgets before global prune")

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
    F.log(f"{keep.sum()} gadgets after global prune ({time.time()-t0:.0f}s)")
    return G[keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(OUT / "submission_22.233377.csv"))
    ap.add_argument("--dirs", nargs="+", default=["data/harvest_1106"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--nmin", type=int, default=100)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--extra-gadgets", nargs="*", default=[])
    ap.add_argument("--fmax", type=float, default=0.97,
                    help="keep gadgets whose overhang is at most this; above 0.97 opens the regime that beats the "
                         "trivial grid on puzzles where f must sit just below 1")
    ap.add_argument("--thr", type=float, nargs="*", default=None,
                    help="tip-length bins; the default adds bins above 0.9 when --fmax does")
    ap.add_argument("--outdir", default=str(OUT / "dp_harvest_wins"))
    a = ap.parse_args()

    if a.thr:
        thr = a.thr
    elif a.fmax > 0.9:
        thr = [0.0, 0.3, 0.45, 0.6, 0.75, 0.85, 0.92, 0.96, 1.0, 1.05, 1.15, 1.3]
    else:
        thr = list(F.THR)
    set_limits(a.fmax, thr)
    F.log(f"FMAX={F.FMAX} THR={list(F.THR)}")

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cur = F.load_csv(a.base)
    seen, donors = set(), []
    for n, sq in cur.items():
        seen.add((n, round(side(sq), 9)))
        donors.append(sq)
    F.log(f"base {Path(a.base).name}: {len(donors)} donors")

    # the pool the previous sessions already built
    cd = np.load(OUT / "cached_donors.npz")
    for i in range(len(cd.files)):
        sq = cd[f"d_{i}"]
        k = (len(sq), round(side(sq), 9))
        if k not in seen:
            seen.add(k)
            donors.append(sq)
    F.log(f"+ cached pool -> {len(donors)} donors")

    res = dict(np.load(OUT / "all_quenched_gadgets_combined.npz"))
    for k_ in res:
        if not k_.endswith("_before"):
            donors.append(res[k_])
    for p in a.extra_gadgets:
        d = dict(np.load(p))
        for k_ in d:
            if not k_.endswith("_before"):
                donors.append(d[k_])
        F.log(f"+ {Path(p).name}: {len(d)} quenched gadgets")
    F.log(f"+ quenched gadgets -> {len(donors)} donors")

    files = []
    for d in a.dirs:
        p = ROOT / d if not Path(d).is_absolute() else Path(d)
        files += sorted(f for f in p.rglob("*.csv") if f.is_file() and f.stat().st_size > 0)
    F.log(f"scanning {len(files)} harvested CSVs for donors")
    added = 0
    for f in files:
        d = packings_in(f)
        new = 0
        for n, sq in d.items():
            k = (n, round(side(sq), 9))
            if k not in seen:
                seen.add(k)
                donors.append(sq)
                new += 1
        added += new
        if new:
            F.log(f"  {f.relative_to(ROOT)}: +{new} new donors")
    F.log(f"{added} new donors from the harvest; {len(donors)} total")

    G = extract_parallel(donors, a.workers, a.fmax, list(F.THR))
    np.save(OUT / f"harvest_G_fmax{a.fmax}.npy", G)

    F.log("running DP...")
    t0 = time.time()
    dp, PG, PM, PQ = F.run_dp(G)
    F.log(f"DP done in {time.time()-t0:.0f}s")

    total, wins = 0.0, []
    for n in range(a.nmin, a.nmax + 1):
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
            continue
        d = (L0 - r[0]) / math.sqrt(n)
        total += d
        wins.append((n, L0, r[0], d))
        with open(outdir / f"{n}.csv", "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {d:.3e} | total {total:.6f}")

    F.log(f"DONE {len(wins)} certified wins, total gain {total:.6f}")


if __name__ == "__main__":
    main()
