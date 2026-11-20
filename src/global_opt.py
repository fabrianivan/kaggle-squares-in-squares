#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Global optimizer using scipy.optimize.basinhopping.
Unlike the LP-based reclosure/polish which does local optimization,
basin hopping is a TRUE global optimizer that jumps between local minima
using the Metropolis criterion. It can escape the local optima that
trap the LP approach.
"""
import sys, os, json, math, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.optimize import basinhopping, minimize

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / 'tools'))
sys.path.insert(0, str(BASE_DIR / 'metric'))

import packing_geometry, metric


def pack_to_flat(p):
    """Convert (n, 3) packing to flat (3n,) array."""
    return p.reshape(-1)


def flat_to_pack(x, n):
    """Convert flat (3n,) array back to (n, 3) packing."""
    return x.reshape(n, 3)


def objective(x, n):
    """Penalty objective: enclosing square side + overlap penalty."""
    p = flat_to_pack(x, n)
    p = packing_geometry.normalize(p)

    # Enclosing square side (what we want to minimize)
    lo, hi = packing_geometry.aabbs(p)
    s = float(np.max(hi.max(0) - lo.min(0)))

    # Overlap penalty
    _, projections, support = packing_geometry.pair_data(p)
    if len(support):
        overlaps = np.maximum(0, support - np.abs(projections).max(1))
        penalty = float(np.sum(overlaps**2) * 1000)
    else:
        penalty = 0.0

    return s + penalty


def overlap_gradient(x, n):
    """Numerical gradient of the objective."""
    eps = 1e-6
    grad = np.zeros_like(x)
    for i in range(len(x)):
        xp = x.copy()
        xp[i] += eps
        xm = x.copy()
        xm[i] -= eps
        grad[i] = (objective(xp, n) - objective(xm, n)) / (2 * eps)
    return grad


def run_basinhopping(args):
    """Run basin hopping for one puzzle."""
    n, p_init, seed, niter = args
    import packing_geometry

    cur_L = packing_geometry.side(p_init)
    x0 = pack_to_flat(p_init)

    # Bounds: positions in [0, cur_L+1], angles in [-pi, pi]
    bounds = [(0, cur_L + 1)] * (2 * n) + [(-math.pi, math.pi)] * n

    best_L = cur_L
    best_p = p_init

    try:
        # Basin hopping with L-BFGS-B local optimizer
        result = basinhopping(
            objective,
            x0,
            niter=niter,
            seed=seed,
            minimizer_kwargs={
                'method': 'L-BFGS-B',
                'args': (n,),
                'bounds': bounds,
                'options': {'maxiter': 50, 'ftol': 1e-10}
            },
            take_step=lambda x: x + np.random.default_rng(seed).normal(0, 0.05, x.shape),
            accept_test=lambda f_new, x_new, f_old, x_old: True,  # Accept all
            interval=5,
            disp=False,
        )

        p_result = flat_to_pack(result.x, n)
        p_result = packing_geometry.normalize(p_result)
        p_result = packing_geometry.repair(p_result, clearance=1.5e-9)

        if p_result is not None:
            L_result = packing_geometry.side(p_result)
            if L_result < cur_L - 1e-8:
                # Further polish with contact_polish
                import cpu_contact_polish
                q, _, _ = cpu_contact_polish.polish(p_result, seed=seed+1000,
                                                    rounds=40, max_seconds=3.0,
                                                    trust_start=0.02)
                q = packing_geometry.repair(q, clearance=1.5e-9)
                if q is not None and packing_geometry.side(q) < L_result - 1e-8:
                    p_result = q
                    L_result = packing_geometry.side(q)

                return n, cur_L, L_result, p_result

    except Exception as e:
        pass

    return n, cur_L, cur_L, None


def run_scipy_minimize(args):
    """Run scipy minimize with multiple random restarts."""
    n, p_init, seed = args
    import packing_geometry

    cur_L = packing_geometry.side(p_init)
    best_L = cur_L
    best_p = p_init
    rng = np.random.default_rng(seed)

    for trial in range(5):
        # Starting point: current best + random perturbation OR grid + random angles
        if trial == 0:
            x0 = pack_to_flat(p_init)
        elif trial == 1:
            # Grid with random angles
            p = packing_geometry.grid(n).copy()
            p[:, 2] = rng.uniform(-math.pi/4, math.pi/4, n)
            x0 = pack_to_flat(p)
        else:
            # Perturb current best
            p = p_init.copy()
            p[:, :2] += rng.normal(0, 0.1, (n, 2))
            p[:, 2] += rng.normal(0, 0.1, n)
            x0 = pack_to_flat(p)

        bounds = [(0, cur_L + 2)] * (2 * n) + [(-math.pi, math.pi)] * n

        try:
            result = minimize(
                objective,
                x0,
                args=(n,),
                method='L-BFGS-B',
                bounds=bounds,
                options={'maxiter': 200, 'ftol': 1e-12}
            )

            p_result = flat_to_pack(result.x, n)
            p_result = packing_geometry.normalize(p_result)
            p_result = packing_geometry.repair(p_result, clearance=1.5e-9)

            if p_result is not None:
                L_result = packing_geometry.side(p_result)
                if L_result < best_L - 1e-8:
                    best_L = L_result
                    best_p = p_result
        except Exception:
            pass

    if best_L < cur_L - 1e-8:
        # Polish with contact_polish
        import cpu_contact_polish
        q, _, _ = cpu_contact_polish.polish(best_p, seed=seed+5000, rounds=50,
                                            max_seconds=3.0, trust_start=0.02)
        q = packing_geometry.repair(q, clearance=1.5e-9)
        if q is not None and packing_geometry.side(q) < best_L - 1e-8:
            best_p = q
            best_L = packing_geometry.side(q)

        return n, cur_L, best_L, best_p

    return n, cur_L, cur_L, None


def main():
    print("=" * 80)
    print("GLOBAL OPTIMIZER - scipy basinhopping + minimize with restarts")
    print("=" * 80)

    # Load current best
    baseline_path = str(BASE_DIR.parent / 'data' / 'submission_best.csv')
    print(f"\nLoading baseline: {Path(baseline_path).name}")
    df_curr = pd.read_csv(baseline_path)
    cur = {}
    for n, g in df_curr.groupby('n'):
        cur[int(n)] = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)

    # Also load our improved submission
    improved_path = str(BASE_DIR.parent / 'output' / 'submission_simple_22.251602.csv')
    if os.path.exists(improved_path):
        df_imp = pd.read_csv(improved_path)
        for n, g in df_imp.groupby('n'):
            n = int(n)
            p = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
            if packing_geometry.side(p) < packing_geometry.side(cur[n]):
                cur[n] = p
        print("Loaded improved baseline (22.251602)")

    # Target puzzles: focus on smaller n where basinhopping is feasible
    # and puzzles where grid is still the baseline
    targets = []
    for n in range(5, 1001):
        cur_L = packing_geometry.side(cur[n])
        grid_L = packing_geometry.side(packing_geometry.grid(n))
        # Prioritize puzzles still at grid level (most room) and small-medium n
        if abs(cur_L - grid_L) < 1e-6:
            targets.append((n, 3.0))  # High priority for grid puzzles
        elif n <= 50:
            targets.append((n, 2.0))
        elif n <= 200:
            targets.append((n, 1.0))

    # Sort by priority then by n (smaller first = faster basinhopping)
    targets.sort(key=lambda x: (-x[1], x[0]))

    # Take top targets
    target_ns = [n for n, _ in targets[:150]]
    print(f"\nTargeting {len(target_ns)} puzzles")
    print(f"Top 10: {target_ns[:10]}")

    # Build jobs
    jobs = []
    for n in target_ns:
        p_best = cur[n]
        # Basin hopping with different seeds
        for seed in range(3):
            jobs.append(('basinhop', (n, p_best, n*100+seed, 10)))
        # scipy minimize with random restarts
        jobs.append(('minimize', (n, p_best, n*100+42)))

    print(f"Total jobs: {len(jobs)}")
    print("Starting global optimization...\n")

    start_time = time.time()
    improvements = {}

    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = []
        for job_type, job_args in jobs:
            if job_type == 'basinhop':
                futures.append(pool.submit(run_basinhopping, job_args))
            else:
                futures.append(pool.submit(run_scipy_minimize, job_args))

        for f in as_completed(futures):
            try:
                n, L0, L1, q = f.result()
                if q is not None:
                    c_L = packing_geometry.side(cur[n])
                    if L1 < c_L - 1e-8:
                        # Certify
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
                                elapsed = time.time() - start_time
                                print(f'[{elapsed/60:.1f}m] >>> n={n:4d}: '
                                      f'{c_L:.10f} -> {float(L_cert):.10f} '
                                      f'(gain: {gain:.10f}) <<<', flush=True)
            except Exception as e:
                pass

    elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"Completed in {elapsed/60:.1f} minutes")
    print(f"Improvements found: {len(improvements)}")

    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - v[0]) / math.sqrt(n)
                        for n, v in improvements.items())
        baseline_score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1
                            for n in range(1, 1001))
        new_score = baseline_score - total_gain
        print(f"Baseline score:  {baseline_score:.10f}")
        print(f"Total gain:     -{total_gain:.10f}")
        print(f"New score:       {new_score:.10f}")

        # Save
        output_dir = BASE_DIR.parent / 'output'
        all_puzzles = {n: improvements[n][1] if n in improvements else cur[n]
                      for n in range(1, 1001)}
        import csv
        out_file = output_dir / f'submission_global_{new_score:.6f}.csv'
        with open(out_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            row_id = 0
            for n in range(1, 1001):
                p = all_puzzles[n]
                for sid in range(len(p)):
                    writer.writerow([row_id, n, sid,
                                   repr(float(p[sid, 0])),
                                   repr(float(p[sid, 1])),
                                   repr(float(p[sid, 2]))])
                    row_id += 1
        print(f"Saved to: {out_file}")
    else:
        print("No improvements found.")

    print("=" * 80)


if __name__ == '__main__':
    main()
