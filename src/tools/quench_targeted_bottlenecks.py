"""Parallel Homotopy Quencher for Active Bottleneck Gadgets."""

import math, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
ALEX_DIR = ROOT / "data" / "new_sources" / "alexchilton_starter_kit"
sys.path.insert(0, str(ALEX_DIR))

import fault_dp as F
import skeleton as S

G_base = None
donors = None

def init_worker():
    global G_base, donors
    G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
    cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

def squeeze_key_worker(key):
    global G_base, donors
    w, h, dm = key
    rows = np.where((G_base[:, :3].astype(int) == np.array(key)).all(1))[0]
    if not len(rows):
        return key, 0.0, 0.0, None, 0
    best_row = rows[np.argmin(G_base[rows, 3])]
    _, _, _, f, _, _, di, si = G_base[best_row]
    sq, _ = F.crop(donors[int(di)], int(si), int(w), int(h), int(dm))
    f0 = S.overhang(sq, int(w), int(h))

    t0 = time.time()
    best_sq, fbest = sq, f0
    k = 0
    stagnant = 0
    r0_schedule = [0.20, 0.15, 0.10, 0.06, 0.03, 0.015, 0.005, 0.0]
    
    while time.time() - t0 < 35.0:  # 35s per key
        k += 1
        r0 = r0_schedule[k % len(r0_schedule)]
        amp = 2.0 if stagnant > 5 else 1.0
        loosen = 1.0 + 0.005 * (1 + (k % 4)) * amp
        kick = 0.0025 * (1 + (k % 3)) * amp
        cand, f_c = S.quench(best_sq, int(w), int(h), loosen=loosen, kick=kick, seed=k * 137 + stagnant, round_r0=r0, outer=40)
        if f_c < fbest - 1e-11 and len(cand) == len(sq):
            best_sq, fbest = cand, f_c
            stagnant = 0
        else:
            stagnant += 1

    # Polish pass
    cand, f_c = S.quench(best_sq, int(w), int(h), loosen=1.00002, kick=0.0, seed=999, round_r0=0.0, outer=100)
    if f_c < fbest - 1e-11 and len(cand) == len(sq):
        best_sq, fbest = cand, f_c

    return key, f0, fbest, best_sq, k

def main():
    target_keys = [
        (11, 16, 4), (16, 11, 4),
        (15, 16, 4), (16, 15, 4),
        (21, 11, 9), (11, 21, 9),
        (7, 12, 5), (12, 7, 5),
        (10, 16, 7),
        (6, 15, 5), (15, 6, 5),
        (6, 13, 7), (13, 6, 7),
        (20, 11, 8), (11, 20, 8),
        (10, 15, 3), (15, 10, 3),
        (6, 14, 9), (14, 6, 9),
        (7, 13, 6), (13, 7, 6),
        (17, 10, 8), (10, 17, 8)
    ]

    print(f"Starting parallel quench on {len(target_keys)} bottleneck keys across 8 cores...")
    t_start = time.time()
    
    improved = []
    with Pool(8, initializer=init_worker) as pool:
        for key, f0, f1, sq, k in pool.imap_unordered(squeeze_key_worker, target_keys):
            df = f0 - f1
            if df > 1e-9:
                status = f">>> IMPROVED by {df:.8f}! <<<"
                improved.append((key, f0, f1, sq))
            else:
                status = "no improvement"
            print(f"{key}: f {f0:.8f} -> {f1:.8f} ({status}) [{k} rounds]", flush=True)

    print(f"\nCompleted in {time.time()-t_start:.1f}s. Improved {len(improved)}/{len(target_keys)} keys.")
    if improved:
        combined_path = ROOT / "output" / "all_quenched_gadgets_combined.npz"
        curr_gadgets = dict(np.load(combined_path))
        for key, f0, f1, sq in improved:
            name = f"{key[0]}_{key[1]}_{key[2]}"
            curr_gadgets[name] = sq
            print(f"Saved key {name} to reservoir.")
        np.savez(combined_path, **curr_gadgets)
        print("Updated persistent reservoir.")

if __name__ == "__main__":
    main()
