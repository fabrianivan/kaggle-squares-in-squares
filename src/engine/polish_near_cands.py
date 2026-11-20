"""Polish near-miss candidate packings from tmp/near_cands.pkl using FQ.

Tests if alternative topology basins discovered in historical runs can be
squeezed below our current best submission.
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src" / "metric"))
import metric  # noqa: E402

FQ_BIN = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "fq")


def polish_candidate(args: tuple[int, int, np.ndarray, float, float, str]) -> tuple[int, int, bool, float, float, list[dict] | None, str]:
    """Worker to polish a single candidate packing."""
    n, cand_idx, sq, L_cand, L0, tmp_dir = args

    in_path = os.path.join(tmp_dir, f"in_{n}_{cand_idx}.txt")
    out_path = os.path.join(tmp_dir, f"out_{n}_{cand_idx}.txt")

    try:
        with open(in_path, "w") as f:
            f.write(f"{n} {L_cand:.17f}\n")
            for xi, yi, ti in sq:
                deg = math.degrees(ti) % 90.0
                f.write(f"{xi:.17f} {yi:.17f} {deg:.17f}\n")

        # Try rigid finish
        cmd = [FQ_BIN, "quench", "--in", in_path, "--out", out_path, "--loosen", "1.0", "--no-alm", "--finish"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)

        if res.returncode != 0 or not os.path.exists(out_path):
            return n, cand_idx, False, L0, L0, None, "fq failed"

        with open(out_path) as f:
            head = f.readline().split()
            if len(head) < 2:
                return n, cand_idx, False, L0, L0, None, "bad header"
            s_out = float(head[1])

            if s_out >= L0 - 1e-11:
                return n, cand_idx, False, L0, s_out, None, "no win"

            new_rows = []
            for i, line in enumerate(f):
                parts = line.strip().split()
                if len(parts) >= 3:
                    new_rows.append({
                        "id": "0",
                        "n": str(n),
                        "square_id": str(i),
                        "x": f"{float(parts[0]):.17f}",
                        "y": f"{float(parts[1]):.17f}",
                        "angle": f"{math.radians(float(parts[2])):.17f}",
                    })

        if len(new_rows) != n:
            return n, cand_idx, False, L0, s_out, None, "row count mismatch"

        _, _, L_cert, why = metric.evaluate_single_puzzle(n, new_rows)
        if why != "ok" or L_cert is None:
            return n, cand_idx, False, L0, s_out, None, f"cert failed: {why}"

        L_cert_float = float(L_cert)
        if L_cert_float < L0 - 1e-11:
            return n, cand_idx, True, L0, L_cert_float, new_rows, "ok"
        else:
            return n, cand_idx, False, L0, L_cert_float, None, "not strictly better"

    except Exception as e:
        return n, cand_idx, False, L0, L0, None, f"exception: {e}"
    finally:
        for p in (in_path, out_path, f"{out_path}.tmp"):
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="output/submission_22.178805.csv")
    parser.add_argument("--near-cands", default="tmp/near_cands.pkl")
    parser.add_argument("--out", default="output/submission_near_polish.csv")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    print(f"Loading base submission: {args.base}", flush=True)
    df = pd.read_csv(args.base, dtype=str)
    cur_L = {}
    groups = {}
    for n_str, g in df.groupby("n"):
        n = int(n_str)
        groups[n] = g.sort_values("square_id").to_dict("records")
        x = g["x"].to_numpy(float)
        y = g["y"].to_numpy(float)
        t = g["angle"].to_numpy(float)
        c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
        X = np.concatenate([x + c - s, x - c - s, x - c + s, x + c + s])
        Y = np.concatenate([y + s + c, y - s + c, y - s - c, y + s - c])
        cur_L[n] = float(max(X.max() - X.min(), Y.max() - Y.min()))

    print(f"Loading near candidates from: {args.near_cands}", flush=True)
    with open(args.near_cands, "rb") as f:
        near_cands = pickle.load(f)

    tmp_dir = tempfile.mkdtemp(prefix="near_polish_")
    tasks = []
    for n, cands in near_cands.items():
        L0 = cur_L.get(n, 100.0)
        for idx, (L_cand, sq) in enumerate(cands):
            tasks.append((n, idx, sq, L_cand, L0, tmp_dir))

    print(f"Total candidate tasks to evaluate: {len(tasks)} across {args.workers} workers", flush=True)

    t0 = time.time()
    wins = {}
    with mp.Pool(args.workers) as pool:
        for i, (n, c_idx, ok, L0, L_new, new_rows, msg) in enumerate(pool.imap_unordered(polish_candidate, tasks)):
            if ok:
                dL = L0 - L_new
                score_gain = dL / math.sqrt(n)
                if n not in wins or L_new < wins[n][1]:
                    wins[n] = (L0, L_new, dL, score_gain, new_rows)
                    print(f"[{i+1}/{len(tasks)}] NEAR-CAND WIN n={n:3d} (cand {c_idx}): L {L0:.10f} -> {L_new:.10f} (gain={score_gain:.2e})", flush=True)
            elif (i + 1) % 100 == 0 or i + 1 == len(tasks):
                print(f"[{i+1}/{len(tasks)}] Checked {i+1} candidates. Total wins so far: {len(wins)}", flush=True)

    dt = time.time() - t0
    print(f"\nNear-cands polishing finished in {dt:.1f}s!", flush=True)
    print(f"Total wins found: {len(wins)}", flush=True)
    tot_gain = sum(v[3] for v in wins.values())
    print(f"Total score gain from near cands: {tot_gain:.8e}", flush=True)

    if wins:
        out_rows = []
        for n in range(1, 1001):
            if n in wins:
                out_rows.extend(wins[n][4])
            else:
                out_rows.extend(groups[n])
        out_df = pd.DataFrame(out_rows)
        out_df["id"] = range(len(out_df))
        cols = ["id", "n", "square_id", "x", "y", "angle"]
        out_df = out_df[cols]
        out_df.to_csv(args.out, index=False)
        print(f"Saved merged near-polish submission to {args.out}", flush=True)

    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass


if __name__ == "__main__":
    main()
