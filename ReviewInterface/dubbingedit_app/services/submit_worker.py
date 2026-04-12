from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QThread, pyqtSignal


class FunctionWorker(QThread):
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, fn: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self._fn()
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
