"""L-Cut & T-Cut Synthetic Gadget Generator & Quencher (Breakthrough Gen-4 Algorithm).

Breeds novel, super-dense Pareto-optimal gadgets by slicing lattice continent borders
(1 or 2 rows/columns) from large high-density donor crops without touching the fault line,
then squeezing with evand's smooth augmented-Lagrangian optimizer (fq).

Injected into the fault DP table, these synthetic gadgets unlock puzzle packings for keys
that never existed naturally in community donor submissions.
"""

import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ALEX_DIR = ROOT_DIR / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(ALEX_DIR))

import fault_dp as F
import skeleton as S
from ensemble import side, certify

OUTPUT_DIR = ROOT_DIR / "output" / "l_cut_run"
NPZ_OUT = OUTPUT_DIR / "l_cut_gadgets.npz"


def slice_lattice_border(cropped, cut_x=1, cut_y=1):
    """Slice lattice continent borders from lower-left (x < cut_x or y < cut_y).
    
    Since the lower-left continent is aligned with the integer lattice, slicing integer
    rows/columns removes exactly cut_x * H + cut_y * W - cut_x * cut_y lattice squares,
    leaving the anti-diagonal fault line completely intact!
    """
    cand = cropped[(cropped[:, 0] >= cut_x) & (cropped[:, 1] >= cut_y)].copy()
    cand[:, 0] -= cut_x
    cand[:, 1] -= cut_y
    return cand


def squeeze_synthetic_job(job):
    """Worker process: runs fq rectangle-quench on a synthetic gadget candidate."""
    key, cand, f_table_best, budget = job
    w, h, dm = key
    t0 = time.time()
    
    f0 = S.overhang(cand, w, h)
    best, fbest = S.quench(cand, w, h, loosen=1.0)
    if fbest > f0:
        best, fbest = cand, f0
        
    k = 0
    while time.time() - t0 < budget:
        k += 1
        loosen = 1.0 + 0.01 * (k % 5)
        kick = 0.01 * (k % 3)
        round_r0 = 0.04 if (k % 4 == 0) else 0.0
        c, f = S.quench(best, w, h, loosen=loosen, kick=kick, seed=k * 13 + 7, round_r0=round_r0)
        if f < fbest and len(c) == w * h + dm:
            best, fbest = c, f

    improved_vs_table = fbest < f_table_best - 1e-4
    return key, f_table_best, f0, fbest, best, k, improved_vs_table


