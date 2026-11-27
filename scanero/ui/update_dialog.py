"""Update-available dialog with download and installation progress."""
from __future__ import annotations

import re

from PyQt6.QtCore import QProcess, Qt, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, REPO_URL
from ..core.actions import open_external_url
from ..core.updater import ReleaseInfo, can_install_updates, install_command
from ..i18n import translate_widget_tree, tr
from .icons import icon
from .theme import P, rgba, scale_inline_fonts, sp
from .update_worker import UpdateDownloadWorker
from .widgets import base_font, set_widget_font


def _plain_notes(markdown: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", markdown, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text if len(text) <= 4000 else text[:3990].rstrip() + "…"


class UpdateDialog(QDialog):
    def __init__(
        self,
        release: ReleaseInfo,
        parent: QWidget | None = None,
        *,
        can_install: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.release = release
        self.can_install = can_install_updates() if can_install is None else can_install
        self.installed = False
        self._busy = False
        self._downloaded_path: str | None = None
        self._worker: UpdateDownloadWorker | None = None
        self._install_proc: QProcess | None = None

        self.setWindowTitle(tr("Доступно обновление"))
        self.setModal(True)
        self.setMinimumWidth(sp(540))
        self.setStyleSheet(f"QDialog {{ background: {P.dialog_bg}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(13)
        badge = QLabel()
        badge.setPixmap(icon("download", P.accent, 24).pixmap(24, 24))
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {rgba(P.accent, 0.1)}; border: 1px solid {rgba(P.accent, 0.28)};"
            f" border-radius: 12px;"
        )
        header.addWidget(badge)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Доступно обновление")
        set_widget_font(title, base_font(19, QFont.Weight.DemiBold))
        subtitle = QLabel(tr(
            "Вышла версия {version}. У вас установлена {current}.",
            version=release.version,
            current=__version__,
        ))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {P.muted}; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        notes = _plain_notes(release.notes)
        if notes:
            notes_title = QLabel("Что нового")
            notes_title.setStyleSheet(f"color: {P.dim}; font-size: 11px;")
            layout.addWidget(notes_title)
            self.notes = QLabel(notes)
            self.notes.setTextFormat(Qt.TextFormat.PlainText)
            self.notes.setWordWrap(True)
            self.notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.notes.setStyleSheet(f"color: {P.text_soft}; font-size: 11.5px; line-height: 1.45;")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setMaximumHeight(sp(160))
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
            scroll.setWidget(self.notes)
            layout.addWidget(scroll)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(
            f"QProgressBar {{ background: {P.input_bg}; border: 1px solid {P.border_soft};"
            f" border-radius: 4px; }}"
            f"QProgressBar::chunk {{ border-radius: 3px;"
            f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {P.accent}, stop:1 {P.accent2}); }}"
        )
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {P.muted}; font-size: 11.5px;")
        self.status.setVisible(False)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.later_btn = QPushButton("Позже")
        self.later_btn.setProperty("variant", "ghost")
        self.later_btn.clicked.connect(self.reject)
        buttons.addWidget(self.later_btn)
        self.repo_btn = QPushButton("Открыть релиз")
        self.repo_btn.setProperty("variant", "ghost")
        self.repo_btn.setIcon(icon("external", P.muted, 14))
        self.repo_btn.setIconSize(QSize(14, 14))
        self.repo_btn.clicked.connect(self._open_release)
        self.repo_btn.setVisible(self.can_install)
        buttons.addWidget(self.repo_btn)
        buttons.addStretch(1)
        self.primary = QPushButton("Обновить" if self.can_install else "Открыть релиз")
        self.primary.setProperty("variant", "primary")
        self.primary.setIcon(icon("download" if self.can_install else "external", P.primary_text, 15))
        self.primary.setIconSize(QSize(15, 15))
        self.primary.clicked.connect(self._primary_clicked)
        buttons.addWidget(self.primary)
        layout.addLayout(buttons)

        scale_inline_fonts(self)
        translate_widget_tree(self)

    def _primary_clicked(self) -> None:
        if self.installed:
            self.accept()
            return
        if not self.can_install:
            self._open_release()
            return
        self._start_download()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.later_btn.setVisible(not busy)
        self.repo_btn.setEnabled(not busy)
        self.primary.setEnabled(not busy)

    def _show_status(self, text: str, color: str = P.muted) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-size: 11.5px;")
        self.status.setVisible(True)

    def _start_download(self) -> None:
        if self._worker is not None or not self.release.deb_url:
            if not self.release.deb_url:
                self._open_release()
            return
        self._set_busy(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._show_status("Скачиваем обновление…")
        worker = UpdateDownloadWorker(self.release, self)
        worker.progress.connect(self.progress.setValue)
        worker.downloaded.connect(self._downloaded)
        worker.failed.connect(self._download_failed)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        worker.start()

    def _worker_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()

    def _downloaded(self, path: str) -> None:
        self._downloaded_path = path
        if self.installed:
            return
        self.progress.setValue(100)
        command = install_command(path)
        if not command:
            self._show_status(
                "Не удалось запустить установку. Скачайте пакет вручную со страницы релиза.",
                P.red,
            )
            self._set_busy(False)
            return
        self._show_status("Устанавливаем обновление…")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.finished.connect(self._install_finished)
        self._install_proc = proc
        proc.setProgram(command[0])
        proc.setArguments(command[1:])
        proc.start()

    def _install_finished(self, code: int, status) -> None:
        output = ""
        if self._install_proc is not None:
            output = bytes(self._install_proc.readAll()).decode("utf-8", errors="replace").strip()
        self._install_proc = None
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
            self.installed = True
            self.progress.setValue(100)
            self._show_status("Обновление установлено. Перезапустите приложение.", P.green)
            self.later_btn.setVisible(False)
            self.repo_btn.setVisible(False)
            self.primary.setText(tr("Перезапустить"))
            self.primary.setIcon(icon("refresh", P.primary_text, 15))
            self.primary.setEnabled(True)
            self._busy = False
            return
        detail = output.splitlines()[-1].strip() if output else tr("код {code}", code=code)
        self._show_status(tr("Не удалось установить обновление: {error}", error=detail), P.red)
        self._set_busy(False)

    def _download_failed(self, error: str) -> None:
        self.progress.setVisible(False)
        self._show_status(tr("Не удалось скачать обновление: {error}", error=error), P.red)
        self._set_busy(False)

    def _open_release(self) -> None:
        open_external_url(self.release.page_url or REPO_URL)

    def _thread_busy(self) -> bool:
        return self._busy or (self._worker is not None and self._worker.isRunning())

    def reject(self) -> None:  # noqa: N802
        if self._thread_busy():
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread_busy():
            event.ignore()
            return
        super().closeEvent(event)
