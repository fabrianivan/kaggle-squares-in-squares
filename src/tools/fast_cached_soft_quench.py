"""Fast Cached Soft-to-Rigid Homotopy Quencher (Nakajima-Ostashev Corner-Radius Annealing).

Loads cached base G and donors in <0.1s, crops target keys from best donor,
runs parallel soft-to-rigid homotopy quenching (r0 schedule: 0.15 -> 0.22 -> 0.12 -> 0.18 -> 0.08 -> 0.0),
updates all_quenched_gadgets_combined.npz, runs full fault DP, and certifies wins.
"""

import json, math, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "alexchilton_starter_kit"))
import fault_dp as F
import skeleton as S
from ensemble import side

sys.path.insert(0, str(Path(__file__).resolve().parent / "reference_sources"))
from official_metric import evaluate_single_puzzle
import pandas as pd


def squeeze_soft(job):
    """Multi-stage soft-to-rigid homotopy seed loop."""
    key, sq, budget = job
    w, h, dm = key
    t0 = time.time()
    f0 = S.overhang(sq, w, h)

    # Initial pure-rigid baseline quench
    best, fbest = S.quench(sq, w, h, loosen=1.0, round_r0=0.0)
    if fbest > f0:
        best, fbest = sq, f0

    k = 0
    stagnant = 0
    # Expanded schedule of corner radii from large soft roundness down to sharp rigid corners
    r0_schedule = [0.20, 0.15, 0.12, 0.08, 0.05, 0.03, 0.01, 0.0]
    while time.time() - t0 < budget:
        k += 1
        r0 = r0_schedule[k % len(r0_schedule)]
        # Adaptive kick and loosen factors
        amp = 1.5 if stagnant > 5 else 1.0
        loosen = 1.0 + 0.006 * (1 + (k % 4)) * amp
        kick = 0.002 * (1 + (k % 3)) * amp
        cand, f = S.quench(best, w, h, loosen=loosen, kick=kick, seed=k * 101 + stagnant, round_r0=r0, outer=75)
        if f < fbest and len(cand) == w * h + dm:
            best, fbest = cand, f
            stagnant = 0
        else:
            stagnant += 1

    # Final ultra-tight rigid polish pass
    cand, f = S.quench(best, w, h, loosen=1.00005, kick=0.0, seed=777, round_r0=0.0, outer=120)
    if f < fbest and len(cand) == w * h + dm:
        best, fbest = cand, f

    return key, f0, fbest, best, k


def main():
    if len(sys.argv) < 5:
        print("Usage: python fast_cached_soft_quench.py KEYS.json BUDGET_S PROCS OUTDIR")
        sys.exit(1)

    keys_p = sys.argv[1]
    budget = float(sys.argv[2])
    procs = int(sys.argv[3])
    outdir = sys.argv[4]
    os.makedirs(outdir, exist_ok=True)

    F.log("Loading cached donors and G...")
    G_base = np.load("output/cached_base_G.npy")
    cd = np.load("output/cached_donors.npz")
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

    combined_npz_path = "output/all_quenched_gadgets_combined.npz"
    npz_data = np.load(combined_npz_path) if os.path.exists(combined_npz_path) else {}
    existing_gadgets = {k: npz_data[k] for k in npz_data.files if not k.endswith("_before")}
    F.log(f"Loaded {len(donors)} base donors, {len(existing_gadgets)} existing quenched gadgets")

    quenched_sqs = list(existing_gadgets.values())
    if quenched_sqs:
        Gn = F.extract(quenched_sqs)
        Gn[:, 6] += len(donors)
        G_all = np.concatenate([G_base, Gn])
        all_donors = donors + quenched_sqs
    else:
        G_all = G_base
        all_donors = donors

    with open(keys_p) as f:
        keys = [tuple(k) for k in json.load(f)]

    jobs = []
    for key in keys:
        rows = np.where((G_all[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            F.log(f"Key {key} not found in G_all, skipping")
            continue
        best_row = rows[np.argmin(G_all[rows, 3])]
        w, h, dm, f, ybr, xtl, di, si = G_all[best_row]
        sq, _ = F.crop(all_donors[int(di)], int(si), int(w), int(h), int(dm))
        jobs.append((key, sq, budget))

    F.log(f"Starting parallel soft-to-rigid quench on {len(jobs)} keys ({budget:.0f}s each on {procs} cores)...")
    improved = []
    with Pool(procs) as pool:
        for key, f0, f1, sq, k in pool.imap_unordered(squeeze_soft, jobs):
            w, h, dm = key
            delta_f = f0 - f1
            status = f"IMPROVED (df = {delta_f:.7f})" if delta_f > 1e-9 else "no improvement"
            F.log(f"{w}x{h}+{dm}: f {f0:.6f} -> {f1:.6f} ({k} iterations) -> {status}")
            if delta_f > 1e-9:
                improved.append((key, sq, f0, f1))
                existing_gadgets[f"{w}_{h}_{dm}"] = sq

    # Update persistent reservoir
    np.savez(combined_npz_path, **existing_gadgets)
    F.log(f"Persistent reservoir updated: now {len(existing_gadgets)} quenched gadgets saved in {combined_npz_path}")

    if not improved:
        F.log("No gadgets improved in this batch. Exiting.")
        return

    F.log(f"Re-extracting and running full fault DP across all n in 325..1000...")
    quenched_sqs_updated = list(existing_gadgets.values())
    Gn_up = F.extract(quenched_sqs_updated)
    Gn_up[:, 6] += len(donors)
    G_final = np.concatenate([G_base, Gn_up])
    donors_final = donors + quenched_sqs_updated

    dp, PG, PM, PQ = F.run_dp(G_final)
    cur = F.load_csv("output/submission_final.csv")
    total_gain = 0.0
    wins = []

    for n in range(325, 1001):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G_final, K, D)
        if f is None or K + f + 2 * F.E >= L0 - 1e-10:
            continue
        r = F.certify_ladder(n, F.compose(K, D, f, links, G_final, donors_final))
        if r is None or r[0] >= L0 - 1e-9:
            continue

        L_cand = r[0]
        gain = (L0 - L_cand) / math.sqrt(n)
        total_gain += gain
        wins.append((n, L_cand, L0, gain))
        out_csv = f"{outdir}/{n}.csv"
        with open(out_csv, "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (a, b, t) in enumerate(r[2]):
                fh.write(f"{n},{i},{a},{b},{t}\n")
        F.log(f"n={n}: *** NEW CERTIFIED RECORD *** L: {L0:.9f} -> {L_cand:.9f} (gain +{gain:.8f}) | Total gain: {total_gain:.8f}")

    F.log(f"DONE. Total certified score gain: {total_gain:.8f} across {len(wins)} puzzles.")


if __name__ == "__main__":
    main()
