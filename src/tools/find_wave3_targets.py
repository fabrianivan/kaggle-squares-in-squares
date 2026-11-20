"""Find unquenched keys used in current optimal DP ladders and rank them for Wave-3 quench."""

import math
import os
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))

import fault_dp as F

G_base = np.load(str(ROOT / "output" / "cached_base_G.npy"))
cd = np.load(str(ROOT / "output" / "cached_donors.npz"))
donors = [cd[f"d_{i}"] for i in range(len(cd.files))]

res = dict(np.load(str(ROOT / "output" / "all_quenched_gadgets_combined.npz")))
print(f"Currently in reservoir: {len(res)} gadgets")

q_sqs = [res[k] for k in res if not k.endswith("_before")]
Gn = F.extract(q_sqs)
Gn[:, 6] += len(donors)
G_all = np.concatenate([G_base, Gn])

dp, PG, PM, PQ = F.run_dp(G_all)

# Check which keys appear in optimal chains across n=325..1000
used_keys = {}  # key -> list of (n, f, L0)
for n in range(325, 1001):
    K = math.isqrt(n); D = n - K * K
    if D == 0: continue
    f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
    if f is not None and links:
        for g, mode in links:
            row = G_all[g]
            k = (int(row[0]), int(row[1]), int(row[2]))
            if k not in used_keys:
                used_keys[k] = []
            used_keys[k].append(n)

print(f"Total distinct keys used in optimal ladders: {len(used_keys)}")
unquenched_used = [k for k in used_keys if f"{k[0]}_{k[1]}_{k[2]}" not in res]
print(f"Unquenched keys used in optimal ladders: {len(unquenched_used)}")

# Detail and sort unquenched keys
unq_details = []
for k in unquenched_used:
    rows = np.where((G_base[:, :3].astype(int) == np.array(k)).all(1))[0]
    if len(rows):
        best_row = rows[np.argmin(G_base[rows, 3])]
        f0 = G_base[best_row, 3]
        puzzle_count = len(used_keys[k])
        unq_details.append((k, f0, k[2], puzzle_count, used_keys[k]))

# Sort by potential impact: numerical dm >= 3 first, then by puzzle count
unq_details.sort(key=lambda x: (x[2] >= 3, x[3], -x[1]), reverse=True)

print(f"\n{'Key':<15} | {'Overhang f':<12} | {'dm':<4} | {'Puzzles Active':<15} | {'Puzzles Sample'}")
print("-" * 75)
for k, f0, dm, count, puzzles in unq_details:
    p_str = str(puzzles[:5]) + ("..." if len(puzzles) > 5 else "")
    print(f"{f'{k[0]}x{k[1]}+{k[2]}':<15} | {f0:<12.6f} | {dm:<4} | {count:<15} | {p_str}")

# Save the top target list for Wave 3
wave3_targets = [k for k, f0, dm, count, _ in unq_details if dm >= 3]
print(f"\nIdentified {len(wave3_targets)} candidates with dm >= 3.")
np.save(str(ROOT / "output" / "wave3_candidates.npy"), np.array(wave3_targets, dtype=int))
