"""Download the public packing sources that appeared after the last sync, each into its own empty directory.

Downloads are untrusted data: nothing here is executed, and the merge step reads only CSV coordinates.

    .venv/bin/python -u src/tools/harvest_1106.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEST = ROOT / "data" / "harvest_1106"

DATASETS = [
    "prvsiyan/squares-verified-best-of-1105",
    "samanyu1808/sis-final-packings",
    "cshara/squares-in-squares-current-best",
    "shzgong/squares-in-squares-source-tracked-index",
    "ruoxuanzhuang/squares-in-squares-two-fault-dp-packings",
    "lucifer19/think-select-reclose-v13-certified-inputs",
    "mdmuqtadirfuad/sis-certified-portfolio",
    "az05192000gmailcom/squares-in-squares-stretched-packings",
    "az05192000gmailcom/squares-in-squares-l-band-packings",
    "kmmmvs/squares-in-squares-private-packings",
]

KERNELS = [
    "gfonsecabr/a-packing-of-109-squares-that-beats-gobel-s",
    "malyshevdanil/squares-in-squares-living-atlas-of-tight-packings",
    "alexchilton/fault-line-dp-basin-hopping-lb-22-2620",
    "sigmaborov/squares-in-squares-certified-contact-polish",
    "prvsiyan/a-square-deal-research-to-verified-packings",
    "saamhm/lb-22-257046-auto-optimizer-packing-unit-squares",
    "pramonoutomo/sis-best-packings-22-2498853780-kaggle-verified",
]


def run(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "")[-400:] + (p.stderr or "")[-400:], time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT", time.time() - t0


def fetch(kind: str, ref: str, timeout: float = 900.0):
    slug = ref.replace("/", "__")
    out = DEST / kind / slug
    if out.exists() and any(out.rglob("*.csv")):
        print(f"[skip] {ref} already has CSVs", flush=True)
        return
    out.mkdir(parents=True, exist_ok=True)
    if kind == "datasets":
        cmd = ["kaggle", "datasets", "download", "-d", ref, "-p", str(out), "--unzip", "--force"]
    else:
        cmd = ["kaggle", "kernels", "output", ref, "-p", str(out), "--force"]
    rc, msg, dt = run(cmd, timeout)
    csvs = list(out.rglob("*.csv"))
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"[{'ok' if rc == 0 else 'FAIL rc=' + str(rc)}] {ref}: {len(csvs)} csv, {size:.1f} MB, {dt:.0f}s",
          flush=True)
    if rc != 0:
        print(f"    {msg.strip()[:300]}", flush=True)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for ref in DATASETS:
        fetch("datasets", ref)
    for ref in KERNELS:
        fetch("kernels", ref)
    csvs = list(DEST.rglob("*.csv"))
    print(f"\nharvest complete: {len(csvs)} CSV files under {DEST}", flush=True)


if __name__ == "__main__":
    main()
