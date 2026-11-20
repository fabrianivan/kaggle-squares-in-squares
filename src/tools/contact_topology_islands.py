"""Explore distinct contact topologies with bounded, graph-guided island moves."""

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "reference_sources"))

import official_metric as metric
import packing_geometry as pg
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish


def load_submission(path):
    frame = pd.read_csv(path, dtype=str)
    required = {"id", "n", "square_id", "x", "y", "angle"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} must contain columns {sorted(required)}")
    rows = {}
    packings = {}
    for n_text, group in frame.groupby("n", sort=False):
        n = int(n_text)
        group = group.sort_values("square_id", key=lambda column: pd.to_numeric(column))
        if len(group) != n or [int(v) for v in group["square_id"]] != list(range(n)):
            raise ValueError(f"Invalid square rows for n={n} in {path}")
        rows[n] = group.to_dict("records")
        packings[n] = group[["x", "y", "angle"]].astype(float).to_numpy()
    if set(packings) != set(range(1, 1001)):
        raise ValueError(f"{path} must contain all puzzles n=1..1000")
    return frame, rows, packings


def contact_edges(p, tolerance=2e-5):
    pairs, projections, support = pg.pair_data(p, radius=1.6)
    if not len(pairs):
        return set()
    gaps = np.abs(projections).max(axis=1) - support
    return {tuple(map(int, pair)) for pair in pairs[gaps <= tolerance]}


def graph_signature(p):
    edges = contact_edges(p)
    return hashlib.blake2b(
        repr(sorted(edges)).encode("ascii"), digest_size=12
    ).hexdigest(), edges


def choose_cluster(p, edges, rng):
    n = len(p)
    adjacency = [[] for _ in range(n)]
    for i, j in edges:
        adjacency[i].append(j)
        adjacency[j].append(i)
    if not edges:
        return np.array([], dtype=int)

    degree = np.fromiter((len(a) for a in adjacency), dtype=int, count=n)
    eligible = np.flatnonzero(degree <= np.quantile(degree, 0.4))
    start = int(rng.choice(eligible if len(eligible) else np.arange(n)))
    target = int(rng.integers(3, min(15, n) + 1))
    cluster = [start]
    included = {start}
    frontier = set(adjacency[start])
    while frontier and len(cluster) < target:
        nodes = list(frontier)
        node = min(nodes, key=lambda k: (len(adjacency[k]), rng.random()))
        frontier.remove(node)
        if node in included:
            continue
        included.add(node)
        cluster.append(node)
        frontier.update(k for k in adjacency[node] if k not in included)
    if len(cluster) < 2:
        return np.array([], dtype=int)
    return np.asarray(cluster, dtype=int)


def jaccard_distance(a, b):
    union = a | b
    return 0.0 if not union else 1.0 - len(a & b) / len(union)


def make_rows(n, p):
    return [
        {
            "id": str(i),
            "n": str(n),
            "square_id": str(i),
            "x": format(float(x), ".17g"),
            "y": format(float(y), ".17g"),
            "angle": format(float(angle), ".17g"),
        }
        for i, (x, y, angle) in enumerate(p)
    ]


def certify(n, p):
    p = pg.repair(p, clearance=2e-9)
    if p is None:
        return None
    rows = make_rows(n, p)
    result = metric.evaluate_single_puzzle(n, rows)
    if result[3] != "ok" or result[2] is None:
        return None
    return p, float(result[2]), rows


def load_archive(path, targets):
    if not path.exists():
        return {}
    candidates = {n: [] for n in targets}
    with np.load(path, allow_pickle=False) as stored:
        for key in stored.files:
            try:
                n = int(key.split("_", 1)[0])
            except ValueError:
                continue
            if n in candidates:
                p = np.asarray(stored[key], dtype=float)
                if p.shape == (n, 3) and np.isfinite(p).all():
                    candidates[n].append(p.copy())
    return candidates


def save_archive(path, archive_by_n):
    stored = {}
    if path.exists():
        with np.load(path, allow_pickle=False) as previous:
            stored = {key: previous[key].copy() for key in previous.files}
    for n, entries in archive_by_n.items():
        stored = {
            key: value
            for key, value in stored.items()
            if not key.startswith(f"{n}_")
        }
        for entry in entries:
            stored[f"{n}_{entry['signature']}"] = entry["packing"]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **stored)


def archive_candidate(archive, p, side, rows):
    signature, edges = graph_signature(p)
    if any(entry["signature"] == signature for entry in archive):
        return False
    if any(
        jaccard_distance(edges, entry["edges"]) < 0.015
        and abs(side - entry["side"]) < 0.01
        for entry in archive
    ):
        return False
    archive.append(
        {"packing": p, "side": side, "rows": rows, "signature": signature, "edges": edges}
    )
    archive.sort(key=lambda entry: entry["side"])
    best_side = archive[0]["side"]
    archive[:] = [
        entry for entry in archive[:6] if entry["side"] <= best_side + 0.025
    ]
    return True


def propose(p, seed, amplitude):
    rng = np.random.default_rng(seed)
    _, edges = graph_signature(p)
    cluster = choose_cluster(p, edges, rng)
    if len(cluster) < 2:
        return None
    q = p.copy()
    pivot = q[cluster, :2].mean(axis=0)
    angle = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.01, 0.09))
    c, s = math.cos(angle), math.sin(angle)
    rotation = np.array([[c, -s], [s, c]])
    q[cluster, :2] = (q[cluster, :2] - pivot) @ rotation.T + pivot
    q[cluster, :2] += rng.normal(0.0, amplitude, size=2)
    q[cluster, 2] += angle
    return q


