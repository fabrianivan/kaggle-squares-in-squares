"""Recompute using an explicitly chosen tensor device; certify every accepted row.

The tensor proposal stage runs on cpu/cuda/mps. Exact LP polishing, decimal
serialization and the unchanged official metric run on CPU in every mode.
"""

import csv, json, math, os, subprocess, sys, tempfile
from pathlib import Path
from collections import defaultdict
import numpy as np
from packing_geometry import load_bank, side, repair, normalize
from portable_seam_search import seam_pressure, choose_device
from cpu_axis_reclosure import reclose
from cpu_contact_polish import polish


def fq_quench(sq, s0=None, loosen=1.001, kick=0.0005, seed=0, outer=60):
    fq_bin = os.environ.get("FQ_BIN") or str(
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "new_sources"
        / "alexchilton"
        / "evand"
        / "search"
        / "packer"
        / "target"
        / "release"
        / "fq"
    )
    if not os.path.exists(fq_bin):
        return None
    sq = normalize(sq)
    n = len(sq)
    if s0 is None:
        s0 = side(sq)
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.txt")
        out = os.path.join(d, "out.txt")
        with open(inp, "w") as f:
            f.write(f"{n} {s0:.17f}\n")
            for x, y, a in sq:
                f.write(f"{x:.17f} {y:.17f} {math.degrees(a):.15f}\n")
        cmd = [
            fq_bin,
            "quench",
            "--in",
            inp,
            "--out",
            out,
            "--loosen",
            str(loosen),
            "--kick",
            str(kick),
            "--seed",
            str(seed),
            "--outer",
            str(outer),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=40)
        except subprocess.TimeoutExpired:
            return None
        if not os.path.exists(out):
            return None
        rows = open(out).read().strip().split("\n")[1:]
    new_sq = np.array([[float(v) for v in r.split()] for r in rows if r.strip()])
    if len(new_sq) != n or not np.isfinite(new_sq).all():
        return None
    new_sq[:, 2] = np.radians(new_sq[:, 2])
    c = (new_sq[:, :2].min(0) + new_sq[:, :2].max(0)) / 2
    new_sq[:, :2] = c + (new_sq[:, :2] - c) * (1 + 1e-12)
    return new_sq


def run_experiment(
    input_csv, output_csv, backend="cpu", sizes=(801, 460), batch=6, steps=240, use_fq=True
):
    choose_device(backend)  # Fail explicitly; never silently switch devices.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "reference_sources"))
    import official_metric as metric

    bank = load_bank(input_csv)
    rows = defaultdict(list)
    with Path(input_csv).open(newline="") as f:
        for row in csv.DictReader(f):
            rows[int(row["n"])].append(row)
    history = []
    for n in sizes:
        if n not in rows:
            raise ValueError("Choose a submitted non-grid puzzle size.")
        before = metric._evaluate_puzzle_worker((n, rows[n]))
        assert before[3] == "ok"
        proposals, report = seam_pressure(
            bank[n], backend=backend, seed=99173 + n, batch=batch, steps=steps
        )
        q, _, _ = reclose(
            bank[n], seed=397 + n, rounds=6, seconds=3, trust=0.3, tie=0.1
        )
        proposals.append(q)

        if use_fq:
            for s_seed in [1, 2]:
                q_fq = fq_quench(bank[n], s0=side(bank[n]), loosen=1.001, kick=0.0005, seed=s_seed)
                if q_fq is not None:
                    proposals.append(q_fq)

        best_rows = rows[n]
        best_score = before[1]
        for q in sorted(proposals, key=side)[:5]:
            if side(q) > side(bank[n]) + 0.015:
                continue
            q, _, _ = polish(q, rounds=60, max_seconds=6, trust_start=0.015)
            # Use non-destructive clearance: 1e-12 relative dilation around center
            q = normalize(q)
            c = (q[:, :2].min(0) + q[:, :2].max(0)) / 2
            q[:, :2] = c + (q[:, :2] - c) * (1 + 1e-12)

            candidate = [
                dict(
                    id=str(sid),
                    n=str(n),
                    square_id=str(sid),
                    x=format(x, ".17g"),
                    y=format(y, ".17g"),
                    angle=format(a, ".17g"),
                )
                for sid, (x, y, a) in enumerate(q)
            ]
            result = metric._evaluate_puzzle_worker((n, candidate))
            if result[3] == "ok" and result[1] < best_score - 1e-8:
                import pandas as pd, io

                buf = io.StringIO()
                pd.read_csv(
                    io.StringIO(pd.DataFrame(candidate).to_csv(index=False))
                ).to_csv(buf, index=False, float_format="%.17g")
                buf.seek(0)
                rt = metric._evaluate_puzzle_worker((n, list(csv.DictReader(buf))))
                if rt[3] != "ok" or abs(rt[1] - result[1]) > 1e-10:
                    continue
                best_rows = candidate
                best_score = result[1]
        rows[n] = best_rows
        report.update(
            n=n,
            official_before=before[1],
            official_after=best_score,
            accepted=best_score < before[1] - 1e-8,
        )
        report.update(
            n=n,
            official_before=before[1],
            official_after=best_score,
            accepted=best_score < before[1] - 1e-8,
        )
        history.append(report)
    fields = ["id", "n", "square_id", "x", "y", "angle"]
    index = 0
    with Path(output_csv).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for n in sorted(rows):
            for row in rows[n]:
                row = dict(row)
                row["id"] = str(index)
                writer.writerow(row)
                index += 1
    Path("recompute_history.json").write_text(json.dumps(history, indent=2))
    return history


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--sizes", nargs="+", type=int, default=[801, 460])
    parser.add_argument("--batch", type=int, default=6)
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--no-fq", action="store_true", help="Disable smooth fq quench proposals")
    args = parser.parse_args()
    history = run_experiment(
        args.input,
        args.output,
        backend=args.backend,
        sizes=args.sizes,
        batch=args.batch,
        steps=args.steps,
        use_fq=not args.no_fq,
    )
    print(
        json.dumps(
            [
                dict(
                    n=r["n"],
                    backend=r["backend"],
                    accepted=r["accepted"],
                    before=r["official_before"],
                    after=r["official_after"],
                )
                for r in history
            ],
            indent=2,
        )
    )
