#!/usr/bin/env python3
"""
Advanced Optimizer - Multi-strategy packing improvement system
Combines multiple optimization techniques with intelligent exploration
"""
import sys, os, json, math, time, random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
sys.path.insert(0, str(Path(__file__).parent / 'data' / 'alexchilton'))
import metric
import cpu_axis_reclosure, cpu_contact_polish, packing_geometry


def strategy_adaptive_multi_phase(args):
    """Multi-phase optimization with adaptive parameters"""
    n, p_base, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    L0 = packing_geometry.side(p_base)
    
    try:
        # Phase 1: Aggressive reclosure with varying trust levels
        best_q = None
        best_L = L0
        
        for trust_mult in [0.6, 0.8, 1.0, 1.2]:
            trust = 0.25 * trust_mult
            tie = 0.15 * trust_mult
            q, _, _ = cpu_axis_reclosure.reclose(p_base, seed=seed+1000, trust=trust, tie=tie, rounds=20, seconds=3.0)
            L_q = packing_geometry.side(q)
            if L_q < best_L - 1e-8:
                best_q = q
                best_L = L_q
        
        if best_q is None:
            best_q = p_base
        
        # Phase 2: Contact polish with varying regularization
        for reg in [0.0, 0.0001, 0.001]:
            q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+2000, rounds=60, max_seconds=4.0, 
                                               trust_start=0.02, regularization=reg)
            L_q = packing_geometry.side(q)
            if L_q < best_L - 1e-8:
                best_q = q
                best_L = L_q
        
        # Phase 3: Fine-tune with optimal rotation
        if best_L < L0 - 1e-8:
            q_rot, _ = packing_geometry.optimal_rotation(best_q)
            L_rot = packing_geometry.side(q_rot)
            if L_rot < best_L - 1e-8:
                best_q = q_rot
                best_L = L_rot
        
        # Final repair
        best_q = packing_geometry.repair(best_q, clearance=1.5e-9)
        if best_q is not None and packing_geometry.side(best_q) < L0 - 1e-8:
            return n, L0, packing_geometry.side(best_q), best_q
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return n, L0, L0, None


def strategy_rotation_sweep(args):
    """Try multiple global rotations before optimization"""
    n, p_base, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    L0 = packing_geometry.side(p_base)
    
    try:
        best_q = None
        best_L = L0
        
        # Try multiple rotation angles
        angles = [0, np.pi/8, np.pi/6, np.pi/4, -np.pi/8, -np.pi/6]
        
        for angle in angles:
            p_rot = packing_geometry.rotate(p_base, angle)
            
            # Quick reclosure
            q, _, _ = cpu_axis_reclosure.reclose(p_rot, seed=seed, trust=0.3, tie=0.12, rounds=15, seconds=2.0)
            # Polish
            q, _, _ = cpu_contact_polish.polish(q, seed=seed+500, rounds=40, max_seconds=2.5, trust_start=0.02)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            
            if q is not None:
                L_q = packing_geometry.side(q)
                if L_q < best_L - 1e-8:
                    best_q = q
                    best_L = L_q
        
        if best_q is not None and best_L < L0 - 1e-8:
            return n, L0, best_L, best_q
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return n, L0, L0, None


def strategy_hybrid_cascade(args):
    """Cascade of alternating reclosure and polish steps"""
    n, p_base, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    L0 = packing_geometry.side(p_base)
    
    try:
        q = p_base
        improved = True
        cascade_rounds = 0
        
        while improved and cascade_rounds < 4:
            improved = False
            L_prev = packing_geometry.side(q)
            
            # Reclosure step
            q_new, _, _ = cpu_axis_reclosure.reclose(q, seed=seed+cascade_rounds*100, 
                                                     trust=0.2, tie=0.1, rounds=12, seconds=1.5)
            if packing_geometry.side(q_new) < L_prev - 1e-8:
                q = q_new
                improved = True
                L_prev = packing_geometry.side(q)
            
            # Polish step
            q_new, _, _ = cpu_contact_polish.polish(q, seed=seed+cascade_rounds*100+50, 
                                                    rounds=30, max_seconds=2.0, trust_start=0.025)
            q_new = packing_geometry.repair(q_new, clearance=1.5e-9)
            if q_new is not None and packing_geometry.side(q_new) < L_prev - 1e-8:
                q = q_new
                improved = True
            
            cascade_rounds += 1
        
        L_final = packing_geometry.side(q)
        if L_final < L0 - 1e-8:
            return n, L0, L_final, q
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return n, L0, L0, None


