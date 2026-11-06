"""Capture an upstream revision without executing any downloaded configuration.

Run before a release. Snapshots and content-addressed ZIPs are append-only; the
current pointer changes only after every package has downloaded and validated.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.workshop import (MAX_ARCHIVE, MAX_INDEX, RAW_ROOT, UPSTREAM_REPOSITORY,
                          USER_AGENT, atomic_write, code_key, inspect_archive,
                          json_bytes, validate_index)


def request(url, limit):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=20) as response:
                content = response.read(limit + 1)
            break
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    if len(content) > limit:
        raise ValueError(f"Response too large: {url}")
    return content


def capture(ref="main", historical=False, output=None):
    root = Path(output or ROOT / "resources" / "workshop")
    api = f"https://api.github.com/repos/{UPSTREAM_REPOSITORY}/git"
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        revision = ref
    else:
        reference = json.loads(request(f"{api}/ref/heads/{quote(ref, safe='/')}", MAX_INDEX))
        revision = reference["object"]["sha"]
    commit = json.loads(request(f"{api}/commits/{revision}", MAX_INDEX))
    path = root / "snapshots" / f"{revision}.json"
    if path.is_file():
        document = json.loads(path.read_text(encoding="utf-8"))
    else:
        index = validate_index(json.loads(request(f"{RAW_ROOT}/{revision}/teams.json", MAX_INDEX)))
        codes = [code for team in index["teams"] for code in team["codes"]]
        for code in codes:
            code["snapshotRawUrl"] = f"{RAW_ROOT}/{revision}/codes/{quote(code['filename'], safe='')}"

        def download(code):
            content = request(code["snapshotRawUrl"], MAX_ARCHIVE)
            inspect_archive(content)
            digest = hashlib.sha256(content).hexdigest()
            archive_path = root / "archives" / f"{digest}.zip"
            if not archive_path.exists():
                atomic_write(archive_path, content)
            return code_key(code), digest

        with ThreadPoolExecutor(max_workers=4) as pool:
            archives = dict(pool.map(download, codes))
        document = {"schema_version": 1, "fetched_at": commit["committer"]["date"],
                    "source": f"{RAW_ROOT}/{revision}/teams.json", "revision": revision,
                    "index": index, "archives": archives}
        atomic_write(path, json_bytes(document))
    # Verify reused snapshots as well; a missing archive must fail the release.
    for digest in document["archives"].values():
        content = (root / "archives" / f"{digest}.zip").read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Corrupt snapshot archive")
    if not historical:
        atomic_write(root / "current.json", json_bytes(document))
    print(json.dumps({"revision": revision, "teams": len(document['index']['teams']),
                      "codes": len(document['archives']), "snapshot": str(path)}, ensure_ascii=False))
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--historical", action="store_true")
    args = parser.parse_args()
    capture(args.ref, args.historical)
