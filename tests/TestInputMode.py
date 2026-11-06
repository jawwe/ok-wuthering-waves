import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.input_mode import BACKGROUND, SYSTEM, SwitchableInteraction, read_mode, switch_all_inputs


class TestInputMode(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.mode_file = Path(self.folder.name) / "settings.json"
        self.window = SimpleNamespace(is_foreground=Mock(return_value=True), bring_to_front=Mock())
        self.background, self.system = Mock(), Mock()
        self.system.check_clickable = True
        self.patches = [patch("src.input_mode.PostMessageInteraction", return_value=self.background),
                        patch("src.input_mode.PynputInteraction", return_value=self.system)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.input = SwitchableInteraction(object(), self.window, self.mode_file)

    def test_one_switch_routes_keyboard_mouse_and_persists(self):
        self.input.send_key("e")
        self.background.send_key.assert_called_once_with("e", .01)
        self.input.set_mode(SYSTEM)
        self.input.send_key("r")
        self.input.click(4, 5)
        self.input.move(7, 8)
        self.input.scroll(7, 8, 1)
        self.system.send_key.assert_called_once_with("r", .01)
        self.system.click.assert_called_once()
        self.system.move.assert_called_once_with(7, 8)
        self.system.scroll.assert_called_once_with(7, 8, 1)
        self.assertEqual(read_mode(self.mode_file), SYSTEM)
        self.input.set_mode(BACKGROUND)
        self.input.click(1, 2)
        self.background.click.assert_called_once()

    def test_focus_loss_blocks_new_input_but_releases_owned_keys(self):
        self.input.set_mode(SYSTEM)
        self.input.send_key_down("w")
        self.input.mouse_down(key="left")
        self.window.is_foreground.return_value = False
        self.input.send_key("e")
        self.system.send_key.assert_not_called()
        self.system.send_key_up.side_effect = lambda key: self.assertFalse(self.system.check_clickable)
        self.input.on_destroy()
        self.system.send_key_up.assert_called_once_with("w")
        self.system.mouse_up.assert_called_once_with(key="left")
        self.assertTrue(self.system.check_clickable)

    def test_cannot_switch_during_a_held_action_or_rotation(self):
        self.input.send_key_down("w")
        with self.assertRaisesRegex(RuntimeError, "Release all inputs"):
            self.input.set_mode(SYSTEM)
        self.assertEqual(self.input.mode, BACKGROUND)
        executor = SimpleNamespace(current_task=object(), interaction=self.input, reset_scene=Mock())
        with self.assertRaisesRegex(RuntimeError, "Stop the current task"):
            switch_all_inputs(executor, SYSTEM)
        executor.reset_scene.assert_not_called()

    def test_failure_to_focus_does_not_save_system_mode(self):
        self.window.is_foreground.return_value = False
        with self.assertRaisesRegex(RuntimeError, "Focus the game"):
            self.input.set_mode(SYSTEM)
        self.assertEqual(self.input.mode, BACKGROUND)
        self.assertFalse(self.mode_file.exists())


if __name__ == "__main__":
    unittest.main()
