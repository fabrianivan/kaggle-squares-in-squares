import os, sys, math, json, csv
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np, pandas as pd

sys.path.insert(0, '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/tools')
sys.path.insert(0, '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/data/alexchilton')
import packing_geometry, metric

def verify_worker(item):
    n, src, c_s, new_s, recs = item
    import metric
    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, recs)
    return n, src, c_s, new_s, float(L_cert), why, recs

def main():
    print('Loading current baseline...')
    df_curr = pd.read_csv('/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/submission_merged_22.253319.csv')
    cur = {}
    for n, g in df_curr.groupby('n'):
        p = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
        cur[n] = (packing_geometry.side(p), g.sort_values('square_id')[['x', 'y', 'angle']].to_dict('records'))

    print('Loading aleksandr candidate...')
    df_cand = pd.read_csv('/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/data/aleksandr_drive/kaggle_public_candidate_20261102.csv')
    cand_rows = {}
    for n, g in df_cand.groupby('n'):
        cand_rows[n] = g.sort_values('square_id')[['x', 'y', 'angle']].to_dict('records')

    # Danil replay for 457 and 984
    with open('/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/danil_nb/squares-in-squares-living-atlas-of-tight-packings.ipynb') as f:
        import base64, lzma
        nb = json.load(f)
    scope = {}
    exec(''.join(nb['cells'][22]['source']), scope)
    matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])), dtype='<f8').reshape(3, -1).T
    danil_packings = {}
    offset = 0
    for n in scope['REPLAY_NS']:
        danil_packings[n] = matrix[offset:offset+n]
        offset += n

    # Collect candidate replacements
    test_items = []
    for n in range(1, 1001):
        c_s = cur[n][0]
        # check candidate
        cand_p = np.array([[r['x'], r['y'], r['angle']] for r in cand_rows[n]], float)
        cand_s = packing_geometry.side(cand_p)
        if cand_s < c_s - 1e-8:
            recs = [{'n': str(n), 'square_id': str(i), 'x': repr(float(r['x'])), 'y': repr(float(r['y'])), 'angle': repr(float(r['angle']))} for i, r in enumerate(cand_rows[n])]
            test_items.append((n, 'cand', c_s, cand_s, recs))

    # check 457 and 984
    for n in [457, 984]:
        d_p = danil_packings[n]
        d_s = packing_geometry.side(d_p)
        if d_s < cur[n][0] - 1e-8:
            recs = [{'n': str(n), 'square_id': str(i), 'x': repr(float(r[0])), 'y': repr(float(r[1])), 'angle': repr(float(r[2]))} for i, r in enumerate(d_p)]
            test_items.append((n, 'danil', cur[n][0], d_s, recs))

    print(f'Total candidates to certify: {len(test_items)}')
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(verify_worker, item) for item in test_items]
        results = [f.result() for f in as_completed(futures)]

    accepted = {}
    rejected = []
    for n, src, c_s, new_s, L_cert, why, recs in results:
        if why == 'ok' and L_cert < c_s - 1e-9:
            gain = (c_s - L_cert) / math.sqrt(n)
            # if multiple sources improved n, keep the smallest
            if n not in accepted or L_cert < accepted[n][0]:
                accepted[n] = (L_cert, src, gain, recs)
        else:
            rejected.append((n, src, c_s, new_s, L_cert, why))

    print(f'Certification results:')
    print(f'  ACCEPTED replacements: {len(accepted)}')
    print(f'  REJECTED replacements: {len(rejected)}')

    if rejected:
        print('Rejected details:')
        for x in rejected:
            print(f'  n={x[0]} ({x[1]}): {x[5]}')

    total_gain = sum(v[2] for v in accepted.values())
    print(f'TOTAL VERIFIED SCORE GAIN: -{total_gain:.10f}')
    print(f'Projected new official score: {22.2533185531 - total_gain:.10f}')

    # Assemble master submission
    final_puzzles = {}
    for n in range(1, 1001):
        if n in accepted:
            final_puzzles[n] = accepted[n][3]
        else:
            final_puzzles[n] = cur[n][1]

    out_csv = '/Users/fabrianivan/.gemini/antigravity-ide/scratch/squares-in-squares/submission_merged_22.251603.csv'
    total_rows = 0
    with open(out_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
        row_id = 0
        for n in range(1, 1001):
            puz = final_puzzles[n]
            assert len(puz) == n, f'Error: puzzle {n} has {len(puz)} squares!'
            for sid, row in enumerate(puz):
                writer.writerow([row_id, n, sid, repr(float(row['x'])), repr(float(row['y'])), repr(float(row['angle']))])
                row_id += 1
        total_rows = row_id

    print(f'Wrote {total_rows} rows to {out_csv}')
    assert total_rows == 500500, f'Expected 500500 rows, got {total_rows}'

    # Double check final file integrity
    df_check = pd.read_csv(out_csv)
    assert len(df_check) == 500500
    assert df_check.isna().sum().sum() == 0
    assert list(df_check.columns) == ['id', 'n', 'square_id', 'x', 'y', 'angle']
    assert (df_check['id'] == np.arange(500500)).all()
    print('Master submission verified 100% structurally complete and valid!')

if __name__ == '__main__':
    main()
