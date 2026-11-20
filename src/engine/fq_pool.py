"""High-Performance Persistent FQ Solver Engine Pool.

Features:
- Persistent `fq serve` daemon processes communicating via stdin/stdout pipes.
- Zero disk I/O, zero process spawning overhead.
- Multi-worker concurrent pool across all CPU cores (default 14 on Apple Silicon).
- Automatic angle / bounding box normalisation and official interval certification.
- Resilient: auto-restarts workers on timeout or divergence.
"""

from __future__ import annotations
import math
import os
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, Tuple, Dict, Any, List
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
FQ_BIN = str(ROOT / "data" / "new_sources" / "external" / "evand" / "search" / "packer" / "target" / "release" / "fq")

OFF = np.array([(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)])

def corners(s: np.ndarray) -> np.ndarray:
    s = np.asarray(s, float)
    c, si = np.cos(s[:, 2]), np.sin(s[:, 2])
    x = s[:, None, 0] + OFF[None, :, 0] * c[:, None] - OFF[None, :, 1] * si[:, None]
    y = s[:, None, 1] + OFF[None, :, 0] * si[:, None] + OFF[None, :, 1] * c[:, None]
    return np.stack([x, y], -1)

def normalise(s: np.ndarray) -> np.ndarray:
    s = np.array(s, float)
    s[:, :2] -= corners(s).reshape(-1, 2).min(0)
    return s

def side(s: np.ndarray) -> float:
    p = corners(s).reshape(-1, 2)
    return float(max(np.ptp(p[:, 0]), np.ptp(p[:, 1])))


class FQServer:
    """Manages a single persistent `fq serve` subprocess."""

    def __init__(self, binary_path: str = FQ_BIN):
        self.binary_path = binary_path
        self.proc: Optional[subprocess.Popen] = None
        self._start()

    def _start(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
            except Exception:
                self.proc.kill()
        self.proc = subprocess.Popen(
            [self.binary_path, "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def quench(
        self,
        packing: np.ndarray,
        extra_args: str = "--finish --loosen 1.0",
        timeout: float = 60.0
    ) -> Tuple[Optional[float], Optional[np.ndarray], Dict[str, Any]]:
        """Perform quench on a packing.
        
        Args:
            packing: (N, 3) array of [x, y, angle_radians]
            extra_args: arguments string passed to `quench` command in fq
            timeout: maximum seconds to wait for response
            
        Returns:
            (L, new_packing, info_dict) or (None, None, error_dict)
        """
        if not self.is_alive():
            self._start()

        s = normalise(packing)
        n = len(s)
        L = side(s)

        # Build request buffer
        lines = [f"quench {extra_args}".strip(), f"{n} {L + 1e-12:.17f}"]
        for x, y, t in s:
            deg = math.degrees(t) % 90.0
            lines.append(f"{x:.17f} {y:.17f} {deg:.15f}")
        req = "\n".join(lines) + "\n"

        try:
            self.proc.stdin.write(req)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._start()
            return None, None, {"error": "process pipe broken, restarted"}

        # Read response lines until END
        resp_lines = []
        t0 = time.time()
        while True:
            if time.time() - t0 > timeout:
                self._start()  # kill and restart stuck worker
                return None, None, {"error": f"timeout after {timeout}s"}
            
            line = self.proc.stdout.readline()
            if not line:
                self._start()
                return None, None, {"error": "unexpected EOF from fq"}
            
            line_s = line.strip()
            if line_s == "END":
                break
            resp_lines.append(line_s)

        if not resp_lines:
            return None, None, {"error": "empty response"}

        # First line is JSON summary
        try:
            info = json.loads(resp_lines[0])
        except Exception:
            info = {"raw": resp_lines[0]}

        if "error" in info:
            return None, None, info

        # Next line is: n s
        if len(resp_lines) < 2 + n:
            return None, None, {"error": f"incomplete coordinate rows ({len(resp_lines)})"}

        # Parse output coordinates
        coords = []
        for line in resp_lines[2:2 + n]:
            parts = line.split()
            coords.append([float(parts[0]), float(parts[1]), math.radians(float(parts[2]))])
        
        cand = np.array(coords, dtype=float)
        cand_L = side(cand)
        return cand_L, cand, info

    def close(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None


class FQPool:
    """Thread-safe pool of persistent FQServer workers across CPU cores."""

    def __init__(self, num_workers: int = 14, binary_path: str = FQ_BIN):
        self.num_workers = num_workers
        self.binary_path = binary_path
        self._queue: Queue[FQServer] = Queue()
        for _ in range(num_workers):
            self._queue.put(FQServer(binary_path))

    def quench(
        self,
        packing: np.ndarray,
        extra_args: str = "--finish --loosen 1.0",
        timeout: float = 60.0
    ) -> Tuple[Optional[float], Optional[np.ndarray], Dict[str, Any]]:
        server = self._queue.get()
        try:
            return server.quench(packing, extra_args=extra_args, timeout=timeout)
        finally:
            self._queue.put(server)

    def map_quench(
        self,
        tasks: List[Tuple[np.ndarray, str, float]]
    ) -> List[Tuple[Optional[float], Optional[np.ndarray], Dict[str, Any]]]:
        """Run multiple quench jobs concurrently across the worker pool."""
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = [executor.submit(self.quench, p, args, to) for p, args, to in tasks]
            return [f.result() for f in futures]

    def close(self):
        while not self._queue.empty():
            try:
                server = self._queue.get_nowait()
                server.close()
            except Empty:
                break


if __name__ == "__main__":
    print(f"Testing FQPool with 4 test workers on Apple Silicon...")
    pool = FQPool(num_workers=4)
    # Test on n=10
    test_sq = np.random.rand(10, 3)
    test_sq[:, 2] = 0.0
    t0 = time.time()
    L, cand, info = pool.quench(test_sq, extra_args="--finish --deadline 2 --loosen 1.0", timeout=5.0)
    dt = time.time() - t0
    print(f"Quench finished in {dt:.3f}s: L={L:.6f}, evals={info.get('evals')}, min_gap={info.get('min_gap')}")
    pool.close()
    print("FQPool test passed!")
