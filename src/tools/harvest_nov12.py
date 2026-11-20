"""Download public packing sources published up to Nov 12, 2026 (UTC).
Downloads are untrusted data: nothing here is executed.
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEST = ROOT / "data" / "harvest_nov12"

DATASETS = [
    "cshara/squares-in-squares-current-best",
    "prvsiyan/squares-verified-best-of-1105",
    "lucifer19/think-select-reclose-v48-certified-snapshot",
    "lucifer19/think-select-reclose-v47-certified-snapshot",
    "lucifer19/think-select-reclose-v46-certified-snapshot",
    "alexchilton/squares-in-squares-starter-kit",
    "busyaprime/squares-in-squares-fq-quenched-packings",
    "mdmuqtadirfuad/sis-certified-portfolio",
    "samanyu1808/sis-final-packings",
    "jonathan1506/joegun-squares-packings",
    "avazaku/squares-contact-lp-cusp-bounds-465-998",
    "pablodiegoo/unit-square-packing-certified-bounds",
]

KERNELS = [
    "jazivxt/boxed-in-sub",
    "malyshevdanil/squares-in-squares-living-atlas-of-tight-packings",
    "alexchilton/squares-101-the-starter-kit-10-500-downloads",
    "prvsiyan/a-square-deal-research-to-verified-packings",
    "pablodiegoo/squares-in-squares-starter-notebook",
    "alexchilton/fault-line-dp-basin-hopping-lb-22-2620",
    "grennwolf/squares-in-squares-top-1-santa-2025",
    "lucifer19/think-select-reclose",
    "nilanjansaha123/squares-gpu-seam-dp-soft-rigid-highs",
    "kmmmvs/squares-public-merge-daily",
    "penguin069/squares-boxed-public-certified-union",
    "busyaprime/lb-22-1945500-sacred-geometry-of-1000-squares",
    "seshurajup/1000-puzzles-ensemble-lb-22-2095",
    "jonathan1506/joegun-22-2004-stretch-fault-line-dp-fq-quench",
    "sigmaborov/squares-in-squares-certified-contact-polish",
    "areebbb/s6e11-three-ladders-two-steps-lb-0-95347",
]

def run(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "")[-300:] + (p.stderr or "")[-300:], time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT", time.time() - t0

def fetch(kind: str, ref: str, timeout: float = 300.0):
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
    if rc != 0 and not csvs:
        print(f"    {msg.strip()[:200]}", flush=True)

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(DATASETS)} datasets and {len(KERNELS)} kernels into {DEST}...", flush=True)
    for ref in DATASETS:
        fetch("datasets", ref)
    for ref in KERNELS:
        fetch("kernels", ref)
    csvs = list(DEST.rglob("*.csv"))
    print(f"\nHarvest complete: {len(csvs)} CSV files under {DEST}", flush=True)

if __name__ == "__main__":
    main()
