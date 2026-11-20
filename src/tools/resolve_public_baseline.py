"""Resolve a public notebook's current slug by stable ID before pinned replay.

Only anonymous public competition listings are read. Notebook renaming changes
slugs, so the version number and file SHA256 are still checked independently.
"""

import requests


def resolve_public_slug(notebook_id, expected_author="kirilltym"):
    page = "https://www.kaggle.com/competitions/squares-in-squares/code"
    s = requests.Session()
    s.get(page, timeout=30).raise_for_status()
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.kaggle.com",
        "Referer": page,
    }
    token = s.cookies.get("XSRF-TOKEN")
    if token:
        headers["X-XSRF-TOKEN"] = token
    for number in range(1, 21):
        payload = {
            "kernelFilterCriteria": {
                "listRequest": {
                    "competitionId": 166661,
                    "sortBy": "SCORE_ASCENDING",
                    "group": "EVERYONE",
                    "pageSize": 100,
                    "page": number,
                }
            },
            "pageSize": 100,
        }
        r = s.post(
            "https://www.kaggle.com/api/i/kernels.KernelsService/ListKernels",
            json=payload,
            headers=headers,
            timeout=40,
        )
        r.raise_for_status()
        rows = r.json()["kernels"]
        for row in rows:
            if row["id"] == notebook_id:
                assert row["author"]["userName"] == expected_author
                return row["currentUrlSlug"]
        if len(rows) < 100:
            break
    raise LookupError(
        "Pinned public baseline notebook ID was not found; keep the frozen hash and version, do not substitute another input."
    )