def main():
    procs = 6
    budget = 12.0  # seconds per synthetic candidate
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    base_csv = ROOT_DIR / "output" / "submission_final.csv"
    cache_g = ROOT_DIR / "output" / "cached_base_G.npy"
    cache_donors = ROOT_DIR / "output" / "cached_donors.npz"

    if os.path.exists(cache_g) and os.path.exists(cache_donors):
        F.log("Loading cached G and donors from disk...")
        G = np.load(str(cache_g))
        d_npz = np.load(str(cache_donors))
        donors = [d_npz[f] for f in d_npz.files]
        F.log(f"Instantly loaded {len(donors)} donors and {len(G)} base gadgets!")
    else:
        extra_donors = [
            ALEX_DIR / "best.csv",
            ALEX_DIR / "couzo.csv",
            ALEX_DIR / "quench.csv",
            ALEX_DIR / "hop.csv",
            ROOT_DIR / "data" / "new_sources" / "danil_v52" / "submission.csv",
        ]

        F.log("Loading donor pool...")
        seen, donors = set(), []
        for p in [base_csv] + extra_donors:
            if not os.path.exists(p):
                continue
            for n, sq in F.load_csv(str(p)).items():
                k = (n, round(side(sq), 9))
                if k not in seen:
                    seen.add(k)
                    donors.append(sq)
        F.log(f"Loaded {len(donors)} donors.")

        F.log("Extracting base donor gadgets...")
        G = F.extract(donors)
        F.log(f"Extracted {len(G)} base gadgets.")
        np.save(str(cache_g), G)
        np.savez(str(cache_donors), **{f"d_{i}": sq for i, sq in enumerate(donors)})
        F.log("Cached G and donors to disk for instant future startup.")

    # Build quick lookup for current best overhang per key (w, h, dm)
    table_best = {}
    for row in G:
        w, h, dm, f = int(row[0]), int(row[1]), int(row[2]), float(row[3])
        k = (w, h, dm)
        if k not in table_best or f < table_best[k]:
            table_best[k] = f

    # Identify source donor gadgets for L-cuts: large, dense gadgets (w >= 14, h >= 14, dm >= 2)
    cut_sources = []
    for row in G:
        w, h, dm, f, _, _, di, si = row
        w, h, dm = int(w), int(h), int(dm)
        if w >= 14 and h >= 14 and dm >= 2 and f < 0.95:
            cut_sources.append((w, h, dm, f, int(di), int(si)))

    F.log(f"Found {len(cut_sources)} candidate source gadgets for synthetic breeding.")

    # Generate synthetic candidates via L-cut (1, 1), T-cut (1, 0), T-cut (0, 1), and Double-L (2, 2)
    synthetic_candidates = {}  # key -> best_cand_by_initial_f
    cuts = [(1, 1), (1, 0), (0, 1), (2, 2)]

    for w, h, dm, f_src, di, si in cut_sources:
        cropped, _ = F.crop(donors[di], si, w, h, dm)
        for cx, cy in cuts:
            target_w = w - cx
            target_h = h - cy
            if target_w < 8 or target_h < 8:
                continue
            cand = slice_lattice_border(cropped, cx, cy)
            target_dm = len(cand) - target_w * target_h
            if target_dm <= 0 or target_dm > 60:
                continue

            target_key = (target_w, target_h, target_dm)
            cand_f = S.overhang(cand, target_w, target_h)
            if cand_f > 0.96:
                continue

            f_cur_best = table_best.get(target_key, 1.0)
            # Only consider if promising (initial overhang close to or better than table)
            if cand_f < f_cur_best + 0.05:
                if target_key not in synthetic_candidates or cand_f < synthetic_candidates[target_key][0]:
                    synthetic_candidates[target_key] = (cand_f, cand, f_cur_best)

    F.log(f"Generated {len(synthetic_candidates)} promising synthetic target keys.")

    # Prepare parallel jobs
    jobs = []
    for target_key, (cand_f, cand, f_cur_best) in synthetic_candidates.items():
        jobs.append((target_key, cand, f_cur_best, budget))

    # Sort jobs by potential leverage (larger dm first)
    jobs.sort(key=lambda j: -j[0][2])
    # Take top 60 highest leverage synthetic keys
    jobs = jobs[:60]
    F.log(f"Launching parallel FQ squeeze on top {len(jobs)} synthetic keys with {procs} workers ({budget}s each)...")

    improved_synthetics = {}
    wins_count = 0
    done_count = 0

    with Pool(procs) as pool:
        for res in pool.imap_unordered(squeeze_synthetic_job, jobs):
            done_count += 1
            key, f_table_best, f0, fbest, sq, k, improved = res
            delta = f_table_best - fbest
            status = f"BEAT TABLE by {delta:+.6f}" if improved else "no beat"
            F.log(f"[{done_count}/{len(jobs)}] Key {key[0]}x{key[1]}+{key[2]}: table={f_table_best:.4f} -> synthetic_f={fbest:.4f} ({k} quenches) [{status}]")
            if improved:
                improved_synthetics[f"{key[0]}_{key[1]}_{key[2]}"] = sq
                wins_count += 1
                np.savez(str(NPZ_OUT), **improved_synthetics)

    F.log(f"Total synthetic gadgets that strictly beat the community DP table: {wins_count}")

    if wins_count > 0:
        np.savez(str(NPZ_OUT), **improved_synthetics)
        F.log(f"Saved synthetic gadgets to {NPZ_OUT}")

        # Run fault DP with the new synthetic gadgets!
        Gn = F.extract(list(improved_synthetics.values()))
        Gn[:, 6] += len(donors)
        G2 = np.concatenate([G, Gn])
        donors2 = donors + list(improved_synthetics.values())

        F.log("Running fault DP with augmented synthetic gadget pool...")
        dp, PG, PM, PQ = F.run_dp(G2)
        cur_best = F.load_csv(str(base_csv))
        total_gain = 0.0
        puzzle_wins = []

        for n in range(325, 1001):
            K = math.isqrt(n)
            D = n - K * K
            if D == 0:
                continue
            L0 = side(cur_best[n]) if n in cur_best else math.ceil(math.sqrt(n))
            f, links = F.chain(dp, PG, PM, PQ, G2, K, D)
            if f is None or K + f + 2 * F.E >= L0 - 1e-6:
                continue
            r = F.certify_ladder(n, F.compose(K, D, f, links, G2, donors2))
            if r is None or r[0] >= L0 - 1e-9:
                continue
            gain = (L0 - r[0]) / math.sqrt(n)
            total_gain += gain
            puzzle_wins.append((n, r[0], L0, gain))
            out_p = f"{OUTPUT_DIR}/{n}.csv"
            with open(out_p, "w") as fh:
                fh.write("n,square_id,x,y,angle\n")
                for i, (x, y, t) in enumerate(r[1]):
                    fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
            F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {gain:.2e} | cumulative {total_gain:.6f}")

        F.log(f"DONE. Total certified score gain from synthetic L-cuts: {total_gain:.8f} across {len(puzzle_wins)} puzzles.")


if __name__ == "__main__":
    main()
