"""14-Core Multi-Strategy Parallel Campaign for Squares in Squares.

Strategy A: Multi-seed Homotopy Pressure Quench on All Critical Bottleneck Gadget Keys.
Strategy B: Defect-Mediated Basin Hopping on High-Excess Jammed Puzzles (n < 325).
Official certification with interval arithmetic (metric.py) on every candidate.
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
PACKER = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "packer")
SUBMISSION_PATH = str(ROOT / "output" / "submission_22.250025.csv")
OUT_DIR = ROOT / "output" / "campaign_14core"

# Globals for workers
G_base = None
donors = None
current_packings = None

def init_worker():
    global G_base, donors, current_packings
    G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
    cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
    donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
    df = pd.read_csv(SUBMISSION_PATH)
    current_packings = {
        int(n): g.sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
        for n, g in df.groupby("n")
    }

# ----------------- Strategy A: Homotopy Gadget Quencher -----------------

def quench_key_task(job):
    """Deep multi-homotopy pressure-driven quench on a specific bottleneck key."""
    key, seed_base, budget_sec = job
    w, h, dm = key
    
    rows = np.where((G_base[:, :3].astype(int) == np.array(key)).all(1))[0]
    if not len(rows):
        return ("gadget", key, 0.0, 0.0, None, 0)
        
    best_row = rows[np.argmin(G_base[rows, 3])]
    _, _, _, f0, _, _, di, si = G_base[best_row]
    sq, _ = F.crop(donors[int(di)], int(si), int(w), int(h), int(dm))
    f_start = S.overhang(sq, int(w), int(h))
    
    m = min(w, h)
    best_sq = sq.copy()
    f_best = f_start
    t0 = time.time()
    rounds = 0
    
    # Parametric schedules
    schedules = [
        # (r0, loosen, press, rk, outer)
        (0.20, 1.015, True, 0.006, 45),
        (0.15, 1.010, True, 0.004, 45),
        (0.10, 1.008, True, 0.003, 50),
        (0.05, 1.004, True, 0.002, 50),
        (0.00, 1.001, False, 0.000, 60),
        (0.18, 1.020, True, 0.008, 45),
        (0.12, 1.012, True, 0.005, 45),
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

    # Final polish pass with tight tolerances
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
            
    return ("gadget", key, f_start, f_best, best_sq, rounds)

# ----------------- Strategy B: Defect Basin Hopping on Puzzles -----------------

def corners_np(sq):
    x, y, t = sq[:, 0], sq[:, 1], sq[:, 2]
    c, s = np.cos(t) * 0.5, np.sin(t) * 0.5
    return np.r_[x + c - s, x - c - s, x - c + s, x + c + s], np.r_[y + s + c, y - s + c, y - s - c, y + s - c]

def puzzle_hop_task(job):
    """Defect-mediated basin hopping with descending target for puzzle n."""
    n, seed, budget_sec = job
    global current_packings
    
    sq_orig = current_packings[n].copy()
    L0 = side(sq_orig)
    
    # Prepare donor variants: original n, or n+1 with least critical square removed
    cand_starts = [sq_orig.copy()]
    if (n + 1) in current_packings:
        donor = current_packings[n + 1].copy()
        # Find least critical square to remove
        cx, cy = np.mean(donor[:, 0]), np.mean(donor[:, 1])
        dists = (donor[:, 0] - cx)**2 + (donor[:, 1] - cy)**2
        # Try removing the square furthest from center or closest to center
        drop_idx = int(np.argmin(dists))
        cand_starts.append(np.delete(donor, drop_idx, axis=0))
        
    best_L = L0
    best_sq = sq_orig
    t0 = time.time()
    
    for s_idx, start_sq in enumerate(cand_starts):
        if time.time() - t0 >= budget_sec:
            break
        rem_time = max(5.0, budget_sec - (time.time() - t0))
        
        X, Y = corners_np(start_sq)
        start_sq[:, 0] -= X.min()
        start_sq[:, 1] -= Y.min()
        
        with tempfile.TemporaryDirectory() as td:
            p_in = os.path.join(td, f"in_{n}.txt")
            p_out = os.path.join(td, f"out_{n}.txt")
            with open(p_in, "w") as fh:
                fh.write(f"{n} {best_L:.17f}\n")
                for x, y, a in start_sq:
                    fh.write(f"{x:.17f} {y:.17f} {math.degrees(a) % 90.0:.15f}\n")
                    
            target_side = best_L - 1e-4
            cmd = [
                PACKER, "hop",
                "--in", p_in,
                "--s", f"{target_side:.12f}",
                "--seed", str(seed * 101 + s_idx * 17),
                "--iters", "250000",
                "--out", p_out,
                "--descend", "1e-5",
                "--quiet"
            ]
            try:
                subprocess.run(cmd, timeout=rem_time, capture_output=True)
            except subprocess.TimeoutExpired:
                pass
                
            if os.path.exists(p_out):
                try:
                    lines = [l.split() for l in open(p_out) if l.strip() and not l.startswith("#")]
                    if len(lines) == n + 1:
                        new_sq = np.array([[float(a), float(b), math.radians(float(c))] for a, b, c, *_ in lines[1:]])
                        L_cand = side(new_sq)
                        if L_cand < best_L - 1e-8:
                            # Verify with official metric
                            r = certify(n, new_sq)
                            if r is not None and r[0] < best_L - 1e-9:
                                best_L = r[0]
                                best_sq = new_sq
                except Exception:
                    pass
                    
    gain = (L0 - best_L) / math.sqrt(n) if best_L < L0 else 0.0
    return ("puzzle", n, L0, best_L, best_sq, gain)

# ----------------- Master Campaign Coordinator -----------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    num_workers = 14
    budget_per_task = 65.0  # seconds
    
    print(f"============================================================")
    print(f"🚀 Launching 14-Core Parallel Optimization Campaign")
    print(f"Workers: {num_workers} | Budget: {budget_per_task}s per job")
    print(f"Baseline: {SUBMISSION_PATH}")
    print(f"============================================================\n", flush=True)
    
    # 1. Bottleneck gadget jobs (Strategy A)
    bottleneck_keys = [
        (16, 11, 4), (11, 16, 4),  # Holds back n=791, 849
        (7, 12, 5), (12, 7, 5),    # Holds back n=541
        (20, 11, 8), (11, 20, 8),  # Holds back n=797, 976
        (8, 23, 10), (23, 8, 10),  # Holds back n=980
        (20, 8, 10), (8, 20, 10),  # Holds back n=921
        (21, 8, 13), (8, 21, 13),  # Holds back n=698
        (7, 13, 6), (13, 7, 6),    # Holds back n=590
        (21, 11, 9), (11, 21, 9),  # Holds back n=689
        (20, 8, 14), (8, 20, 14),  # Holds back n=992
        (8, 22, 14), (22, 8, 14),  # Holds back n=989
        (10, 16, 7), (16, 10, 7),
        (10, 15, 3), (15, 10, 3),
        (14, 6, 9), (6, 14, 9)
    ]
    gadget_jobs = [(k, seed, budget_per_task) for seed, k in enumerate(bottleneck_keys, 1)]
    
    # 2. High-excess small puzzle jobs (Strategy B)
    priority_puzzles = [51, 53, 55, 50, 41, 39, 37, 29, 28, 26, 20, 19, 18, 17, 11, 10]
    puzzle_jobs = [(n, seed, budget_per_task) for seed, n in enumerate(priority_puzzles, 101)]
    
    print(f"Dispatching Phase 1: {len(gadget_jobs)} Bottleneck Gadget Quench Jobs across 14 workers...")
    t_start = time.time()
    
    improved_gadgets = []
    with Pool(num_workers, initializer=init_worker) as pool:
        for res in pool.imap_unordered(quench_key_task, gadget_jobs):
            _, key, f0, f1, sq, rounds = res
            df = f0 - f1
            if df > 1e-9:
                status = f">>> GADGET IMPROVED by {df:.8f}! <<<"
                improved_gadgets.append((key, f0, f1, sq))
            else:
                status = "no gain"
            print(f"[Gadget {key[0]}x{key[1]}+{key[2]}] f: {f0:.8f} -> {f1:.8f} ({status}) [{rounds} rounds]", flush=True)
            
    print(f"\nPhase 1 completed in {time.time() - t_start:.1f}s. Improved {len(improved_gadgets)} gadgets.")
    
    # If any gadget improved, save to reservoir and run DP
    all_puzzle_updates = {}
    if improved_gadgets:
        res_path = ROOT / "output" / "all_quenched_gadgets_combined.npz"
        res_data = dict(np.load(res_path))
        for key, f0, f1, sq in improved_gadgets:
            res_data[f"{key[0]}_{key[1]}_{key[2]}"] = sq
        np.savez(res_path, **res_data)
        print("Updated central gadget reservoir. Running full fault DP...")
        
        # Load unified donors
        G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
        cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
        base_donors = [cd[f"d_{i}"] for i in range(len(cd.files))]
        
        all_q = dict(np.load(res_path))
        q_sqs = [all_q[k] for k in all_q if not k.endswith("_before")]
        Gn = F.extract(q_sqs)
        Gn[:, 6] += len(base_donors)
        
        G_all = np.concatenate([G_base, Gn])
        donors_all = base_donors + q_sqs
        
        dp, PG, PM, PQ = F.run_dp(G_all)
        cur = F.load_csv(SUBMISSION_PATH)
        for n in range(325, 1001):
            K = math.isqrt(n); D = n - K * K
            if D == 0: continue
            L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
            f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
            if f is None or K + f + 2 * F.E >= L0 - 1e-9: continue
            r = F.certify_ladder(n, F.compose(K, D, f, links, G_all, donors_all))
            if r is not None and r[0] < L0 - 1e-9:
                gain = (L0 - r[0]) / math.sqrt(n)
                print(f"🎉 DP WIN on n={n}: {L0:.9f} -> {r[0]:.9f} (gain: {gain:.2e})")
                all_puzzle_updates[n] = (r[0], r[2])
                
        if all_puzzle_updates:
            print(f"Found {len(all_puzzle_updates)} DP ladder improvements!")
            
    print(f"\nDispatching Phase 2: {len(puzzle_jobs)} Defect Basin-Hopping Jobs across 14 workers...")
    t2 = time.time()
    with Pool(num_workers, initializer=init_worker) as pool:
        for res in pool.imap_unordered(puzzle_hop_task, puzzle_jobs):
            _, n, L0, L1, sq, gain = res
            if gain > 1e-9:
                print(f"🎉 PUZZLE WIN on n={n}: {L0:.9f} -> {L1:.9f} (gain: {gain:.2e})", flush=True)
                r = certify(n, sq)
                if r is not None:
                    all_puzzle_updates[n] = (r[0], r[2])
            else:
                print(f"[Puzzle n={n:2d}] L0={L0:.8f} (no escape from basin)", flush=True)
                
    print(f"\nPhase 2 completed in {time.time() - t2:.1f}s.")
    
    if all_puzzle_updates:
        print(f"\n🔥 Total certified improvements: {len(all_puzzle_updates)} puzzles!")
        base_df = pd.read_csv(SUBMISSION_PATH, dtype=str)
        # Apply updates
        rows_list = []
        cur_id = 0
        for n_str, g in base_df.groupby("n", sort=False):
            n = int(n_str)
            if n in all_puzzle_updates:
                _, text_tuples = all_puzzle_updates[n]
                for i, (a, b, t) in enumerate(text_tuples):
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(i), "x": str(a), "y": str(b), "angle": str(t)})
                    cur_id += 1
            else:
                for _, r in g.sort_values("square_id", key=lambda c: c.astype(int)).iterrows():
                    rows_list.append({"id": str(cur_id), "n": str(n), "square_id": str(r["square_id"]), "x": str(r["x"]), "y": str(r["y"]), "angle": str(r["angle"])})
                    cur_id += 1
                    
        new_df = pd.DataFrame(rows_list)
        new_path = ROOT / "output" / "submission_campaign_improved.csv"
        new_df.to_csv(new_path, index=False)
        print(f"Saved candidate submission to {new_path}")
        
        # Validate candidate submission
        print("Running official validation...")
        val_cmd = [sys.executable, str(ROOT / "src" / "tools" / "validate_submission.py"), str(new_path)]
        val_res = subprocess.run(val_cmd, capture_output=True, text=True)
        print(val_res.stdout)
    else:
        print("\nNo puzzles improved in this round.")
        
    print(f"\n============================================================")
    print(f"🏁 14-Core Parallel Campaign Finished. Total time: {time.time() - t_start:.1f}s")
    print(f"============================================================")

if __name__ == "__main__":
    main()
