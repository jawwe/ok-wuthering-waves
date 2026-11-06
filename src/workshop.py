"""Read-only upstream catalog, durable offline cache and immutable bundled snapshots.

Downloaded Python is inspected as text here; it is never imported or executed by
the cache. Character loading remains the explicit team's import operation.
"""
import ast
import hashlib
import io
import json
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from src.app_identity import DATA_ROOT, RESOURCE_ROOT

UPSTREAM_REPOSITORY = "ok-oldking/ok-ww-char-code"
SITE = "https://okwwcharcode.ok-script.com"
RAW_ROOT = f"https://raw.githubusercontent.com/{UPSTREAM_REPOSITORY}"
CATALOG_URLS = (f"{SITE}/teams.json", f"{RAW_ROOT}/main/teams.json",
                "https://cfokwwchar.ok-script.com/teams.json")
ARCHIVE_HOSTS = {"okwwcharcode.ok-script.com", "cfokwwchar.ok-script.com", "raw.githubusercontent.com"}
USER_AGENT = "AsterDesk"
MAX_INDEX = 5_000_000
MAX_ARCHIVE = 20_000_000


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def flatten_codes(index):
    codes = []
    for team in index["teams"]:
        for code in team["codes"]:
            codes.append(dict(code, team=code.get("team") or team["team"],
                              members=code.get("members") or team["members"]))
    return sorted(codes, key=lambda item: int(item.get("timestamp") or 0), reverse=True)


def validate_index(index):
    if not isinstance(index, dict) or not isinstance(index.get("teams"), list):
        raise ValueError("Workshop response is invalid.")
    for team in index["teams"]:
        if (not isinstance(team, dict) or not isinstance(team.get("team"), str)
                or not isinstance(team.get("members"), list) or len(team["members"]) != 3
                or not all(isinstance(name, str) and name for name in team["members"])
                or not isinstance(team.get("codes"), list)):
            raise ValueError("Workshop response is invalid.")
        for code in team["codes"]:
            if not isinstance(code, dict) or not isinstance(code.get("filename"), str):
                raise ValueError("Workshop response is invalid.")
            int(code.get("timestamp") or 0)
            if not archive_urls(code):
                raise ValueError("Workshop download URL is invalid.")
    return index


