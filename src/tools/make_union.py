"""Build a precision-preserving per-puzzle-best union of all CSV sources.

Picks, for every n=1..1000, the source with the smallest bounding side and
keeps that source's original decimal coordinate strings (never averages, never
re-serializes CSV sources through float).  Writes the union submission plus a
provenance/summary JSON.

Run from the workspace root:
    python src/tools/make_union.py
"""

import json
import sys
from pathlib import Path

# Make sibling imports (packing_geometry, portfolio_union) resolvable.
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import portfolio_union  # noqa: E402

BASE = TOOLS.parent.parent  # workspace root

SOURCES = {
    "baseline": str(BASE / "data" / "submission_merged_22.253319.csv"),
    "aleksandr": str(BASE / "data" / "external_packings" / "kaggle_public_candidate_20261102.csv"),
    "notebook": str(BASE / "output" / "notebook_packings.csv"),
}


def main():
    out_csv = BASE / "output" / "submission_union.csv"
    summary = portfolio_union.build_portfolio(
        source_paths=SOURCES,
        leader_name="baseline",
        output_path=str(out_csv),
    )
    out_json = BASE / "output" / "union_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))

    # Report deltas.
    before = summary["leader_score"]
    after = summary["score"]
    changes = summary["changes"]
    print(f"leader (baseline) score: {before:.10f}")
    for name, sc in summary["source_scores"].items():
        print(f"  source {name:10s}: {sc:.10f}")
    print(f"union score:             {after:.10f}")
    print(f"gain vs baseline:         {before - after:.10f}")
    print(f"puzzles changed:          {len(changes)}")
    # Breakdown by source.
    by_src = {}
    for c in changes:
        by_src.setdefault(c["source"], 0)
        by_src[c["source"]] += 1
    for name, cnt in sorted(by_src.items()):
        print(f"  from {name}: {cnt} puzzles")
    print(f"\noutput: {out_csv}")
    print(f"summary: {out_json}")
    # Top gains.
    changes.sort(key=lambda c: c["gain"], reverse=True)
    print("\nTop 15 gains:")
    for c in changes[:15]:
        print(f"  n={c['n']:4d} {c['before']:.10f} -> {c['after']:.10f} "
              f"(gain {c['gain']:.10f}, src={c['source']})")


if __name__ == "__main__":
    main()
