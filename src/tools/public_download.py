"""Read public CSV bytes with bounded, resumable range downloads."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests


def download_public_csv(url, destination):
    destination = Path(destination)
    response = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=40)
    response.raise_for_status()
    if response.status_code == 200:
        destination.write_bytes(response.content)
        return
    assert response.status_code == 206
    length = int(response.headers["Content-Range"].split("/")[-1])
    resolved_url = response.url
    block_size = 262144

    def read_block(start):
        end = min(start + block_size, length) - 1
        for attempt in range(3):
            try:
                block = requests.get(
                    resolved_url, headers={"Range": f"bytes={start}-{end}"}, timeout=40
                )
                block.raise_for_status()
                assert len(block.content) == end - start + 1
                return block.content
            except (requests.RequestException, AssertionError):
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(max_workers=4) as executor:
        blocks = list(executor.map(read_block, range(0, length, block_size)))
    content = b"".join(blocks)
    assert len(content) == length
    destination.write_bytes(content)
