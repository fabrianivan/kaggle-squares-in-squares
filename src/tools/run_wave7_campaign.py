"""Wave-7 14-Core Asymmetric dm=5 Campaign.

Targets 56 prime unquenched asymmetric keys (dm=5, |w-h| in [4, 23], area <= 280, f0 in [0.70, 0.75]).
Dispatches across 14 cores using multi-stage homotopy pressure annealing.
Automatically updates the reservoir, solves the DP ladder, and validates improvements.
"""

import math
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))
sys.path.insert(0, str(ROOT / "src" / "metric"))

import metric
import fault_dp as F
import skeleton as S
from ensemble import side, certify

FQ = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "fq")
SUBMISSION_PATH = str(ROOT / "output" / "submission_22.246775.csv")
RESERVOIR_PATH = str(ROOT / "output" / "all_quenched_gadgets_combined.npz")

G_base = None
donors = None
res_data = None

def init_worker():
    global G_base, donors, res_data
    G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
    cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
    if os.path.exists(RESERVOIR_PATH):
        res_data = dict(np.load(RESERVOIR_PATH))
    else:
        res_data = {}

def quench_worker(job):
    key, seed_base, budget_sec = job
    w, h, dm = key
    key_str = f"{w}_{h}_{dm}"
    
    if key_str in res_data:
        sq = res_data[key_str]
        f_start = S.overhang(sq, int(w), int(h))
    else:
        rows = np.where((G_base[:, :3].astype(int) == np.array(key)).all(1))[0]
        if not len(rows):
            return key, 0.0, 0.0, None, 0
        best_row = rows[np.argmin(G_base[rows, 3])]
        _, _, _, f0, _, _, di, si = G_base[best_row]
        sq, _ = F.crop(donors[int(di)], int(si), int(w), int(h), int(dm))
        f_start = S.overhang(sq, int(w), int(h))

    m = min(w, h)
    best_sq = sq.copy()
    f_best = f_start
    t0 = time.time()
    rounds = 0

    schedules = [
        (0.20, 1.015, True,  0.006, 45),
        (0.15, 1.010, True,  0.004, 45),
        (0.10, 1.008, True,  0.003, 50),
        (0.05, 1.004, True,  0.002, 50),
        (0.00, 1.001, False, 0.000, 60),
        (0.18, 1.020, True,  0.008, 45),
        (0.12, 1.012, True,  0.005, 45),
        (0.03, 1.003, False, 0.001, 55),
    ]

    while time.time() - t0 < budget_sec:
        rounds += 1
        sched_idx = (rounds + seed_base) % len(schedules)
        r0, loosen, press, rk, outer = schedules[sched_idx]
        seed = (rounds * 1009 + seed_base * 73) & 0x7FFFFFFF

        with tempfile.TemporaryDirectory() as td:
            p_in = os.path.join(td, "in.txt")
            p_out = os.path.join(td, "out.txt")

            s = m + f_best
            sq_c = best_sq.copy()
            _, xlo, _, ylo, _ = S._bounds(sq_c)
            sq_c[:, 0] -= xlo.min()
            sq_c[:, 1] -= ylo.min()

            with open(p_in, "w") as fh:
                fh.write(f"{len(sq_c)} {s + 1e-9:.17f}\n")
                for x, y, t in sq_c:
                    fh.write(f"{x:.17f} {y:.17f} {math.degrees(t):.15f}\n")

            cmd = [
                FQ, "quench",
                "--in", p_in, "--out", p_out,
                "--rect-dx", str(float(w - m)), "--rect-dy", str(float(h - m)),
                "--loosen", str(float(loosen)),
                "--seed", str(seed),
                "--outer", str(outer)
            ]
            if r0 > 0:
                cmd += [
                    "--round-r0", str(float(r0)),
                    "--round-compress",
                    "--round-steps", "30",
                    "--round-kick", str(float(rk))
                ]
                if press:
                    cmd += ["--round-press"]

            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
                if os.path.exists(p_out):
                    lines = open(p_out).read().splitlines()[1:]
                    cand = np.array([[float(v) for v in r.split()] for r in lines if r.strip()])
                    if len(cand) == len(sq) and np.isfinite(cand).all():
                        cand[:, 2] = np.radians(cand[:, 2])
                        fc = S.overhang(cand, int(w), int(h))
                        if fc < f_best - 1e-11:
                            f_best = fc
                            best_sq = cand
            except Exception:
                pass

    # Final tight polish pass
    with tempfile.TemporaryDirectory() as td:
        p_in = os.path.join(td, "in.txt")
        p_out = os.path.join(td, "out.txt")
        s = m + f_best
        sq_c = best_sq.copy()
        _, xlo, _, ylo, _ = S._bounds(sq_c)
        sq_c[:, 0] -= xlo.min(); sq_c[:, 1] -= ylo.min()
        with open(p_in, "w") as fh:
            fh.write(f"{len(sq_c)} {s + 1e-9:.17f}\n")
            for x, y, t in sq_c:
                fh.write(f"{x:.17f} {y:.17f} {math.degrees(t):.15f}\n")
        cmd = [
            FQ, "quench",
            "--in", p_in, "--out", p_out,
            "--rect-dx", str(float(w - m)), "--rect-dy", str(float(h - m)),
            "--loosen", "1.000005",
            "--seed", "9999",
            "--outer", "100"
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=40)
            if os.path.exists(p_out):
                lines = open(p_out).read().splitlines()[1:]
                cand = np.array([[float(v) for v in r.split()] for r in lines if r.strip()])
                if len(cand) == len(sq) and np.isfinite(cand).all():
                    cand[:, 2] = np.radians(cand[:, 2])
                    fc = S.overhang(cand, int(w), int(h))
                    if fc < f_best - 1e-11:
                        f_best = fc
                        best_sq = cand
        except Exception:
            pass

    return key, f_start, f_best, best_sq, rounds

