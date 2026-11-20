import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
from concurrent.futures import ProcessPoolExecutor
import math

def polish_puzzle(args):
    n, p_base, seed = args
    L0 = pg.side(p_base)
    
    try:
        q, _, _ = polish.polish(p_base, seed=seed, rounds=100, max_seconds=8.0, 
                               trust_start=0.012, regularization=0.0)
        q = pg.repair(q, clearance=1e-9)
        
        if q is not None:
            L = pg.side(q)
            if L < L0 - 1e-12:
                gain = (L0 - L) / math.sqrt(n)
                return (n, L0, L, q, gain)
    except:
        pass
    return None

def main():
    import sys
    baseline = sys.argv[1] if len(sys.argv) > 1 else 'output/submission_final.csv'
    
    df = pd.read_csv(baseline)
    
    # All puzzles
    targets = []
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            targets.append((n, p, n * 17))
    
    print(f"Polishing all {len(targets)} puzzles...")
    
    wins = []
    completed = 0
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(polish_puzzle, args) for args in targets]
        
        for future in futures:
            completed += 1
            result = future.result()
            if result:
                wins.append(result)
                n, L0, L_best, p, gain = result
                print(f"  ✓ n={n}: gain={gain:.12f}")
            
            if completed % 50 == 0:
                print(f"  Progress: {completed}/{len(targets)}, Wins: {len(wins)}")
    
    print(f"\nTotal wins: {len(wins)}")
    
    if wins:
        patch_data = {str(n): p for n, L0, L, p, gain in wins}
        np.savez('output/phase4_polish_wins.npz', **patch_data)

if __name__ == '__main__':
    main()
