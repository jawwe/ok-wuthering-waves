"""Build a self-contained Windows x64 ZIP with neutral launcher/worker names."""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app_identity import APP_NAME, CHANNEL_BRANCH, RELEASE_PREFIX, REPOSITORY
from src.workshop import WorkshopStore, json_bytes


def generate_icons():
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    svg = (ROOT / "icons/asterdesk.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(svg))
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, 256, 256))
    painter.end()
    image.save(str(ROOT / "icons/asterdesk.png"))
    png = (ROOT / "icons/asterdesk.png").read_bytes()
    (ROOT / "icons/asterdesk.ico").write_bytes(struct.pack("<HHH", 0, 1, 1)
        + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png)


def build(version, refresh=True):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must use MAJOR.MINOR.PATCH")
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise RuntimeError("Build with Windows x64 Python")
    if refresh:
        from tools.snapshot_workshop import capture
        capture()
    store = WorkshopStore(cache_root=ROOT / "build" / "snapshot-check")
    document = json.loads((store.bundle_root / "current.json").read_text(encoding="utf-8"))
    for code in store.cached_catalog().codes:
        if store._cached_archive(code) is None:
            raise RuntimeError("Missing or corrupt bundled configuration: " + code["filename"])
    generate_icons()
    output_root = ROOT / "dist"
    output_root.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="portable-", dir=output_root))
    target = staging / APP_NAME
    app, runtime = target / "app", target / "runtime"
    target.mkdir()
    app.mkdir()
    try:
        for name in ("src", "assets", "icons", "i18n"):
            shutil.copytree(ROOT / name, app / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
        for name in ("main.py", "config.py", "LICENSE.txt", "requirements.txt"):
            shutil.copy2(ROOT / name, app / name)
        shutil.copy2(ROOT / "packaging/self_check.py", app / "self_check.py")
        # Ship only the current catalog's packages; historical snapshots stay in Git.
        bundle = app / "resources/workshop"
        bundle.mkdir(parents=True)
        shutil.copy2(store.bundle_root / "current.json", bundle / "current.json")
        (bundle / "archives").mkdir()
        for digest in set(document["archives"].values()):
            shutil.copy2(store.bundle_root / "archives" / f"{digest}.zip", bundle / "archives" / f"{digest}.zip")
        shutil.copytree(Path(sys.base_prefix), runtime, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(Path(sys.prefix) / "Lib/site-packages", runtime / "Lib/site-packages", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(runtime / "pythonw.exe", runtime / "AsterRuntime.exe")
        compiler = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
        if not compiler.is_file():
            raise RuntimeError("The .NET Framework C# compiler is required")
        launcher_source = staging / "Launcher.cs"
        launcher_source.write_text((ROOT / "packaging/Launcher.cs").read_text(encoding="utf-8").replace(
            'Version("1.0.0.0")', f'Version("{version}.0")'), encoding="utf-8")
        subprocess.run([str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/debug-",
                        "/reference:System.Windows.Forms.dll", f"/win32icon:{ROOT / 'icons/asterdesk.ico'}",
                        f"/out:{target / (APP_NAME + '.exe')}", str(launcher_source)], check=True)
        metadata = {"application": APP_NAME, "version": version, "repository": REPOSITORY,
                    "branch": CHANNEL_BRANCH, "release_prefix": RELEASE_PREFIX,
                    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "snapshot": document["revision"], "snapshot_time": document["fetched_at"]}
        (target / "distribution.json").write_bytes(json_bytes(metadata))
        shutil.copy2(ROOT / "docs/portable-readme.txt", target / "README.txt")
        shutil.copy2(ROOT / "LICENSE.txt", target / "LICENSE.txt")
        artifact = output_root / f"{APP_NAME}-{version}-windows-x64.zip"
        with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging).as_posix())
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        artifact.with_name(artifact.name + ".sha256").write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
        print(json.dumps({"artifact": str(artifact), "sha256": digest, "bytes": artifact.stat().st_size,
                          "snapshot": document["revision"]}))
        return artifact
    finally:
        # staging is freshly created under the known output root, never user data.
        if staging.resolve().parent != output_root.resolve():
            raise RuntimeError("Unsafe staging directory")
        shutil.rmtree(staging)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--offline-snapshot", action="store_true")
    arguments = parser.parse_args()
    build(arguments.version, refresh=not arguments.offline_snapshot)
