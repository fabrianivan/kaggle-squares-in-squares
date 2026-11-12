"""Mega Multi-Key Gadget DP Solver.

Integrates ALL quenched gadgets from all runs:
- tmp/quench_out/gadgets_quenched.npz
- tmp/quench_med_out/gadgets_quenched.npz
- tmp/quench_large_out/gadgets_quenched.npz
- tmp/quench_new_out/gadgets_quenched.npz
- tmp/deep_quench_out/gadgets_quenched.npz

Caches G_base for instant reruns (<5 seconds).
"""

from __future__ import annotations
import os
import sys
import math
import pickle
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))

import fault_dp as F
from ensemble import side

def main():
    base_csv = os.path.join(ROOT, "output/submission_final.csv")
    extra_csvs = [
        os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit/couzo.csv"),
        os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit/couzo_big.csv"),
    ]
    quench_files = [
        os.path.join(ROOT, "tmp/quench_out/gadgets_quenched.npz"),
        os.path.join(ROOT, "tmp/quench_med_out/gadgets_quenched.npz"),
        os.path.join(ROOT, "tmp/quench_large_out/gadgets_quenched.npz"),
        os.path.join(ROOT, "tmp/quench_new_out/gadgets_quenched.npz"),
        os.path.join(ROOT, "tmp/deep_quench_out/gadgets_quenched.npz"),
    ]
    outdir = os.path.join(ROOT, "tmp/mega_quench_dp_out")
    cache_file = os.path.join(ROOT, "tmp/g_base_cache.pkl")
    os.makedirs(outdir, exist_ok=True)

    if os.path.exists(cache_file):
        F.log("Loading G_base and donors from cache...")
        with open(cache_file, "rb") as fh:
            donors, G_base = pickle.load(fh)
        F.log(f"Cache loaded: {len(donors)} donors, {len(G_base)} base gadgets.")
    else:
        seen, donors = set(), []
        for p in [base_csv] + extra_csvs:
            if not os.path.exists(p): continue
            for n, sq in F.load_csv(p).items():
                k = (n, round(side(sq), 9))
                if k not in seen:
                    seen.add(k)
                    donors.append(sq)

        F.log(f"{len(donors)} base donors loaded")
        G_base = F.extract(donors)
        with open(cache_file, "wb") as fh:
            pickle.dump((donors, G_base), fh)
        F.log("Saved G_base to cache.")

    # Load all improved gadgets
    improved_gadgets = []
    quench_sources = 0
    for qf in quench_files:
        if not os.path.exists(qf): continue
        quench_sources += 1
        data = np.load(qf)
        for key in data.files:
            if not key.endswith("_before"):
                improved_gadgets.append(data[key])

    F.log(f"Loaded {len(improved_gadgets)} improved quenched gadgets across {quench_sources} archives")

    # Extract quenched gadgets
    G_quenched = F.extract(improved_gadgets)
    G_quenched[:, 6] += len(donors)

    G_all = np.concatenate([G_base, G_quenched])
    donors_all = donors + improved_gadgets

    F.log(f"Running full DP on unified table of {len(G_all)} gadgets...")
    dp, PG, PM, PQ = F.run_dp(G_all)
    F.log("DP completed. Searching for ladder compositions across n=325..1000...")

    cur = F.load_csv(base_csv)
    total_gain = 0.0
    improvements = []

    for n in range(325, 1001):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0: continue

        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
        if f is None or K + f + 2 * F.E >= L0 - 1e-6:
            continue

        r = F.certify_ladder(n, F.compose(K, D, f, links, G_all, donors_all))
        if r is None or r[0] >= L0 - 1e-9:
            continue

        d = (L0 - r[0]) / math.sqrt(n)
        total_gain += d
        improvements.append((n, L0, r[0], d))

        cand_file = os.path.join(outdir, f"{n}.csv")
        with open(cand_file, "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")

        F.log(f"  >>> CERTIFIED IMPROVEMENT n={n}: {L0:.9f} -> {r[0]:.9f}, gain +{d:.2e} | cumulative: +{total_gain:.8f}")

    F.log(f"\n==========================================")
    F.log(f"Mega Quench DP Finished: {len(improvements)} puzzles improved!")
    F.log(f"Total verified score drop: -{total_gain:.10f}")
    F.log(f"==========================================")

if __name__ == "__main__":
    main()
