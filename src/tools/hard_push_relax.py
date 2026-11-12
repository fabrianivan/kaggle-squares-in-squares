"""Bounded parallel Rust squeeze search for high-impact puzzles."""
import argparse, math, subprocess, tempfile
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd

from packing_geometry import aabbs, min_gap, repair, side


def job(args):
    n, input_csv, binary, outdir, delta = args
    group = input_csv[ n ]
    p = group.copy()
    p[:, :2] -= aabbs(p)[0].min(0)
    old = side(p)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.txt", Path(tmp) / "out.txt"
        with src.open("w") as f:
            f.write(f"{n} {old:.17g}\n")
            for x, y, angle in p:
                f.write(f"{x:.17g} {y:.17g} {math.degrees(angle):.17g}\n")
        target = old - delta
        try:
            subprocess.run(
                [binary, "relax", "--in", str(src), "--s", f"{target:.17g}",
                 "--squeeze", "--out", str(dst)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return n, old, None
        if not dst.exists():
            return n, old, None
        lines = [line.split() for line in dst.read_text().splitlines() if line.strip()]
        if len(lines) != n + 1:
            return n, old, None
        q = np.array([[float(x), float(y), math.radians(float(a))] for x, y, a, *_ in lines[1:]])
        if len(q) != n or min_gap(q) < 0:
            q = repair(q)
        if q is None:
            return n, old, None
        new = side(q)
        if new >= old - 1e-8:
            return n, old, None
        out = Path(outdir) / f"{n}.csv"
        with out.open("w") as f:
            f.write("n,square_id,x,y,angle\n")
            for i, (x, y, a) in enumerate(q):
                f.write(f"{n},{i},{x:.17g},{y:.17g},{a:.17g}\n")
        return n, old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", default="output/submission_final.csv")
    ap.add_argument("--binary", default="data/new_sources/external/evand/search/packer/target/release/packer")
    ap.add_argument("--outdir", default="output/hard_push")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delta", type=float, default=1e-4)
    args = ap.parse_args()
    df = pd.read_csv(args.submission)
    bank = {int(n): g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
            for n, g in df.groupby("n")}
    targets = [11, 17, 18, 19, 26, 27, 28, 29, 37, 38, 39, 40, 41, 50, 51, 53, 55, 65, 66, 67, 68, 69, 70, 71, 84, 86]
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    jobs = [(n, bank, args.binary, args.outdir, args.delta) for n in targets]
    with Pool(args.workers) as pool:
        for n, old, new in pool.imap_unordered(job, jobs):
            print(f"n={n} old={old:.9f} new={new}", flush=True)


if __name__ == "__main__":
    main()
