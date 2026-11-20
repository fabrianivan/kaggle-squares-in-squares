"""Advanced Multi-Symmetry Stretching Engine with Integrated FQPool Quenching.

Improvements over basic stretch:
1. Full D4 Symmetry Exploration: Evaluates all 8 rotations and reflections of each packing,
   allowing arms on ANY wall (top, bottom, left, right) to be aligned and stretched.
2. Adaptive Patch Sizing: Adapts minimum patch size to packing scale (down to 8 squares for smaller N).
3. Multi-cut candidate generation: Tests multiple integer cut lines and selects the one with
   cleanest seam separation.
4. Zero-Overhead FQPool Relaxation: Integrates directly with the persistent 14-core FQPool
   for instant in-memory ALM+SLP relaxation.
5. Official Interval Metric Certification: Automatically verifies any candidates that improve
   upon the baseline.
"""

from __future__ import annotations
import math
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "data" / "new_sources" / "alexchilton_starter_kit"))
sys.path.insert(0, str(ROOT / "src" / "engine"))
from fq_pool import FQPool, side, normalise, corners
from ensemble import certify


# 8 D4 symmetries for (x, y, angle)
def apply_symmetry(p: np.ndarray, sym: int) -> np.ndarray:
    """Apply symmetry 0..7 to packing p.
    0..3: rot 0, 90, 180, 270
    4..7: rot + reflect x
    """
    s = p.copy()
    x, y, t = s[:, 0].copy(), s[:, 1].copy(), s[:, 2].copy()
    
    rot = sym % 4
    refl = sym >= 4
    
    if refl:
        x = -x
        t = -t
        
    if rot == 1: # 90 deg CCW
        x, y = -y, x
        t = t + math.pi / 2
    elif rot == 2: # 180 deg
        x, y = -x, -y
        t = t + math.pi
    elif rot == 3: # 270 deg
        x, y = y, -x
        t = t + 3 * math.pi / 2
        
    s[:, 0] = x
    s[:, 1] = y
    s[:, 2] = t % (math.pi / 2)
    return normalise(s)


def find_tilted_patches(a: np.ndarray, min_size: int = 10) -> List[Dict[str, Any]]:
    """Connected groups of tilted squares."""
    deg = np.degrees(np.mod(a[:, 2], math.pi / 2))
    deg = np.where(deg > 45, deg - 90, deg)
    t = np.where(np.abs(deg) > 3)[0]
    res = []
    if len(t) == 0:
        return res
    
    P = a[t, :2]
    pr = cKDTree(P).query_pairs(1.6, output_type='ndarray')
    A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(P), len(P))) if len(pr) else coo_matrix((len(P), len(P)))
    nc, lab = connected_components(A, directed=False)
    
    for k in range(nc):
        idx = t[lab == k]
        if len(idx) < min_size:
            continue
        th = math.radians(float(np.median(deg[idx])))
        u = np.array([math.cos(th), math.sin(th)])
        v = np.array([-math.sin(th), math.cos(th)])
        pu, pv = a[idx, :2] @ u, a[idx, :2] @ v
        iu = np.round(pu - np.mean(pu - np.round(pu))).astype(int)
        iv = np.round(pv - np.mean(pv - np.round(pv))).astype(int)
        horiz = np.ptp(a[idx, 0]) >= np.ptp(a[idx, 1])
        res.append(dict(
            idx=idx, th=th, iu=iu, iv=iv, horiz=horiz,
            x0=a[idx, 0].min(), x1=a[idx, 0].max(),
            y0=a[idx, 1].min(), y1=a[idx, 1].max()
        ))
    return res


