"""CPU reuse of accepted round29 witnesses by rigid rotation and free closures.
L-border and boundary deletion are established constructions credited to
Deotte, Danil, lightningv08 and upstream square-packing literature.
No square dimensions change; serialized official gates remain mandatory.
"""

import json, math, time
from pathlib import Path
import numpy as np
from packing_geometry import (
    load_bank,
    normalize,
    side,
    repair,
    optimal_rotation,
    save_bank,
    aabbs,
)


def deletions(p, count, width=2):
    beam = [p]
    for _ in range(count):
        candidates = []
        for q in beam:
            lo, hi = aabbs(q)
            ids = set()
            for d in [0, 1]:
                ids.update(np.argsort(lo[:, d])[:2])
                ids.update(np.argsort(hi[:, d])[-2:])
            for i in sorted(ids):
                r = np.delete(q, i, axis=0)
                candidates.append((side(r), int(i), r))
        candidates.sort(key=lambda r: (r[0], r[1]))
        beam = [r[2] for r in candidates[:width]]
    return beam


def main():
    start = time.monotonic()
    b = load_bank("artifacts/round29_submission.csv")
    z = np.load("artifacts/round29_cpu_packings.npz")
    patch = {int(k): z[k].copy() for k in z.files}
    history = []
    trials = {}
    for n, q in patch.items():
        if side(q) < side(b[n]):
            b[n] = q.copy()

    def offer(q, seed, kind):
        n = len(q)
        trials[kind] = trials.get(kind, 0) + 1
        if not 1 <= n <= 1000 or (side(b[n]) - side(q)) / math.sqrt(n) <= 1e-8:
            return
        q = repair(q, clearance=2e-9)
        if q is None or (side(b[n]) - side(q)) / math.sqrt(n) <= 1e-8:
            return
        gain = (side(b[n]) - side(q)) / math.sqrt(n)
        before = side(b[n])
        b[n] = q
        patch[n] = q
        history.append(
            dict(n=n, seed_n=seed, kind=kind, before=before, after=side(q), gain=gain)
        )
        print(json.dumps(history[-1]), flush=True)

    seeds = sorted(patch)
    for seed in seeds:
        q, angle = optimal_rotation(b[seed])
        offer(q, seed, "rigid_rotation")
        q = b[seed].copy()
        for stage in range(20):
            offer(q, seed, "border_reuse")
            for count in [1, 2]:
                if len(q) <= count:
                    continue
                for r in deletions(q, count):
                    offer(r, seed, "boundary_delete")
            q = normalize(q)
            L = side(q)
            k = math.floor(L)
            target = len(q) + 2 * k + 1
            if target > 1000:
                break
            extra = np.array(
                [(L + 0.5, j + 0.5, 0.0) for j in range(k)]
                + [(j + 0.5, L + 0.5, 0.0) for j in range(k + 1)]
            )
            q = repair(np.vstack((q, extra)), clearance=2e-9)
            if q is None:
                break
        if time.monotonic() - start > 60:
            break
    save_bank("artifacts/round29_cpu_packings.npz", patch)
    Path("artifacts/round29_closure_history.json").write_text(
        json.dumps(
            dict(
                trials=trials,
                accepted=history,
                seconds=time.monotonic() - start,
                seeds=seeds,
            ),
            indent=2,
        )
    )
    print(
        "closure gain",
        sum(r["gain"] for r in history),
        "seconds",
        time.monotonic() - start,
        flush=True,
    )


if __name__ == "__main__":
    main()
