"""Combined Multi-Key Gadget DP Solver.

Merges all quenched gadgets from all three quench runs:
- tmp/quench_out/gadgets_quenched.npz (20 gadgets)
- tmp/quench_med_out/gadgets_quenched.npz (18 gadgets)
- tmp/quench_large_out/gadgets_quenched.npz (4 gadgets)

Runs full DP ladder search across all 1000 puzzles and certifies every improvement.
"""

import os
import sys
import math
import numpy as np

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
    ]
    outdir = os.path.join(ROOT, "tmp/quench_combined_out")
    os.makedirs(outdir, exist_ok=True)

    seen, donors = set(), []
    for p in [base_csv] + extra_csvs:
        if not os.path.exists(p): continue
        for n, sq in F.load_csv(p).items():
            k = (n, round(side(sq), 9))
            if k not in seen:
                seen.add(k)
                donors.append(sq)

    F.log(f"{len(donors)} base donors loaded")

    # Load all improved gadgets
    improved_gadgets = []
    for qf in quench_files:
        if not os.path.exists(qf): continue
        data = np.load(qf)
        for key in data.files:
            if not key.endswith("_before"):
                improved_gadgets.append(data[key])

    F.log(f"Loaded {len(improved_gadgets)} improved quenched gadgets")

    # Extract base gadgets
    G_base = F.extract(donors)

    # Extract quenched gadgets
    G_quenched = F.extract(improved_gadgets)
    G_quenched[:, 6] += len(donors)

    G_all = np.concatenate([G_base, G_quenched])
    donors_all = donors + improved_gadgets

    F.log(f"Running full DP on unified table of {len(G_all)} gadgets...")
    dp, PG, PM, PQ = F.run_dp(G_all)
    F.log("DP completed. Searching for improvements across n=325..1000...")

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

        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {d:.2e} | total {total_gain:.6f}")

    F.log(f"DONE total certified gain: {total_gain:.8f} on {len(improvements)} puzzles")

if __name__ == "__main__":
    main()