def strategy_perturbation_search(args):
    """Random perturbations followed by optimization"""
    n, p_base, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    L0 = packing_geometry.side(p_base)
    rng = np.random.default_rng(seed)
    
    try:
        best_q = None
        best_L = L0
        
        # Try multiple random perturbations
        for trial in range(5):
            # Small random perturbation
            p_perturb = p_base.copy()
            perturb_scale = 0.02 * (1.0 - 0.15 * trial)  # Decreasing perturbation
            p_perturb[:, 0] += rng.normal(0, perturb_scale, n)
            p_perturb[:, 1] += rng.normal(0, perturb_scale, n)
            p_perturb[:, 2] += rng.normal(0, perturb_scale * 0.3, n)
            p_perturb = packing_geometry.normalize(p_perturb)
            
            # Optimize perturbed configuration
            q, _, _ = cpu_contact_polish.polish(p_perturb, seed=seed+trial, rounds=45, 
                                               max_seconds=2.0, trust_start=0.03)
            q = packing_geometry.repair(q, clearance=1.5e-9)
            
            if q is not None:
                L_q = packing_geometry.side(q)
                if L_q < best_L - 1e-8:
                    best_q = q
                    best_L = L_q
        
        if best_q is not None and best_L < L0 - 1e-8:
            return n, L0, best_L, best_q
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return n, L0, L0, None


