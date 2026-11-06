"""Independent release discovery/download. Never consume upstream releases/tags."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.app_identity import APP_NAME, DATA_ROOT, RELEASE_PREFIX, REPOSITORY

API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"


def release_version(tag):
    match = re.fullmatch(re.escape(RELEASE_PREFIX) + r"(\d+)\.(\d+)\.(\d+)", tag or "")
    return tuple(int(part) for part in match.groups()) if match else None


def trusted_asset(url, tag):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname == "github.com"
            and parsed.path.startswith(f"/{REPOSITORY}/releases/download/{tag}/")
            and not parsed.username and not parsed.password and parsed.port in (None, 443))


def latest_release(opener=None):
    opener = opener or urlopen
    with opener(Request(API_URL, headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"}), timeout=15) as response:
        payload = json.loads(response.read(2_000_001).decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Invalid release response")
    candidates = []
    for item in payload:
        tag = item.get("tag_name", "")
        version = release_version(tag)
        if item.get("draft") or item.get("prerelease") or version is None:
            continue
        expected = f"{APP_NAME}-{'.'.join(map(str, version))}-windows-x64.zip"
        assets = {asset.get("name"): asset.get("browser_download_url", "") for asset in item.get("assets", [])}
        archive, checksum = assets.get(expected, ""), assets.get(expected + ".sha256", "")
        if trusted_asset(archive, tag) and trusted_asset(checksum, tag):
            candidates.append({"tag": tag, "version": version, "name": expected,
                               "archive": archive, "checksum": checksum,
                               "page": f"https://github.com/{REPOSITORY}/releases/tag/{tag}"})
    return max(candidates, key=lambda item: item["version"]) if candidates else None


def download_release(release, destination=None, opener=None):
    opener = opener or urlopen
    tag = release["tag"]
    if release_version(tag) is None or not all(trusted_asset(release[key], tag) for key in ("archive", "checksum")):
        raise ValueError("Untrusted release channel")
    expected_name = f"{APP_NAME}-{'.'.join(map(str, release_version(tag)))}-windows-x64.zip"
    if release["name"] != expected_name:
        raise ValueError("Invalid release filename")
    headers = {"User-Agent": APP_NAME}
    with opener(Request(release["checksum"], headers=headers), timeout=15) as response:
        checksum = response.read(1025).decode("ascii").split()[0]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
        raise ValueError("Invalid update checksum")
    folder = Path(destination or DATA_ROOT / "updates")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / expected_name
    temporary = target.with_suffix(".partial")
    digest = hashlib.sha256()
    total = 0
    try:
        with opener(Request(release["archive"], headers=headers), timeout=30) as response, temporary.open("wb") as output:
            while content := response.read(1024 * 1024):
                total += len(content)
                if total > 2_000_000_000:
                    raise ValueError("Update archive is too large")
                digest.update(content)
                output.write(content)
        if digest.hexdigest() != checksum.lower():
            raise ValueError("Update checksum mismatch")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