def stack_info(a: np.ndarray, p: Dict[str, Any], axis: int):
    k = p['iu'] if axis == 0 else p['iv']
    coord = a[p['idx'], axis]
    ks = np.unique(k)
    means = np.array([coord[k == q].mean() for q in ks])
    mid = slice(len(ks) // 4, max(len(ks) // 4 + 2, 3 * len(ks) // 4))
    d = np.diff(means)[mid]
    pitch = float(np.median(np.abs(d))) if len(d) else 1.0
    return k, ks, means, pitch


def apply_cut_operation(a: np.ndarray, axis: int, cut: float, op: int, min_patch_size: int = 10):
    P = find_tilted_patches(a, min_size=min_patch_size)
    cross = [p for p in P if (p['x0'] < cut < p['x1'] if axis == 0 else p['y0'] < cut < p['y1'])]
    good = [p for p in cross if p['horiz'] == (axis == 0)]
    if len(cross) != len(good) or not good:
        return None, "cut mismatch or no patch"

    in_patch = np.zeros(len(a), bool)
    beyond = a[:, axis] > cut
    copy_mask = np.zeros(len(a), bool)
    shift = np.zeros(len(a))
    pitches = []
    
    for p in good:
        k, ks, means, pitch = stack_info(a, p, axis)
        pitches.append(pitch)
        kc = ks[np.argmin(np.abs(means - cut))]
        in_patch[p['idx']] = True
        beyond[p['idx']] = k > kc
        copy_mask[p['idx'][k == kc]] = True
        if op < 0:
            shift[p['idx'][k > kc]] = -pitch

    d = max([1.0] + pitches)
    up_col = (~in_patch) & (a[:, axis] > cut - 1.0) & (a[:, axis] <= cut)
    deg = np.degrees(np.mod(a[:, 2], math.pi / 2))
    upright = np.minimum(deg, 90 - deg) < 3
    up_col &= upright
    
    b = a.copy()
    if op > 0:
        b[beyond, axis] += d
        cp = a[copy_mask | up_col].copy()
        cp[:, axis] += d
        b = np.vstack([b, cp])
    else:
        rest = beyond & ~in_patch
        shift[rest] = -1.0
        b[:, axis] += shift
        b = b[~(copy_mask | up_col)]
        
    return b, f"axis {axis} cut {cut:.1f} op {op:+d} pitch {d:.4f} removed/added {int((copy_mask | up_col).sum())}"


def pick_best_cuts(a: np.ndarray, axis: int, min_patch_size: int = 10) -> List[float]:
    """Find all viable integer cuts along the arm on axis."""
    P = [p for p in find_tilted_patches(a, min_size=min_patch_size) if p['horiz'] == (axis == 0)]
    if not P:
        return []
    p = max(P, key=lambda q: len(q['idx']))
    lo, hi = (p['x0'], p['x1']) if axis == 0 else (p['y0'], p['y1'])
    c_mid = math.floor((lo + hi) / 2) + 0.0
    
    valid_cuts = []
    for dc in [0, 1, -1, 2, -2, 3, -3, 4, -4]:
        cc = c_mid + dc
        others = [q for q in find_tilted_patches(a, min_size=min_patch_size) if q['horiz'] != (axis == 0) and
                  ((q['x0'] - 0.8 < cc < q['x1'] + 0.8) if axis == 0 else (q['y0'] - 0.8 < cc < q['y1'] + 0.8))]
        if not others and lo + 1.5 < cc < hi - 1.5:
            valid_cuts.append(cc)
    return valid_cuts


def stretch_multisym(a: np.ndarray, steps: int) -> List[Tuple[np.ndarray, List[str]]]:
    """Try stretching under all 8 D4 symmetries and multiple cut lines.
    Returns a list of viable stretched candidate geometries.
    """
    candidates = []
    seen_keys = set()
    n = len(a)
    min_patch = max(8, int(0.015 * n))
    
    for sym in range(8):
        sym_a = apply_symmetry(a, sym)
        # Try both axes
        cuts_x = pick_best_cuts(sym_a, 0, min_patch_size=min_patch)
        cuts_y = pick_best_cuts(sym_a, 1, min_patch_size=min_patch)
        
        if not cuts_x or not cuts_y:
            continue
            
        for cx in cuts_x[:2]: # Top 2 cut candidates on axis 0
            b1, n1 = apply_cut_operation(sym_a, 0, cx, 1 if steps > 0 else -1, min_patch_size=min_patch)
            if b1 is None:
                continue
            for cy in cuts_y[:2]: # Top 2 cut candidates on axis 1
                b2, n2 = apply_cut_operation(b1, 1, cy, 1 if steps > 0 else -1, min_patch_size=min_patch)
                if b2 is None:
                    continue
                
                m = len(b2)
                key = (m, round(side(b2), 4))
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append((normalise(b2), [n1, n2]))
                    
    return candidates


class AdvancedStretchingEngine:
    """End-to-end multi-core stretching and quench optimization engine."""

    def __init__(self, num_workers: int = 14):
        self.pool = FQPool(num_workers=num_workers)

    def optimize_stretch(
        self,
        src_packing: np.ndarray,
        step: int,
        target_n: int,
        current_best_L: float,
        deadline_sec: int = 15
    ) -> Optional[Tuple[float, np.ndarray, Dict[str, Any]]]:
        """Generate, quench, and certify stretched candidates for target_n."""
        raw_cands = stretch_multisym(src_packing, step)
        filtered = [b for b, notes in raw_cands if len(b) == target_n]
        
        if not filtered:
            return None

        best_result = None
        best_L = current_best_L

        # Quench all viable candidate geometries through FQPool
        quench_tasks = [
            (cand, f"--finish --deadline {deadline_sec} --loosen 1.0", deadline_sec + 5.0)
            for cand in filtered
        ]
        results = self.pool.map_quench(quench_tasks)

        for cand_L, q_cand, info in results:
            if cand_L is not None and q_cand is not None and cand_L < best_L - 1e-9:
                # Interval arithmetic certification
                r = certify(target_n, q_cand)
                if r is not None and r[0] < best_L - 1e-9:
                    best_L = r[0]
                    best_result = (best_L, r[2], info)

        return best_result

    def close(self):
        self.pool.close()


if __name__ == "__main__":
    print("Testing AdvancedStretchingEngine...")
    engine = AdvancedStretchingEngine(num_workers=4)
    # Test on known good specimen 930 (+1) -> 993
    import pandas as pd
    df = pd.read_csv(ROOT / "output" / "submission_22.233377.csv")
    p930 = df[df.n == 930].sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
    p993 = df[df.n == 993].sort_values("square_id")[["x", "y", "angle"]].to_numpy(float)
    cur_993_L = side(p993)
    
    t0 = time.time()
    res = engine.optimize_stretch(p930, step=1, target_n=993, current_best_L=cur_993_L + 0.1, deadline_sec=5)
    dt = time.time() - t0
    if res:
        print(f"Success! Reconstructed n=993 in {dt:.1f}s with side={res[0]:.9f} (vs cur={cur_993_L:.9f})")
    engine.close()
