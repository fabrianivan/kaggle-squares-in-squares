"""Run DP with all combined gadgets and evaluate against submission_22.233486.csv"""
import pandas as pd
import numpy as np
import time, math, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'data' / 'new_sources' / 'alexchilton_starter_kit'))
sys.path.insert(0, str(ROOT / 'src' / 'tools'))
import fault_dp as F
from ensemble import side

CUR_CSV = ROOT / 'output' / 'submission_22.233486.csv'
cur = F.load_csv(str(CUR_CSV))

print("Loading cached base and donors...")
G_base = np.load(ROOT / 'output' / 'cached_base_G.npy')
cd = np.load(ROOT / 'output' / 'cached_donors.npz')
base_donors = [cd[f'd_{i}'] for i in range(len(cd.files))]

# Load all 1000 puzzles from our latest submission
all_cur_donors = [cur[n] for n in range(325, 1001) if n in cur]
print(f"Extracting sub-gadgets from {len(all_cur_donors)} submission donors...")
t0 = time.time()
Gn_cur = F.extract(all_cur_donors)
print(f"Extraction done in {time.time()-t0:.1f}s ({len(Gn_cur)} gadgets)")
Gn_cur[:, 6] += len(base_donors)

# Quenched gadgets reservoir
res = dict(np.load(ROOT / 'output' / 'all_quenched_gadgets_combined.npz'))
q_keys = [k for k in res if not k.endswith('_before')]
q_sqs = [res[k] for k in q_keys]
print(f"Extracting sub-gadgets from {len(q_sqs)} quenched reservoir gadgets...")
Gn_q = F.extract(q_sqs)
Gn_q[:, 6] += len(base_donors) + len(all_cur_donors)

G_all = np.concatenate([G_base, Gn_cur, Gn_q])
donors_all = base_donors + all_cur_donors + q_sqs
print(f"Total gadgets in G_all: {len(G_all)}")

print("Running DP...")
t0 = time.time()
dp, PG, PM, PQ = F.run_dp(G_all)
print(f"run_dp finished in {time.time()-t0:.1f}s")

dp_wins = []
print("Evaluating ladder constructions vs current best...")
for n in range(325, 1001):
    K = math.isqrt(n); D = n - K * K
    if D == 0: continue
    L0 = side(cur[n]) if n in cur else math.ceil(math.sqrt(n))
    f, links = F.chain(dp, PG, PM, PQ, G_all, K, D)
    if f is None or K + f + 2 * F.E >= L0 - 1e-9: continue
    
    cand = F.compose(K, D, f, links, G_all, donors_all)
    L_cand = side(cand)
    if L_cand < L0 - 1e-9:
        # Certify
        r = F.certify_ladder(n, cand)
        if r is not None and r[0] < L0 - 1e-9:
            dp_wins.append((n, L0, r[0], L0 - r[0], r[2]))
            print(f"  🎉 CERTIFIED DP WIN: n={n}: {L0:.9f} -> {r[0]:.9f} (gain={L0-r[0]:+.6e})")
        else:
            print(f"  ⚠️  Uncertified candidate: n={n}: {L0:.9f} -> {L_cand:.9f}")

print(f"\nTotal new certified DP wins: {len(dp_wins)}")
if dp_wins:
    # Save wins
    np.save(ROOT / 'output' / 'fresh_dp_wins.npy', {'wins': dp_wins}, allow_pickle=True)
    print("Saved fresh_dp_wins.npy!")
