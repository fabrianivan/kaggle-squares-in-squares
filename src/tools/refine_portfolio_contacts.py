"""Small CPU-only control experiment on complementary public packings."""

import os

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import numpy as np
from packing_geometry import load_bank, side, repair, save_bank
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish


def trial(job):
    count, packing, seed = job
    candidate, trace, elapsed = reclose(
        packing, seed=seed, trust=0.35, tie=0.12, rounds=10, seconds=2
    )
    candidate, _, _ = polish(
        candidate, seed=seed, rounds=15, max_seconds=2, trust_start=0.012
    )
    candidate = repair(candidate, clearance=2e-9)
    gain = (
        (side(packing) - side(candidate)) / math.sqrt(count)
        if candidate is not None
        else 0
    )
    accepted = gain > 1e-8
    receipt = {
        "n": count,
        "seed": seed,
        "kind": "contact_reclosure",
        "gain": gain if accepted else 0,
        "accepted": accepted,
        "seconds": elapsed,
    }
    return candidate if accepted else None, receipt


def main():
    Path("artifacts").mkdir(exist_ok=True)
    scan = json.load(open("research_union_scan.json"))
    banks = {name: load_bank(path) for name, path in scan["source_paths"].items()}
    targets = [
        row["n"] for row in sorted(scan["changes"], key=lambda row: -row["gain"])[:16]
    ]
    jobs = [
        (count, banks[scan["winners"][str(count)]][count], 311000 + index)
        for index, count in enumerate(targets)
    ]
    patches = {}
    history = []
    with ProcessPoolExecutor(max_workers=2) as executor:
        for candidate, receipt in executor.map(trial, jobs):
            history.append(receipt)
            if candidate is not None:
                patches[receipt["n"]] = candidate
            print(receipt, flush=True)
    save_bank("artifacts/round31_cpu_packings.npz", patches)
    Path("artifacts/round31_cpu_history.json").write_text(json.dumps(history, indent=2))


if __name__ == "__main__":
    main()
