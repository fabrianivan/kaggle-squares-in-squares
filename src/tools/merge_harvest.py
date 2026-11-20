"""Per-puzzle best over the current submission and every CSV found in the given directories.

A candidate only replaces a puzzle if the official interval metric certifies it strictly better, and the text that
gets certified is exactly the text written to the merged file, so the board sees what we measured. Rows for
untouched puzzles are copied from the base file verbatim.

    .venv/bin/python -u src/tools/merge_harvest.py --base output/submission_22.233377.csv \
        --dirs data/harvest_1106 data/fresh_sync_today [--workers 8] [--no-validate]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
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


_FAST_DT = {"n": np.int64, "square_id": np.int64, "x": np.float64, "y": np.float64, "angle": np.float64}


def sides_of(path: Path, filter_ns: set[int] | None = None):
    """{n: (L, DataFrame)} for every well-formed puzzle in a CSV, or {} if the file is not a packing table."""
    try:
        with Path(path).open("r", newline="") as fh:
            hdr = next(csv.reader(fh), None)
        if not hdr or not set(COLS) <= set(hdr):
            return {}
        try:
            df = pd.read_csv(path, usecols=list(COLS), dtype=_FAST_DT)
        except Exception:
            df = pd.read_csv(path, usecols=list(COLS))
            df = df[list(COLS)].apply(pd.to_numeric, errors="coerce")
            if df.isna().any().any():
                df = df.dropna()
    except Exception:
        return {}
    if filter_ns is not None:
        df = df[df["n"].isin(filter_ns)]
    if df.empty:
        return {}
    ns = df["n"].to_numpy(np.int64, copy=False)
    sid = df["square_id"].to_numpy(np.int64, copy=False)
    if np.any(ns[1:] < ns[:-1]) or np.any((ns[1:] == ns[:-1]) & (sid[1:] < sid[:-1])):
        order = np.lexsort((sid, ns))
        df = df.iloc[order]
        ns = df["n"].to_numpy(np.int64, copy=False)
    x = df["x"].to_numpy(np.float64, copy=False)
    y = df["y"].to_numpy(np.float64, copy=False)
    t = df["angle"].to_numpy(np.float64, copy=False)
    ex = 0.5 * (np.abs(np.cos(t)) + np.abs(np.sin(t)))
    splits = np.flatnonzero(ns[1:] != ns[:-1]) + 1
    starts = np.concatenate(([0], splits))
    ends = np.concatenate((splits, [len(ns)]))
    sides = np.maximum(
        np.maximum.reduceat(x + ex, starts) - np.minimum.reduceat(x - ex, starts),
        np.maximum.reduceat(y + ex, starts) - np.minimum.reduceat(y - ex, starts),
    )
    arr = df[["square_id", "x", "y", "angle"]].to_numpy(copy=False)
    out = {}
    for k, (a, b) in enumerate(zip(starts, ends)):
        n = int(ns[a])
        if 1 <= n <= 1000 and (b - a) == n:
            out[n] = (float(sides[k]), arr[a:b])
    return out


def rows_as_text(n: int, g):
    n_str = str(n)
    if isinstance(g, pd.DataFrame):
        arr = g[["square_id", "x", "y", "angle"]].to_numpy()
        return [
            dict(n=n_str, square_id=str(int(r[0])), x=repr(float(r[1])), y=repr(float(r[2])), angle=repr(float(r[3])))
            for r in arr
        ]
    arr = np.asarray(g)
    if arr.shape[1] == 4:
        return [
            dict(n=n_str, square_id=str(int(r[0])), x=repr(float(r[1])), y=repr(float(r[2])), angle=repr(float(r[3])))
            for r in arr
        ]
    return [
        dict(n=n_str, square_id=str(k), x=repr(float(arr[k, 0])), y=repr(float(arr[k, 1])), angle=repr(float(arr[k, 2])))
        for k in range(len(arr))
    ]


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

    tmp = ROOT / "output" / f"submission_{a.tag}_tmp.csv"
    rid = 0
    seen_n: set[int] = set()
    with base_path.open("r", newline="") as src, tmp.open("w") as fh:
        reader = csv.reader(src)
        hdr = next(reader)
        ix = {col: hdr.index(col) for col in ("n", "square_id", "x", "y", "angle")}
        i_n, i_s, i_x, i_y, i_a = ix["n"], ix["square_id"], ix["x"], ix["y"], ix["angle"]
        fh.write("id,n,square_id,x,y,angle\n")

        def _flush_group(n_val: int, rows_buf: list[tuple[int, str, str, str, str]]) -> None:
            nonlocal rid
            if n_val in wins:
                buf = [f"{rid + k},{n_val},{r['square_id']},{r['x']},{r['y']},{r['angle']}\n"
                       for k, r in enumerate(wins[n_val][1])]
                fh.writelines(buf)
                rid += len(buf)
                return
            if any(rows_buf[k][0] > rows_buf[k + 1][0] for k in range(len(rows_buf) - 1)):
                rows_buf.sort(key=lambda r: r[0])
            buf = [f"{rid + k},{n_val},{sid_s},{xs},{ys},{as_}\n"
                   for k, (_, sid_s, xs, ys, as_) in enumerate(rows_buf)]
            fh.writelines(buf)
            rid += len(buf)

        cur_n: int | None = None
        cur_rows: list[tuple[int, str, str, str, str]] = []
        for row in reader:
            n_val = int(row[i_n])
            if cur_n is not None and n_val != cur_n:
                if n_val in seen_n:
                    raise ValueError(f"Non-contiguous group for n={n_val} in {base_path}")
                _flush_group(cur_n, cur_rows)
                seen_n.add(cur_n)
                cur_rows = []
            cur_n = n_val
            cur_rows.append((int(row[i_s]), row[i_s], row[i_x], row[i_y], row[i_a]))
        if cur_n is not None:
            _flush_group(cur_n, cur_rows)
    print(f"wrote {tmp} ({rid} rows)", flush=True)

    if a.no_validate:
        return
    rep_path = ROOT / "output" / f"validation_report_{a.tag}.json"
    subprocess.run([sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"),
                    str(tmp), str(rep_path), "--workers", str(a.workers)], check=True)
    rep = json.loads(rep_path.read_text())
    score = rep["score"]
    assert not rep["rejected"], rep["rejected"][:3]
    # Nine decimals so two results never share a name, and an atomic rename so a file that is being uploaded is
    # never rewritten in place (two merges once both rounded to 22.159031 and Kaggle received a half-written file).
    final = ROOT / "output" / f"submission_{score:.9f}.csv"
    staging = final.with_name(final.name + ".partial")
    staging.write_bytes(tmp.read_bytes())
    os.replace(staging, final)
    print(f"\nCERTIFIED SCORE {score:.12f}  (base {base_score:.12f}, gain {base_score - score:.12f})", flush=True)
    print(f"saved {final}", flush=True)


if __name__ == "__main__":
    main()
