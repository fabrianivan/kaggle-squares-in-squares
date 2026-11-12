"""Per-puzzle best over the current submission and every CSV found in the given directories.

A candidate only replaces a puzzle if the official interval metric certifies it strictly better, and the text that
gets certified is exactly the text written to the merged file, so the board sees what we measured. Rows for
untouched puzzles are copied from the base file verbatim.

    .venv/bin/python -u src/tools/merge_harvest.py --base output/submission_22.233377.csv \
        --dirs data/harvest_1106 data/fresh_sync_today [--workers 8] [--no-validate]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric  # noqa: E402

COLS = ("n", "square_id", "x", "y", "angle")


def sides_of(path: Path):
    """{n: (L, DataFrame)} for every well-formed puzzle in a CSV, or {} if the file is not a packing table."""
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if not set(COLS) <= set(df.columns):
        return {}
    df = df[list(COLS)].apply(pd.to_numeric, errors="coerce")
    if df.isna().any().any():
        df = df.dropna()
    out = {}
    for n, g in df.groupby("n"):
        n = int(n)
        if not 1 <= n <= 1000 or len(g) != n:
            continue
        g = g.sort_values("square_id")
        x, y, t = (g[c].to_numpy(float) for c in ("x", "y", "angle"))
        c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
        X = np.concatenate([x + c - s, x - c - s, x - c + s, x + c + s])
        Y = np.concatenate([y + s + c, y - s + c, y - s - c, y + s - c])
        out[n] = (float(max(X.max() - X.min(), Y.max() - Y.min())), g)
    return out


def rows_as_text(n: int, g: pd.DataFrame):
    return [dict(n=str(n), square_id=str(int(r.square_id)), x=repr(float(r.x)), y=repr(float(r.y)),
                 angle=repr(float(r.angle))) for r in g.itertuples()]


def certify(job):
    n, rows = job
    try:
        _, _, L, why = metric.evaluate_single_puzzle(n, rows)
    except Exception as e:                                      # a malformed candidate must not kill the merge
        return n, None, f"exception {e}"
    if why != "ok" or L is None:
        return n, None, why
    return n, float(L), "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="output/submission_22.233377.csv")
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--tag", default="harvest")
    a = ap.parse_args()

    base_path = ROOT / a.base if not Path(a.base).is_absolute() else Path(a.base)
    print(f"base: {base_path}", flush=True)
    base = sides_of(base_path)
    base_score = sum(L / math.sqrt(n) - 1.0 for n, (L, _) in base.items())
    print(f"base puzzles {len(base)}, score {base_score:.12f}", flush=True)

    files = []
    for d in a.dirs:
        p = ROOT / d if not Path(d).is_absolute() else Path(d)
        files += sorted(f for f in p.rglob("*.csv") if f.is_file() and f.stat().st_size > 0)
    print(f"scanning {len(files)} candidate CSV files", flush=True)

    cand = {}                                                   # n -> (L, rows_text, source)
    for i, f in enumerate(files, 1):
        d = sides_of(f)
        if not d:
            continue
        hits = 0
        for n, (L, g) in d.items():
            cur = cand[n][0] if n in cand else base.get(n, (math.inf,))[0]
            if L < cur - 1e-12:
                cand[n] = (L, rows_as_text(n, g), str(f.relative_to(ROOT)))
                hits += 1
        if hits:
            print(f"  [{i}/{len(files)}] {f.relative_to(ROOT)}: {hits} candidate wins", flush=True)

    if not cand:
        print("no candidate beats the base on any puzzle", flush=True)
        return
    print(f"\n{len(cand)} puzzles have a better candidate; certifying with the official metric", flush=True)

    t0 = time.time()
    wins = {}
    jobs = [(n, v[1]) for n, v in sorted(cand.items())]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for n, L, why in pool.map(certify, jobs):
            L0 = base[n][0]
            if L is not None and L < L0 - 1e-12:
                g = (L0 - L) / math.sqrt(n)
                wins[n] = (L, cand[n][1])
                print(f"  certified n={n:4d} {L0:.9f} -> {L:.9f}  gain {g:.3e}  [{cand[n][2]}]", flush=True)
            else:
                print(f"  rejected  n={n:4d} ({why})", flush=True)
    print(f"certified {len(wins)}/{len(cand)} in {time.time()-t0:.0f}s", flush=True)
    if not wins:
        return

    gain = sum((base[n][0] - L) / math.sqrt(n) for n, (L, _) in wins.items())
    print(f"predicted new score {base_score - gain:.12f} (gain {gain:.12f})", flush=True)

    raw = pd.read_csv(base_path, dtype=str)
    out_rows, rid = [], 0
    for n_str, g in raw.groupby("n", sort=False):
        n = int(n_str)
        if n in wins:
            for r in wins[n][1]:
                out_rows.append((rid, n, r["square_id"], r["x"], r["y"], r["angle"])); rid += 1
        else:
            for r in g.sort_values("square_id", key=lambda c: c.astype(int)).itertuples():
                out_rows.append((rid, n, r.square_id, r.x, r.y, r.angle)); rid += 1

    tmp = ROOT / "output" / f"submission_{a.tag}_tmp.csv"
    with open(tmp, "w") as fh:
        fh.write("id,n,square_id,x,y,angle\n")
        for r in out_rows:
            fh.write(",".join(map(str, r)) + "\n")
    print(f"wrote {tmp} ({rid} rows)", flush=True)

    if a.no_validate:
        return
    rep_path = ROOT / "output" / f"validation_report_{a.tag}.json"
    subprocess.run([sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"),
                    str(tmp), str(rep_path), "--workers", str(a.workers)], check=True)
    rep = json.loads(rep_path.read_text())
    score = rep["score"]
    assert not rep["rejected"], rep["rejected"][:3]
    final = ROOT / "output" / f"submission_{score:.6f}.csv"
    final.write_bytes(tmp.read_bytes())
    print(f"\nCERTIFIED SCORE {score:.12f}  (base {base_score:.12f}, gain {base_score - score:.12f})", flush=True)
    print(f"saved {final}", flush=True)


if __name__ == "__main__":
    main()
