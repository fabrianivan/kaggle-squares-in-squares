#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Aggressive optimizer - much higher trust values and longer time than before.
Previous attempts used trust_start=0.02-0.05. This uses 0.1-0.5.
Also tries starting from GRID (completely different landscape).
"""
import sys, os, json, math, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np, pandas as pd

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / 'tools'))
sys.path.insert(0, str(BASE_DIR / 'metric'))
import packing_geometry, metric


def aggressive_polish(args):
    n, p_init, seed, trust_start, rounds, max_sec = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry

    L0 = packing_geometry.side(p_init)
    best_q = p_init
    best_L = L0

    try:
        # Phase 1: Reclosure with high trust
        for trust in [0.3, 0.5, 0.8]:
            q, _, _ = cpu_axis_reclosure.reclose(p_init, seed=seed, trust=trust,
                                                  tie=0.2, rounds=30, seconds=5.0)
            L_q = packing_geometry.side(q)
            if L_q < best_L - 1e-8:
                best_q = q
                best_L = L_q

        # Phase 2: VERY aggressive contact polish
        # High trust = large position/angle changes allowed
        for trust in [trust_start, trust_start * 2, trust_start * 4]:
            q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+1000, rounds=rounds,
                                                max_seconds=max_sec, trust_start=trust)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            if q is not None:
                L_q = packing_geometry.side(q)
                if L_q < best_L - 1e-8:
                    best_q = q
                    best_L = L_q

        # Phase 3: Optimal rotation + final polish
        if best_L < L0 - 1e-8:
            q_rot, _ = packing_geometry.optimal_rotation(best_q)
            q, _, _ = cpu_contact_polish.polish(q_rot, seed=seed+5000, rounds=40,
                                                max_seconds=3.0, trust_start=0.03)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            if q is not None and packing_geometry.side(q) < best_L - 1e-8:
                best_q = q
                best_L = packing_geometry.side(q)

        return n, L0, best_L, best_q if best_L < L0 - 1e-8 else None
    except:
        return n, L0, L0, None


def main():
    print("=" * 80)
    print("AGGRESSIVE OPTIMIZER - High trust, long time, grid + current best")
    print("=" * 80)

    # Load current best
    best_path = str(BASE_DIR.parent / 'data' / 'submission_best.csv')
    df = pd.read_csv(best_path)
    cur = {}
    for n, g in df.groupby('n'):
        cur[int(n)] = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
    score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"\nBaseline: {score:.10f}")

    # Build jobs: for each puzzle, try both current best AND grid start
    # with aggressive parameters
    jobs = []
    for n in range(1, 1001):
        # From current best: high trust
        jobs.append((n, cur[n], n * 100, 0.1, 80, 8.0))
        # From current best: very high trust
        jobs.append((n, cur[n], n * 100 + 1, 0.2, 80, 8.0))
        # From grid: let optimizer find packing from scratch
        if n >= 5:  # Skip trivial grid cases
            grid_p = packing_geometry.grid(n)
            jobs.append((n, grid_p, n * 100 + 2, 0.15, 80, 8.0))

    print(f"Total jobs: {len(jobs)}")
    print(f"Workers: 8")
    print("Starting...\n")

    t0 = time.time()
    improvements = {}

    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(aggressive_polish, j) for j in jobs]

        for f in as_completed(futures):
            try:
                n, L0, L1, q = f.result()
                if q is not None:
                    c_L = packing_geometry.side(cur[n])
                    if L1 < c_L - 1e-8:
                        rows = [{'n': str(n), 'square_id': str(i),
                                'x': repr(float(r[0])), 'y': repr(float(r[1])),
                                'angle': repr(float(r[2]))}
                               for i, r in enumerate(q)]
                        status, sc, L_cert, why = metric.evaluate_single_puzzle(n, rows)
                        if why == 'ok':
                            curr_best = improvements.get(n, (c_L, None))[0]
                            if float(L_cert) < curr_best - 1e-9:
                                improvements[n] = (float(L_cert), q)
                                gain = (c_L - float(L_cert)) / math.sqrt(n)
                                elapsed = time.time() - t0
                                print(f'[{elapsed/60:.1f}m] >>> n={n:4d}: '
                                      f'{c_L:.10f} -> {float(L_cert):.10f} '
                                      f'(gain: {gain:.10f}) <<<', flush=True)
            except:
                pass

    elapsed = time.time() - t0
    print(f"\n{'=' * 80}")
    print(f"Completed in {elapsed/60:.1f} minutes")
    print(f"Improvements: {len(improvements)}")

    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - v[0]) / math.sqrt(n)
                        for n, v in improvements.items())
        new_score = score - total_gain
        print(f"Gain: -{total_gain:.10f}")
        print(f"New score: {new_score:.10f}")

        # Save
        import csv
        out = BASE_DIR.parent / 'output' / f'submission_aggressive_{new_score:.6f}.csv'
        with open(out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            rid = 0
            for n in range(1, 1001):
                p = improvements[n][1] if n in improvements else cur[n]
                for sid in range(n):
                    w.writerow([rid, n, sid, repr(float(p[sid, 0])),
                               repr(float(p[sid, 1])), repr(float(p[sid, 2]))])
                    rid += 1
        print(f"Saved: {out}")
    else:
        print("No improvements found.")
    print("=" * 80)


if __name__ == '__main__':
    main()