def main():
    num_workers = 14
    budget_per_key = 40.0  # seconds

    target_keys = [
        (12, 18, 5), (18, 12, 5), (14, 19, 5), (19, 14, 5),
        (14, 18, 5), (18, 14, 5), (13, 19, 5), (19, 13, 5),
        (12, 17, 5), (17, 12, 5), (8, 17, 5),  (17, 8, 5),
        (9, 17, 5),  (17, 9, 5),  (10, 17, 5), (17, 10, 5),
        (11, 17, 5), (17, 11, 5), (8, 22, 5),  (22, 8, 5),
        (9, 22, 5),  (22, 9, 5),  (10, 22, 5), (22, 10, 5),
        (5, 28, 5),  (28, 5, 5),  (5, 27, 5),  (27, 5, 5),
        (9, 18, 5),  (18, 9, 5),  (11, 18, 5), (18, 11, 5),
        (7, 17, 5),  (17, 7, 5),  (12, 20, 5), (20, 12, 5),
        (9, 16, 5),  (16, 9, 5),  (10, 16, 5), (16, 10, 5),
        (8, 21, 5),  (21, 8, 5),  (9, 21, 5),  (21, 9, 5),
        (10, 21, 5), (21, 10, 5), (12, 21, 5), (21, 12, 5),
        (8, 20, 5),  (20, 8, 5),  (9, 20, 5),  (20, 9, 5),
        (10, 20, 5), (20, 10, 5), (11, 20, 5), (20, 11, 5),
    ]

    print("============================================================")
    print("🚀 Wave-7 14-Core Asymmetric dm=5 Campaign")
    print(f"Workers: {num_workers} | Budget: {budget_per_key}s per key | Total keys: {len(target_keys)}")
    print(f"Baseline: {SUBMISSION_PATH}")
    print("============================================================\n", flush=True)

    jobs = [(k, seed, budget_per_key) for seed, k in enumerate(target_keys, 1)]
    t_start = time.time()

    improved = []
    with Pool(num_workers, initializer=init_worker) as pool:
        for res in pool.imap_unordered(quench_worker, jobs):
            key, f0, f1, sq, rounds = res
            df = f0 - f1
            if df > 1e-9:
                status = f">>> IMPROVED by {df:.8f}! <<<"
                improved.append((key, f0, f1, sq))
            else:
                status = "no gain"
            print(f"[Key {key[0]}x{key[1]}+{key[2]}] f: {f0:.8f} -> {f1:.8f} ({status}) [{rounds} rounds]", flush=True)

    print(f"\nQuench phase completed in {time.time() - t_start:.1f}s. Improved {len(improved)}/{len(target_keys)} keys.")

    if improved:
        res_data_curr = dict(np.load(RESERVOIR_PATH)) if os.path.exists(RESERVOIR_PATH) else {}
        for key, f0, f1, sq in improved:
            res_data_curr[f"{key[0]}_{key[1]}_{key[2]}"] = sq
        np.savez(RESERVOIR_PATH, **res_data_curr)
        print("Updated central gadget reservoir. Running full fault DP across n=325..1000...")

        G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
        cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
        base_donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

        q_sqs = [res_data_curr[k] for k in res_data_curr if not k.endswith("_before")]
        Gn = F.extract(q_sqs)
        Gn[:, 6] += len(base_donors)

        G_all = np.concatenate([G_base, Gn])
        donors_all = base_donors + q_sqs

        dp, PG, PM, PQ = F.run_dp(G_all)
        cur = F.load_csv(SUBMISSION_PATH)
        dp_wins = []
        for n in range(325, 1001):
            K = math.isqrt(n); D = n - K * K
            if D == 0: continue
            L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
            f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
            if f is None or K + f + 2 * F.E >= L0 - 1e-9: continue
            r = F.certify_ladder(n, F.compose(K, D, f, links, G_all, donors_all))
            if r is not None and r[0] < L0 - 1e-9:
                gain = (L0 - r[0]) / math.sqrt(n)
                print(f"🎉 CERTIFIED DP WIN on n={n}: {L0:.9f} -> {r[0]:.9f} (gain: {gain:.2e})")
                dp_wins.append((n, r[0], r[2]))

        if dp_wins:
            print(f"\nApplying {len(dp_wins)} certified puzzle wins to submission...")
            base_df = pd.read_csv(SUBMISSION_PATH, dtype=str)
            updates_dict = {n: text for n, _, text in dp_wins}

            rows_list = []
            cur_id = 0
            for n_str, g in base_df.groupby("n", sort=False):
                n = int(n_str)
                if n in updates_dict:
                    for i, (a, b, t) in enumerate(updates_dict[n]):
                        rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(i), "x": str(a), "y": str(b), "angle": str(t)})
                        cur_id += 1
                else:
                    for _, r in g.sort_values("square_id", key=lambda c: c.astype(int)).iterrows():
                        rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                        cur_id += 1

            new_df = pd.DataFrame(rows_list)
            out_csv = ROOT / "output" / "submission_wave7_improved.csv"
            new_df.to_csv(out_csv, index=False)
            print(f"Saved candidate submission to {out_csv}")

            val_json = ROOT / "output" / "validation_report_wave7.json"
            val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json)]
            subprocess.run(val_cmd, check=True)
            print(f"Validation complete! Report saved to {val_json}")
        else:
            print("No ladder improvement surpassed current records.")
    else:
        print("No gadget improved in this round.")

if __name__ == "__main__":
    main()
