"""Quench the gadget keys that bind the most score, starting from several donor basins each.

Earlier campaigns quenched only the single lowest-f crop of each key, so a key whose best crop sits in a jammed
basin never moved. This one seeds every key from up to `--starts` structurally distinct crops (different donors
or symmetries), and alternates three move classes: soft-to-rigid corner-radius annealing, global kicks, and kicks
aimed at just the squares that stick out past the w x h box. Improved gadgets are written to an npz the DP can
pick up.

    .venv/bin/python -u src/engine/quench_campaign.py --keys 64 --budget 180 --procs 8
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))

import fault_dp as F  # noqa: E402
import skeleton as S  # noqa: E402

OUT = ROOT / "output"


def worker(job):
    """Anneal one key from several starts; return the best layout found."""
    key, starts, budget = job
    w, h, dm = (int(v) for v in key)
    need = w * h + dm
    t0 = time.time()

    f0 = min(S.overhang(s, w, h) for s in starts)
    best, fbest = starts[0], S.overhang(starts[0], w, h)
    for s in starts[1:]:
        fs = S.overhang(s, w, h)
        if fs < fbest:
            best, fbest = s, fs

    # one rigid squeeze from every start, so a worse-f basin still gets its chance
    for s in starts:
        cand, f = S.quench(s, w, h, loosen=1.0, round_r0=0.0)
        if f < fbest and len(cand) == need:
            best, fbest = cand, f

    r0_sched = [0.0, 0.15, 0.22, 0.10, 0.18, 0.05, 0.12, 0.0]
    k = 0
    per_start = budget / max(1, len(starts))
    for si, s in enumerate(starts):
        anchor, fanchor = s, S.overhang(s, w, h)
        deadline = t0 + per_start * (si + 1)
        while time.time() < deadline:
            k += 1
            mode = k % 3
            r0 = r0_sched[k % len(r0_sched)]
            loosen = 1.0 + 0.01 * (k % 5)
            if mode == 0:                                   # global kick
                cand, f = S.quench(anchor, w, h, loosen=loosen, kick=0.004 * (1 + k % 4),
                                   seed=k, round_r0=r0)
            elif mode == 1:                                 # soft-to-rigid, no kick
                cand, f = S.quench(anchor, w, h, loosen=loosen, kick=0.0, seed=k, round_r0=r0, outer=80)
            else:                                           # kick only the protruding squares
                idx = np.concatenate([S.edge_squares(anchor, w, h, "right", 6),
                                      S.edge_squares(anchor, w, h, "top", 6)])
                kicked = S.kick(anchor, 0.02, k, idx=idx, angle_deg=3.0)
                cand, f = S.quench(kicked, w, h, loosen=1.0, kick=0.0, seed=k, round_r0=r0)
            if len(cand) != need or not np.isfinite(f):
                continue
            if f < fbest - 1e-12:
                best, fbest = cand, f
            if f < fanchor - 1e-12:
                anchor, fanchor = cand, f

    # final tight rigid polish
    for seed in (997, 998, 999):
        cand, f = S.quench(best, w, h, loosen=1.0001, kick=0.0, seed=seed, round_r0=0.0, outer=100)
        if f < fbest - 1e-12 and len(cand) == need:
            best, fbest = cand, f
    return key, float(f0), float(fbest), best, k


def collect_starts(G, donors, key, max_starts):
    """Distinct starting crops for a key, cheapest overhang first, one per (donor, symmetry) basin."""
    w, h, dm = (int(v) for v in key)
    rows = np.where((G[:, :3].astype(int) == np.array([w, h, dm])).all(1))[0]
    if not len(rows):
        return []
    rows = rows[np.argsort(G[rows, 3])]
    starts, seen = [], set()
    for ri in rows:
        di, si = int(G[ri, 6]), int(G[ri, 7])
        if (di, si) in seen:
            continue
        seen.add((di, si))
        if di >= len(donors):
            continue
        sq = F.crop(donors[di], si, w, h, dm)[0]
        if len(sq) != w * h + dm:
            continue
        f = S.overhang(sq, w, h)
        if any(abs(f - S.overhang(s, w, h)) < 1e-9 for s in starts):
            continue
        starts.append(sq)
        if len(starts) >= max_starts:
            break
    return starts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", type=int, default=64)
    ap.add_argument("--budget", type=float, default=180.0)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--starts", type=int, default=4)
    ap.add_argument("--skip-quenched", action="store_true", help="skip keys an earlier campaign already improved")
    ap.add_argument("--library", default=str(OUT / "lib_G_all.npy"))
    ap.add_argument("--out", default=str(OUT / "campaign_gadgets.npz"))
    a = ap.parse_args()

    import fine_bin_dp as FB  # noqa: E402  (same dir)
    donors, _ = FB.load_donors()
    G = np.load(a.library)
    F.log(f"library {Path(a.library).name}: {len(G)} gadgets, {len(donors)} donors")

    rank = json.loads((OUT / "leverage_rank.json").read_text())
    reservoir = dict(np.load(OUT / "all_quenched_gadgets_combined.npz"))

    jobs = []
    for key, price, cnt, fb, was_done in rank:
        if len(jobs) >= a.keys:
            break
        if a.skip_quenched and was_done:
            continue
        starts = collect_starts(G, donors, key, a.starts)
        ks = f"{key[0]}_{key[1]}_{key[2]}"
        if ks in reservoir:                       # the best known layout for this key so far
            starts = [reservoir[ks]] + starts
        if not starts:
            continue
        jobs.append((tuple(key), starts[:a.starts + 1], a.budget))

    F.log(f"quenching {len(jobs)} keys, {a.budget:.0f}s each, {a.procs} processes, "
          f"{sum(len(j[1]) for j in jobs)} starting layouts")
    t0 = time.time()
    with Pool(a.procs) as pool:
        res = pool.map(worker, jobs)
    F.log(f"campaign finished in {time.time()-t0:.0f}s")

    improved = {}
    for key, f0, f1, sq, k in res:
        tag = "  IMPROVED" if f1 < f0 - 1e-9 else ""
        F.log(f"{key[0]}x{key[1]}+{key[2]}: f {f0:.9f} -> {f1:.9f} ({k} quenches){tag}")
        if f1 < f0 - 1e-9:
            improved[f"{key[0]}_{key[1]}_{key[2]}"] = sq

    if not improved:
        F.log("no gadget improved")
        return
    np.savez(a.out, **improved)
    F.log(f"wrote {len(improved)} improved gadgets to {a.out}")


if __name__ == "__main__":
    main()
