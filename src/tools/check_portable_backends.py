"""Exercise the requested real tensor device and full small-puzzle export path."""

import argparse, csv, json, tempfile, os, hashlib
from pathlib import Path
import numpy as np
from portable_seam_search import choose_device, tensor_loss, seam_pressure
from portable_experiment import run_experiment


def check(backend):
    import torch

    device = choose_device(backend)
    dtype = torch.float32 if backend == "mps" else torch.float64
    c = torch.tensor(
        [[[0.7, 0.8], [1.5, 1.1], [1.1, 1.8]]],
        dtype=dtype,
        device=device,
        requires_grad=True,
    )
    a = torch.tensor(
        [[0.12, -0.21, 0.37]], dtype=dtype, device=device, requires_grad=True
    )
    pairs = torch.tensor([[0, 1], [0, 2], [1, 2]], dtype=torch.long, device=device)
    loss = tensor_loss(c, a, pairs, 2.8).sum()
    loss.backward()
    assert torch.isfinite(c.grad).all() and torch.isfinite(a.grad).all()
    # Finite differences on a smooth configuration check angle and centre gradients.
    eps = 2e-3 if dtype == torch.float32 else 1e-6
    errors = []
    for tensor, index in [(c, (0, 0, 0)), (a, (0, 1))]:
        analytic = float(tensor.grad[index].item())
        plus = tensor.detach().clone()
        minus = plus.clone()
        plus[index] += eps
        minus[index] -= eps
        fplus = tensor_loss(
            plus if tensor is c else c.detach(),
            a.detach() if tensor is c else plus,
            pairs,
            2.8,
        ).sum()
        fminus = tensor_loss(
            minus if tensor is c else c.detach(),
            a.detach() if tensor is c else minus,
            pairs,
            2.8,
        ).sum()
        err = abs(float((fplus - fminus).item()) / (2 * eps) - analytic)
        errors.append(err)
    assert max(errors) < (3e-3 if dtype == torch.float32 else 1e-5), errors
    root = Path.cwd()
    source = Path("submission.csv")
    with source.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if int(r["n"]) == 5]
    assert len(rows) == 5
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        inp = work / "input.csv"
        with inp.open("w", newline="") as f:
            w = csv.DictWriter(
                f, fieldnames=["id", "n", "square_id", "x", "y", "angle"]
            )
            w.writeheader()
            w.writerows(rows)
        # Keep an audit run separate from any production recomputation history.
        os.chdir(work)
        try:
            history = run_experiment(
                str(inp),
                str(work / "output.csv"),
                backend=backend,
                sizes=[5],
                batch=2,
                steps=24,
            )
        finally:
            os.chdir(root)
    assert history[0]["backend"] == backend and history[0]["steps"] == 24
    result = dict(
        backend=backend,
        actual_tensor_device=str(device),
        torch_version=torch.__version__,
        gradient_max_error=max(errors),
        full_export_history=history,
        cpu_certification=True,
    )
    Path("device_check_" + backend + ".json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["cpu", "cuda", "mps"], default="cpu")
    check(p.parse_args().backend)
