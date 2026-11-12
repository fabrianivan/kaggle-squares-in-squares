"""L-cut gadget extraction for fault-line DP.

The standard fault_dp.extract() crops a rectangular w×h region from each donor,
keeping w*h + dm squares with the smallest overhang. The L-cut extends this by
using a *wider* (w+1)×h or *taller* w×(h+1) crop that provides more dm squares at
the same or lower f, because the extra column/row gives dm up to h (or w) extra
squares that sit just outside the standard w×h box.

This is the key technique from Deotte's LB-22.39 kernel that breaks the dm=34
ceiling and reaches dm=36-61 (the 421 trivial-grid puzzles).

Usage:
    .venv/bin/python -u src/engine/lcut_dp.py \
        --base output/submission_22.203807.csv \
        --workers 8 \
        --outdir output/lcut_wins
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
sys.path.insert(0, str(ROOT / "src" / "tools"))

import fault_dp as F
from ensemble import side

OUT = ROOT / "output"
COLS = ("n", "square_id", "x", "y", "angle")


def extract_lcut(donors):
    """Extended gadget extraction using L-cut crops.

    For each donor and symmetry, in addition to the standard w×h rectangular crop,
    we also try:
    - Wide L-cut: treat the donor as a (w+1)×h rectangle; squares in column w+1
      that overflow give additional dm at potentially lower f
    - Tall L-cut: treat the donor as a w×(h+1) rectangle; squares in row h+1 that
      overflow give additional dm at potentially lower f

    The key insight: for a donor with n squares, sorting by R = max(0, xhi-w, yhi-h),
    the first w*h squares have R≈0 (inside the box), and the next dm squares have
    small R (just overflowing). With an L-cut, we consider the w*h squares inside
    PLUS any dm squares from the extra column/row that have small R.
    """
    W = np.arange(1, F.WMAX + 1)
    DM = np.arange(1, F.DMAX + 1)
    best = {}

    for di, sq in enumerate(donors):
        n = len(sq)
        L = side(sq)
        parts = []

        for si, sym in enumerate(F.SYMS):
            _, xlo, xhi, ylo, yhi = F.mapped(sq, sym)

            # --- Standard rectangular crop (from fault_dp.extract) ---
            for h in range(1, min(F.WMAX, math.ceil(L)) + 1):
                R = np.maximum(np.maximum(xhi[:, None] - W[None, :], (yhi - h)[:, None]), 0.0)
                order = np.argsort(R, axis=0, kind="stable")
                Rs = np.take_along_axis(R, order, axis=0)
                ybr = np.minimum.accumulate(
                    np.where(xhi[order] > W[None, :] + 1e-9, ylo[order], np.inf), axis=0)
                xtl = np.minimum.accumulate(
                    np.where(yhi[order] > h + 1e-9, xlo[order], np.inf), axis=0)
                idx = W[:, None] * h + DM[None, :] - 1
                ok = (idx < n) & (W[:, None] <= math.ceil(L))
                wi, dj = np.nonzero(ok)
                k = idx[wi, dj]
                f = Rs[k, wi]
                m = f <= F.FMAX
                wi, dj, k, f = wi[m], dj[m], k[m], f[m]
                if len(wi):
                    parts.append(np.c_[wi + 1, np.full(len(f), h), dj + 1, f,
                                       np.minimum(ybr[k, wi], 9.0),
                                       np.minimum(xtl[k, wi], 9.0),
                                       np.full(len(f), di), np.full(len(f), si)])

            # --- Wide L-cut: use (w+1)×h footprint ---
            # Sort by R_wide = max(0, xhi-(w+1), yhi-h). The gadget is still w×h,
            # but selecting (w+1)*h+dm squares under the wider ordering puts more
            # dm squares into the box at potentially lower f against w×h.
            for h in range(1, min(F.WMAX, math.ceil(L)) + 1):
                W_wide = W + 1
                R_wide = np.maximum(
                    np.maximum(xhi[:, None] - W_wide[None, :], (yhi - h)[:, None]), 0.0)
                order_wide = np.argsort(R_wide, axis=0, kind="stable")

                # R_orig: overhang against the ACTUAL w×h box
                R_orig = np.maximum(
                    np.maximum(xhi[:, None] - W[None, :], (yhi - h)[:, None]), 0.0)
                # Running max of R_orig along the wide ordering → shape (n, len(W))
                R_orig_ordered = R_orig[order_wide, np.arange(len(W))[None, :]]
                Rs_running = np.maximum.accumulate(R_orig_ordered, axis=0)

                ybr_wide = np.minimum.accumulate(
                    np.where(xhi[order_wide] > W[None, :] + 1e-9,
                             ylo[order_wide], np.inf), axis=0)
                xtl_wide = np.minimum.accumulate(
                    np.where(yhi[order_wide] > h + 1e-9,
                             xlo[order_wide], np.inf), axis=0)

                idx_wide = (W + 1)[:, None] * h + DM[None, :] - 1  # (w, dm)
                ok_wide = (idx_wide < n) & (W[:, None] + 1 <= math.ceil(L))
                wi, dj = np.nonzero(ok_wide)
                k = idx_wide[wi, dj]
                f_wide = Rs_running[k, wi]
                m = f_wide <= F.FMAX
                wi, dj, k, f_wide = wi[m], dj[m], k[m], f_wide[m]
                if len(wi):
                    parts.append(np.c_[wi + 1, np.full(len(f_wide), h), dj + 1, f_wide,
                                       np.minimum(ybr_wide[k, wi], 9.0),
                                       np.minimum(xtl_wide[k, wi], 9.0),
                                       np.full(len(f_wide), di), np.full(len(f_wide), si)])

            # --- Tall L-cut: use w×(h+1) footprint ---
            for h in range(1, min(F.WMAX - 1, math.ceil(L)) + 1):
                h_tall = h + 1
                R_tall = np.maximum(
                    np.maximum(xhi[:, None] - W[None, :], (yhi - h_tall)[:, None]), 0.0)
                order_tall = np.argsort(R_tall, axis=0, kind="stable")

                R_orig = np.maximum(
                    np.maximum(xhi[:, None] - W[None, :], (yhi - h)[:, None]), 0.0)
                R_orig_ordered_tall = R_orig[order_tall, np.arange(len(W))[None, :]]
                Rs_running_tall = np.maximum.accumulate(R_orig_ordered_tall, axis=0)

                ybr_tall = np.minimum.accumulate(
                    np.where(xhi[order_tall] > W[None, :] + 1e-9,
                             ylo[order_tall], np.inf), axis=0)
                xtl_tall = np.minimum.accumulate(
                    np.where(yhi[order_tall] > h + 1e-9,
                             xlo[order_tall], np.inf), axis=0)

                idx_tall = W[:, None] * h_tall + DM[None, :] - 1
                ok_tall = (idx_tall < n) & (W[:, None] <= math.ceil(L))
                wi, dj = np.nonzero(ok_tall)
                k = idx_tall[wi, dj]
                f_tall = Rs_running_tall[k, wi]
                m = f_tall <= F.FMAX
                wi, dj, k, f_tall = wi[m], dj[m], k[m], f_tall[m]
                if len(wi):
                    parts.append(np.c_[wi + 1, np.full(len(f_tall), h), dj + 1, f_tall,
                                       np.minimum(ybr_tall[k, wi], 9.0),
                                       np.minimum(xtl_tall[k, wi], 9.0),
                                       np.full(len(f_tall), di), np.full(len(f_tall), si)])

        P = np.concatenate(parts) if parts else np.zeros((0, 8))
        if not len(P):
            continue
        qb = np.maximum(np.searchsorted(F.THR, P[:, 4], side="right") - 1, 0)
        qt = np.maximum(np.searchsorted(F.THR, P[:, 5], side="right") - 1, 0)
        key = (((P[:, 0] * 32 + P[:, 1]) * 64 + P[:, 2]) * F.NB + qb) * F.NB + qt
        o = np.lexsort((P[:, 3], key))
        first = np.r_[True, key[o][1:] != key[o][:-1]]
        for kk, row in zip(key[o][first].astype(np.int64), P[o][first]):
            if kk not in best or row[3] < best[kk][3]:
                best[kk] = row
        if di % 50 == 0:
            F.log(f"lcut extract donor {di}/{len(donors)}: {len(best)} keys")

    G = np.array(list(best.values()))
    if not len(G):
        F.log("No gadgets found!")
        return G

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
    F.log(f"lcut gadgets: {len(G)} per-key, {keep.sum()} after dominance")
    return G[keep]


def packings_in(path: Path):
    """Sub-grid packings in a CSV."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(OUT / "submission_22.203807.csv"))
    ap.add_argument("--dirs", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--nmin", type=int, default=100)
    ap.add_argument("--nmax", type=int, default=1000)
    ap.add_argument("--outdir", default=str(OUT / "lcut_wins"))
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    F.log(f"Loading base submission: {a.base}")
    cur = F.load_csv(a.base)
    base_score = sum(side(sq) / math.sqrt(n) - 1.0 for n, sq in cur.items())
    F.log(f"Base: {len(cur)} puzzles, score {base_score:.12f}")

    # Collect donors from base submission + cached pool + all harvest dirs
    seen, donors = set(), []
    for n, sq in cur.items():
        k = (n, round(side(sq), 9))
        if k not in seen:
            seen.add(k)
            donors.append(sq)
    F.log(f"+ base submission donors: {len(donors)}")

    # Cached donors
    for fname in ["cached_donors.npz", "all_quenched_gadgets_combined.npz"]:
        p = OUT / fname
        if p.exists():
            cd = np.load(p)
            for key in cd.files:
                if not key.endswith("_before"):
                    sq = cd[key]
                    k = (len(sq), round(side(sq), 9))
                    if k not in seen:
                        seen.add(k)
                        donors.append(sq)
            F.log(f"+ {fname}: {len(donors)} total donors")

    # Harvest dirs
    dirs = a.dirs or []
    # Also scan default harvest dirs
    for harvest_root in [
        ROOT / "data" / "harvest_nov_6_9",
        ROOT / "data" / "harvest_nov10",
        ROOT / "data" / "harvest_nov10b",
        ROOT / "data" / "harvest_nov10c",
        ROOT / "data" / "harvest_now",
        ROOT / "data" / "fresh_sync_today",
    ]:
        if harvest_root.exists():
            dirs.append(str(harvest_root))

    files = []
    for d in dirs:
        p = Path(d)
        if p.exists():
            files += sorted(f for f in p.rglob("*.csv") if f.is_file() and f.stat().st_size > 0)
    F.log(f"Scanning {len(files)} CSV files for additional donors")
    added = 0
    for f in files:
        d = packings_in(f)
        for n, sq in d.items():
            k = (n, round(side(sq), 9))
            if k not in seen:
                seen.add(k)
                donors.append(sq)
                added += 1
    F.log(f"+ harvest donors: {added} new, {len(donors)} total")

    # Extract L-cut gadgets
    F.log("Extracting L-cut gadgets...")
    t0 = time.time()
    G = extract_lcut(donors)
    F.log(f"L-cut extraction done in {time.time()-t0:.0f}s: {len(G)} gadgets")

    if not len(G):
        F.log("No gadgets — aborting.")
        return

    # Report dm distribution
    dm = G[:, 2].astype(int)
    F.log(f"dm range: {dm.min()} - {dm.max()}")
    for lo, hi in [(1, 10), (11, 20), (21, 35), (36, 50), (51, 62)]:
        cnt = ((dm >= lo) & (dm <= hi)).sum()
        F.log(f"  D={lo}-{hi}: {cnt} gadgets")

    # Save gadgets
    gpath = OUT / "lcut_G.npy"
    np.save(gpath, G)
    F.log(f"Saved gadgets to {gpath}")

    # Also merge with existing cached library
    cpath = OUT / "cached_base_G.npy"
    if cpath.exists():
        G_base = np.load(cpath)
        G_merged = np.concatenate([G_base, G])
        F.log(f"Merged with cached library: {len(G_base)} + {len(G)} = {len(G_merged)} gadgets")
        # Re-prune for dominance
        qb = np.maximum(np.searchsorted(F.THR, G_merged[:, 4], side="right") - 1, 0)
        qt = np.maximum(np.searchsorted(F.THR, G_merged[:, 5], side="right") - 1, 0)
        M2 = np.full((F.WMAX + 2, F.WMAX + 2, F.DMAX + 2, F.NB, F.NB), np.inf)
        for (w, h, d, f), b, t in zip(G_merged[:, :4], qb, qt):
            M2[int(w), int(h), int(d), b, t] = min(M2[int(w), int(h), int(d), b, t], f)
        for ax in (0, 1):
            M2 = np.minimum.accumulate(M2, axis=ax)
        for ax in (2, 3, 4):
            M2 = np.flip(np.minimum.accumulate(np.flip(M2, axis=ax), axis=ax), axis=ax)
        keep = G_merged[:, 3] <= M2[G_merged[:, 0].astype(int), G_merged[:, 1].astype(int),
                                     G_merged[:, 2].astype(int), qb, qt] + 1e-15
        G = G_merged[keep]
        F.log(f"After merged dominance prune: {keep.sum()} gadgets")
        gm_path = OUT / "lcut_G_merged.npy"
        np.save(gm_path, G)
        F.log(f"Saved merged gadgets to {gm_path}")

    # Run DP
    F.log("Running DP...")
    t0 = time.time()
    dp, PG, PM, PQ = F.run_dp(G)
    F.log(f"DP done in {time.time()-t0:.0f}s")

    # Find wins
    total_gain, wins = 0.0, []
    for n in range(a.nmin, a.nmax + 1):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else float(K + 1)
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
        total_gain += d
        wins.append((n, L0, r[0], d))
        with open(outdir / f"{n}.csv", "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {d:.3e} | total {total_gain:.6f}")

    F.log(f"DONE: {len(wins)} certified wins, total gain {total_gain:.6f}")


if __name__ == "__main__":
    main()