def optimize_target(n, base, seconds, seed, archived=()):
    start = time.monotonic()
    best = base.copy()
    best_side = pg.side(base)
    archive = []
    initial = certify(n, base)
    if initial is None:
        raise ValueError(f"Baseline packing n={n} failed official certification")
    archive_candidate(archive, initial[0], initial[1], initial[2])
    for candidate in archived:
        certified = certify(n, candidate)
        if certified is not None:
            archive_candidate(archive, *certified)
    history = []
    attempts = 0
    stats = {
        "reclosed_below_parent": 0,
        "post_polish_near_best": 0,
        "officially_certified": 0,
        "novel_topologies": 0,
    }
    rng = random.Random(seed)

    while time.monotonic() - start < seconds:
        parent = rng.choice(archive)
        amplitude = rng.choice([0.004, 0.008, 0.015, 0.03, 0.06])
        proposal = propose(parent["packing"], seed + attempts * 104729, amplitude)
        attempts += 1
        if proposal is None:
            continue

        trial, _, _ = reclose(
            proposal,
            seed=seed + attempts,
            trust=max(0.04, amplitude * 2.5),
            tie=0.08,
            rounds=3,
            seconds=min(3.0, max(0.5, seconds - (time.monotonic() - start))),
        )
        if pg.side(trial) < parent["side"] - 1e-9:
            stats["reclosed_below_parent"] += 1
        if pg.side(trial) >= parent["side"] + 0.01:
            continue

        trial, _, _ = polish(
            trial,
            seed=seed + attempts * 17,
            rounds=18,
            max_seconds=min(2.5, max(0.5, seconds - (time.monotonic() - start))),
            trust_start=max(0.008, min(0.025, amplitude)),
        )
        trial = pg.repair(trial, clearance=2e-9)
        if trial is None:
            continue
        trial_side = pg.side(trial)
        if trial_side > best_side + 0.025:
            continue
        stats["post_polish_near_best"] += 1

        certified = certify(n, trial)
        if certified is None:
            continue
        stats["officially_certified"] += 1
        candidate, certified_side, rows = certified
        novel = archive_candidate(archive, candidate, certified_side, rows)
        if novel:
            stats["novel_topologies"] += 1
        if certified_side < best_side - 1e-9:
            old_side = best_side
            best, best_side = candidate, certified_side
            history.append(
                {
                    "n": n,
                    "before": old_side,
                    "after": best_side,
                    "gain": (old_side - best_side) / math.sqrt(n),
                    "attempt": attempts,
                    "new_topology": novel,
                }
            )
            print(json.dumps(history[-1]), flush=True)

    return best, best_side, history, attempts, stats, archive, time.monotonic() - start


def write_submission(path, rows_by_n, best_packings):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["id", "n", "square_id", "x", "y", "angle"]
    index = 0
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for n in range(1, 1001):
            rows = make_rows(n, best_packings[n]) if n in best_packings else rows_by_n[n]
            for row in rows:
                writer.writerow(
                    {
                        "id": str(index),
                        "n": str(n),
                        "square_id": row["square_id"],
                        "x": row["x"],
                        "y": row["y"],
                        "angle": row["angle"],
                    }
                )
                index += 1
    if index != 500500:
        raise ValueError(f"Expected 500500 output rows, wrote {index}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output" / "submission_final.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "submission_topology.csv")
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "output" / "contact_topology_archive.npz",
        help="Persistent NPZ archive of officially certified contact topologies",
    )
    parser.add_argument("--targets", nargs="*", type=int, default=[86, 105, 127, 147, 175])
    parser.add_argument("--seconds", type=float, default=120.0, help="Total wall-time budget")
    parser.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args()
    if args.seconds <= 0:
        raise ValueError("--seconds must be positive")

    _, rows_by_n, packings = load_submission(args.input)
    before_score = sum(pg.side(packings[n]) / math.sqrt(n) - 1 for n in range(1, 1001))
    best_packings = {}
    history = []
    archive_by_n = load_archive(args.archive, args.targets)
    deadline = time.monotonic() + args.seconds

    for index, n in enumerate(args.targets):
        if n not in packings:
            raise ValueError(f"Target n={n} is not in the submission")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        share = remaining / (len(args.targets) - index)
        best, best_side, records, attempts, stats, archive, elapsed = optimize_target(
            n, packings[n], share, args.seed + n, archive_by_n.get(n, ())
        )
        archive_by_n[n] = archive
        save_archive(args.archive, archive_by_n)
        history.extend(records)
        if best_side < pg.side(packings[n]) - 1e-9:
            best_packings[n] = best
        print(
            json.dumps(
                {
                    "n": n,
                    "attempts": attempts,
                    "seconds": elapsed,
                    "search_stats": stats,
                    "certified_gain": sum(item["gain"] for item in records),
                    "archive": "contact-topology island hopping",
                }
            ),
            flush=True,
        )

    if not best_packings:
        print(f"No certified improvements; baseline score remains {before_score:.12f}")
        return

    write_submission(args.output, rows_by_n, best_packings)
    after_score = before_score - sum(
        (pg.side(packings[n]) - pg.side(best_packings[n])) / math.sqrt(n)
        for n in best_packings
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "improved_puzzles": sorted(best_packings),
                "baseline_score": before_score,
                "estimated_score": after_score,
                "history": history,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
