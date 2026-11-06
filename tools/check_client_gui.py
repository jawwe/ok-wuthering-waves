"""Exercise the real GUI lifecycle without starting or sending input to a game."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["QT_QPA_PLATFORM"] = os.environ.get("ASTERDESK_QA_PLATFORM", "offscreen")

from src.bootstrap import prepare_environment
prepare_environment()
from config import config
from ok import OK
from PySide6.QtCore import QTimer, QEventLoop
from PySide6.QtWidgets import QApplication
from src.gui.CharacterCodeTab import CharacterCodeTab, WorkshopDialog
from src.gui.ClientSettingsTab import ClientSettingsTab
from src.workshop import WorkshopStore

config["windows"]["start_exe"] = False
config["mcp"] = {"enabled": False}
runtime = OK(config)
attempts = 0
failure = None


def settle():
    loop = QEventLoop()
    QTimer.singleShot(350, loop.quit)
    loop.exec()


def inspect_gui():
    global attempts, failure
    attempts += 1
    window = getattr(runtime.app, "main_window", None)
    if window is None:
        if attempts < 120:
            QTimer.singleShot(250, inspect_gui)
            return
        failure = "Main window did not appear"
        runtime.quit()
        return
    try:
        assert "AsterDesk" in window.windowTitle(), window.windowTitle()
        pages = window.findChildren(CharacterCodeTab) + window.findChildren(ClientSettingsTab)
        assert len(pages) == 2, [type(page).__name__ for page in pages]
        assert window.about_tab.update_card is None
        output = ROOT / "data/qa"
        output.mkdir(parents=True, exist_ok=True)
        for page in pages:
            window.switch_to(page)
            settle()
            window.grab().save(str(output / f"{type(page).__name__}.png"))
        catalog = WorkshopStore().cached_catalog()
        dialog = WorkshopDialog(catalog.codes, parent=window)
        dialog.set_catalog(catalog)
        dialog.open()
        settle()
        assert dialog.table.rowCount() == len(catalog.codes)
        dialog.grab().save(str(output / "workshop.png"))
        dialog.close()
        report = {"title": window.windowTitle(), "pages": [type(page).__name__ for page in pages],
                  "catalog_rows": len(catalog.codes), "legacy_updater": False, "sent_game_input": False}
        (output / "gui-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    except Exception as error:
        failure = repr(error)
        print(f"GUI check failed: {failure}")
    finally:
        runtime.quit()


QTimer.singleShot(500, inspect_gui)
runtime.start()
if failure:
    raise RuntimeError(failure)
