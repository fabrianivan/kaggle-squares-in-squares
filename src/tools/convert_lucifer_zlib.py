"""Convert any lucifer *_geometry_snapshot.zlib into a standard packing CSV."""
import zlib
import json
import csv
from pathlib import Path

def convert_zlib(zlib_path: Path):
    out_csv = zlib_path.parent / (zlib_path.stem + ".csv")
    if out_csv.exists() and out_csv.stat().st_size > 0:
        return out_csv
    with open(zlib_path, "rb") as f:
        data = json.loads(zlib.decompress(f.read()).decode("utf-8"))
    
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["n", "square_id", "x", "y", "angle"])
        for n_str, squares in data.items():
            n = int(n_str)
            for sq_id, sq in enumerate(squares):
                # sq is [x, y, angle]
                writer.writerow([n, sq_id, sq[0], sq[1], sq[2]])
    print(f"Converted {zlib_path.name} -> {out_csv.name} ({len(data)} puzzles)")
    return out_csv

def main():
    root = Path(".")
    for p in root.rglob("*_geometry_snapshot.zlib"):
        try:
            convert_zlib(p)
        except Exception as e:
            print(f"Error converting {p}: {e}")

if __name__ == "__main__":
    main()
