"""Download the public packing sources published Nov 6-9, 2026 (UTC), each into its own empty directory.
Downloads are untrusted data: nothing here is executed, and the merge step reads only CSV coordinates.
    .venv/bin/python -u src/tools/harvest_nov_6_9.py
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
DEST = ROOT / "data" / "harvest_nov_6_9"
DATASETS = [
    "alexchilton/squares-in-squares-starter-kit",
    "avazaku/squares-contact-lp-cusp-bounds-465-998",
    "lucifer19/think-select-reclose-v43-certified-snapshot",
    "lucifer19/think-select-reclose-v42-certified-snapshot",
    "lucifer19/think-select-reclose-v41-certified-snapshot",
    "lucifer19/think-select-reclose-v39-certified-snapshot",
    "prvsiyan/squares-verified-best-of-1105",
    "busyaprime/squares-in-squares-fq-quenched-packings",
    "kmmmvs/squares-search-engine",
    "krisdreemurr/squares-in-squares-big-universe-sides",
    "pablodiegoo/unit-square-packing-certified-bounds",
    # New sources discovered Nov 6-9 2026
    "mdmuqtadirfuad/sis-certified-portfolio",
    "samanyu1808/sis-final-packings",
    "vijaikm/squares-in-squares-champion-v26-solution",
    "penguin069/squares-in-squares-certified-portfolio-data",
    "lucifer19/think-select-reclose-v13-certified-inputs",
    "kmmmvs/squares-in-squares-private-packings",
]
KERNELS = [
    "jazivxt/boxed-in-sub",
    "kmmmvs/squares-public-merge-daily",
    "kirilltym/22-2162-cpu-cuda-mps-eda-correction-union",
    "inversion/squares-in-squares-per-puzzle-leaderboard",
    "alexchilton/squares-101-the-starter-kit-9-000-downloads",
    "nilanjansaha123/squares-gpu-seam-dp-soft-rigid-highs",
    "seshurajup/1000-puzzles-ensemble-lb-22-2231",
    "avazaku/contact-lp-cusp-bounds",
    "lucifer19/think-select-reclose",
    # New kernels discovered Nov 6-9 2026
    "malyshevdanil/squares-in-squares-living-atlas-of-tight-packings",
    "alexchilton/fault-line-dp-basin-hopping-lb-22-2620",
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
