#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Quick Wins - Target the highest-value improvements first
Focus on puzzles where we know improvements exist or are most likely
"""
import sys, os, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
sys.path.insert(0, str(Path(__file__).parent / 'data' / 'alexchilton'))
import metric, packing_geometry, cpu_axis_reclosure, cpu_contact_polish


def ultra_polish(args):
    """Extra intensive polish for high-value targets"""
    n, p_base, seed = args
    import cpu_axis_reclosure, cpu_contact_polish, packing_geometry
    
    L0 = packing_geometry.side(p_base)
    best_q = p_base
    best_L = L0
    
    try:
        # Step 1: Multiple reclosure attempts with varying parameters
        for trust in [0.15, 0.25, 0.35, 0.5]:
            for tie in [0.08, 0.15, 0.25]:
                q, _, _ = cpu_axis_reclosure.reclose(p_base, seed=seed, trust=trust, tie=tie, 
                                                     rounds=25, seconds=4.0)
                L_q = packing_geometry.side(q)
                if L_q < best_L - 1e-8:
                    best_q = q
                    best_L = L_q
                    seed += 1
        
        # Step 2: Intensive polish with multiple trust schedules
        for start_trust in [0.01, 0.02, 0.03, 0.05]:
            for reg in [0.0, 0.0005]:
                q, _, _ = cpu_contact_polish.polish(best_q, seed=seed, rounds=70, 
                                                    max_seconds=6.0, trust_start=start_trust,
                                                    regularization=reg)
                q = packing_geometry.repair(q, clearance=1.5e-9)
                if q is not None:
                    L_q = packing_geometry.side(q)
                    if L_q < best_L - 1e-8:
                        best_q = q
                        best_L = L_q
                        seed += 1
        
        # Step 3: Optimal rotation
        if best_L < L0 - 1e-8:
            q_rot, angle = packing_geometry.optimal_rotation(best_q)
            L_rot = packing_geometry.side(q_rot)
            if L_rot < best_L - 1e-8:
                best_q = q_rot
                best_L = L_rot
                
                # Polish the rotated version
                q, _, _ = cpu_contact_polish.polish(best_q, seed=seed+1000, rounds=40, 
                                                    max_seconds=3.0, trust_start=0.015)
                q = packing_geometry.repair(q, clearance=1.5e-9)
                if q is not None:
                    L_q = packing_geometry.side(q)
                    if L_q < best_L - 1e-8:
                        best_q = q
                        best_L = L_q
        
        # Final certification
        if best_L < L0 - 1e-8:
            return n, L0, best_L, best_q
            
    except Exception as e:
        print(f"Error on n={n}: {e}")
    
    return n, L0, L0, None


def main():
    print("="*80)
    print("QUICK WINS - High-Value Target Optimizer")
    print("="*80)
    
    # Load baseline
    baseline_csv = '/Users/fabrianivan/kaggle-squares-in-squares/data/submission_best.csv'
    print(f"\nLoading baseline: {baseline_csv}")
    df_curr = pd.read_csv(baseline_csv)
    cur = {int(n): g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float) 
           for n, g in df_curr.groupby('n')}
    
    # Load external packings
    external = {}
    
    # Danil's packings
    try:
        with open('/Users/fabrianivan/kaggle-squares-in-squares/data/external_packings/squares-in-squares-living-atlas-of-tight-packings.ipynb') as f:
            import base64, lzma
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
        print(f"Could not load Danil: {e}")
    
    # PJ's packings (299, 260, 232)
    try:
        with open('/Users/fabrianivan/kaggle-squares-in-squares/data/external_packings/three-square-packings-that-beat-the-records.ipynb') as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][3]['source']), scope)
        for n, coords in scope['PACKINGS'].items():
            external[n] = np.array(coords, float)
        print(f"Loaded PJ packings: {list(scope['PACKINGS'].keys())}")
    except Exception as e:
        print(f"Could not load PJ: {e}")
    
    # Identify high-value targets
    opportunities = []
    
    for n in range(1, 1001):
        score_weight = math.sqrt(n)  # Larger n = more valuable
        priority = 0
        
        # Check if external packing is better
        if n in external:
            ext_L = packing_geometry.side(external[n])
            cur_L = packing_geometry.side(cur[n])
            if ext_L < cur_L - 1e-8:
                potential_gain = (cur_L - ext_L) / math.sqrt(n)
                priority = potential_gain * 1000  # Known improvements get highest priority
        
        # Larger puzzles always get some priority
        if n >= 200:
            priority += 1.0
        elif n >= 100:
            priority += 0.5
        elif n >= 50:
            priority += 0.2
        
        if priority > 0:
            opportunities.append((n, priority))
    
    # Sort by priority
    opportunities.sort(key=lambda x: x[1], reverse=True)
    
    # Take top targets
    top_n = 150
    targets = [n for n, _ in opportunities[:top_n]]
    
    print(f"\nFocusing on top {len(targets)} opportunities")
    print(f"Top 10 targets: {targets[:10]}")
    
    # Build jobs - multiple attempts per target
    jobs = []
    for n in targets:
        # Use best available starting point
        p_start = cur[n]
        if n in external:
            ext_p = external[n]
            if packing_geometry.side(ext_p) < packing_geometry.side(p_start):
                p_start = ext_p
        
        # Multiple seeds for diversity
        for seed_offset in range(4):
            jobs.append((n, p_start, n * 10000 + seed_offset))
    
    print(f"Total jobs: {len(jobs)}")
    print("Starting optimization...\n")
    
    improvements = {}
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(ultra_polish, job) for job in jobs]
        
        for f in as_completed(futures):
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
                            print(f'>>> n={n:4d}: {c_L:.10f} -> {float(L_cert):.10f} '
                                 f'(gain: {gain:.10f}) <<<', flush=True)
    
    elapsed = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"Completed in {elapsed/60:.1f} minutes")
    print(f"Improvements found: {len(improvements)}")
    
    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - L) / math.sqrt(n) 
                        for n, (L, _) in improvements.items())
        baseline_score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1 
                           for n in range(1, 1001))
        new_score = baseline_score - total_gain
        
        print(f"Baseline score: {baseline_score:.10f}")
        print(f"Total gain: -{total_gain:.10f}")
        print(f"New score: {new_score:.10f}")
        
        # Save
        out_dir = Path('/Users/fabrianivan/kaggle-squares-in-squares/output/quick_wins_out')
        out_dir.mkdir(exist_ok=True)
        
        # Save improvements
        with open(out_dir / 'improvements.json', 'w') as f:
            json.dump({str(n): q.tolist() for n, (_, q) in improvements.items()}, f)
        
        # Create submission
        import csv
        with open(out_dir / f'submission_{new_score:.6f}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            row_id = 0
            for n in range(1, 1001):
                p = improvements[n][1] if n in improvements else cur[n]
                for sid in range(len(p)):
                    writer.writerow([row_id, n, sid, repr(float(p[sid, 0])), 
                                   repr(float(p[sid, 1])), repr(float(p[sid, 2]))])
                    row_id += 1
        
        print(f"\nResults saved to {out_dir}/")
        
        # Show top improvements
        print("\nTop 10 improvements:")
        imp_list = [(n, (packing_geometry.side(cur[n]) - L) / math.sqrt(n)) 
                    for n, (L, _) in improvements.items()]
        imp_list.sort(key=lambda x: x[1], reverse=True)
        for n, gain in imp_list[:10]:
            print(f"  n={n:4d}: gain={gain:.10f}")
    
    print("="*80)


if __name__ == '__main__':
    main()
