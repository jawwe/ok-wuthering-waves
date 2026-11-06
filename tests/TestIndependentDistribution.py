import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app_identity import APP_NAME, REPOSITORY
from src.config_migration import apply_pending_migration, stage_legacy_config
from src.distribution import API_URL, download_release, latest_release


class TestIndependentDistribution(unittest.TestCase):
    def test_only_complete_independent_releases_are_selected(self):
        def release(tag, version, repository=REPOSITORY):
            name = f"{APP_NAME}-{version}-windows-x64.zip"
            return {"tag_name": tag, "assets": [
                {"name": asset, "browser_download_url": f"https://github.com/{repository}/releases/download/{tag}/{asset}"}
                for asset in (name, name + ".sha256")]}
        payload = [release("v99.0.0", "99.0.0"), release("aster-v1.0.0", "1.0.0"),
                   release("aster-v2.0.0", "2.0.0", "ok-oldking/ok-wuthering-waves")]
        def opener(request, **kwargs):
            self.assertEqual(request.full_url, API_URL)
            return io.BytesIO(json.dumps(payload).encode())
        self.assertEqual(latest_release(opener)["tag"], "aster-v1.0.0")

    def test_checksum_failure_does_not_publish_download(self):
        tag = "aster-v1.0.0"
        name = f"{APP_NAME}-1.0.0-windows-x64.zip"
        prefix = f"https://github.com/{REPOSITORY}/releases/download/{tag}/"
        release = {"tag": tag, "name": name, "archive": prefix + name, "checksum": prefix + name + ".sha256"}
        def opener(request, **kwargs):
            return io.BytesIO(("0" * 64).encode() if request.full_url.endswith("sha256") else b"changed")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                download_release(release, folder, opener)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_import_is_staged_and_applied_once_with_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, data = root / "old", root / "data"
            source.mkdir()
            (source / "Task.json").write_text('{"setting": "old"}')
            (data / "configs").mkdir(parents=True)
            (data / "configs" / "Task.json").write_text('{"setting": "new"}')
            self.assertEqual(stage_legacy_config(source, data), 1)
            self.assertEqual(json.loads((data / "configs/Task.json").read_text())["setting"], "new")
            self.assertTrue(apply_pending_migration(data))
            self.assertEqual(json.loads((data / "configs/Task.json").read_text())["setting"], "old")
            self.assertEqual(json.loads((data / "config-before-import/Task.json").read_text())["setting"], "new")
            self.assertFalse(apply_pending_migration(data))
            with self.assertRaisesRegex(ValueError, "already been imported"):
                stage_legacy_config(source, data)

    def test_invalid_configuration_does_not_stage_partial_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "old"
            source.mkdir()
            (source / "bad.json").write_text("invalid")
            with self.assertRaises(ValueError):
                stage_legacy_config(source, root / "data")
            self.assertEqual(list((root / "data").iterdir()), [])

    def test_failed_import_commit_restores_current_configuration_and_can_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, data = root / "old", root / "data"
            source.mkdir()
            (source / "Task.json").write_text('{"setting":"old"}')
            (data / "configs").mkdir(parents=True)
            (data / "configs/Task.json").write_text('{"setting":"current"}')
            stage_legacy_config(source, data)
            with patch("src.config_migration.atomic_write", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    apply_pending_migration(data)
            self.assertEqual(json.loads((data / "configs/Task.json").read_text())["setting"], "current")
            self.assertTrue((data / "import-pending.json").is_file())
            self.assertTrue(apply_pending_migration(data))
            self.assertEqual(json.loads((data / "configs/Task.json").read_text())["setting"], "old")


if __name__ == "__main__":
    unittest.main()
