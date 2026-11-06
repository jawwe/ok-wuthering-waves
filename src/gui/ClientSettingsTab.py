import threading

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

from ok.core.icons import Icon
from ok.ui.qt.kit.buttons import Button
from ok.ui.qt.kit.dialogs import Dialog
from ok.ui.qt.kit.feedback import show_toast
from ok.ui.qt.widget.CustomTab import CustomTab

from src.app_identity import APP_NAME, DATA_ROOT, distribution_version
from src.config_migration import stage_legacy_config
from src.distribution import download_release, latest_release, release_version
from src.input_mode import BACKGROUND, SYSTEM, read_mode, switch_all_inputs


class ClientSettingsTab(CustomTab):
    input_finished = Signal(object)
    update_finished = Signal(object)
    icon = Icon.APPLICATION

    def __init__(self):
        super().__init__()
        content = QWidget(self.view)
        layout = QVBoxLayout(content)
        self.input_status = QLabel()
        self.input_status.setWordWrap(True)
        self.input_button = Button(self.tr("Switch all keyboard and mouse input"), variant="primary")
        self.input_button.clicked.connect(self._toggle_input)
        layout.addWidget(self.input_status)
        layout.addWidget(self.input_button)
        self.input_finished.connect(self._input_finished)
        self._show_input_mode(read_mode())
        description = QLabel(self.tr("System input uses the real keyboard and cursor. Keep the game focused. Changes apply between tasks."))
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addSpacing(24)
        self.update_status = QLabel(f"{APP_NAME} {distribution_version()}")
        self.update_status.setWordWrap(True)
        self.update_button = Button(self.tr("Check independent channel"))
        self.update_button.clicked.connect(self._check_update)
        self.download_button = Button(self.tr("Download portable update"))
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._download_update)
        self.open_downloads = Button(self.tr("Open update folder"))
        self.open_downloads.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_ROOT / "updates"))))
        for widget in (self.update_status, self.update_button, self.download_button, self.open_downloads):
            layout.addWidget(widget)
        self.update_finished.connect(self._update_finished)
        self.release = None
        layout.addSpacing(24)
        migration_description = QLabel(self.tr("Import old configuration once. The current configuration is backed up and replaced on the next start."))
        migration_description.setWordWrap(True)
        layout.addWidget(migration_description)
        self.import_button = Button(self.tr("Import old configuration"))
        self.import_button.clicked.connect(self._import_config)
        layout.addWidget(self.import_button)
        self.add_widget(content)

    @property
    def name(self):
        return self.tr("Client Settings")

    def _show_input_mode(self, mode):
        label = self.tr("System keyboard and mouse") if mode == SYSTEM else self.tr("Background window messages")
        self.input_status.setText(self.tr("Current input mode: {mode}").format(mode=label))

    def _toggle_input(self):
        executor = self.executor
        if executor is None or getattr(executor, "current_task", None) is not None:
            show_toast(self.window(), self.tr("Stop the current task before switching input mode."), tone="danger")
            return
        mode = BACKGROUND if getattr(executor.interaction, "mode", read_mode()) == SYSTEM else SYSTEM
        self.input_button.setEnabled(False)
        try:
            job = executor.submit(lambda: switch_all_inputs(executor, mode), name="change input mode")
            job.future.add_done_callback(self.input_finished.emit)
        except Exception as error:
            self.input_button.setEnabled(True)
            show_toast(self.window(), self.tr(str(error)), tone="danger")

    def _input_finished(self, future):
        self.input_button.setEnabled(True)
        try:
            self._show_input_mode(future.result())
        except Exception as error:
            show_toast(self.window(), self.tr(str(error)), tone="danger")

    def _background(self, action, kind):
        def run():
            try:
                result = (kind, action(), None)
            except Exception as error:
                result = (kind, None, str(error))
            try:
                self.update_finished.emit(result)
            except RuntimeError:
                pass
        threading.Thread(target=run, name="DistributionCheck", daemon=True).start()

    def _check_update(self):
        self.update_button.setEnabled(False)
        self._background(latest_release, "check")

    def _download_update(self):
        self.download_button.setEnabled(False)
        self._background(lambda: download_release(self.release), "download")

    def _update_finished(self, result):
        kind, value, error = result
        self.update_button.setEnabled(True)
        if error:
            self.update_status.setText(self.tr("Update check failed: {error}").format(error=error))
            self.download_button.setEnabled(self.release is not None)
            return
        if kind == "download":
            self.update_status.setText(self.tr("Update saved to {path}. Close the app and extract it over this portable folder; keep the data folder.").format(path=value))
        else:
            self.release = value
            current = release_version("aster-v" + distribution_version())
            newer = value is not None and (current is None or value["version"] > current)
            self.download_button.setEnabled(newer)
            self.update_status.setText(self.tr("Available version: {version}").format(version=value["tag"]) if newer else self.tr("No newer independent release available."))

    def _import_config(self):
        if self.executor is not None and getattr(self.executor, "current_task", None) is not None:
            show_toast(self.window(), self.tr("Stop the current task before importing configuration."), tone="danger")
            return
        source = QFileDialog.getExistingDirectory(self.window(), self.tr("Choose old configuration folder"))
        if not source:
            return
        dialog = Dialog(self.window(), self.tr("Import old configuration"),
                        self.tr("The current configuration will be backed up and replaced after restart. Continue?"))
        if not dialog.exec():
            return
        try:
            count = stage_legacy_config(source)
            show_toast(self.window(), self.tr("Staged {count} files. Restart to finish importing.").format(count=count))
        except Exception as error:
            show_toast(self.window(), self.tr(str(error)), tone="danger")
