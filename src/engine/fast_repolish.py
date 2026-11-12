"""High-speed contact repolish using FQ rigid polish (--no-alm --loosen 1.0 --finish).

Squeezes numerical slack from active contact graphs across all non-trivial puzzles,
strictly certifying every candidate with the official mpmath interval metric.
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import os
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


def polish_single_puzzle(args: tuple[int, list[dict], float, str]) -> tuple[int, bool, float, float, list[dict] | None, str]:
    """Worker function to polish a single puzzle."""
    n, rows_orig, L0_float, tmp_dir = args

    # Write input file
    in_path = os.path.join(tmp_dir, f"in_{n}.txt")
    out_path = os.path.join(tmp_dir, f"out_{n}.txt")

    try:
        with open(in_path, "w") as f:
            f.write(f"{n} {L0_float:.17f}\n")
            for r in rows_orig:
                xi = float(r["x"])
                yi = float(r["y"])
                ti = float(r["angle"])
                deg = math.degrees(ti) % 90.0
                f.write(f"{xi:.17f} {yi:.17f} {deg:.17f}\n")

        cmd = [FQ_BIN, "quench", "--in", in_path, "--out", out_path, "--loosen", "1.0", "--no-alm", "--finish"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)

        if res.returncode != 0 or not os.path.exists(out_path):
            return n, False, L0_float, L0_float, None, f"fq error: {res.stderr[:60]}"

        # Parse output
        with open(out_path) as f:
            head = f.readline().split()
            if len(head) < 2:
                return n, False, L0_float, L0_float, None, "bad header"
            s_out = float(head[1])

            if s_out >= L0_float - 1e-11:
                return n, False, L0_float, s_out, None, "no gain"

            new_rows = []
            for i, line in enumerate(f):
                parts = line.strip().split()
                if len(parts) >= 3:
                    new_rows.append({
                        "id": f"{n}_{i}",
                        "n": str(n),
                        "square_id": str(i),
                        "x": f"{float(parts[0]):.17f}",
                        "y": f"{float(parts[1]):.17f}",
                        "angle": f"{math.radians(float(parts[2])):.17f}",
                    })

        if len(new_rows) != n:
            return n, False, L0_float, s_out, None, f"bad row count {len(new_rows)}"

        # Certify with official interval metric
        _, _, L_cert, why = metric.evaluate_single_puzzle(n, new_rows)
        if why != "ok" or L_cert is None:
            return n, False, L0_float, s_out, None, f"cert failed: {why}"

        L_cert_float = float(L_cert)
        if L_cert_float < L0_float - 1e-11:
            return n, True, L0_float, L_cert_float, new_rows, "ok"
        else:
            return n, False, L0_float, L_cert_float, None, "metric rejected (slack within interval)"

    except Exception as e:
        return n, False, L0_float, L0_float, None, f"exception: {e}"
    finally:
        for p in (in_path, out_path, f"{out_path}.tmp"):
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="output/submission_22.178807.csv")
    parser.add_argument("--out", default="output/submission_repolish.csv")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    print(f"Loading base submission: {args.base}")
    df = pd.read_csv(args.base, dtype=str)

    # Group by n
    groups = {int(n): g.sort_values("square_id").to_dict("records") for n, g in df.groupby("n")}

    # Calculate L0 for each puzzle
    todo = []
    tmp_dir = tempfile.mkdtemp(prefix="repolish_")

    for n in range(1, 1001):
        rows = groups[n]
        # Calculate bounding box
        x = np.array([float(r["x"]) for r in rows])
        y = np.array([float(r["y"]) for r in rows])
        t = np.array([float(r["angle"]) for r in rows])
        c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
        X = np.concatenate([x + c - s, x - c - s, x - c + s, x + c + s])
        Y = np.concatenate([y + s + c, y - s + c, y - s - c, y + s - c])
        L0 = float(max(X.max() - X.min(), Y.max() - Y.min()))

        # Non-trivial puzzles only
        if L0 < math.ceil(math.sqrt(n)) - 1e-9:
            todo.append((n, rows, L0, tmp_dir))

    print(f"Total non-trivial puzzles to polish: {len(todo)} across {args.workers} workers")

    t0 = time.time()
    improved_puzzles = {}
    total_gain = 0.0

    with mp.Pool(args.workers) as pool:
        for i, (n, ok, L_old, L_new, new_rows, msg) in enumerate(pool.imap_unordered(polish_single_puzzle, todo)):
            if ok:
                dL = L_old - L_new
                score_gain = dL / math.sqrt(n)
                total_gain += score_gain
                improved_puzzles[n] = (L_old, L_new, dL, score_gain, new_rows)
                print(f"[{i+1}/{len(todo)}] WIN n={n:3d}: L {L_old:.10f} -> {L_new:.10f} (dL={dL:.2e}, gain={score_gain:.2e})")
            elif (i + 1) % 50 == 0 or i + 1 == len(todo):
                print(f"[{i+1}/{len(todo)}] Progress: {len(improved_puzzles)} wins, cumulative gain={total_gain:.4e}")

    dt = time.time() - t0
    print(f"\nPolishing finished in {dt:.1f}s!")
    print(f"Total improved puzzles: {len(improved_puzzles)}")
    print(f"Total certified score gain: {total_gain:.8e}")

    # Build output dataframe
    if improved_puzzles:
        out_rows = []
        for n in range(1, 1001):
            if n in improved_puzzles:
                out_rows.extend(improved_puzzles[n][4])
            else:
                out_rows.extend(groups[n])

        out_df = pd.DataFrame(out_rows)
        # Ensure column order
        cols = ["id", "n", "square_id", "x", "y", "angle"]
        out_df = out_df[cols]
        out_df.to_csv(args.out, index=False)
        print(f"Saved improved submission to {args.out}")

    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass


if __name__ == "__main__":
    main()
