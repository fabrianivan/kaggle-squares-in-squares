"""Whole-packing union of pinned public inputs; optional independently repaired CPU patches."""

import csv, json, hashlib, math
from pathlib import Path
import numpy as np
from packing_geometry import load_bank, side, total_score, repair, save_bank, grid

SOURCES = json.loads(Path("artifacts/round29_union_scan.json").read_text())[
    "source_paths"
]


def main():
    b = {k: load_bank(p) for k, p in SOURCES.items()}
    raw = {}
    chosen = {}
    which = {}
    gains = []
    for n in range(1, 1001):
        k = min(b, key=lambda k: side(b[k][n]))
        k = (
            k
            if (side(b["leader"][n]) - side(b[k][n])) / math.sqrt(n) > 1e-8
            else "leader"
        )
        chosen[n] = b[k][n]
        which[n] = k
    patch_path = Path("artifacts/round29_cpu_packings.npz")
    patch = {}
    if patch_path.exists():
        with np.load(patch_path) as z:
            for key in z.files:
                n = int(key)
                q = repair(np.rint(z[key] * 1e12) / 1e12, clearance=2e-9)
                if q is not None and (side(chosen[n]) - side(q)) / math.sqrt(n) > 1e-8:
                    chosen[n] = q
                    which[n] = "cpu"
                    patch[n] = q
    for k, path in SOURCES.items():
        wanted = {
            n
            for n in which
            if which[n] == k and side(chosen[n]) < math.ceil(math.sqrt(n)) - 1e-7
        }
        raw[k] = {}
        if not wanted:
            continue
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                n = int(r["n"])
                if n in wanted:
                    raw[k].setdefault(n, []).append(
                        [r[x] for x in ["square_id", "x", "y", "angle"]]
                    )
    rows = 0
    path = Path("artifacts/round29_submission.csv")
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "n", "square_id", "x", "y", "angle"])
        for n in range(1, 1001):
            k = which[n]
            if k == "cpu":
                group = [
                    [sid, *[format(x, ".17g") for x in row]]
                    for sid, row in enumerate(patch[n])
                ]
            else:
                group = raw[k].get(n, [])
            if side(chosen[n]) >= math.ceil(math.sqrt(n)) - 1e-7:
                group = []
                chosen[n] = grid(n)
            for row in group:
                w.writerow([rows, n, *row])
                rows += 1
            gain = (side(b["leader"][n]) - side(chosen[n])) / math.sqrt(n)
            if gain > 1e-8:
                gains.append(
                    dict(
                        n=n,
                        source=k,
                        before=side(b["leader"][n]),
                        after=side(chosen[n]),
                        gain=gain,
                        donor_side=min(side(bank[n]) for bank in b.values()),
                        cpu_increment=max(
                            0.0,
                            (min(side(b[k2][n]) for k2 in b) - side(chosen[n]))
                            / math.sqrt(n),
                        ),
                    )
                )
    save_bank("artifacts/round29_packings.npz", chosen)
    s = dict(
        leader_score=total_score(b["leader"]),
        ours_score=total_score(b["ours"]),
        extra_score=min(total_score(bank) for bank in b.values()),
        source_scores={key: total_score(bank) for key, bank in b.items()},
        score=total_score(chosen),
        changes=gains,
        rows=rows,
        submitted_ns=[
            n
            for n in range(1, 1001)
            if side(chosen[n]) < math.ceil(math.sqrt(n)) - 1e-7
        ],
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_paths=SOURCES,
    )
    Path("artifacts/round29_summary.json").write_text(json.dumps(s, indent=2))
    print(
        "union",
        s["score"],
        "changes",
        len(gains),
        "CPU",
        sum(r["source"] == "cpu" for r in gains),
        flush=True,
    )


if __name__ == "__main__":
    main()
