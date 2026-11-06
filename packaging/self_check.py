"""Offline verification of the extracted portable payload, with no target input."""
import hashlib
import json
import os
import sys
from pathlib import Path

code_root = Path(__file__).resolve().parent
if not (code_root / "src").is_dir():
    code_root = code_root.parent
sys.path.insert(0, str(code_root))
os.chdir(code_root)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from ok.util.config import Config
from src.app_identity import APP_NAME, APP_ROOT, DATA_ROOT
from src.workshop import WorkshopStore


def main():
    from config import config
    from src.gui.CharacterCodeTab import CharacterCodeTab
    from src.gui.ClientSettingsTab import ClientSettingsTab
    from src.char.CustomCharLoader import inspect_team_archive
    from src.input_mode import SwitchableInteraction
    Config.config_folder = config["config_folder"]
    application = QApplication.instance() or QApplication([])
    tabs = [CharacterCodeTab(), ClientSettingsTab()]
    assert config["gui_title"] == APP_NAME
    assert config["windows"]["interaction"] is SwitchableInteraction
    assert "update_pyappify" not in config
    assert "ok-oldking" not in json.dumps(config["links"])
    def offline(*args, **kwargs):
        raise OSError("offline self-check")
    store = WorkshopStore(opener=offline)
    catalog = store.refresh()
    assert catalog.offline and catalog.codes
    verified = 0
    for code in catalog.codes:
        content = store.archive(code)
        temporary = DATA_ROOT / "self-check-package.zip"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(content)
        try:
            inspect_team_archive(temporary)
            verified += 1
        finally:
            temporary.unlink(missing_ok=True)
    report = {"application": APP_NAME, "root": str(APP_ROOT), "executable": sys.executable,
              "pid": os.getpid(), "offline_catalog": len(catalog.codes), "verified_archives": verified,
              "pages": [tab.name for tab in tabs], "snapshot_time": catalog.fetched_at}
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / "self-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for tab in tabs:
        tab.deleteLater()
    application.processEvents()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
