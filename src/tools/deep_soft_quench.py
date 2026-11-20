"""Deep Soft-to-Rigid Homotopy Quencher (Nakajima-Ostashev Corner-Radius Annealing).

Targeted augmented-Lagrangian squeezing of high-leverage gadget keys using smooth
variable-corner-radius relaxation (round_r0: 0.15 -> 0.22 -> 0.10 -> 0.05 -> 0.0)
and multi-phase kicks to tunnel through jammed contact-graph barriers.
"""

import json, math, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "alexchilton_starter_kit"))
import fault_dp as F
import skeleton as S
from ensemble import side


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
    # Schedule of corner radii and kick amplitudes
    r0_schedule = [0.15, 0.22, 0.12, 0.18, 0.08, 0.0]
    while time.time() - t0 < budget:
        k += 1
        r0 = r0_schedule[k % len(r0_schedule)]
        loosen = 1.0 + 0.01 * (k % 4)
        kick = 0.003 * (1 + (k % 3))
        cand, f = S.quench(best, w, h, loosen=loosen, kick=kick, seed=k, round_r0=r0, outer=60)
        if f < fbest and len(cand) == w * h + dm:
            best, fbest = cand, f

    # Final rigid polish pass with tight loosen factor
    cand, f = S.quench(best, w, h, loosen=1.0001, kick=0.0, seed=999, round_r0=0.0, outer=80)
    if f < fbest and len(cand) == w * h + dm:
        best, fbest = cand, f

    return key, f0, fbest, best, k


def main():
    if len(sys.argv) < 6:
        print("Usage: python deep_soft_quench.py BASE.csv OUTDIR KEYS.json BUDGET_S PROCS [DONOR.csv ...]")
        sys.exit(1)

    base = sys.argv[1]
    outdir = sys.argv[2]
    keys_p = sys.argv[3]
    budget = float(sys.argv[4])
    procs = int(sys.argv[5])
    extra = sys.argv[6:]

    os.makedirs(outdir, exist_ok=True)
    seen, donors = set(), []
    for p in [base] + extra:
        if not os.path.exists(p):
            continue
        for n, sq in F.load_csv(p).items():
            k = (n, round(side(sq), 9))
            if k not in seen:
                seen.add(k)
                donors.append(sq)
    F.log(f"{len(donors)} donors loaded")
    G = F.extract(donors)

    keys = [tuple(k) for k in json.load(open(keys_p))]
    jobs = []
    for key in keys:
        rows = np.where((G[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            continue
        w, h, dm, _, _, _, di, si = G[rows[np.argmin(G[rows, 3])]]
        jobs.append((key, F.crop(donors[int(di)], int(si), int(w), int(h), int(dm))[0], budget))

    F.log(f"Soft-to-rigid quenching {len(jobs)} keys, {budget:.0f}s each, {procs} processes")
    with Pool(procs) as pool:
        res = pool.map(squeeze_soft, jobs)

    improved, before = [], {}
    start = {job[0]: job[1] for job in jobs}
    for key, f0, f1, sq, k in res:
        F.log(f"{key[0]}x{key[1]}+{key[2]}: f {f0:.6f} -> {f1:.6f} ({k} quenches){'  IMPROVED' if f1 < f0 - 1e-9 else ''}")
        if f1 < f0 - 1e-9:
            improved.append((key, sq))
            before[key] = start[key]

    np.savez(f"{outdir}/gadgets_quenched.npz",
             **{f"{w}_{h}_{dm}": sq for (w, h, dm), sq in improved},
             **{f"{w}_{h}_{dm}_before": sq for (w, h, dm), sq in before.items()})

    if not improved:
        F.log("DONE total certified gain 0.000000 (no gadget improved)")
        return

    Gn = F.extract([sq for _, sq in improved])
    Gn[:, 6] += len(donors)
    G2, donors2 = np.concatenate([G, Gn]), donors + [sq for _, sq in improved]
    dp, PG, PM, PQ = F.run_dp(G2)
    cur = F.load_csv(base)
    total = 0.0
    wins = []

    for n in range(325, 1001):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G2, K, D)
        if f is None or K + f + 2 * F.E >= L0 - 1e-6:
            continue
        r = F.certify_ladder(n, F.compose(K, D, f, links, G2, donors2))
        if r is None or r[0] >= L0 - 1e-9:
            continue
        d = (L0 - r[0]) / math.sqrt(n)
        total += d
        wins.append((n, r[0], L0, d))
        with open(f"{outdir}/{n}.csv", "w") as fh:
            fh.write("n,square_id,x,y,angle\n")
            for i, (x, y, t) in enumerate(r[1]):
                fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
        F.log(f"n={n}: CERTIFIED {r[0]:.9f} vs {L0:.9f}, gain {d:.2e} | total {total:.6f}")

    F.log(f"DONE total certified gain {total:.6f} across {len(wins)} puzzles from {len(improved)} improved gadgets")


if __name__ == "__main__":
    main()

