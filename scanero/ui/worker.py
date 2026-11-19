"""Qt wrapper around the synchronous scanner core."""
from __future__ import annotations

import copy
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.scanner import ScanOptions, ScanResult, scan_network


class ScanWorker(QThread):
    found = pyqtSignal(object)
    updated = pyqtSignal(object)
    progress = pyqtSignal(object)
    phase = pyqtSignal(object)
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, targets, options: ScanOptions, range_expr: str, parent=None) -> None:
        super().__init__(parent)
        self._targets = list(targets)
        self._options = options
        self._range_expr = range_expr
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:  # noqa: D401
        def on_event(kind: str, payload: object) -> None:
            if kind == "found":
                self.found.emit(copy.deepcopy(payload))
            elif kind == "updated":
                self.updated.emit(copy.deepcopy(payload))
            elif kind == "progress":
                self.progress.emit(payload)
            elif kind == "phase":
                self.phase.emit(payload)

        try:
            result: ScanResult = scan_network(
                self._targets,
                self._options,
                self._range_expr,
                on_event,
                self.stop_event,
            )
            self.result.emit(result)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))
