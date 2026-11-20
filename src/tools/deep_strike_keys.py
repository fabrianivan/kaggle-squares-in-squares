"""Deep Strike Homotopy Quencher: Targeted high-iteration annealing on DP bottleneck keys."""

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


def squeeze_deep_strike(job):
    """Deep targeted soft-to-rigid homotopy annealer with fast outer iterations."""
    key, sq, budget = job
    w, h, dm = key
    t0 = time.time()
    f0 = S.overhang(sq, w, h)

    best, fbest = S.quench(sq, w, h, loosen=1.0, round_r0=0.0, outer=30)
    if fbest > f0:
        best, fbest = sq, f0

    k = 0
    stagnant = 0
    # Fine-grained corner radii schedule
    r0_schedule = [0.18, 0.12, 0.08, 0.05, 0.03, 0.015, 0.005, 0.0]
    while time.time() - t0 < budget:
        k += 1
        r0 = r0_schedule[k % len(r0_schedule)]
        amp = 1.8 if stagnant > 6 else 1.0
        loosen = 1.0 + 0.005 * (1 + (k % 4)) * amp
        kick = 0.002 * (1 + (k % 3)) * amp
        cand, f = S.quench(best, w, h, loosen=loosen, kick=kick, seed=k * 137 + stagnant, round_r0=r0, outer=35)
        if f < fbest and len(cand) == w * h + dm:
            best, fbest = cand, f
            stagnant = 0
        else:
            stagnant += 1

    # Final rigid polish pass with higher outer iterations
    cand, f = S.quench(best, w, h, loosen=1.00005, kick=0.0, seed=999, round_r0=0.0, outer=90)
    if f < fbest and len(cand) == w * h + dm:
        best, fbest = cand, f

    return key, f0, fbest, best, k


def main():
    base = "output/submission_final.csv"
    outdir = "output/batch_deep_strike"
    os.makedirs(outdir, exist_ok=True)

    target_keys = [
        (27, 27, 10),
        (25, 25, 13),
        (28, 28, 17),
        (20, 11, 8), (11, 20, 8),
        (5, 14, 4), (14, 5, 4),
        (16, 11, 4), (11, 16, 4),
        (15, 16, 4), (16, 15, 4),
        (7, 12, 5), (12, 7, 5),
        (16, 10, 7), (10, 16, 7),
        (22, 8, 9), (8, 22, 9),
        (21, 11, 9), (11, 21, 9),
        (10, 15, 3), (15, 10, 3)
    ]

    F.log("Loading cached donors and G...")
    G_base = np.load("output/cached_base_G.npy")
    cd = np.load("output/cached_donors.npz")
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

    combined_npz_path = "output/all_quenched_gadgets_combined.npz"
    npz_data = np.load(combined_npz_path)
    existing_gadgets = {k: npz_data[k] for k in npz_data.files if not k.endswith("_before")}
    F.log(f"Loaded {len(donors)} base donors, {len(existing_gadgets)} existing quenched gadgets")

    quenched_sqs = list(existing_gadgets.values())
    Gn = F.extract(quenched_sqs)
    Gn[:, 6] += len(donors)
    G_all = np.concatenate([G_base, Gn])
    all_donors = donors + quenched_sqs

    budget = 120.0
    procs = 10

    jobs = []
    for key in target_keys:
        rows = np.where((G_all[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            F.log(f"Key {key} not found, skipping")
            continue
        best_row = rows[np.argmin(G_all[rows, 3])]
        w, h, dm, f, ybr, xtl, di, si = G_all[best_row]
        sq, _ = F.crop(all_donors[int(di)], int(si), int(w), int(h), int(dm))
        jobs.append((key, sq, budget))

    F.log(f"Starting Deep Strike quench on {len(jobs)} keys ({budget:.0f}s each on {procs} cores)...")
    improved = []
    with Pool(procs) as pool:
        for key, f0, f1, sq, k in pool.imap_unordered(squeeze_deep_strike, jobs):
            w, h, dm = key
            delta_f = f0 - f1
            status = f"IMPROVED (df = {delta_f:.7f})" if delta_f > 1e-9 else "no improvement"
            F.log(f"{w}x{h}+{dm}: f {f0:.6f} -> {f1:.6f} ({k} iterations) -> {status}")
            if delta_f > 1e-9:
                improved.append((key, sq, f0, f1))
                existing_gadgets[f"{w}_{h}_{dm}"] = sq

    np.savez(combined_npz_path, **existing_gadgets)
    F.log(f"Updated persistent reservoir: {len(existing_gadgets)} quenched gadgets saved")

    if not improved:
        F.log("No gadgets improved in this Deep Strike pass.")
        return

    F.log("Re-evaluating full fault DP across all n in 325..1000...")
    quenched_sqs_updated = list(existing_gadgets.values())
    Gn_up = F.extract(quenched_sqs_updated)
    Gn_up[:, 6] += len(donors)
    G_final = np.concatenate([G_base, Gn_up])
    donors_final = donors + quenched_sqs_updated

    dp, PG, PM, PQ = F.run_dp(G_final)
    cur = F.load_csv(base)
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