def run_optimizer(baseline_csv, output_dir, n_workers=8, target_puzzles=None, max_time_hours=4):
    """Main optimization driver"""
    print("="*80)
    print("ADVANCED MULTI-STRATEGY OPTIMIZER")
    print("="*80)
    
    # Load baseline
    print(f"\nLoading baseline from {baseline_csv}...")
    df_curr = pd.read_csv(baseline_csv)
    cur = {int(n): g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float) 
           for n, g in df_curr.groupby('n')}
    
    # Load all available external packings
    external_packings = {}
    
    # Load Danil's packings
    try:
        danil_nb_path = Path(__file__).parent / 'danil_nb' / 'squares-in-squares-living-atlas-of-tight-packings.ipynb'
        if danil_nb_path.exists():
            with open(danil_nb_path) as f:
                import base64, lzma
                nb = json.load(f)
            scope = {}
            exec(''.join(nb['cells'][22]['source']), scope)
            matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])), dtype='<f8').reshape(3, -1).T
            offset = 0
            for n in scope['REPLAY_NS']:
                external_packings[n] = matrix[offset:offset+n]
                offset += n
            print(f"Loaded {len(external_packings)} packings from Danil's notebook")
    except Exception as e:
        print(f"Could not load Danil packings: {e}")
    
    # Load PJ's record-breaking packings
    try:
        pj_nb_path = Path(__file__).parent / 'pj_nb' / 'three-square-packings-that-beat-the-records.ipynb'
        if pj_nb_path.exists():
            with open(pj_nb_path) as f:
                nb = json.load(f)
            src = ''.join(nb['cells'][3]['source'])
            scope = {}
            exec(src, scope)
            pj_packings = scope['PACKINGS']
            for n, coords in pj_packings.items():
                if n not in external_packings or packing_geometry.side(np.array(coords, float)) < packing_geometry.side(external_packings[n]):
                    external_packings[n] = np.array(coords, float)
            print(f"Loaded PJ packings for n={list(pj_packings.keys())}")
    except Exception as e:
        print(f"Could not load PJ packings: {e}")
    
    # Determine targets
    if target_puzzles is None:
        # Prioritize larger puzzles (better score improvements) and those with external packings
        all_n = list(range(1, 1001))
        # Score: prioritize larger n and those with potential improvements
        scores = {}
        for n in all_n:
            base_score = math.sqrt(n) * 0.001  # Larger n = better potential
            if n in external_packings:
                ext_L = packing_geometry.side(external_packings[n])
                cur_L = packing_geometry.side(cur[n])
                if ext_L < cur_L - 1e-8:
                    base_score += (cur_L - ext_L) / math.sqrt(n) * 100  # Huge priority for known improvements
            scores[n] = base_score
        
        # Sort by score descending, focus on top candidates
        target_puzzles = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)[:400]
    
    print(f"\nTargeting {len(target_puzzles)} puzzles")
    print(f"Using {n_workers} workers")
    print(f"Max runtime: {max_time_hours} hours")
    
    # Build jobs - multiple strategies per puzzle
    jobs = []
    strategies = [
        ('adaptive_multi_phase', strategy_adaptive_multi_phase),
        ('rotation_sweep', strategy_rotation_sweep),
        ('hybrid_cascade', strategy_hybrid_cascade),
        ('perturbation_search', strategy_perturbation_search),
    ]
    
    for n in target_puzzles:
        # Use external packing if better
        p_start = cur[n]
        if n in external_packings:
            ext_p = external_packings[n]
            if packing_geometry.side(ext_p) < packing_geometry.side(p_start):
                p_start = ext_p
        
        # Create jobs for each strategy
        for strat_name, strat_func in strategies:
            base_seed = hash(strat_name) % 10000 + n * 1000
            jobs.append((strat_func, (n, p_start, base_seed)))
    
    print(f"\nTotal optimization jobs: {len(jobs)}")
    print(f"Starting optimization...\n")
    
    start_time = time.time()
    improvements = {}
    max_seconds = max_time_hours * 3600
    
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(func, args) for func, args in jobs]
        
        for f in as_completed(futures):
            if time.time() - start_time > max_seconds:
                print(f"\nTime limit reached ({max_time_hours} hours), stopping...")
                break
            
            try:
                n, L0, L1, q = f.result()
                
                if q is not None:
                    c_L = packing_geometry.side(cur[n])
                    if L1 < c_L - 1e-8:
                        # Verify with official metric
                        rows = [{'n': str(n), 'square_id': str(i), 
                                'x': repr(float(r[0])), 'y': repr(float(r[1])), 'angle': repr(float(r[2]))} 
                               for i, r in enumerate(q)]
                        status, sc, L_cert, why = metric.evaluate_single_puzzle(n, rows)
                        
                        if why == 'ok':
                            curr_best = improvements.get(n, (c_L, None))[0]
                            if float(L_cert) < curr_best - 1e-9:
                                improvements[n] = (float(L_cert), q)
                                gain = (c_L - float(L_cert)) / math.sqrt(n)
                                elapsed = time.time() - start_time
                                print(f'[{elapsed/60:.1f}m] >>> IMPROVEMENT n={n:4d}: {c_L:.10f} -> {float(L_cert):.10f} '
                                     f'(gain: {gain:.10f}) <<<', flush=True)
            except Exception as e:
                print(f"Job failed: {e}")
    
    elapsed = time.time() - start_time
    print("\n" + "="*80)
    print(f'Optimization completed in {elapsed/60:.1f} minutes')
    print(f'Found improvements for {len(improvements)} puzzles')
    
    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - L) / math.sqrt(n) for n, (L, _) in improvements.items())
        print(f'Total score improvement: -{total_gain:.10f}')
        
        # Baseline score
        baseline_score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
        print(f'Projected new score: {baseline_score - total_gain:.10f}')
        
        # Save improvements
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        improvements_file = output_dir / 'improvements.json'
        out_dict = {str(n): q.tolist() for n, (_, q) in improvements.items()}
        with open(improvements_file, 'w') as f:
            json.dump(out_dict, f)
        print(f'\nSaved improvements to {improvements_file}')
        
        # Create new submission
        print('\nCreating new submission...')
        all_puzzles = {}
        for n in range(1, 1001):
            if n in improvements:
                all_puzzles[n] = improvements[n][1]
            else:
                all_puzzles[n] = cur[n]
        
        submission_file = output_dir / f'submission_advanced_{baseline_score - total_gain:.6f}.csv'
        with open(submission_file, 'w', newline='') as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            row_id = 0
            for n in range(1, 1001):
                packing = all_puzzles[n]
                for sid in range(len(packing)):
                    writer.writerow([row_id, n, sid, 
                                   repr(float(packing[sid, 0])), 
                                   repr(float(packing[sid, 1])), 
                                   repr(float(packing[sid, 2]))])
                    row_id += 1
        
        print(f'Saved submission to {submission_file}')
    else:
        print('No improvements found')
    
    print("="*80)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Advanced multi-strategy optimizer')
    parser.add_argument('--baseline', type=str, 
                       default='submission_merged_22.253319.csv',
                       help='Baseline submission CSV')
    parser.add_argument('--output', type=str, 
                       default='advanced_out',
                       help='Output directory')
    parser.add_argument('--workers', type=int, default=8,
                       help='Number of parallel workers')
    parser.add_argument('--hours', type=float, default=4.0,
                       help='Maximum runtime in hours')
    parser.add_argument('--targets', type=str, default=None,
                       help='Comma-separated list of n values to target (default: auto-select)')
    
    args = parser.parse_args()
    
    targets = None
    if args.targets:
        targets = [int(x.strip()) for x in args.targets.split(',')]
    
    run_optimizer(args.baseline, args.output, args.workers, targets, args.hours)
