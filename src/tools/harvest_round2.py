"""Second harvest pass: the sources round 1 missed, plus a retry of the big bundles with a longer deadline.

Downloads are untrusted data: nothing here is executed, and the merge step reads only CSV coordinates.

    .venv/bin/python -u src/tools/harvest_round2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src" / "tools"))

from harvest_1106 import DEST, fetch  # noqa: E402

# (ref, timeout seconds) -- the big bundles need far more than the default
DATASETS = [
    ("lostdecimal27/squares-in-squares-bank", 900),
    ("dariushafshar/squares-in-squares-certified-packings", 1200),
    ("kmmmvs/squares-in-squares-best-packings", 900),
    ("busyaprime/squares-in-squares-fq-quenched-packings", 600),
    ("kmmmvs/squares-in-squares-private-packings", 3000),
    ("lightningv08/squares-in-squares-layout-atlas", 3000),
]

KERNELS = [
    ("alexchilton/fault-line-dp-basin-hopping-lb-22-2620", 900),
    ("sigmaborov/squares-in-squares-certified-contact-polish", 900),
    ("prvsiyan/a-square-deal-research-to-verified-packings", 900),
    ("saamhm/lb-22-257046-auto-optimizer-packing-unit-squares", 900),
    ("pramonoutomo/sis-best-packings-22-2498853780-kaggle-verified", 900),
    ("malyshevdanil/squares-in-squares-living-atlas-of-tight-packings", 1200),
]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for ref, to in DATASETS:
        fetch("datasets", ref, timeout=to)
    for ref, to in KERNELS:
        fetch("kernels", ref, timeout=to)
    print(f"\nround 2 complete: {len(list(DEST.rglob('*.csv')))} CSV files under {DEST}", flush=True)


if __name__ == "__main__":
    main()
