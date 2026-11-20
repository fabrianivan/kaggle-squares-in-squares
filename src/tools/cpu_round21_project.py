"""Restore nearly feasible CPU proposals with an exact fixed-angle LP.
Uses trust-region contact constraints from cpu_axis_reclosure, allows restoration
above the proposal's side while requiring a net gain over its original baseline.
"""

import math, numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
from packing_geometry import normalize, side, repair


def project(p, limit, trust=0.08, seconds=0.7):
    p = normalize(p)
    n = len(p)
    L = side(p)
    a = p[:, 2]
    c = np.cos(a)
    s = np.sin(a)
    h = (abs(c) + abs(s)) / 2
    pairs = cKDTree(p[:, :2]).query_pairs(
        math.sqrt(2) + 2 * math.sqrt(2) * trust + 1e-4, output_type="ndarray"
    )
    i, j = pairs.T
    d = p[j, :2] - p[i, :2]
    ux = np.column_stack((c[i], -s[i], c[j], -s[j]))
    uy = np.column_stack((s[i], c[i], s[j], c[j]))
    pr = d[:, 0, None] * ux + d[:, 1, None] * uy
    k = abs(pr).argmax(1)
    rr = np.arange(len(i))
    sg = np.where(pr[rr, k] >= 0, 1.0, -1.0)
    vx = sg * ux[rr, k]
    vy = sg * uy[rr, k]
    rad = (1 + abs(np.cos(a[i] - a[j])) + abs(np.sin(a[i] - a[j]))) / 2
    cols = [np.column_stack((2 * i, 2 * i + 1, 2 * j, 2 * j + 1))]
    vals = [np.column_stack((vx, vy, -vx, -vy))]
    rhs = [abs(pr[rr, k]) - rad - 3e-9]
    rows = [np.repeat(rr, 4)]
    offset = len(i)
    ids = np.arange(n)
    for dim in [0, 1]:
        for upper in [False, True]:
            cols.append(np.column_stack((2 * ids + dim, np.full(n, 2 * n))))
            vals.append(
                np.tile([1.0 if upper else -1.0, -1.0 if upper else 0.0], (n, 1))
            )
            rhs.append(L - p[:, dim] - h if upper else p[:, dim] - h)
            rows.append(np.repeat(np.arange(offset, offset + n), 2))
            offset += n
    A = coo_matrix(
        (
            np.concatenate([v.ravel() for v in vals]),
            (np.concatenate(rows), np.concatenate([v.ravel() for v in cols])),
        ),
        shape=(offset, 2 * n + 1),
    ).tocsr()
    obj = np.zeros(2 * n + 1)
    obj[-1] = 1.0
    bound = min(trust, limit - L)
    if bound < -trust:
        return None
    fit = linprog(
        obj,
        A_ub=A,
        b_ub=np.concatenate(rhs),
        bounds=[(-trust, trust)] * (2 * n) + [(-trust, bound)],
        method="highs",
        options={
            "time_limit": seconds,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    if not fit.success:
        return None
    q = p.copy()
    q[:, :2] += fit.x[: 2 * n].reshape(n, 2)
    q = repair(q, clearance=2e-9)
    return q if q is not None and side(q) < limit else None
