from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from config import get_asset_path
from ui.customwindowtitlebar import ButtonIconPaths, TitleBarButton


class _CustomTitleBar(QFrame):
    """Title bar kustom dengan dukungan drag, icon otomatis, dan tombol close kustom."""

    def __init__(
        self,
        dialog: QDialog,
        titlebar_color: str,
        title_text_color: str,
        close_btn_color: str,
        close_btn_text_color: str,
        close_btn_hover_color: str,
        close_btn_pressed_color: str,
        height: int = 36,
        close_symbol: str | None = None,
        close_icon_paths: ButtonIconPaths | None = None,
        bottom_border_color: str = "#313244",
    ):
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset = None

        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("CustomTitleIcon")
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setScaledContents(True)
        self._icon_label.hide()

        self._title_label = QLabel(self)
        self._title_label.setObjectName("CustomTitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if close_icon_paths is not None:
            self._close_btn = TitleBarButton(
                icon_paths=close_icon_paths,
                parent=self,
                button_size=QSize(42, height),
                icon_size=QSize(14, 14),
                hover_bg_color=close_btn_hover_color,
                pressed_bg_color=close_btn_pressed_color,
            )
        else:
            self._close_btn = QPushButton(close_symbol or "✕", self)
            self._close_btn.setObjectName("CustomCloseButton")
            self._close_btn.setFixedSize(40, height)
            self._close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._close_btn.clicked.connect(self._dialog.reject)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._title_label, 1)
        layout.addWidget(self._close_btn)

        self.setStyleSheet(
            f"""
            QFrame#CustomTitleBar {{
                background-color: {titlebar_color};
                border: none;
                border-bottom: 1px solid {bottom_border_color};
            }}
            QLabel#CustomTitleLabel {{
                color: {title_text_color};
                font-weight: 600;
                font-size: 13px;
                background: transparent;
            }}
            QLabel#CustomTitleIcon {{
                background: transparent;
            }}
            QPushButton#CustomCloseButton {{
                background-color: {close_btn_color};
                color: {close_btn_text_color};
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#CustomCloseButton:hover {{
                background-color: {close_btn_hover_color};
                color: #FFFFFF;
            }}
            QPushButton#CustomCloseButton:pressed {{
                background-color: {close_btn_pressed_color};
                color: #FFFFFF;
            }}
            """
        )

    def set_title(self, title: str):
        self._title_label.setText(title)

    def set_icon(self, icon: QIcon):
        if not icon.isNull():
            pixmap = icon.pixmap(16, 16)
            if not pixmap.isNull():
                self._icon_label.setPixmap(pixmap)
                self._icon_label.show()
                return
        self._icon_label.clear()
        self._icon_label.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class CustomInputDialog(QDialog):
    """
    Pengganti drop-in QInputDialog (PySide6) dengan title bar dan tombol close kustom.
    Signature pemanggilan dan return value sama persis dengan QInputDialog.
    """

    TITLEBAR_COLOR = "#181825"
    TITLE_TEXT_COLOR = "#CDD6F4"
    CLOSE_BTN_COLOR = "transparent"
    CLOSE_BTN_TEXT_COLOR = "#CDD6F4"
    CLOSE_BTN_HOVER_COLOR = "#E81123"
    CLOSE_BTN_PRESSED_COLOR = "#F1707A"
    BORDER_COLOR = "#313244"
    TITLEBAR_HEIGHT = 36
    CLOSE_ICON_NORMAL = "icons/close.svg"
    CLOSE_ICON_HOVER = "icons/close_hover.svg"
    CLOSE_SYMBOL = None

    def __init__(
        self,
        parent=None,
        flags: Qt.WindowType | None = None,
        *,
        titlebar_color: str | None = None,
        title_text_color: str | None = None,
        close_btn_color: str | None = None,
        close_btn_text_color: str | None = None,
        close_btn_hover_color: str | None = None,
        close_btn_pressed_color: str | None = None,
        border_color: str | None = None,
        titlebar_height: int | None = None,
        close_symbol: str | None = None,
        close_icon_paths: ButtonIconPaths | None = None,
    ):
        base_flags = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        if flags is not None:
            base_flags |= flags
        super().__init__(parent, base_flags)

        resolved_close_icon_paths = close_icon_paths
        if resolved_close_icon_paths is None and close_symbol is None:
            normal_path = get_asset_path(self.CLOSE_ICON_NORMAL)
            hover_path = get_asset_path(self.CLOSE_ICON_HOVER)
            if normal_path.exists() and hover_path.exists():
                resolved_close_icon_paths = ButtonIconPaths(
                    normal=normal_path,
                    hover=hover_path,
                )

        effective_border_color = border_color or self.BORDER_COLOR
        self._container = QFrame(self)
        self._container.setObjectName("CustomInputContainer")
        self._container.setStyleSheet(
            f"""
            QFrame#CustomInputContainer {{
                background-color: #181825;
                border: 1px solid {effective_border_color};
                border-radius: 0px;
            }}
            """
        )

        self._title_bar = _CustomTitleBar(
            dialog=self,
            titlebar_color=titlebar_color or self.TITLEBAR_COLOR,
            title_text_color=title_text_color or self.TITLE_TEXT_COLOR,
            close_btn_color=close_btn_color or self.CLOSE_BTN_COLOR,
            close_btn_text_color=close_btn_text_color or self.CLOSE_BTN_TEXT_COLOR,
            close_btn_hover_color=close_btn_hover_color or self.CLOSE_BTN_HOVER_COLOR,
            close_btn_pressed_color=(
                close_btn_pressed_color or self.CLOSE_BTN_PRESSED_COLOR
            ),
            height=titlebar_height or self.TITLEBAR_HEIGHT,
            close_symbol=close_symbol or self.CLOSE_SYMBOL,
            close_icon_paths=resolved_close_icon_paths,
            bottom_border_color=effective_border_color,
        )

        self._input_dialog = QInputDialog(self._container)
        self._input_dialog.setWindowFlags(Qt.WindowType.Widget)
        self._input_dialog.accepted.connect(self.accept)
        self._input_dialog.rejected.connect(self.reject)

        self._apply_theme_style()

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._title_bar)
        container_layout.addWidget(self._input_dialog)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._container)

        self.setMinimumWidth(380)
        self._update_titlebar_icon()

    def _apply_theme_style(self) -> None:
        """Menerapkan gaya visual gelap selaras tema POS pada dialog input."""
        self._input_dialog.setStyleSheet(
            """
            QInputDialog {
                background-color: #181825;
                color: #CDD6F4;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 500;
                background-color: transparent;
                padding-bottom: 4px;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 7px 12px;
                color: #CDD6F4;
                font-size: 14px;
                font-weight: bold;
                selection-background-color: #89B4FA;
                selection-color: #11111B;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #2ECC71;
                background-color: #11111B;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 3px;
                width: 24px;
                margin: 1px 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #313244;
                border-color: #2ECC71;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #CDD6F4;
                width: 0px;
                height: 0px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #CDD6F4;
                width: 0px;
                height: 0px;
            }
            QComboBox {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 7px 12px;
                color: #CDD6F4;
                font-size: 13px;
            }
            QComboBox:focus {
                border: 1px solid #2ECC71;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #313244;
            }
            QComboBox QAbstractItemView {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #313244;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
            }
            QDialogButtonBox QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 600;
                min-width: 80px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
            }
            QDialogButtonBox QPushButton:pressed {
                background-color: #181825;
            }
            QDialogButtonBox QPushButton[default="true"] {
                background-color: #2ECC71;
                color: #11111B;
                font-weight: bold;
            }
            QDialogButtonBox QPushButton[default="true"]:hover {
                background-color: #27AE60;
                color: #FFFFFF;
            }
            QDialogButtonBox QPushButton[default="true"]:pressed {
                background-color: #1E8449;
            }
            """
        )

    def _resolve_native_icon(self) -> QIcon:
        """Mengikuti hierarki icon title bar asli: dialog -> parent -> app -> style standar."""
        icon = self.windowIcon()
        if not icon.isNull():
            return icon

        parent = self.parentWidget()
        if parent is not None:
            parent_icon = parent.window().windowIcon()
            if not parent_icon.isNull():
                return parent_icon

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app_icon = app.windowIcon()
            if not app_icon.isNull():
                return app_icon

        return self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton)

    def _update_titlebar_icon(self):
        self._title_bar.set_icon(self._resolve_native_icon())

    def _style_dialog_buttons(self) -> None:
        """Menyesuaikan tombol OK dan Cancel agar menggunakan kursor pointer."""
        button_box = self._input_dialog.findChild(QDialogButtonBox)
        if button_box:
            for btn in button_box.buttons():
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        self._title_bar.set_title(title)
        self._input_dialog.setWindowTitle(title)

    def setWindowIcon(self, icon: QIcon | QPixmap) -> None:
        super().setWindowIcon(icon)
        self._update_titlebar_icon()

    def showEvent(self, event):
        self._update_titlebar_icon()
        self._style_dialog_buttons()
        super().showEvent(event)

    def __getattr__(self, name: str):
        input_dialog = self.__dict__.get("_input_dialog")
        if input_dialog is not None:
            return getattr(input_dialog, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    # =========================================================================
    # Static Methods (Identik dengan PySide6 QInputDialog)
    # =========================================================================

    @classmethod
    def getText(
        cls,
        parent,
        title: str,
        label: str,
        echo: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal,
        text: str = "",
        flags: Qt.WindowType | None = None,
        inputMethodHints: Qt.InputMethodHint = Qt.InputMethodHint.ImhNone,
    ) -> tuple[str, bool]:
        dialog = cls(parent, flags)
        dialog.setWindowTitle(title)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setLabelText(label)
        dialog.setTextEchoMode(echo)
        dialog.setTextValue(text)
        dialog.setInputMethodHints(inputMethodHints)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (dialog.textValue() if ok else "", ok)

    @classmethod
    def getMultiLineText(
        cls,
        parent,
        title: str,
        label: str,
        text: str = "",
        flags: Qt.WindowType | None = None,
        inputMethodHints: Qt.InputMethodHint = Qt.InputMethodHint.ImhNone,
    ) -> tuple[str, bool]:
        dialog = cls(parent, flags)
        dialog.setWindowTitle(title)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setOption(
            QInputDialog.InputDialogOption.UsePlainTextEditForTextInput, True
        )
        dialog.setLabelText(label)
        dialog.setTextValue(text)
        dialog.setInputMethodHints(inputMethodHints)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (dialog.textValue() if ok else "", ok)

    @classmethod
    def getInt(
        cls,
        parent,
        title: str,
        label: str,
        value: int = 0,
        minValue: int = -2147483647,
        maxValue: int = 2147483647,
        step: int = 1,
        flags: Qt.WindowType | None = None,
    ) -> tuple[int, bool]:
        dialog = cls(parent, flags)
        dialog.setWindowTitle(title)
        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        dialog.setLabelText(label)
        dialog.setIntRange(minValue, maxValue)
        dialog.setIntStep(step)
        dialog.setIntValue(value)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (dialog.intValue() if ok else value, ok)

    @classmethod
    def getDouble(
        cls,
        parent,
        title: str,
        label: str,
        value: float = 0.0,
        minValue: float = -2147483647.0,
        maxValue: float = 2147483647.0,
        decimals: int = 1,
        flags: Qt.WindowType | None = None,
        step: float = 1.0,
    ) -> tuple[float, bool]:
        dialog = cls(parent, flags)
        dialog.setWindowTitle(title)
        dialog.setInputMode(QInputDialog.InputMode.DoubleInput)
        dialog.setLabelText(label)
        dialog.setDoubleDecimals(decimals)
        dialog.setDoubleRange(minValue, maxValue)
        dialog.setDoubleStep(step)
        dialog.setDoubleValue(value)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (dialog.doubleValue() if ok else value, ok)

    @classmethod
    def getItem(
        cls,
        parent,
        title: str,
        label: str,
        items,
        current: int = 0,
        editable: bool = True,
        flags: Qt.WindowType | None = None,
        inputMethodHints: Qt.InputMethodHint = Qt.InputMethodHint.ImhNone,
    ) -> tuple[str, bool]:
        items_list = list(items)
        dialog = cls(parent, flags)
        dialog.setWindowTitle(title)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setLabelText(label)
        dialog.setComboBoxItems(items_list)
        dialog.setComboBoxEditable(editable)
        dialog.setInputMethodHints(inputMethodHints)

        default_text = ""
        if items_list and 0 <= current < len(items_list):
            default_text = items_list[current]
            dialog.setTextValue(default_text)
            combo = dialog._input_dialog.findChild(QComboBox)
            if combo is not None:
                combo.setCurrentIndex(current)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (dialog.textValue() if ok else default_text, ok)