import os
import sys
import numpy as np
import pandas as pd

# Add starter kit to sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "data/new_sources/alexchilton_starter_kit"))
import metric

def main():
    base_path = os.path.join(ROOT, "output/submission_final.csv")
    print(f"Loading baseline from {base_path}...")
    base_df = pd.read_csv(base_path, dtype=str)
    
    # Store rows per n
    puzzles = {}
    for n, g in base_df.groupby("n"):
        puzzles[int(n)] = g.sort_values("square_id", key=lambda c: c.astype(int)).copy()
        
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

    # 1. Update n=798 from fault_dp
    fault_798_path = os.path.join(ROOT, "tmp/fault_out/798.csv")
    if os.path.exists(fault_798_path):
        f798 = pd.read_csv(fault_798_path, dtype=str).sort_values("square_id", key=lambda c: c.astype(int))
        old_sc, old_L, old_r = eval_records(798, puzzles[798])
        new_sc, new_L, new_r = eval_records(798, f798)
        if new_r == "ok" and new_L < old_L:
            gain = (old_L - new_L) / np.sqrt(798)
            print(f"[n=798 Fault DP] Certified win! L: {old_L:.10f} -> {new_L:.10f}, Gain: {gain:.10e}")
            puzzles[798] = f798
        else:
            print(f"[n=798 Fault DP] Rejected or no gain (r={new_r}, new_L={new_L}, old_L={old_L})")
            
    # 2. Update n=791 from closure
    closure_path = os.path.join(ROOT, "tmp/test_closure_out.csv")
    if os.path.exists(closure_path):
        c_df = pd.read_csv(closure_path, dtype=str)
        c791 = c_df[c_df["n"] == "791"].sort_values("square_id", key=lambda c: c.astype(int))
        old_sc, old_L, old_r = eval_records(791, puzzles[791])
        new_sc, new_L, new_r = eval_records(791, c791)
        if new_r == "ok" and new_L < old_L:
            gain = (old_L - new_L) / np.sqrt(791)
            print(f"[n=791 Closure] Certified win! L: {old_L:.10f} -> {new_L:.10f}, Gain: {gain:.10e}")
            puzzles[791] = c791
        else:
            print(f"[n=791 Closure] Rejected or no gain")
            
    # 3. Update 19 puzzles from malyshev_atlas/submission_merged.csv
    merged_path = os.path.join(ROOT, "data/fresh_sync_0003/malyshev_atlas/submission_merged.csv")
    if os.path.exists(merged_path):
        m_df = pd.read_csv(merged_path, dtype=str)
        target_ns = [307, 548, 652, 694, 699, 702, 748, 806, 817, 858, 864, 868, 918, 922, 923, 924, 925, 979, 985]
        for tn in target_ns:
            sub = m_df[m_df["n"] == str(tn)].sort_values("square_id", key=lambda c: c.astype(int))
            old_sc, old_L, old_r = eval_records(tn, puzzles[tn])
            new_sc, new_L, new_r = eval_records(tn, sub)
            if new_r == "ok" and new_L < old_L:
                gain = (old_L - new_L) / np.sqrt(tn)
                print(f"[n={tn} Merged Atlas] Certified win! L: {old_L:.10f} -> {new_L:.10f}, Gain: {gain:.10e}")
                puzzles[tn] = sub
            else:
                print(f"[n={tn} Merged Atlas] No gain or rejected")
                
    # Reassemble full submission
    rows = []
    rid = 0
    for n in range(1, 1001):
        g = puzzles[n]
        for sid, (_, r) in enumerate(g.iterrows()):
            rows.append({
                "id": rid,
                "n": n,
                "square_id": sid,
                "x": r["x"],
                "y": r["y"],
                "angle": r["angle"]
            })
            rid += 1
            
    out_df = pd.DataFrame(rows)
    assert len(out_df) == 500500, f"Expected 500500 rows, got {len(out_df)}"
    assert out_df["id"].iloc[-1] == 500499, f"Invalid final id: {out_df['id'].iloc[-1]}"
    
    out_csv = os.path.join(ROOT, "output/submission_22.250252.csv")
    out_df.to_csv(out_csv, index=False)
    print(f"Saved {len(out_df)} rows to {out_csv}")
    
    final_csv = os.path.join(ROOT, "output/submission_final.csv")
    out_df.to_csv(final_csv, index=False)
    print(f"Updated {final_csv}")
    
    best_csv = os.path.join(ROOT, "data/submission_best.csv")
    out_df.to_csv(best_csv, index=False)
    print(f"Updated {best_csv}")

if __name__ == "__main__":
    main()
