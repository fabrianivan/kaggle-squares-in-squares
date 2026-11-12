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
    L0 = packing_geometry.side(p_base)
    best_q = p_base
    best_L = L0
    try:
        # Strategy 0-2: reclosure with increasing trust then polish
        trust = [0.12, 0.25, 0.5, 0.8][arm % 4]
        tie = [0.03, 0.12, 0.25, 0.4][(arm // 4) % 4]

        # Reclosure
        q, _, _ = cpu_axis_reclosure.reclose(p_base, seed=seed, trust=trust, tie=tie, rounds=25, seconds=3.0)
        if packing_geometry.side(q) < best_L - 1e-8:
            best_q = q
            best_L = packing_geometry.side(q)

        # Aggressive polish with high trust
        for ts in [0.02, 0.05, 0.1]:
            q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+ts*1000, rounds=60, max_seconds=4.0, trust_start=ts)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            if q is not None and packing_geometry.side(q) < best_L - 1e-8:
                best_q = q
                best_L = packing_geometry.side(q)

        # Optimal rotation + final polish
        if best_L < L0 - 1e-8:
            q_rot, _ = packing_geometry.optimal_rotation(best_q)
            q, _, _ = cpu_contact_polish.polish(q_rot, seed=seed+9999, rounds=30, max_seconds=2.0, trust_start=0.02)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            if q is not None and packing_geometry.side(q) < best_L - 1e-8:
                best_q = q
                best_L = packing_geometry.side(q)

        if best_L < L0 - 1e-8:
            return n, L0, best_L, best_q
    except Exception:
        pass
    return n, L0, L0, None

def main():
    df_curr = pd.read_csv('/Users/fabrianivan/kaggle-squares-in-squares/data/submission_best.csv')
    cur = {int(n): g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float) for n, g in df_curr.groupby('n')}
    base_score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f'Baseline score: {base_score:.10f}')

    # Load Danil packings for better starting points
    danil_packings = {}
    try:
        with open('/Users/fabrianivan/kaggle-squares-in-squares/data/external_packings/squares-in-squares-living-atlas-of-tight-packings.ipynb') as f:
            import base64, lzma
            nb = json.load(f)
        c22 = nb['cells'][22].get('source', '')
        if isinstance(c22, list): c22 = ''.join(c22)
        scope = {}
        exec(c22, scope)
        matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])), dtype='<f8').reshape(3, -1).T
        offset = 0
        for n in scope['REPLAY_NS']:
            danil_packings[n] = matrix[offset:offset+n]
            offset += n
        print(f'Loaded {len(danil_packings)} Danil packings')
    except Exception as e:
        print(f'Danil load failed: {e}')

    # Target ALL 1000 puzzles with 8 arms each
    targets = list(range(1, 1001))
    print(f'Setting up jobs for {len(targets)} targets...')

    jobs = []
    for n in targets:
        p = cur[n]
        if n in danil_packings and packing_geometry.side(danil_packings[n]) < packing_geometry.side(p):
            p = danil_packings[n]
        for arm in range(8):
            jobs.append((n, p, arm, arm * 137 + n * 31 + 42))

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
                            gain = (c_L - float(L_cert)) / math.sqrt(n)
                            print(f'>>> IMPROVEMENT n={n:3d}: {c_L:.8f} -> {float(L_cert):.8f} (gain: {gain:.8f}) <<<', flush=True)

    elapsed = time.time() - t0
    print('=' * 60)
    print(f'Finished in {elapsed:.1f}s. Improvements found: {len(improvements)}')

    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - v[0]) / math.sqrt(n) for n, v in improvements.items())
        new_score = base_score - total_gain
        print(f'Total gain: {total_gain:.10f}')
        print(f'New score: {new_score:.10f}')

        # Merge and save
        import csv
        out = '/Users/fabrianivan/kaggle-squares-in-squares/output/submission_focus_new.csv'
        with open(out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            rid = 0
            for n in range(1, 1001):
                p = improvements[n][1] if n in improvements else cur[n]
                for sid in range(n):
                    w.writerow([rid, n, sid, repr(float(p[sid, 0])), repr(float(p[sid, 1])), repr(float(p[sid, 2]))])
                    rid += 1
        print(f'Saved to {out}')

    # Also save improvements JSON
    out_dict = {str(n): q.tolist() for n, (_, q) in improvements.items()}
    with open('/Users/fabrianivan/kaggle-squares-in-squares/output/focus_improvements.json', 'w') as out_f:
        json.dump(out_dict, out_f)

if __name__ == '__main__':
    main()
