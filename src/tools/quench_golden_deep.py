"""Golden Deep Quench: Target 20 unquenched bottleneck keys holding back ladder DP."""

import json
import math
import os
import sys
import time
import pickle
from multiprocessing import Pool
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))

import fault_dp as F
import skeleton as S
from ensemble import side

def squeeze_key(job):
    key, sq, budget = job
    w, h, dm = key
    t0 = time.time()
    f0 = S.overhang(sq, w, h)

    best, fbest = S.quench(sq, w, h, loosen=1.0, round_r0=0.0, outer=30)
    if fbest > f0:
        best, fbest = sq, f0

    k = 0
    stagnant = 0
    r0_schedule = [0.18, 0.14, 0.10, 0.07, 0.05, 0.03, 0.015, 0.005, 0.0]
    while time.time() - t0 < budget:
        k += 1
        r0 = r0_schedule[k % len(r0_schedule)]
        amp = 2.0 if stagnant > 6 else 1.0
        loosen = 1.0 + 0.004 * (1 + (k % 5)) * amp
        kick = 0.0015 * (1 + (k % 4)) * amp
        cand, f = S.quench(best, w, h, loosen=loosen, kick=kick, seed=k * 137 + stagnant, round_r0=r0, outer=30)
        if f < fbest and len(cand) == w * h + dm:
            best, fbest = cand, f
            stagnant = 0
        else:
            stagnant += 1

    cand, f = S.quench(best, w, h, loosen=1.00002, kick=0.0, seed=999, round_r0=0.0, outer=80)
    if f < fbest and len(cand) == w * h + dm:
        best, fbest = cand, f

    return key, f0, fbest, best, k

def main():
    base_csv = str(ROOT / "output" / "submission_final.csv")
    outdir = str(ROOT / "tmp" / "golden_quench_out")
    os.makedirs(outdir, exist_ok=True)

    with open(str(ROOT / "tmp" / "golden_deep_keys.json")) as f:
        target_keys = json.load(f)

    # Add symmetrical pairs
    expanded_keys = set()
    for w, h, dm in target_keys:
        expanded_keys.add((w, h, dm))
        expanded_keys.add((h, w, dm))

    cache_file = str(ROOT / "tmp" / "g_base_cache.pkl")
    F.log("Loading G_base and donors from cache...")
    with open(cache_file, "rb") as fh:
        donors, G_base = pickle.load(fh)
    F.log(f"Cache loaded: {len(donors)} donors, {len(G_base)} base gadgets.")

    # Load all existing quenched gadgets
    quench_files = [
        str(ROOT / "tmp" / "quench_out" / "gadgets_quenched.npz"),
        str(ROOT / "tmp" / "quench_med_out" / "gadgets_quenched.npz"),
        str(ROOT / "tmp" / "quench_large_out" / "gadgets_quenched.npz"),
        str(ROOT / "tmp" / "quench_new_out" / "gadgets_quenched.npz"),
        str(ROOT / "tmp" / "deep_quench_out" / "gadgets_quenched.npz"),
    ]
    existing_gadgets = {}
    for qf in quench_files:
        if os.path.exists(qf):
            data = np.load(qf)
            for k in data.files:
                if not k.endswith("_before"):
                    existing_gadgets[k] = data[k]

    quenched_sqs = list(existing_gadgets.values())
    Gn = F.extract(quenched_sqs)
    Gn[:, 6] += len(donors)
    G_all = np.concatenate([G_base, Gn])
    all_donors = donors + quenched_sqs

    budget = 30.0
    procs = 10
    jobs = []
    for key in expanded_keys:
        rows = np.where((G_all[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            continue
        best_row = rows[np.argmin(G_all[rows, 3])]
        w, h, dm, f, ybr, xtl, di, si = G_all[best_row]
        sq, _ = F.crop(all_donors[int(di)], int(si), int(w), int(h), int(dm))
        jobs.append((key, sq, budget))

    F.log(f"Starting Golden Deep Quench on {len(jobs)} keys ({budget:.0f}s each on {procs} cores)...")

    improved = []
    with Pool(procs) as pool:
        for key, f0, f1, sq, k in pool.imap_unordered(squeeze_key, jobs):
            w, h, dm = key
            delta_f = f0 - f1
            status = f"IMPROVED (df = {delta_f:.7f})" if delta_f > 1e-9 else "no improvement"
            F.log(f"{w}x{h}+{dm}: f {f0:.6f} -> {f1:.6f} ({k} iterations) -> {status}")
            if delta_f > 1e-9:
                improved.append((key, sq, f0, f1))
                existing_gadgets[f"{w}_{h}_{dm}"] = sq

    save_npz = str(ROOT / "tmp" / "golden_quench_out" / "gadgets_quenched.npz")
    np.savez(save_npz, **existing_gadgets)
    F.log(f"Saved {len(existing_gadgets)} gadgets to {save_npz}")

    if not improved:
        F.log("No gadgets improved in this pass.")
        return

    F.log("Re-evaluating full fault DP across n=325..1000...")
    quenched_sqs_updated = list(existing_gadgets.values())
    Gn_up = F.extract(quenched_sqs_updated)
    Gn_up[:, 6] += len(donors)
    G_final = np.concatenate([G_base, Gn_up])
    donors_final = donors + quenched_sqs_updated

    dp, PG, PM, PQ = F.run_dp(G_final)
    cur = F.load_csv(base_csv)
    total_gain = 0.0
    wins = []

    for n in range(325, 1001):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0: continue

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
        out_csv = os.path.join(outdir, f"{n}.csv")
        with open(out_csv, "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (a, b, t) in enumerate(r[2]):
                fh.write(f"{n},{i},{a},{b},{t}\n")
        F.log(f"n={n}: *** NEW RECORD *** L: {L0:.9f} -> {L_cand:.9f} (gain +{gain:.8e}) | Total: +{total_gain:.8f}")

    F.log(f"DONE. Total certified score gain: {total_gain:.10e} across {len(wins)} puzzles.")

if __name__ == "__main__":
    main()
