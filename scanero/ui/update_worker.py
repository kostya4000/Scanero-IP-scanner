"""Background workers for GitHub update checks and downloads."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.updater import ReleaseInfo, download_release, fetch_latest_release


class UpdateCheckWorker(QThread):
    found = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self) -> None:  # noqa: D401
        try:
            self.found.emit(fetch_latest_release())
        except Exception as exc:  # pragma: no cover - network dependent
            self.failed.emit(str(exc))


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(int)
    downloaded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, release: ReleaseInfo, parent=None) -> None:
        super().__init__(parent)
        self.release = release

    def run(self) -> None:  # noqa: D401
        try:
            path = download_release(self.release, progress=self.progress.emit)
            self.downloaded.emit(str(path))
        except Exception as exc:  # pragma: no cover - network dependent
            self.failed.emit(str(exc))
