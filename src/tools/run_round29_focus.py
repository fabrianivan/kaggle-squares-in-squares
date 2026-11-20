"""CPU-only repeated separating-axis LP on the most productive fresh starts.
Established contact optimization; no new method or global optimality claim.
"""

import os

for k in [
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "MKL_NUM_THREADS",
]:
    os.environ[k] = "1"
import json, time, math, argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from packing_geometry import load_bank, side, repair, save_bank
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish


def worker(job):
    n, p, visit, seed = job
    t = time.monotonic()
    L = side(p)
    trust = [0.08, 0.2, 0.55, 1.0][visit % 4]
    tie = [0.02, 0.1, 0.28, 0.8][(visit // 4) % 4]
    q, trace, _ = reclose(p, seed=seed, trust=trust, tie=tie, rounds=24, seconds=1.5)
    if side(q) < L - 1e-8:
        q, _, _ = polish(q, seed=seed, rounds=60, max_seconds=2.0, trust_start=0.015)
    q = repair(q, clearance=2e-9)
    ok = q is not None and (L - side(q)) / math.sqrt(n) > 1e-8
    r = dict(
        n=n,
        seed=seed,
        arm=visit,
        kind="contact_focus",
        phase="focus",
        trust=trust,
        tie=tie,
        before=L,
        after=side(q) if q is not None else L,
        accepted=ok,
        gain=(L - side(q)) / math.sqrt(n) if ok else 0.0,
        seconds=time.monotonic() - t,
    )
    return q if ok else None, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=120)
    a = ap.parse_args()
    start = time.monotonic()
    b = load_bank("artifacts/round29_submission.csv")
    z = np.load("artifacts/round29_cpu_packings.npz")
    patch = {int(k): z[k].copy() for k in z.files}
    h = json.load(open("artifacts/round29_cpu_history.json"))
    g = {}
    for r in h:
        if r.get("accepted"):
            g[r["n"]] = g.get(r["n"], 0) + r["gain"]
    targets = sorted(g, key=lambda n: -g[n])[:10]
    visits = {n: 0 for n in targets}
    seq = 0
    for n, q in patch.items():
        if side(q) < side(b[n]):
            b[n] = q.copy()
    with ProcessPoolExecutor(max_workers=2) as ex:
        active = {}

        def add():
            nonlocal seq
            n = targets[seq % len(targets)]
            visit = visits[n]
            visits[n] += 1
            seq += 1
            active[ex.submit(worker, (n, b[n], visit, 291029000 + seq * 19997))] = n

        for _ in range(2):
            add()
        while active:
            f = next(as_completed(active))
            active.pop(f)
            q, r = f.result()
            h.append(r)
            if q is not None and side(q) < side(b[r["n"]]):
                b[r["n"]] = q
                patch[r["n"]] = q
                print(json.dumps(r), flush=True)
            if time.monotonic() - start < a.seconds:
                add()
    save_bank("artifacts/round29_cpu_packings.npz", patch)
    Path("artifacts/round29_cpu_history.json").write_text(json.dumps(h, indent=2))
    Path("artifacts/round29_focus_summary.json").write_text(
        json.dumps(
            dict(targets=targets, seconds=time.monotonic() - start, trials=seq),
            indent=2,
        )
    )
    print("focus done", seq, "seconds", time.monotonic() - start, flush=True)


if __name__ == "__main__":
    main()