def archive_urls(code):
    urls = []
    for field in ("snapshotRawUrl", "downloadUrl", "rawUrl"):
        value = code.get(field)
        if not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if (parsed.scheme != "https" or parsed.hostname not in ARCHIVE_HOSTS
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            continue
        if parsed.hostname == "raw.githubusercontent.com" and not parsed.path.startswith(f"/{UPSTREAM_REPOSITORY}/"):
            continue
        if value not in urls:
            urls.append(value)
        # Keep the old site's working URL intact; it is also the fallback for CF.
        if parsed.hostname == "cfokwwchar.ok-script.com":
            alternative = parsed._replace(netloc="okwwcharcode.ok-script.com").geturl()
            if alternative not in urls:
                urls.append(alternative)
    return urls


def inspect_archive(content):
    if len(content) > MAX_ARCHIVE:
        raise ValueError("Workshop archive is too large.")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (len(names) != 4 or len(set(names)) != 4 or "team.json" not in names
                or any("/" in name or "\\" in name or name.startswith(".") for name in names)
                or any(entry.file_size > 2_000_000 for entry in entries)
                or sum(name.endswith(".py") for name in names) != 3):
            raise ValueError("Invalid team archive")
        manifest = json.loads(archive.read("team.json").decode("utf-8"))
        if not isinstance(manifest, dict) or any(
                not isinstance(manifest.get(key), str) or not manifest[key].strip()
                for key in ("name", "description", "author", "version", "team")):
            raise ValueError("Invalid team manifest")
        for name in names:
            if name.endswith(".py"):
                code = archive.read(name).decode("utf-8")
                tree = ast.parse(code, filename=name)
                if not any(isinstance(node, ast.ClassDef) and node.name == name[:-3] for node in tree.body):
                    raise ValueError(f"Missing character class: {name}")
                compile(tree, name, "exec")
    return manifest


def code_key(code):
    identity = {key: code.get(key) for key in ("filename", "timestamp", "size")}
    return hashlib.sha256(json_bytes(identity)).hexdigest()


@dataclass
class Catalog:
    index: dict
    fetched_at: str
    source: str
    offline: bool = False
    error: str = ""

    @property
    def codes(self):
        return flatten_codes(self.index)


class WorkshopStore:
    def __init__(self, cache_root=None, bundle_root=None, opener=None, timeout=6):
        self.cache_root = Path(cache_root) if cache_root is not None else DATA_ROOT / "cache" / "workshop"
        self.bundle_root = Path(bundle_root) if bundle_root is not None else RESOURCE_ROOT / "workshop"
        self.opener = opener or urlopen
        self.timeout = timeout

    def _read_url(self, url, limit):
        with self.opener(Request(url, headers={"User-Agent": USER_AGENT}), timeout=self.timeout) as response:
            # Do not follow an upstream redirect to an arbitrary download host.
            final = response.geturl() if callable(getattr(response, "geturl", None)) else url
            parsed = urlparse(final)
            if parsed.scheme != "https" or parsed.hostname not in ARCHIVE_HOSTS:
                raise ValueError("Workshop download URL is invalid.")
            content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Workshop response is too large.")
        return content

    def cached_catalog(self):
        candidates = []
        for path, source in ((self.cache_root / "index.json", "cache"),
                             (self.bundle_root / "current.json", "bundle")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                index = validate_index(document["index"])
                fetched_at = document["fetched_at"]
                datetime.fromisoformat(fetched_at)
                candidates.append(Catalog(index, fetched_at, source, offline=True))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return max(candidates, key=lambda value: value.fetched_at) if candidates else None

    def refresh(self, urls=CATALOG_URLS, prefetch=True):
        errors = []
        for url in urls:
            try:
                index = validate_index(json.loads(self._read_url(url, MAX_INDEX).decode("utf-8")))
                document = {"schema_version": 1, "fetched_at": now_utc(), "source": url, "index": index}
                catalog = Catalog(index, document["fetched_at"], url)
                if prefetch:
                    failures = self.prefetch(catalog)
                    if failures:
                        raise OSError("Incomplete configuration cache: " + "; ".join(failures))
                atomic_write(self.cache_root / "index.json", json_bytes(document))
                return catalog
            except (OSError, ValueError, TypeError) as error:
                errors.append(f"{url}: {error}")
        cached = self.cached_catalog()
        if cached is None:
            raise OSError("Workshop unavailable; no cached catalog. " + "; ".join(errors))
        cached.error = "; ".join(errors)
        return cached

    def _cached_archive(self, code):
        key = code_key(code)
        for root in (self.cache_root, self.bundle_root):
            try:
                if root == self.bundle_root:
                    document = json.loads((root / "current.json").read_text(encoding="utf-8"))
                    digest = document["archives"][key]
                else:
                    digest = json.loads((root / "keys" / f"{key}.json").read_text(encoding="utf-8"))["sha256"]
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    continue
                content = (root / "archives" / f"{digest}.zip").read_bytes()
                if hashlib.sha256(content).hexdigest() != digest:
                    continue
                inspect_archive(content)
                return content
            except (OSError, ValueError, TypeError, KeyError, SyntaxError, zipfile.BadZipFile):
                continue
        return None

    def archive(self, code):
        cached = self._cached_archive(code)
        if cached is not None:
            return cached
        errors = []
        for url in archive_urls(code):
            try:
                content = self._read_url(url, MAX_ARCHIVE)
                inspect_archive(content)
                digest = hashlib.sha256(content).hexdigest()
                atomic_write(self.cache_root / "archives" / f"{digest}.zip", content)
                atomic_write(self.cache_root / "keys" / f"{code_key(code)}.json", json_bytes({"sha256": digest}))
                return content
            except (OSError, ValueError, SyntaxError, zipfile.BadZipFile) as error:
                errors.append(f"{url}: {error}")
        raise OSError("Workshop archive unavailable. " + "; ".join(errors))

    def prefetch(self, catalog):
        def download(code):
            try:
                self.archive(code)
                return None
            except (OSError, ValueError) as error:
                return f"{code['filename']}: {error}"
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="CatalogCache") as pool:
            return [error for error in pool.map(download, catalog.codes) if error]
