"""Hash-pinned public inputs for optional research replay after notebook renames."""

from pathlib import Path
import hashlib, requests
from resolve_public_baseline import resolve_public_slug


def ensure_input(path, notebook_id, author, version, digest):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        slug = resolve_public_slug(notebook_id, expected_author=author)
        url = f"https://www.kaggle.com/api/v1/kernels/output/download/{author}/{slug}/submission.csv?versionNumber={version}"
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == digest
        p.write_bytes(response.content)
    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest
    return p
