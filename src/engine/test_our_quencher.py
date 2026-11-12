"""Test our proprietary OriginalGadgetQuencher on donor gadgets.
"""

from __future__ import annotations
import os
import sys
import pickle
import time
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import fault_dp as F
from src.engine.orig_gadget_quencher import OriginalGadgetQuencher

def main():
    cache_file = os.path.join(ROOT, "tmp/g_base_cache.pkl")
    with open(cache_file, "rb") as fh:
        donors, G_base = pickle.load(fh)

    test_keys = [
        (20, 21, 5),
        (25, 26, 10),
        (27, 27, 10),
        (27, 28, 8),
        (29, 29, 12),
    ]

    print("Testing OriginalGadgetQuencher on target keys:")
    for key in test_keys:
        w, h, dm = key
        rows = np.where((G_base[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            print(f"  Key {key} not found in G_base")
            continue

        best_row_idx = rows[np.argmin(G_base[rows, 3])]
        _, _, _, f_base, _, _, di, si = G_base[best_row_idx]
        gadget = F.crop(donors[int(di)], int(si), int(w), int(h), int(dm))[0]

        centers = gadget[:, :2].copy()
        angles = gadget[:, 2].copy()

        quencher = OriginalGadgetQuencher(w=int(w), h=int(h), guard_buffer=1e-11, trust_pos=0.015, trust_ang=0.03)
        f_init = quencher.compute_overhang(centers, angles)

        t0 = time.time()
        new_c, new_a, f_new, feas = quencher.quench(centers, angles, max_rounds=25)
        elapsed = time.time() - t0

        delta_f = f_init - f_new
        print(f"  [{w}x{h}+{dm}] f: {f_init:.8f} -> {f_new:.8f} (Delta f = {delta_f:.2e}) in {elapsed:.2f}s")

if __name__ == "__main__":
    main()
