#!/Users/fabrianivan/.local/share/kaggle-venv/bin/python3.14
"""
Simple Improvement Script - Merge known better packings
Fastest way to improve score by combining external sources
"""
import sys, os, json, math
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / 'tools'))
sys.path.insert(0, str(BASE_DIR / 'metric'))

def main():
    print("="*80)
    print("SIMPLE IMPROVEMENT - Merge Known Better Packings")
    print("="*80)
    
    # Import here
    import numpy as np
    import pandas as pd
    from tools import packing_geometry
    
    # Load baseline
    baseline = BASE_DIR.parent / 'data' / 'submission_merged_22.253319.csv'
    print(f"\n1. Loading baseline: {baseline.name}")
    df_curr = pd.read_csv(baseline)
    cur = {}
    for n, g in df_curr.groupby('n'):
        cur[int(n)] = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
    
    print(f"   Loaded {len(cur)} puzzles")
    
    # Calculate baseline score
    baseline_score = sum(packing_geometry.side(cur[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    print(f"   Baseline score: {baseline_score:.10f}")
    
    # Load external improvements
    improvements = {}
    
    # 1. Load Danil's packings
    print("\n2. Loading Danil's packings...")
    try:
        import base64, lzma
        danil_path = BASE_DIR.parent / 'data' / 'external_packings' / 'squares-in-squares-living-atlas-of-tight-packings.ipynb'
        with open(danil_path) as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][22]['source']), scope)
        matrix = np.frombuffer(lzma.decompress(base64.b64decode(scope['REPLAY_B64'])), 
                              dtype='<f8').reshape(3, -1).T
        offset = 0
        count = 0
        for n in scope['REPLAY_NS']:
            danil_p = matrix[offset:offset+n]
            offset += n
            cur_L = packing_geometry.side(cur[n])
            danil_L = packing_geometry.side(danil_p)
            if danil_L < cur_L - 1e-8:
                improvements[n] = danil_p
                gain = (cur_L - danil_L) / math.sqrt(n)
                print(f"   n={n:4d}: {cur_L:.10f} -> {danil_L:.10f} (gain: {gain:.10f})")
                count += 1
        print(f"   Found {count} improvements from Danil")
    except Exception as e:
        print(f"   Could not load Danil: {e}")
    
    # 2. Load PJ's packings
    print("\n3. Loading PJ's packings...")
    try:
        pj_path = BASE_DIR.parent / 'data' / 'external_packings' / 'three-square-packings-that-beat-the-records.ipynb'
        with open(pj_path) as f:
            nb = json.load(f)
        scope = {}
        exec(''.join(nb['cells'][3]['source']), scope)
        count = 0
        for n, coords in scope['PACKINGS'].items():
            pj_p = np.array(coords, float)
            cur_L = packing_geometry.side(cur[n])
            pj_L = packing_geometry.side(pj_p)
            if pj_L < cur_L - 1e-8:
                if n not in improvements or pj_L < packing_geometry.side(improvements[n]):
                    improvements[n] = pj_p
                    gain = (cur_L - pj_L) / math.sqrt(n)
                    print(f"   n={n:4d}: {cur_L:.10f} -> {pj_L:.10f} (gain: {gain:.10f})")
                    count += 1
        print(f"   Found {count} improvements from PJ")
    except Exception as e:
        print(f"   Could not load PJ: {e}")
    
    # 3. Load Aleksandr's candidate
    print("\n4. Loading Aleksandr's candidates...")
    try:
        alex_path = BASE_DIR.parent / 'data' / 'external_packings' / 'kaggle_public_candidate_20261102.csv'
        df_cand = pd.read_csv(alex_path)
        count = 0
        for n, g in df_cand.groupby('n'):
            n = int(n)
            cand_p = g.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
            cur_L = packing_geometry.side(cur[n])
            cand_L = packing_geometry.side(cand_p)
            if cand_L < cur_L - 1e-8:
                if n not in improvements or cand_L < packing_geometry.side(improvements[n]):
                    improvements[n] = cand_p
                    gain = (cur_L - cand_L) / math.sqrt(n)
                    print(f"   n={n:4d}: {cur_L:.10f} -> {cand_L:.10f} (gain: {gain:.10f})")
                    count += 1
        print(f"   Found {count} improvements from Aleksandr")
    except Exception as e:
        print(f"   Could not load Aleksandr: {e}")
    
    # Calculate improvements
    print("\n" + "="*80)
    print(f"TOTAL IMPROVEMENTS FOUND: {len(improvements)}")
    
    if improvements:
        total_gain = sum((packing_geometry.side(cur[n]) - packing_geometry.side(improvements[n])) / math.sqrt(n) 
                        for n in improvements)
        new_score = baseline_score - total_gain
        
        print(f"Baseline score:  {baseline_score:.10f}")
        print(f"Total gain:     -{total_gain:.10f}")
        print(f"New score:       {new_score:.10f}")
        print(f"Improvement:    -{total_gain:.10f} ({-total_gain/baseline_score*100:.3f}%)")
        
        # Create merged submission
        print("\n5. Creating new submission...")
        import csv
        
        output_dir = BASE_DIR.parent / 'output'
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f'submission_simple_{new_score:.6f}.csv'
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
            row_id = 0
            for n in range(1, 1001):
                p = improvements[n] if n in improvements else cur[n]
                for sid in range(len(p)):
                    writer.writerow([row_id, n, sid, 
                                   repr(float(p[sid, 0])), 
                                   repr(float(p[sid, 1])), 
                                   repr(float(p[sid, 2]))])
                    row_id += 1
        
        print(f"   Saved to: {output_file}")
        print(f"   Total rows: {row_id} (expected: 500500)")
        
        # Verify
        df_check = pd.read_csv(output_file)
        assert len(df_check) == 500500, f"Row count mismatch: {len(df_check)}"
        assert df_check.isna().sum().sum() == 0, "Contains NaN values"
        print("   ✓ Verification passed")
        
        # Show top improvements
        print("\n6. Top 20 improvements:")
        imp_list = [(n, (packing_geometry.side(cur[n]) - packing_geometry.side(improvements[n])) / math.sqrt(n)) 
                    for n in improvements]
        imp_list.sort(key=lambda x: x[1], reverse=True)
        for i, (n, gain) in enumerate(imp_list[:20], 1):
            cur_L = packing_geometry.side(cur[n])
            new_L = packing_geometry.side(improvements[n])
            print(f"   {i:2d}. n={n:4d}: {cur_L:.10f} -> {new_L:.10f} (gain: {gain:.10f})")
        
        print("\n" + "="*80)
        print(f"SUCCESS! New submission ready: {output_file.name}")
        print(f"Location: {output_file}")
        print(f"Upload this file to Kaggle to improve your score!")
        print("="*80)
    else:
        print("No improvements found - baseline is already optimal!")


if __name__ == '__main__':
    main()
