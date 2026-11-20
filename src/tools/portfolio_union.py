"""Select whole packings and preserve inherited decimal coordinate strings.

Coordinates are never averaged. Grid fallback is retained for omitted puzzles.
Certification of the resulting decimal CSV is a separate mandatory step.
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from packing_geometry import grid, load_bank, repair, side, total_score


def build_portfolio(source_paths, leader_name, output_path, patch_path=None):
    banks = {name: load_bank(path) for name, path in source_paths.items()}
    chosen = {}
    selected_sources = {}
    raw_groups = {}
    for name, path in source_paths.items():
        raw_groups[name] = {}
        with open(path, newline="") as stream:
            for row in csv.DictReader(stream):
                count = int(row["n"])
                raw_groups[name].setdefault(count, []).append(
                    [row[key] for key in ("square_id", "x", "y", "angle")]
                )
    for count in range(1, 1001):
        source = min(banks, key=lambda name: side(banks[name][count]))
        chosen[count] = banks[source][count]
        selected_sources[count] = source
    donor_sides = {count: side(packing) for count, packing in chosen.items()}
    patches = {}
    if patch_path is not None:
        with np.load(patch_path) as archive:
            for key in archive.files:
                count = int(key)
                candidate = repair(archive[key], clearance=2e-9)
                if (
                    candidate is not None
                    and (side(chosen[count]) - side(candidate)) / math.sqrt(count)
                    > 1e-8
                ):
                    chosen[count] = candidate
                    selected_sources[count] = "additional_cpu"
                    patches[count] = candidate
    rows = 0
    changes = []
    provenance = []
    with Path(output_path).open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "n", "square_id", "x", "y", "angle"])
        for count in range(1, 1001):
            source = selected_sources[count]
            if side(chosen[count]) >= math.ceil(math.sqrt(count)) - 1e-7:
                chosen[count] = grid(count)
                group = []
                source = "official_grid_fallback"
            elif source == "additional_cpu":
                group = [
                    [index, *[format(value, ".17g") for value in square]]
                    for index, square in enumerate(patches[count])
                ]
            else:
                group = raw_groups[source].get(count, [])
            for row in group:
                writer.writerow([rows, count, *row])
                rows += 1
            before = side(banks[leader_name][count])
            after = side(chosen[count])
            gain = (before - after) / math.sqrt(count)
            record = {
                "n": count,
                "source": source,
                "before": before,
                "after": after,
                "gain": gain,
                "donor_side": donor_sides[count],
                "cpu_increment": max(
                    0, (donor_sides[count] - after) / math.sqrt(count)
                ),
            }
            provenance.append(record)
            if gain > 1e-10:
                changes.append(record)
    summary = {
        "leader_score": total_score(banks[leader_name]),
        "source_scores": {name: total_score(bank) for name, bank in banks.items()},
        "score": total_score(chosen),
        "changes": changes,
        "provenance": provenance,
        "rows": rows,
        "sha256": hashlib.sha256(Path(output_path).read_bytes()).hexdigest(),
    }
    return summary
