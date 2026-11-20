"""Deep 14-Core Parallel Homotopy Quencher for the Exact 14 Gatekeeper Keys.

Targets the 14 single-bottleneck gadget keys holding back:
- n=683, 791, 792, 849 (held by (16, 11, 4) / (11, 16, 4))
- n=541 (held by (7, 12, 5) / (12, 7, 5))
- n=969 (held by (16, 15, 4) / (15, 16, 4))
- n=689 (held by (21, 11, 9) / (11, 21, 9))
- n=698 (held by (21, 8, 13) / (8, 21, 13))
- n=914 (held by (8, 18, 6) / (18, 8, 6))
- n=931 (held by (21, 7, 15) / (7, 21, 15))
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
SUBMISSION_PATH = str(ROOT / "output" / "submission_22.248625.csv")
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

def deep_quench_worker(job):
    """Deep multi-homotopy quench on a specific bottleneck key."""
    key, seed_base, budget_sec = job
    w, h, dm = key
    key_str = f"{w}_{h}_{dm}"
    
    # Check if key is already in reservoir
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

    # Diverse homotopy schedules
    schedules = [
        # mode, r0, a0, loosen, press, kick, outer
        ("round", 0.22, 0.00, 1.018, True,  0.006, 50),
        ("round", 0.16, 0.00, 1.012, True,  0.004, 50),
        ("round", 0.08, 0.00, 1.006, True,  0.002, 55),
        ("soft",  0.00, 0.05, 1.015, False, 0.005, 50),
        ("soft",  0.00, 0.03, 1.008, False, 0.003, 50),
        ("both",  0.15, 0.03, 1.012, True,  0.004, 50),
        ("both",  0.10, 0.02, 1.006, True,  0.002, 55),
        ("kick",  0.00, 0.00, 1.008, False, 0.004, 60),
        ("kick",  0.00, 0.00, 1.003, False, 0.002, 60),
        ("tight", 0.02, 0.00, 1.001, False, 0.0005, 70),
    ]

    while time.time() - t0 < budget_sec:
        rounds += 1
        sched = schedules[(rounds + seed_base) % len(schedules)]
        mode, r0, a0, loosen, press, rk, outer = sched
        seed = (rounds * 7919 + seed_base * 313) & 0x7FFFFFFF

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
            if a0 > 0:
                cmd += [
                    "--soft-a0", str(float(a0)),
                    "--soft-steps", "25",
                    "--soft-kick", str(float(rk))
                ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=35)
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

    # Final polish pass
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
            "--loosen", "1.000002",
            "--seed", "8888",
            "--outer", "120"
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=45)
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
    budget_per_key = 120.0  # 2 minutes per key across 14 cores
    
    target_keys = [
        (16, 11, 4), (11, 16, 4),  # Unlocks n=683, 791, 792, 849
        (7, 12, 5),  (12, 7, 5),   # Unlocks n=541
        (16, 15, 4), (15, 16, 4),  # Unlocks n=969
        (21, 11, 9), (11, 21, 9),  # Unlocks n=689
        (21, 8, 13), (8, 21, 13),  # Unlocks n=698
        (8, 18, 6),  (18, 8, 6),   # Unlocks n=914
        (21, 7, 15), (7, 21, 15),  # Unlocks n=931
    ]
    
    assert len(target_keys) == 14, f"Expected exactly 14 keys, got {len(target_keys)}"
    
    print("============================================================")
    print("🚀 Deep 14-Core Dedicated Gatekeeper Quench Campaign")
    print(f"Workers: {num_workers} | Budget: {budget_per_key}s per key")
    print(f"Targeting: 14 single-bottleneck gatekeeper keys holding back 11 puzzles")
    print("============================================================\n", flush=True)
    
    jobs = [(k, seed, budget_per_key) for seed, k in enumerate(target_keys, 1)]
    t_start = time.time()
    
    improved = []
    with Pool(num_workers, initializer=init_worker) as pool:
        for res in pool.imap_unordered(deep_quench_worker, jobs):
            key, f0, f1, sq, rounds = res
            df = f0 - f1
            if df > 1e-9:
                status = f">>> IMPROVED by {df:.8f}! <<<"
                improved.append((key, f0, f1, sq))
            else:
                status = "no gain"
            print(f"[Key {key[0]}x{key[1]}+{key[2]}] f: {f0:.8f} -> {f1:.8f} ({status}) [{rounds} rounds]", flush=True)

    print(f"\nQuench phase completed in {time.time() - t_start:.1f}s. Improved {len(improved)}/14 keys.")
    
    if improved:
        res_data_curr = dict(np.load(RESERVOIR_PATH)) if os.path.exists(RESERVOIR_PATH) else {}
        for key, f0, f1, sq in improved:
            res_data_curr[f"{key[0]}_{key[1]}_{key[2]}"] = sq
        np.savez(RESERVOIR_PATH, **res_data_curr)
        print("Updated persistent reservoir. Running full fault DP across n=325..1000...")
        
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
            out_csv = ROOT / "output" / "submission_deep_improved.csv"
            new_df.to_csv(out_csv, index=False)
            print(f"Saved new candidate to {out_csv}")
            
            val_json = ROOT / "output" / "validation_report_deep.json"
            val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(out_csv), str(val_json)]
            subprocess.run(val_cmd, check=True)
            print(f"Validation complete! Report saved to {val_json}")
    else:
        print("No gatekeeper gadget improved in this round.")

if __name__ == "__main__":
    main()
