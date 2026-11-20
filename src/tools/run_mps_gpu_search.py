"""Run batched seam-pressure search using Apple Metal Performance Shaders (MPS) GPU acceleration."""

import math, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "data" / "new_sources" / "kirilltym"))
from portable_seam_search import seam_pressure, choose_device
from packing_geometry import load_bank, side, repair
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish

sys.path.insert(0, str(Path(__file__).resolve().parent / "reference_sources"))
from official_metric import evaluate_single_puzzle


def main():
    device = choose_device("mps")
    print(f"Initialized PyTorch GPU acceleration on {device}")

    base = "output/submission_final.csv"
    outdir = "output/mps_gpu_candidates"
    os.makedirs(outdir, exist_ok=True)

    bank = load_bank(base)

    target_ns = [51, 53, 54, 55, 68, 69, 70, 71, 83, 84, 85, 86, 87, 88, 89]
    print(f"Running MPS GPU search across {len(target_ns)} target puzzles...")

    for n in target_ns:
        p0 = bank[n]
        L0 = side(p0)
        t_start = time.time()
        print(f"n={n}: starting side {L0:.9f}")

        # GPU batch seam pressure search
        proposals, _ = seam_pressure(p0, backend="mps", seed=20261103 + n, batch=32, steps=180)

        # CPU axis reclosure
        q, _, _ = reclose(p0, seed=100 + n, rounds=8, seconds=3, trust=0.25, tie=0.1)
        proposals.append(q)

        best_cand = None
        best_L = L0

        for cand in sorted(proposals, key=side)[:6]:
            if side(cand) > L0 + 0.01:
                continue
            cand_p, _, _ = polish(cand, rounds=60, max_seconds=5, trust_start=0.015)
            r = repair(cand_p, clearance=2e-9)
            if r is not None and side(r) < best_L - 1e-9:
                best_L = side(r)
                best_cand = r

        if best_cand is not None:
            # Certify with official metric
            recs = [
                {"n": str(n), "square_id": str(i), "x": str(best_cand[i, 0]), "y": str(best_cand[i, 1]), "angle": str(best_cand[i, 2])}
                for i in range(len(best_cand))
            ]
            _, sc, L_cert, why = evaluate_single_puzzle(n, recs)
            if why == "ok" and float(L_cert) < L0 - 1e-9:
                official_L = float(L_cert)
                gain = (L0 - official_L) / math.sqrt(n)
                print(f"n={n}: *** NEW MPS GPU CERTIFIED RECORD *** L: {L0:.9f} -> {official_L:.9f} (gain: {gain:.8f})")
                out_p = f"{outdir}/{n}.csv"
                with open(out_p, "w") as fh:
                    fh.write("n,square_id,x,y,angle\n")
                    for i in range(len(best_cand)):
                        fh.write(f"{n},{i},{best_cand[i, 0]!r},{best_cand[i, 1]!r},{best_cand[i, 2]!r}\n")
            else:
                print(f"n={n}: candidate not certified ({why})")
        else:
            print(f"n={n}: no improvement after {time.time()-t_start:.1f}s")


if __name__ == "__main__":
    main()

