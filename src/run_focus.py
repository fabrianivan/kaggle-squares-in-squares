#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
import sys, os, json, math, time
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'metric'))
import metric
import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
import numpy as np, pandas as pd

def solve_job(args):
    n, p_base, arm, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    trust = [0.12, 0.25, 0.5][arm % 3]
    tie = [0.03, 0.12, 0.25][(arm // 3) % 3]
    L0 = packing_geometry.side(p_base)
    try:
        q, _, _ = cpu_axis_reclosure.reclose(p_base, seed=seed, trust=trust, tie=tie, rounds=16, seconds=2.0)
        if packing_geometry.side(q) < L0 - 1e-8:
            q, _, _ = cpu_contact_polish.polish(q, seed=seed, rounds=35, max_seconds=2.5, trust_start=0.015)
        q = packing_geometry.repair(q, clearance=1.5e-9)
        if q is not None and packing_geometry.side(q) < L0 - 1e-8:
            return n, L0, packing_geometry.side(q), q
    except Exception:
        pass
    return n, L0, L0, None

def main():
    df_curr = pd.read_csv('/Users/fabrianivan/kaggle-squares-in-squares/data/submission_merged_22.253319.csv')
    cur = {int(n): g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float) for n, g in df_curr.groupby('n')}

    with open('/Users/fabrianivan/kaggle-squares-in-squares/data/external_packings/squares-in-squares-living-atlas-of-tight-packings.ipynb') as f:
        import base64, lzma
        nb = json.load(f)
    c22 = nb['cells'][22].get('source', '')
    if isinstance(c22, list): c22 = ''.join(c22)
    scope = {}
    exec(c22, scope)
    matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])), dtype='<f8').reshape(3, -1).T

    danil_packings = {}
    offset = 0
    for n in scope['REPLAY_NS']:
        danil_packings[n] = matrix[offset:offset+n]
        offset += n

    targets = scope['REPLAY_NS']
    print(f'Setting up jobs for {len(targets)} targets...')

    jobs = []
    for n in targets:
        p = cur[n]
        if n in danil_packings and packing_geometry.side(danil_packings[n]) < packing_geometry.side(p):
            p = danil_packings[n]
        for arm in range(6):
            jobs.append((n, p, arm, arm * 100 + 42))

    print(f'Total jobs: {len(jobs)} on 8 workers...')
    t0 = time.time()
    improvements = {}

    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(solve_job, j) for j in jobs]
        for f in as_completed(futures):
            n, L0, L1, q = f.result()
            if q is not None:
                c_L = packing_geometry.side(cur[n])
                if L1 < c_L - 1e-8:
                    rows = [{'n': str(n), 'square_id': str(i), 'x': repr(float(r[0])), 'y': repr(float(r[1])), 'angle': repr(float(r[2]))} for i, r in enumerate(q)]
                    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, rows)
                    if why == 'ok':
                        curr_best = improvements.get(n, (c_L, None))[0]
                        if float(L_cert) < curr_best - 1e-9:
                            improvements[n] = (float(L_cert), q)
                            print(f'>>> IMPROVEMENT n={n:3d}: {c_L:.8f} -> {float(L_cert):.8f} (gain: {(c_L - float(L_cert))/math.sqrt(n):.8f}) <<<', flush=True)

    print('=' * 60)
    print(f'Finished in {time.time() - t0:.1f}s. New improvements found by search: {len(improvements)}')
    # Save improvements
    out_dict = {str(n): q.tolist() for n, (_, q) in improvements.items()}
    with open('/Users/fabrianivan/kaggle-squares-in-squares/output/focus_improvements.json', 'w') as out_f:
        json.dump(out_dict, out_f)

if __name__ == '__main__':
    main()
