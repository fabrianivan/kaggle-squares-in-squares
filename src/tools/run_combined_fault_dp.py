"""Run full fault DP using all combined quenched gadgets across all donor pools."""

import math, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "alexchilton_starter_kit"))
import fault_dp as F
from ensemble import side


def main():
    base = "output/submission_final.csv"
    outdir = "output/combined_dp_run"
    os.makedirs(outdir, exist_ok=True)

    F.log("Loading cached donors and G...")
    G_base = np.load("output/cached_base_G.npy")
    cd = np.load("output/cached_donors.npz")
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
    F.log(f"Loaded {len(donors)} base donors")

    # Load all quenched gadgets
    npz_data = np.load("output/all_quenched_gadgets_combined.npz")
    quenched_sqs = [npz_data[k] for k in npz_data.files if not k.endswith("_before")]
    F.log(f"Loaded {len(quenched_sqs)} quenched gadgets")

    Gn = F.extract(quenched_sqs)
    Gn[:, 6] += len(donors)

    G2 = np.concatenate([G_base, Gn])
    donors2 = donors + quenched_sqs
    F.log(f"Total gadgets for DP: {len(G2)}")

    dp, PG, PM, PQ = F.run_dp(G2)
    cur = F.load_csv(base)
    total_gain = 0.0
    wins = []

    for n in range(325, 1001):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G2, K, D)
        if f is None or K + f + 2 * F.E >= L0 - 1e-10:
            continue
        r = F.certify_ladder(n, F.compose(K, D, f, links, G2, donors2))
        if r is None or r[0] >= L0 - 1e-9:
            continue
        gain = (L0 - r[0]) / math.sqrt(n)
        total_gain += gain
        wins.append((n, r[0], L0, gain))
        out_p = f"{outdir}/{n}.csv"
        with open(out_p, "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (a, b, t) in enumerate(r[2]):
                fh.write(f"{n},{i},{a},{b},{t}\n")
        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {gain:.2e} | total gain {total_gain:.8f}")

    F.log(f"DONE. Total certified score gain: {total_gain:.8f} across {len(wins)} puzzles.")


if __name__ == "__main__":
    main()
