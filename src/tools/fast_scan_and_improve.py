import os
import sys
import glob
import math
import time
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

def compute_box_L(df):
    xs = df["x"].astype(float).values
    ys = df["y"].astype(float).values
    thetas = df["angle"].astype(float).values
    c = np.abs(np.cos(thetas))
    s = np.abs(np.sin(thetas))
    hx = 0.5 * (c + s)
    hy = 0.5 * (s + c)
    min_x, max_x = np.min(xs - hx), np.max(xs + hx)
    min_y, max_y = np.min(ys - hy), np.max(ys + hy)
    return max(max_x - min_x, max_y - min_y)

def eval_records(n, df_subset):
    records = []
    for _, r in df_subset.iterrows():
        records.append({
            "square_id": int(r["square_id"]),
            "x": str(r["x"]).strip(),
            "y": str(r["y"]).strip(),
            "angle": str(r["angle"]).strip()
        })
    _n, score, L_str, reason = metric.evaluate_single_puzzle(n, records)
    return score, float(L_str) if L_str else None, reason

def main():
    base_path = os.path.join(ROOT, "output/submission_22.250252.csv")
    print(f"Loading baseline from {base_path}...", flush=True)
    base_df = pd.read_csv(base_path, dtype=str)

    base_puzzles = {}
    base_L = {}
    for n, g in base_df.groupby("n"):
        n_int = int(n)
        puz = g.sort_values("square_id", key=lambda c: c.astype(int))
        base_puzzles[n_int] = puz
        base_L[n_int] = compute_box_L(puz)

    base_excess = sum((base_L[n] / np.sqrt(n) - 1.0) for n in range(1, 1001))
    print(f"Loaded 1000 base puzzles. Starting Float Excess Score: {base_excess:.10f}", flush=True)

    # High-value candidate files
    target_files = [
        "data/fresh_sync_0003/kirill_guard/_contact_lab_inputs/public_leader_v20.csv",
        "data/fresh_sync_0003/kirill_complete/submission.csv",
        "data/fresh_sync_0003/kirill_guard/submission.csv",
        "data/fresh_sync_0003/danil_latest/submission_merged.csv",
        "data/fresh_sync_0003/danil_latest/submission.csv",
        "data/fresh_sync_0003/malyshev_atlas/submission_merged.csv",
        "data/fresh_sync_0003/malyshev_atlas/submission.csv",
        "data/fresh_sync_0003/busyaprime_quenched/packings.csv",
        "data/fresh_sync_0003/fuad_portfolio/portfolio.csv",
        "data/fresh_sync_0003/alex_starter/best_current.csv",
        "data/fresh_sync_0003/alex_starter/hop.csv",
        "data/latest_sync_1900/kumoriai/submission_22.250441.csv",
        "/Users/fabrianivan/pjmathematician-three-square-packings/pj_packings.csv"
    ]

    # Add any other submission files found in fresh_sync or latest_sync
    for pattern in ["data/fresh_sync_0003/**/*.csv", "data/latest_sync_1900/**/*.csv"]:
        for f in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            if f not in target_files and os.path.isfile(f):
                target_files.append(f)

    print(f"Scanning {len(target_files)} targeted candidate files...", flush=True)
    
    total_gain = 0.0
    wins = {}

    for fpath in target_files:
        if not os.path.exists(fpath):
            continue
        try:
            df = pd.read_csv(fpath, dtype=str)
        except Exception:
            continue
        if "n" not in df.columns or "x" not in df.columns or "y" not in df.columns or "angle" not in df.columns:
            continue
            
        fname = os.path.basename(fpath)
        found_in_file = 0
        for n_str, g in df.groupby("n"):
            try:
                n = int(n_str)
            except:
                continue
            if n < 1 or n > 1000 or len(g) != n:
                continue
            cand_puz = g.sort_values("square_id", key=lambda c: c.astype(int))
            cand_L = compute_box_L(cand_puz)
            cur_L = wins[n][1] if n in wins else base_L[n]
            if cand_L < cur_L - 1e-7:
                # Rigorous official verification
                sc, L_cert, reason = eval_records(n, cand_puz)
                if reason == "ok" and L_cert is not None and L_cert < cur_L - 1e-7:
                    gain = (cur_L - L_cert) / np.sqrt(n)
                    print(f"*** CERTIFIED WIN on n={n} from {fname} ***: L={L_cert:.10f} (prev {cur_L:.10f}), delta={cur_L - L_cert:.8e}, gain={gain:.8e}", flush=True)
                    wins[n] = (cand_puz, L_cert, fname)
                    total_gain += gain
                    found_in_file += 1
        if found_in_file > 0:
            print(f"--> File {fname} provided {found_in_file} certified wins! Current total gain: {total_gain:.10e}", flush=True)

    print(f"\nScan completed! Found {len(wins)} improved puzzles across candidates.", flush=True)
    
    if len(wins) > 0:
        new_excess = base_excess - total_gain
        print(f"Projected New Float Excess Score: {new_excess:.10f} (Down from {base_excess:.10f})", flush=True)
        
        # Apply wins to base puzzles
        for n, (cand_puz, L_cert, _) in wins.items():
            base_puzzles[n] = cand_puz
            
        # Build new submission
        out_sub_name = f"submission_{new_excess:.6f}.csv"
        out_path = os.path.join(ROOT, "output", out_sub_name)
        rows = []
        rid = 0
        for n in range(1, 1001):
            puz = base_puzzles[n]
            for _, r in puz.iterrows():
                rows.append({
                    "id": rid,
                    "n": n,
                    "square_id": int(r["square_id"]),
                    "x": str(r["x"]).strip(),
                    "y": str(r["y"]).strip(),
                    "angle": str(r["angle"]).strip()
                })
                rid += 1
                
        out_df = pd.DataFrame(rows)
        out_df.to_csv(out_path, index=False)
        print(f"Saved new submission to {out_path} with {len(out_df)} rows.", flush=True)
        
        # Also copy to output/submission_final.csv
        final_path = os.path.join(ROOT, "output/submission_final.csv")
        out_df.to_csv(final_path, index=False)
        print(f"Updated {final_path} baseline.", flush=True)
        return out_path, new_excess
    else:
        print("No candidates beat the current 22.250252 baseline directly.", flush=True)
        return None, base_excess

if __name__ == "__main__":
    main()
