"""Rank gadget keys by how much total score their overhang f locks up.

n = K^2 + D is built as a ladder of gadgets along the fault line; the box side is K + f + 2e where f is the
*maximum* overhang over the gadgets in the chain. So for each n exactly one gadget (the arg-max) is binding:
lowering its f lowers that puzzle's L, until the second-largest f in the chain takes over. The shadow price of a
key is therefore sum over the puzzles it binds of (f_binding - f_runner_up) / sqrt(n), capped by the gain that
is actually reachable before another gadget becomes the bottleneck.

Writes output/bottleneck_report.json and caches the donor/gadget tables so later quench rounds are cheap.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(KIT))

import fault_dp as F  # noqa: E402
from ensemble import side  # noqa: E402

BASE_CSV = ROOT / "output" / "submission_22.233377.csv"
OUT = ROOT / "output"


def build_library(base_csv: Path = BASE_CSV, rebuild: bool = False):
    """(G_all, donors_all, cur) with gadgets from the cached pool, the current submission and the quench reservoir."""
    cache_G = OUT / "lib_G_all.npy"
    cache_meta = OUT / "lib_meta.json"

    cur = F.load_csv(str(base_csv))
    F.log(f"base {base_csv.name}: {len(cur)} sub-grid puzzles")

    cd = np.load(OUT / "cached_donors.npz")
    base_donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
    G_base = np.load(OUT / "cached_base_G.npy")
    F.log(f"cached pool: {len(base_donors)} donors, {len(G_base)} gadgets")

    cur_donors = [cur[n] for n in sorted(cur) if n >= 325]
    res = dict(np.load(OUT / "all_quenched_gadgets_combined.npz"))
    q_keys = [k for k in res if not k.endswith("_before")]
    q_sqs = [res[k] for k in q_keys]

    donors_all = base_donors + cur_donors + q_sqs

    if cache_G.exists() and not rebuild:
        G_all = np.load(cache_G)
        meta = json.loads(cache_meta.read_text())
        if meta["n_donors"] == len(donors_all):
            F.log(f"reusing cached library: {len(G_all)} gadgets over {len(donors_all)} donors")
            return G_all, donors_all, cur
        F.log("cached library stale, rebuilding")

    t0 = time.time()
    F.log(f"extracting from {len(cur_donors)} current-submission donors...")
    Gn_cur = F.extract(cur_donors)
    Gn_cur[:, 6] += len(base_donors)
    F.log(f"extracting from {len(q_sqs)} quenched reservoir gadgets...")
    Gn_q = F.extract(q_sqs)
    Gn_q[:, 6] += len(base_donors) + len(cur_donors)

    G_all = np.concatenate([G_base, Gn_cur, Gn_q])
    np.save(cache_G, G_all)
    cache_meta.write_text(json.dumps(dict(n_donors=len(donors_all), n_gadgets=len(G_all))))
    F.log(f"library: {len(G_all)} gadgets over {len(donors_all)} donors in {time.time()-t0:.0f}s")
    return G_all, donors_all, cur


def analyse(G_all, donors_all, cur, nmin=325, nmax=1000):
    F.log("running DP...")
    t0 = time.time()
    dp, PG, PM, PQ = F.run_dp(G_all)
    F.log(f"DP done in {time.time()-t0:.0f}s")

    # shadow price per key, and the puzzles each key binds
    price = defaultdict(float)
    binds = defaultdict(list)
    headroom = []          # (n, L_now, L_dp) where the DP already beats the submission
    rows = []

    for n in range(nmin, nmax + 1):
        K = math.isqrt(n)
        D = n - K * K
        if D == 0:
            continue
        L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
        f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
        if f is None:
            continue
        L_dp = K + f + 2 * F.E
        if L_dp < L0 - 1e-9:
            headroom.append((n, L0, L_dp, (L0 - L_dp) / math.sqrt(n)))

        fs = np.array([G_all[g, 3] for g, _ in links])
        order = np.argsort(-fs)
        gb = links[order[0]][0]
        key = tuple(int(v) for v in G_all[gb, :3])
        runner = float(fs[order[1]]) if len(fs) > 1 else 0.0
        # reachable gain if this key's f dropped to the runner-up (then another gadget binds)
        slack = max(0.0, float(fs[order[0]]) - runner)
        gain = min(slack, max(0.0, L0 - (K + runner))) / math.sqrt(n)
        price[key] += gain
        binds[key].append(n)
        rows.append(dict(n=n, K=K, D=D, L0=L0, f=float(f), L_dp=L_dp,
                         bottleneck=list(key), f_bottleneck=float(fs[order[0]]),
                         f_runner_up=runner, reachable_gain=gain, chain_len=len(links)))

    ranked = sorted(price.items(), key=lambda kv: -kv[1])
    report = dict(
        base=str(BASE_CSV),
        n_gadgets=int(len(G_all)),
        n_donors=int(len(donors_all)),
        total_reachable=float(sum(price.values())),
        headroom=[dict(n=n, L0=a, L_dp=b, gain=g) for n, a, b, g in headroom],
        ranked_keys=[dict(key=list(k), price=v, n_bound=len(binds[k]), puzzles=binds[k][:40]) for k, v in ranked],
        puzzles=rows,
    )
    (OUT / "bottleneck_report.json").write_text(json.dumps(report, indent=2))

    F.log(f"DP already beats submission on {len(headroom)} puzzles "
          f"(total {sum(g for *_, g in headroom):.6e})")
    F.log(f"total reachable gain from perfect quenching: {sum(price.values()):.6f}")
    F.log("top 40 quench targets (key, shadow price, #puzzles bound):")
    for k, v in ranked[:40]:
        F.log(f"   {k[0]:2d}x{k[1]:2d}+{k[2]:2d}  price {v:.3e}  binds {len(binds[k]):3d} puzzles")
    return report


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    G_all, donors_all, cur = build_library(rebuild=rebuild)
    analyse(G_all, donors_all, cur)
