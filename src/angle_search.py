#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Angle Search - Try fundamentally different angle configurations as starting points.
Instead of perturbing the current best, create completely different layouts:
  1. Uniform tilt (all squares at 45°, 30°, etc.)
  2. Mixed 0°/45° checkerboard pattern
  3. Random angle assignments
  4. Current best + large angle perturbations
Then run reclosure + polish from each starting point.
"""
import sys, os, json, math, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / 'tools'))
sys.path.insert(0, str(BASE_DIR / 'metric'))

import packing_geometry, cpu_axis_reclosure, cpu_contact_polish, metric


def make_uniform_tilt(n, angle):
    """Grid packing with all squares tilted at the same angle."""
    k = math.ceil(math.sqrt(n))
    p = packing_geometry.grid(n).copy()
    p[:, 2] = angle
    return packing_geometry.normalize(p)


def make_mixed_tilt(n, angle1=0.0, angle2=math.pi/4):
    """Grid packing with alternating angles (checkerboard pattern)."""
    k = math.ceil(math.sqrt(n))
    p = packing_geometry.grid(n).copy()
    for i in range(n):
        row, col = i // k, i % k
        p[i, 2] = angle1 if (row + col) % 2 == 0 else angle2
    return packing_geometry.normalize(p)


def make_row_tilt(n, angle1=0.0, angle2=math.pi/4):
    """Grid packing with alternating rows at different angles."""
    k = math.ceil(math.sqrt(n))
    p = packing_geometry.grid(n).copy()
    for i in range(n):
        row = i // k
        p[i, 2] = angle1 if row % 2 == 0 else angle2
    return packing_geometry.normalize(p)


def make_block_tilt(n, angle1=0.0, angle2=math.pi/4, frac=0.3):
    """Grid packing with a central block tilted at angle2."""
    k = math.ceil(math.sqrt(n))
    p = packing_geometry.grid(n).copy()
    center = k / 2
    half = k * frac
    for i in range(n):
        row, col = i // k, i % k
        if abs(row - center + 0.5) < half and abs(col - center + 0.5) < half:
            p[i, 2] = angle2
        else:
            p[i, 2] = angle1
    return packing_geometry.normalize(p)


def make_random_angles(n, seed=0, scale=math.pi/4):
    """Grid packing with random angles."""
    rng = np.random.default_rng(seed)
    p = packing_geometry.grid(n).copy()
    p[:, 2] = rng.uniform(-scale, scale, n)
    return packing_geometry.normalize(p)


def perturb_angles(p_base, seed=0, scale=0.3):
    """Take current best and add large random angle perturbations."""
    rng = np.random.default_rng(seed)
    p = p_base.copy()
    p[:, 2] += rng.normal(0, scale, len(p))
    p = packing_geometry.normalize(p)
    return p


def try_config(args):
    """Try one angle configuration: create starting point, optimize, return result."""
    n, config_name, p_init, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry

    L0 = packing_geometry.side(p_init)
    best_q = p_init
    best_L = L0

    try:
        # Phase 1: Reclosure (fix angles, optimize positions)
        for trust in [0.15, 0.3, 0.5]:
            q, _, _ = cpu_axis_reclosure.reclose(p_init, seed=seed, trust=trust,
                                                  tie=0.15, rounds=20, seconds=3.0)
            L_q = packing_geometry.side(q)
            if L_q < best_L - 1e-8:
                best_q = q
                best_L = L_q

        # Phase 2: Contact polish (optimize both positions and angles)
        for start_trust in [0.02, 0.05, 0.1]:
            q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+1000, rounds=60,
                                                max_seconds=5.0, trust_start=start_trust)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            if q is not None:
                L_q = packing_geometry.side(q)
                if L_q < best_L - 1e-8:
                    best_q = q
                    best_L = L_q

        # Phase 3: Optimal rotation
        if best_L < L0 - 1e-8:
            q_rot, _ = packing_geometry.optimal_rotation(best_q)
            L_rot = packing_geometry.side(q_rot)
            if L_rot < best_L - 1e-8:
                best_q = q_rot
                best_L = L_rot
                # One more polish after rotation
                q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+2000, rounds=30,
                                                    max_seconds=2.0, trust_start=0.02)
                q = packing_geometry.repair(q, clearance=1.5e-9)
                if q is not None:
                    L_q = packing_geometry.side(q)
                    if L_q < best_L - 1e-8:
                        best_q = q
                        best_L = L_q

        return n, config_name, L0, best_L, best_q

    except Exception:
        return n, config_name, L0, L0, None


def main():
    print("=" * 80)
    print("ANGLE SEARCH - Different angle configurations as starting points")
    print("=" * 80)

    # Load current best
    baseline_path = str(BASE_DIR.parent / 'data' / 'submission_best.csv')
    print(f"\nLoading baseline: {baseline_path}")
    df_curr = pd.read_csv(baseline_path)
    cur = {}
    for n, g in df_curr.groupby('n'):
        cur[int(n)] = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)

    # Also load external packings (Danil, PJ)
    external = {}
    try:
        import base64, lzma
        danil_path = str(BASE_DIR.parent / 'data' / 'external_packings' / 'squares-in-squares-living-atlas-of-tight-packings.ipynb')
        with open(danil_path) as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][22]['source']), scope)
        matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])),
                               dtype='<f8').reshape(3, -1).T
        offset = 0
        for n in scope['REPLAY_NS']:
            external[n] = matrix[offset:offset+n]
            offset += n
        print(f"Loaded {len(external)} Danil packings")
    except Exception as e:
        print(f"Danil: {e}")

    # Build jobs: for each target puzzle, try multiple angle configurations
    # Focus on puzzles where grid is the baseline (not already optimal)
    # and larger puzzles (more score impact)
    targets = list(range(5, 1001))

    # Prioritize: large n, and puzzles where current is a grid (score > 0)
    priorities = {}
    for n in targets:
        cur_L = packing_geometry.side(cur[n])
        grid_L = packing_geometry.side(packing_geometry.grid(n))
        priority = math.sqrt(n)  # larger n = more valuable
        if abs(cur_L - grid_L) < 1e-6:  # still a grid, lots of room
            priority *= 5
        priorities[n] = priority

    # Sort by priority and take top targets
    targets = sorted(targets, key=lambda n: priorities[n], reverse=True)[:200]

    print(f"\nTargeting {len(targets)} puzzles")
    print(f"Top 10: {targets[:10]}")

    # Build configurations for each target
    jobs = []
    configs_per_puzzle = 0

    for n in targets:
        p_best = cur[n]
        if n in external:
            ext_p = external[n]
            if packing_geometry.side(ext_p) < packing_geometry.side(p_best):
                p_best = ext_p

        cur_L = packing_geometry.side(p_best)

        # Config 1: Uniform tilt at 45°
        jobs.append((n, 'uniform_45', make_uniform_tilt(n, math.pi/4), n*100))
        configs_per_puzzle += 1

        # Config 2: Uniform tilt at 30°
        jobs.append((n, 'uniform_30', make_uniform_tilt(n, math.pi/6), n*100+1))
        configs_per_puzzle += 1

        # Config 3: Mixed 0°/45° checkerboard
        jobs.append((n, 'mixed_checker', make_mixed_tilt(n), n*100+2))
        configs_per_puzzle += 1

        # Config 4: Mixed 0°/45° rows
        jobs.append((n, 'mixed_rows', make_row_tilt(n), n*100+3))
        configs_per_puzzle += 1

        # Config 5: Central block tilted 45°
        jobs.append((n, 'block_tilt', make_block_tilt(n), n*100+4))
        configs_per_puzzle += 1

        # Config 6: Random angles (seed 1)
        jobs.append((n, 'random_1', make_random_angles(n, seed=n), n*100+5))
        configs_per_puzzle += 1

        # Config 7: Random angles (seed 2)
        jobs.append((n, 'random_2', make_random_angles(n, seed=n*7+13), n*100+6))
        configs_per_puzzle += 1

        # Config 8: Current best + large angle perturbation
        jobs.append((n, 'perturb_cur', perturb_angles(p_best, seed=n, scale=0.2), n*100+7))
        configs_per_puzzle += 1

    print(f"Total jobs: {len(jobs)} ({configs_per_puzzle//len(targets)} configs per puzzle)")
    print("Starting optimization...\n")

    start_time = time.time()
    improvements = {}

    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(try_config, job) for job in jobs]

        for f in as_completed(futures):
            n, config_name, L0, L1, q = f.result()

            if q is not None:
                c_L = packing_geometry.side(cur[n])
                if L1 < c_L - 1e-8:
                    # Certify with official metric
                    rows = [{'n': str(n), 'square_id': str(i),
                            'x': repr(float(r[0])), 'y': repr(float(r[1])),
                            'angle': repr(float(r[2]))}
                           for i, r in enumerate(q)]
                    status, sc, L_cert, why = metric.evaluate_single_puzzle(n, rows)

                    if why == 'ok':
                        curr_best = improvements.get(n, (c_L, None, None))[0]
                        if float(L_cert) < curr_best - 1e-9:
                            improvements[n] = (float(L_cert), q, config_name)
                            gain = (c_L - float(L_cert)) / math.sqrt(n)
                            elapsed = time.time() - start_time
                            print(f'[{elapsed/60:.1f}m] >>> n={n:4d} [{config_name:15s}]: '
                                  f'{c_L:.10f} -> {float(L_cert):.10f} '
                                  f'(gain: {gain:.10f}) <<<', flush=True)

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

        # Show which configs found improvements
        config_counts = {}
        for n, (_, _, config_name) in improvements.items():
            config_counts[config_name] = config_counts.get(config_name, 0) + 1
        print("\nImprovements by config:")
        for name, count in sorted(config_counts.items(), key=lambda x: -x[1]):
            print(f"  {name:20s}: {count}")

        # Save improvements
        output_dir = BASE_DIR.parent / 'output'
        output_dir.mkdir(exist_ok=True)

        # Merge with current best
        all_puzzles = {}
        for n in range(1, 1001):
            if n in improvements:
                all_puzzles[n] = improvements[n][1]
            else:
                all_puzzles[n] = cur[n]

        import csv
        out_file = output_dir / f'submission_angle_{new_score:.6f}.csv'
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

        print(f"\nSaved to: {out_file}")
        print(f"Rows: {row_id}")

        # Show top improvements
        print("\nTop 10 improvements:")
        imp_list = [(n, (packing_geometry.side(cur[n]) - v[0]) / math.sqrt(n), v[2])
                    for n, v in improvements.items()]
        imp_list.sort(key=lambda x: x[1], reverse=True)
        for n, gain, config in imp_list[:10]:
            print(f"  n={n:4d} [{config:15s}]: gain={gain:.10f}")
    else:
        print("No improvements found.")

    print("=" * 80)


if __name__ == '__main__':
    main()
