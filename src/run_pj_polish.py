import json, sys, math, numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/tools')
sys.path.insert(0, '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/data/alexchilton')
import packing_geometry, cpu_axis_reclosure, cpu_contact_polish, metric

def try_polish(args):
    n, p_init, seed, trust, tie, rounds = args
    import sys
    sys.path.insert(0, '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/tools')
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    L_in = packing_geometry.side(p_init)
    try:
        q, _, _ = cpu_axis_reclosure.reclose(p_init, seed=seed, trust=trust, tie=tie, rounds=rounds, seconds=6.0)
        q, _, _ = cpu_contact_polish.polish(q, seed=seed, rounds=50, max_seconds=8.0, trust_start=0.015)
        q = packing_geometry.repair(q, clearance=1.5e-9)
        if q is not None:
            L_out = packing_geometry.side(q)
            return n, L_in, L_out, q
    except Exception as e:
        pass
    return n, L_in, L_in, None

def main():
    with open('pj_nb/three-square-packings-that-beat-the-records.ipynb') as f:
        nb = json.load(f)
    src = ''.join(nb['cells'][3]['source'])
    scope = {}
    exec(src, scope)
    pj_packings = scope['PACKINGS']

    df_curr = pd.read_csv('submission_merged_22.253319.csv')
    cur = {}
    for n in [232, 260, 299]:
        cur[n] = df_curr[df_curr['n'] == n].sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)

    jobs = []
    for n in [232, 260, 299]:
        for src_name, p in [('cur', cur[n]), ('pj', np.array(pj_packings[n], float))]:
            for arm in range(8):
                seed = arm * 1000 + (1 if src_name=='cur' else 2)
                trust = [0.08, 0.15, 0.25, 0.4][arm % 4]
                tie = [0.02, 0.08, 0.15, 0.25][(arm // 4) % 4]
                jobs.append((n, p, seed, trust, tie, 25))

    print(f'Running {len(jobs)} polish jobs for n=232, 260, 299 across 8 cores...')
    best = {n: (packing_geometry.side(cur[n]), cur[n]) for n in [232, 260, 299]}

    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(try_polish, j) for j in jobs]
        for f in as_completed(futures):
            n, L_in, L_out, q = f.result()
            if q is not None and L_out < best[n][0] - 1e-8:
                rows = [{'n': str(n), 'square_id': str(i), 'x': repr(float(r[0])), 'y': repr(float(r[1])), 'angle': repr(float(r[2]))} for i, r in enumerate(q)]
                status, sc, L_cert, why = metric.evaluate_single_puzzle(n, rows)
                if why == 'ok' and float(L_cert) < best[n][0] - 1e-9:
                    print(f'*** Certified improvement for n={n}: {best[n][0]:.8f} -> {float(L_cert):.8f} (gain: {(best[n][0]-float(L_cert))/math.sqrt(n):.8f})', flush=True)
                    best[n] = (float(L_cert), q)

    print('=== Final Results for n=232, 260, 299 ===')
    for n in [232, 260, 299]:
        c_side = packing_geometry.side(cur[n])
        b_side = best[n][0]
        print(f'n={n}: start={c_side:.8f}, best={b_side:.8f}, delta={c_side - b_side:.8f}')

if __name__ == '__main__':
    main()
