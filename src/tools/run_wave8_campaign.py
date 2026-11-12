"""Wave-8 14-Core Compact Asymmetric Quench Campaign.

Targets 118 prime unquenched compact asymmetric keys:
dm in [4, 5], w in [8, 17], h in [8, 17], |w - h| >= 1, f >= 0.65.
Aims to break the 45-degree algebraic locks (4*sqrt(2)-5 and 1/sqrt(2))
on gatekeeper puzzles n in [329, 366, 406, 447, 490, 535, 536, 583, 633, 850, 909].

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
    budget_per_key = 35.0  # seconds

    G_base_main = np.load(str(ROOT / "output" / "cached_base_G.npy"))
    if os.path.exists(RESERVOIR_PATH):
        res_main = dict(np.load(RESERVOIR_PATH))
    else:
        res_main = {}

    candidates = []
    seen = set()
    for row in G_base_main:
        w, h, dm, f = int(row[0]), int(row[1]), int(row[2]), row[3]
        if dm in [4, 5] and 8 <= w <= 17 and 8 <= h <= 17 and abs(w - h) >= 1:
            key_str = f"{w}_{h}_{dm}"
            if key_str in res_main and not key_str.endswith("_before"):
                continue
            if (w, h, dm) not in seen and f >= 0.65:
                seen.add((w, h, dm))
                candidates.append((f, (w, h, dm)))

    candidates.sort(reverse=True)
    target_keys = [k for _, k in candidates]

    print("============================================================")
    print("🚀 Wave-8 14-Core Compact Asymmetric Quench Campaign")
    print(f"Workers: {num_workers} | Budget: {budget_per_key}s per key | Total keys: {len(target_keys)}")
    print(f"Baseline: {SUBMISSION_PATH}")
    print("============================================================\n", flush=True)

    jobs = [(k, i, budget_per_key) for i, k in enumerate(target_keys)]
    improved_keys = {}
    t_start = time.time()

    with Pool(num_workers, initializer=init_worker) as pool:
        for res in pool.imap_unordered(quench_worker, jobs):
            key, f_start, f_best, best_sq, rounds = res
            w, h, dm = key
            key_str = f"{w}_{h}_{dm}"
            if best_sq is not None and f_best < f_start - 1e-11:
                diff = f_start - f_best
                print(f"[Key {w}x{h}+{dm}] f: {f_start:.8f} -> {f_best:.8f} (>>> IMPROVED by {diff:.8f}! <<<) [{rounds} rounds]", flush=True)
                improved_keys[key_str] = (best_sq, f_start, f_best)
            else:
                print(f"[Key {w}x{h}+{dm}] f: {f_start:.8f} -> {f_best:.8f} (no gain) [{rounds} rounds]", flush=True)

    elapsed = time.time() - t_start
    print(f"\nQuench phase completed in {elapsed:.1f}s. Improved {len(improved_keys)}/{len(target_keys)} keys.")

    if improved_keys:
        print("Updating central gadget reservoir...")
        res_data_curr = dict(np.load(RESERVOIR_PATH)) if os.path.exists(RESERVOIR_PATH) else {}
        for k_str, (sq_arr, f_start, f_best) in improved_keys.items():
            if k_str not in res_data_curr:
                res_data_curr[f"{k_str}_before"] = f_start
            res_data_curr[k_str] = sq_arr

        np.savez_compressed(RESERVOIR_PATH, **res_data_curr)
        print(f"Saved {len(res_data_curr)} items in {RESERVOIR_PATH}")

        print("Running full fault DP across n=325..1000...")
        G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
        cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
        base_donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

        # Extract only from newly improved gadgets (lightning-fast)
        new_q_sqs = [sq_arr for sq_arr, _, _ in improved_keys.values()]
        Gn = F.extract(new_q_sqs)
        Gn[:, 6] += len(base_donors)

        G_all = np.concatenate([G_base, Gn])
        donors_all = base_donors + new_q_sqs

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
            # Compute provisional score
            prov_score = 0.0
            # validate
            out_csv = ROOT / "output" / "submission_wave8_temp.csv"
            new_df.to_csv(out_csv, index=False)

            val_json = ROOT / "output" / "validation_report_wave8.json"
            val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json), "--workers", "14"]
            subprocess.run(val_cmd, check=True)
            import json
            rep = json.loads(val_json.read_text())
            score_certified = rep["score"]
            print(f"\n🏆 Official Certified Score: {score_certified:.12f}")

            final_csv = ROOT / "output" / f"submission_{score_certified:.6f}.csv"
            new_df.to_csv(final_csv, index=False)
            new_df.to_csv(ROOT / "output" / "submission_final.csv", index=False)
            print(f"Updated final submission to {final_csv}")
        else:
            print("No ladder improvement surpassed current records with new gadgets alone.")
    else:
        print("No gadget improved in this round.")

if __name__ == "__main__":
    main()
