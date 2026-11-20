"""Find the best packing for every puzzle across all local candidate CSVs.

Usage:
    python src/tools/scan_all_sources.py --baseline output/submission_final.csv \
        --out output/source_scan.json

Only whole, feasible-looking `n` groups are considered (exactly n rows).  The
float side length is a fast pre-filter; the caller must still certify selected
replacements with the official interval metric.
"""

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packing_geometry as pg

ROOT = Path(__file__).resolve().parents[2]
SEARCH_DIRS = [
    ROOT / "data" / "new_sources",
    ROOT / "data" / "external_packings",
    ROOT / "output",
]
HEADERS = (
    ["id", "n", "square_id", "x", "y", "angle"],
    ["n", "square_id", "x", "y", "angle"],
)


def iter_csvs(dirs):
    seen = set()
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.csv")):
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            if digest in seen:
                continue
            seen.add(digest)
            yield path


def read_packings(path):
    groups = {}
    try:
        with path.open(newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader, None)
            if not header:
                return None
            if header[:6] == HEADERS[0]:
                columns = (1, 3, 4, 5)
            elif header[:5] == HEADERS[1]:
                columns = (0, 2, 3, 4)
            else:
                return None
            for row in reader:
                if len(row) <= max(columns):
                    return None
                try:
                    n = int(row[columns[0]])
                    x = float(row[columns[1]])
                    y = float(row[columns[2]])
                    angle = float(row[columns[3]])
                except ValueError:
                    return None
                if not (abs(x) <= 1e4 and abs(y) <= 1e4 and abs(angle) <= 100):
                    return None
                groups.setdefault(n, []).append(
                    (row[columns[1]], row[columns[2]], row[columns[3]])
                )
    except (OSError, UnicodeDecodeError):
        return None
    return groups


def sides_from_groups(groups):
    sides = {}
    for n, rows in groups.items():
        if not 1 <= n <= 1000 or len(rows) != n:
            continue
        arr = np.array([[float(x), float(y), float(a)] for x, y, a in rows])
        # Bounding-box comparisons are only a pre-filter. Reject overlapping
        # candidates here so invalid optimizer artifacts cannot look optimal.
        if pg.min_gap(arr) < -1e-9:
            continue
        sides[n] = pg.side(arr)
    return sides


def load_baseline(path):
    path = Path(path)
    groups = read_packings(path)
    if groups is None:
        raise SystemExit(f"cannot parse baseline {path}")
    return groups, sides_from_groups(groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=str(ROOT / "output" / "submission_final.csv"))
    parser.add_argument("--out", default=str(ROOT / "output" / "source_scan.json"))
    parser.add_argument("--min-gain", type=float, default=0.0)
    args = parser.parse_args()

    base_groups, base_sides = load_baseline(args.baseline)
    print(f"baseline: {sum(base_sides[n] / math.sqrt(n) - 1 for n in range(1, 1001)):.12f}")

    best = {n: (base_sides[n], str(Path(args.baseline).resolve()), None) for n in base_sides}
    scanned = 0
    for path in iter_csvs(SEARCH_DIRS):
        groups = read_packings(path)
        if groups is None:
            continue
        scanned += 1
        sides = sides_from_groups(groups)
        for n, side in sides.items():
            if side < best[n][0] - 1e-12:
                best[n] = (side, str(path.resolve()), groups[n])
        if scanned % 20 == 0:
            print(f"  scanned {scanned} files...", flush=True)

    improvements = []
    total_gain = 0.0
    for n in range(1, 1001):
        side, source, rows = best[n]
        gain = (base_sides[n] - side) / math.sqrt(n)
        if gain > args.min_gain:
            total_gain += gain
            improvements.append(
                {"n": n, "before": base_sides[n], "after": side, "gain": gain, "source": source}
            )

    payload = {
        "baseline": str(Path(args.baseline).resolve()),
        "baseline_score": sum(base_sides[n] / math.sqrt(n) - 1 for n in range(1, 1001)),
        "scanned_files": scanned,
        "improved_puzzles": len(improvements),
        "total_gain": total_gain,
        "projected_score": sum(side / math.sqrt(n) - 1 for n, (side, _, _) in best.items()),
        "improvements": improvements,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(json.dumps({k: v for k, v in payload.items() if k != "improvements"}, indent=2))
    for item in sorted(improvements, key=lambda item: -item["gain"])[:20]:
        print(
            f"  n={item['n']:4d} {item['before']:.9f} -> {item['after']:.9f} "
            f"gain {item['gain']:.2e} {Path(item['source']).name}"
        )


if __name__ == "__main__":
    main()
