"""Event-Chain Basin Hopping (Option B: Non-Ladder Jammed Puzzles).

Runs hard-square Event-Chain Monte Carlo + Augmented Lagrangian squeeze (packer hhop)
with soft-transient penalty steps (--soft 0.25) to jump over combinatorial contact barriers
in the highest-excess non-ladder puzzles (n < 325).
"""

import math, os, subprocess, sys, tempfile, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "alexchilton_starter_kit"))
from ensemble import side, certify

PACKER_BIN = str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "packer")


def run_single_puzzle(job):
    n, sq, iters, seed, soft, gmax = job
    s0 = side(sq)
    t0 = time.time()

    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.txt")
        out = os.path.join(d, "out.txt")
        with open(inp, "w") as f:
            f.write(f"{n} {s0:.17f}\n")
            for x, y, a in sq:
                f.write(f"{x:.17f} {y:.17f} {math.degrees(a) % 90.0:.15f}\n")

        cmd = [
            PACKER_BIN, "hhop",
            "--in", inp,
            "--seed", str(seed),
            "--iters", str(iters),
            "--soft", str(soft),
            "--gmax", str(gmax),
            "--etol", "1e-20",
            "--out", out
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            return n, s0, None, "TIMEOUT", time.time() - t0

        if not os.path.exists(out):
            return n, s0, None, f"NO_OUT ({res.stderr[:60]})", time.time() - t0

        rows = [l.split() for l in open(out) if l.strip() and not l.startswith("#")][1:]
        new = np.array([[float(a), float(b), math.radians(float(c))] for a, b, c, *_ in rows])
        s1 = side(new)
        if s1 >= s0 - 1e-9:
            return n, s0, s1, "NO_GAIN", time.time() - t0

        # Center-relative non-destructive dilation
        cx, cy = (new[:, 0].min() + new[:, 0].max()) / 2, (new[:, 1].min() + new[:, 1].max()) / 2
        new[:, 0] = cx + (new[:, 0] - cx) * (1 + 1e-12)
        new[:, 1] = cy + (new[:, 1] - cy) * (1 + 1e-12)

        r = certify(n, new)
        if r is None:
            return n, s0, s1, "UNCERTIFIED", time.time() - t0

        return n, s0, r[0], "CERTIFIED", time.time() - t0, new


def main():
    base_csv = sys.argv[1] if len(sys.argv) > 1 else "output/submission_final.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "output/hhop_run"
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 42

    os.makedirs(out_dir, exist_ok=True)
    df = pd.read_csv(base_csv)

    # Top 10 highest-excess non-ladder targets
    targets = [68, 86, 105, 127, 147, 175, 51, 84, 103, 106]
    print(f"[{time.strftime('%H:%M:%S')}] Launching Option B (ECMC Basin Hopping) on {len(targets)} targets:")
    print(f"Targets: {targets}, iters={iters}, procs={procs}, seed={seed}")

    jobs = []
    for n in targets:
        sub = df[df.n == n].sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
        jobs.append((n, sub, iters, seed, 0.25, 0.04))

    total_gain = 0.0
    wins = []

    with Pool(procs) as pool:
        for res in pool.imap_unordered(run_single_puzzle, jobs):
            n, s0, s1, why, elapsed = res[:5]
            if why == "CERTIFIED":
                new_sq = res[5]
                gain = (s0 - s1) / math.sqrt(n)
                total_gain += gain
                wins.append((n, s1, s0, gain))
                out_p = f"{out_dir}/{n}.csv"
                with open(out_p, "w") as fh:
                    fh.write("n,square_id,x,y,angle\n")
                    for i, (x, y, t) in enumerate(new_sq):
                        fh.write(f"{n},{i},{float(x)!r},{float(y)!r},{float(t)!r}\n")
                print(f"[{time.strftime('%H:%M:%S')}] n={n:3d}: CERTIFIED {s1:.9f} vs {s0:.9f} (gain {gain:.2e}) in {elapsed:.1f}s | Total gain: {total_gain:.8f}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] n={n:3d}: {why} (s0={s0:.9f}, s1={s1 if s1 else s0:.9f}) in {elapsed:.1f}s")

    print(f"[{time.strftime('%H:%M:%S')}] Option B complete. Total certified gain: {total_gain:.8f} across {len(wins)} puzzles.")


if __name__ == "__main__":
    main()

