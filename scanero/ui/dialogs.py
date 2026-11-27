"""Modal dialogs: remote shutdown and about."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.actions import open_external_url, remote_shutdown_supported, run_remote_shutdown
from ..core.models import Device
from .. import REPO_URL, __version__
from ..i18n import translate_text, translate_widget_tree
from .icons import icon
from .theme import P, rgba, scale_inline_fonts, sp
from .widgets import LogoWidget, ToggleSwitch, base_font, font, set_widget_font


class ShutdownDialog(QDialog):
    def __init__(self, device: Device, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.device = device
        self.setWindowTitle("Удалённое выключение")
        self.setModal(True)
        self.setMinimumWidth(sp(460))
        self.setStyleSheet(f"QDialog {{ background: {P.dialog_bg}; }}")
        self._proc = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        badge = QLabel()
        badge.setPixmap(icon("power", P.red, 24).pixmap(24, 24))
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {rgba(P.red, 0.1)}; border:1px solid {rgba(P.red, 0.25)}; border-radius:11px;"
        )
        header.addWidget(badge)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Выключить компьютер")
        set_widget_font(title, base_font(17, QFont.Weight.DemiBold))
        subtitle = QLabel(f"{device.name or 'Устройство'} · {device.ip}")
        subtitle.setStyleSheet(f"color: {P.muted}; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        hint = QLabel(
            "Команда отправляется через Samba (net rpc) и работает для Windows-компьютеров "
            "с включённой службой удалённого реестра. Нужны права администратора."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {P.dim}; font-size: 11.5px; line-height: 1.4;")
        layout.addWidget(hint)

        user_label = QLabel("Учётная запись")
        user_label.setStyleSheet(f"color: {P.muted}; font-size: 11px;")
        layout.addWidget(user_label)
        self.user = QLineEdit()
        self.user.setPlaceholderText("Администратор")
        layout.addWidget(self.user)
        pass_label = QLabel("Пароль")
        pass_label.setStyleSheet(f"color: {P.muted}; font-size: 11px;")
        layout.addWidget(pass_label)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Пароль")
        layout.addWidget(self.password)

        options = QFrame()
        options.setObjectName("ShutdownOptions")
        options.setStyleSheet(
            f"QFrame#ShutdownOptions {{ background:{P.input_bg}; border:1px solid {P.border_soft}; border-radius:11px; }}"
        )
        opt_layout = QVBoxLayout(options)
        opt_layout.setContentsMargins(14, 10, 14, 10)
        opt_layout.setSpacing(8)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Принудительное выключение"))
        row1.addStretch(1)
        self.force = ToggleSwitch()
        self.force.setChecked(True)
        row1.addWidget(self.force)
        opt_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Перезагрузить вместо выключения"))
        row2.addStretch(1)
        self.reboot = ToggleSwitch()
        row2.addWidget(self.reboot)
        opt_layout.addLayout(row2)
        for label in options.findChildren(QLabel):
            label.setStyleSheet(f"color: {P.text_soft}; font-size: 12px;")
        layout.addWidget(options)

        self.message = QLineEdit()
        self.message.setPlaceholderText("Сообщение пользователю (необязательно)")
        layout.addWidget(self.message)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {P.muted}; font-size: 11.5px;")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        self.submit = QPushButton("Выключить")
        self.submit.setProperty("variant", "danger")
        self.submit.setIcon(icon("power", P.red, 16))
        self.submit.setIconSize(QSize(16, 16))
        self.submit.clicked.connect(self._run)
        buttons.addWidget(cancel)
        buttons.addWidget(self.submit)
        layout.addLayout(buttons)
        scale_inline_fonts(self)
        translate_widget_tree(self)
        translate_widget_tree(self)

        if not remote_shutdown_supported():
            self.submit.setEnabled(False)
            self.status.setText("Утилита net (samba-common-bin) не найдена в системе.")

    def _run(self) -> None:
        if not self.user.text().strip():
            self.status.setText("Укажите имя пользователя.")
            return
        self.submit.setEnabled(False)
        self.status.setText("Отправляем команду…")
        self._proc = run_remote_shutdown(
            self.device.ip,
            self.user.text().strip(),
            self.password.text(),
            reboot=self.reboot.isChecked(),
            force=self.force.isChecked(),
            message=self.message.text().strip(),
            on_finished=self._done,
        )
        if self._proc is None and translate_text(
            "Утилита net (samba-common-bin) не найдена в системе."
        ) not in self.status.text():
            self.status.setText("Не удалось запустить команду net rpc shutdown.")

    def _done(self, ok: bool, text: str) -> None:
        self.submit.setEnabled(True)
        color = P.green if ok else P.red
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-size: 11.5px;")


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setModal(True)
        self.setFixedWidth(sp(510))
        self.setStyleSheet(f"QDialog {{ background: {P.dialog_bg}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(LogoWidget(46))
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("Scanero IP Сканер")
        set_widget_font(title, base_font(22, QFont.Weight.DemiBold))
        sub = QLabel(f"Версия {__version__} · сканер сети для Ubuntu")
        sub.setStyleSheet(f"color:{P.muted}; font-size:12px;")
        box.addWidget(title)
        box.addWidget(sub)
        row.addLayout(box, 1)
        layout.addLayout(row)
        text = QLabel(
            "Быстрый сканер локальной сети с современным интерфейсом. Находит устройства, "
            "определяет MAC-адреса и производителей, имена NetBIOS/DNS/mDNS/SSDP, "
            "открытые сервисы и операционные системы. Позволяет открывать общие папки, "
            "FTP, HTTP и RDP, отправлять Wake-on-LAN, выключать компьютеры удалённо, "
            "работать в тёмной или светлой теме и экспортировать отчёты."
        )
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setMinimumHeight(sp(135))
        text.setStyleSheet(f"color:{P.text_soft}; font-size:12px;")
        layout.addWidget(text)
        made = QLabel("Сделано с вниманием к деталям · PyQt6 / Ubuntu")
        made.setStyleSheet(f"color:{P.dim}; font-size:11px;")
        layout.addWidget(made)
        buttons = QHBoxLayout()
        repo = QPushButton("Репозиторий на GitHub")
        repo.setProperty("variant", "ghost")
        repo.setIcon(icon("external", P.muted, 15))
        repo.setCursor(Qt.CursorShape.PointingHandCursor)
        repo.clicked.connect(lambda: open_external_url(REPO_URL))
        buttons.addWidget(repo)
        buttons.addStretch(1)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        scale_inline_fonts(self)
        translate_widget_tree(self)
