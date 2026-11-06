import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from ok.ui.qt.about.AboutTab import AboutTab, ProjectCard
from src.globals import Globals
from src.gui.ClientSettingsTab import ClientSettingsTab
from src.input_mode import BACKGROUND, SYSTEM


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


if __name__ == "__main__":
    unittest.main()
