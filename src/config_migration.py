"""Explicit import into an isolated configuration directory; never overwrite it."""
import json
import shutil
import tempfile
from pathlib import Path

from src.app_identity import CONFIG_ROOT, DATA_ROOT
from src.workshop import atomic_write, json_bytes, now_utc


def import_legacy_config(source, destination=None):
    source = Path(source).resolve()
    destination = Path(destination or CONFIG_ROOT).resolve()
    if not source.is_dir() or source == destination or destination in source.parents or source in destination.parents:
        raise ValueError("Choose a separate existing configuration folder.")
    if any(destination.rglob("*.json")) or any(destination.rglob("*.py")):
        # Only our input preference is safe to retain; all imported data is user chosen.
        existing = [p for p in destination.rglob("*") if p.is_file() and p.name != "ClientSettings.json"]
        if existing:
            raise ValueError("Import requires an empty configuration folder.")
    files = []
    for path in source.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Configuration links cannot be imported.")
        if not path.is_file() or path.suffix not in {".json", ".py"}:
            continue
        relative = path.relative_to(source)
        if path.name == "ClientSettings.json" or any(part in {"cache", "logs", "updates", "__pycache__"} for part in relative.parts):
            continue
        if path.stat().st_size > 20_000_000:
            raise ValueError("Configuration file is too large.")
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        files.append((path, destination / relative))
    if not files:
        raise ValueError("No configuration files found.")
    # Validate the whole selection before copying anything.
    written = []
    try:
        for source_file, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError("Import would overwrite an existing file.")
            shutil.copy2(source_file, target)
            written.append(target)
    except Exception:
        for target in written:
            target.unlink(missing_ok=True)
        raise
    return len(written)


def stage_legacy_config(source, data_root=None):
    root = Path(data_root or DATA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "configuration-import.json").exists():
        raise ValueError("Configuration has already been imported.")
    if (root / "import-pending.json").exists():
        raise ValueError("Restart to finish the pending import first.")
    staging = Path(tempfile.mkdtemp(prefix="config-import-", dir=root))
    try:
        count = import_legacy_config(source, staging)
        current_settings = root / "configs" / "ClientSettings.json"
        if current_settings.is_file():
            shutil.copy2(current_settings, staging / current_settings.name)
        atomic_write(root / "import-pending.json", json_bytes({"folder": staging.name, "count": count}))
        return count
    except Exception:
        shutil.rmtree(staging)
        raise


def apply_pending_migration(data_root=None):
    root = Path(data_root or DATA_ROOT)
    marker = root / "import-pending.json"
    if not marker.is_file():
        return False
    document = json.loads(marker.read_text(encoding="utf-8"))
    name = document["folder"]
    if not isinstance(name, str) or Path(name).name != name or not name.startswith("config-import-"):
        raise ValueError("Invalid pending import")
    staging = root / name
    target = root / "configs"
    backup = root / "config-before-import"
    if not staging.is_dir() and target.is_dir():
        # Recover a completed rename interrupted before the completion marker.
        atomic_write(root / "configuration-import.json", json_bytes({"imported_at": now_utc(), "count": document["count"]}))
        marker.unlink()
        return True
    if not staging.is_dir() or (backup.exists() and target.exists()):
        raise ValueError("Cannot apply pending import")
    had_target = target.exists()
    if had_target:
        target.rename(backup)
    installed = False
    try:
        staging.rename(target)
        installed = True
        atomic_write(root / "configuration-import.json", json_bytes({"imported_at": now_utc(), "count": document["count"]}))
    except Exception:
        if installed:
            target.rename(staging)
        if backup.exists() and not target.exists():
            backup.rename(target)
        raise
    marker.unlink()
    return True
