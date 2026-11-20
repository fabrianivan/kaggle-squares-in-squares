import math
import subprocess
import os
import sys
import numpy as np
import pandas as pd

# Add project root and starter kit to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))

import metric

PACKER = os.path.join(ROOT, "data/new_sources/alexchilton/evand/search/packer/target/release/packer")


def get_corners(xs, ys, angs):
    # angs in radians
    c = np.cos(angs) * 0.5
    s = np.sin(angs) * 0.5
    dx = np.array([-1, 1, 1, -1])
    dy = np.array([-1, -1, 1, 1])
    # vx, vy: shape (n, 4)
    vx = xs[:, None] + (c[:, None]*dx - s[:, None]*dy)
    vy = ys[:, None] + (s[:, None]*dx + c[:, None]*dy)
    return vx, vy

def compute_L(xs, ys, angs):
    vx, vy = get_corners(xs, ys, angs)
    return max(vx.max() - vx.min(), vy.max() - vy.min())

def test_puzzle(n, csv_path="output/submission_final.csv", mode="relax", iters=20000, seed=42):
    df = pd.read_csv(csv_path)
    puzzle = df[df["n"] == n].sort_values("square_id").copy()
    if len(puzzle) == 0:
        print(f"n={n} not found")
        return None
        
    xs = puzzle["x"].values.copy()
    ys = puzzle["y"].values.copy()
    angs = puzzle["angle"].values.copy() # in radians
    
    vx, vy = get_corners(xs, ys, angs)
    min_x, min_y = vx.min(), vy.min()
    xs -= min_x
    ys -= min_y
    
    L0 = compute_L(xs, ys, angs)
    print(f"\n[n={n}] Current side L0 = {L0:.12f}")
    
    os.makedirs("tmp/packer", exist_ok=True)
    in_file = f"tmp/packer/in_{n}.txt"
    out_file = f"tmp/packer/out_{n}.txt"
    if os.path.exists(out_file):
        os.remove(out_file)
        
    with open(in_file, "w") as f:
        f.write(f"{n} {L0 + 1e-12:.17f}\n")
        for x, y, a in zip(xs, ys, angs):
            deg = math.degrees(a) % 90.0
            f.write(f"{x:.17f} {y:.17f} {deg:.15f}\n")
            
    if mode == "relax":
        cmd = [PACKER, "relax", "--in", in_file, "--squeeze", "--out", out_file]
    elif mode == "hop":
        cmd = [PACKER, "hop", "--in", in_file, "--s", f"{L0:.15f}", "--seed", str(seed), "--iters", str(iters), "--out", out_file]
    else:
        raise ValueError(mode)
        
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Packer stderr: {res.stderr}")
        return None
        
    if not os.path.exists(out_file):
        print(f"Packer did not produce {out_file}")
        return None
        
    lines = [line.strip().split() for line in open(out_file) if line.strip() and not line.startswith("#")]
    if not lines:
        print("Empty packer output")
        return None
        
    header = lines[0]
    out_L = float(header[1])
    print(f"Packer returned side: {out_L:.12f} (raw diff: {L0 - out_L:.10e})")
    
    data_lines = lines[1:]
    new_xs = np.array([float(r[0]) for r in data_lines])
    new_ys = np.array([float(r[1]) for r in data_lines])
    new_angs = np.array([math.radians(float(r[2])) for r in data_lines])
    
    # Check official metric
    # The metric expects list[dict] where x, y, angle are string formatted numbers
    cand_records = [
        {'square_id': i, 'x': f"{new_xs[i]:.17f}", 'y': f"{new_ys[i]:.17f}", 'angle': f"{new_angs[i]:.17f}"}
        for i in range(n)
    ]
    
    _n, score, L_str, reason = metric.evaluate_single_puzzle(n, cand_records)
    certified_L = float(L_str) if L_str is not None else float("inf")
    print(f"Metric cert: side={certified_L:.12f}, reason={reason}")
    
    if reason == "ok" and certified_L < L0 - 1e-11:
        gain = (L0 - certified_L) / np.sqrt(n)
        print(f"*** VERIFIED IMPROVEMENT FOR n={n}: L {L0:.12f} -> {certified_L:.12f}, Gain: {gain:.10e} ***")
        return certified_L, cand_records
    elif reason != "ok":
        # try dilating slightly
        print(f"Uncertified with reason={reason}, trying dilation...")
        cx, cy = (new_xs.min() + new_xs.max()) / 2, (new_ys.min() + new_ys.max()) / 2
        for factor in [1e-12, 1e-11, 1e-10, 1e-9]:
            d_xs = cx + (new_xs - cx) * (1 + factor)
            d_ys = cy + (new_ys - cy) * (1 + factor)
            d_records = [
                {'square_id': i, 'x': f"{d_xs[i]:.17f}", 'y': f"{d_ys[i]:.17f}", 'angle': f"{new_angs[i]:.17f}"}
                for i in range(n)
            ]
            _n, sc, d_L_str, r = metric.evaluate_single_puzzle(n, d_records)
            if r == "ok":
                cL = float(d_L_str)
                print(f"Certified with dilation {factor:.1e}: side={cL:.12f}")
                if cL < L0 - 1e-11:
                    gain = (L0 - cL) / np.sqrt(n)
                    print(f"*** VERIFIED IMPROVEMENT FOR n={n}: L {L0:.12f} -> {cL:.12f}, Gain: {gain:.10e} ***")
                    return cL, d_records
                else:
                    print("Dilation lost advantage.")
                break
    return None

if __name__ == "__main__":
    target_n = int(sys.argv[1]) if len(sys.argv) > 1 else 51
    mode = sys.argv[2] if len(sys.argv) > 2 else "relax"
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
    test_puzzle(target_n, mode=mode, iters=iters)
