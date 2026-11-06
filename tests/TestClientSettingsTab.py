import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QWidget
from ok import og
from ok.device.DeviceManager import DeviceManager
from ok.ui.qt.about.AboutTab import AboutTab, ProjectCard
from ok.ui.qt.shell.connection import ConnectionPopover
from config import config
from src.globals import Globals
from src.gui.ClientSettingsTab import ClientSettingsTab
from src.input_mode import BACKGROUND, SYSTEM, SwitchableInteraction


class TestClientSettingsTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_switch_button_schedules_all_inputs_and_updates_state(self):
        tab = ClientSettingsTab()
        future = Future()
        interaction = SimpleNamespace(mode=BACKGROUND)
        executor = SimpleNamespace(current_task=None, interaction=interaction,
                                   submit=Mock(return_value=SimpleNamespace(future=future)))
        tab.executor = executor
        try:
            tab.input_button.click()
            self.assertFalse(tab.input_button.isEnabled())
            with patch("src.gui.ClientSettingsTab.switch_all_inputs", return_value=SYSTEM) as switch:
                future.set_result(executor.submit.call_args.args[0]())
                switch.assert_called_once_with(executor, SYSTEM)
            self.assertTrue(tab.input_button.isEnabled())
            self.assertIn("System", tab.input_status.text())
        finally:
            tab.deleteLater()

    def test_legacy_update_and_related_project_cards_are_removed_by_app_hook(self):
        about = AboutTab({"gui_title": "AsterDesk", "version": "1.0.0"})
        try:
            self.assertIsNotNone(about.update_card)
            self.assertTrue(about.findChildren(ProjectCard))
            Globals(None).on_show_main_window(SimpleNamespace(about_tab=about))
            self.assertIsNone(about.update_card)
            self.assertFalse(any(section.findChildren(ProjectCard) for section in about.sections))
        finally:
            about.deleteLater()

    def test_connection_popover_refreshes_with_the_production_input_config(self):
        window = QWidget()
        popover = ConnectionPopover(window)
        device = {"device": "windows", "imei": "pc", "nick": "Desktop", "connected": False}
        manager = SimpleNamespace(
            windows_capture_config=config["windows"],
            config={"preferred": "pc", "interaction": SwitchableInteraction.__name__},
            get_devices=lambda: [device], get_preferred_device=lambda: device,
            get_preferred_capture=lambda: "WGC",
        )
        try:
            with (patch.object(og, "device_manager", manager),
                  patch.object(og, "executor", SimpleNamespace(paused=True)),
                  patch.object(og, "app", SimpleNamespace(overlay_state=lambda: {"boxes": False}))):
                popover.refresh()
            self.assertEqual(popover._interaction_names, [SwitchableInteraction.__name__])
            self.assertEqual(popover.window_combo.count(), 1)
        finally:
            popover.deleteLater()
            window.deleteLater()

    def test_connection_selection_resolves_the_custom_backend_class(self):
        manager = DeviceManager.__new__(DeviceManager)
        manager.windows_capture_config = config["windows"]
        manager.config = {}
        manager.start = Mock()
        manager.set_interaction(SwitchableInteraction.__name__)
        self.assertIs(manager.win_interaction_class, SwitchableInteraction)
        self.assertEqual(manager.config["interaction"], SwitchableInteraction.__name__)
        manager.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
