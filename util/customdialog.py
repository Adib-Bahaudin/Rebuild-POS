"""Modul dialog kustom PySide6 dengan title bar tanpa bingkai bawaan OS."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from config import get_asset_path
from ui.customwindowtitlebar import ButtonIconPaths, TitleBarButton


@dataclass(frozen=True, slots=True)
class DialogTitleBarConfig:
    """Konfigurasi visual untuk title bar dan wadah dialog kustom.

    Attributes:
        titlebar_color: Warna latar belakang title bar dalam format CSS.
        title_text_color: Warna teks judul pada title bar.
        close_btn_color: Warna latar default tombol tutup teks.
        close_btn_text_color: Warna teks tombol tutup default.
        close_btn_hover_color: Warna latar tombol tutup saat kursor di atasnya.
        close_btn_pressed_color: Warna latar tombol tutup saat ditekan.
        border_color: Warna garis tepi dialog dan pemisah bawah title bar.
        background_color: Warna latar belakang utama wadah dialog.
        height: Tinggi title bar dalam piksel.
        close_symbol: Simbol teks alternatif jika ikon SVG tidak digunakan.
        close_icon_paths: Kumpulan path ikon normal dan hover untuk tombol tutup.
    """

    titlebar_color: str = "#181825"
    title_text_color: str = "#CDD6F4"
    close_btn_color: str = "transparent"
    close_btn_text_color: str = "#CDD6F4"
    close_btn_hover_color: str = "#E81123"
    close_btn_pressed_color: str = "#F1707A"
    border_color: str = "#313244"
    background_color: str = "#181825"
    height: int = 36
    close_symbol: str | None = None
    close_icon_paths: ButtonIconPaths | None = None


class _CustomTitleBar(QFrame):
    """Title bar kustom dengan dukungan drag, ikon otomatis, dan tombol tutup."""

    def __init__(self, dialog: QDialog, config: DialogTitleBarConfig) -> None:
        """Menginisialisasi title bar kustom untuk dialog.

        Args:
            dialog: Instance dialog induk yang dikendalikan oleh title bar.
            config: Objek konfigurasi tampilan dan perilaku title bar.
        """
        super().__init__(dialog)
        self._dialog: QDialog = dialog
        self._drag_offset: QPoint | None = None

        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(config.height)

        title_layout = QHBoxLayout(self)
        title_layout.setContentsMargins(10, 0, 0, 0)
        title_layout.setSpacing(8)

        self._icon_label: QLabel = QLabel(self)
        self._icon_label.setObjectName("CustomTitleIcon")
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setScaledContents(True)
        self._icon_label.hide()

        self._title_label: QLabel = QLabel(self)
        self._title_label.setObjectName("CustomTitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._close_btn: TitleBarButton | QPushButton
        if config.close_icon_paths is not None:
            self._close_btn = TitleBarButton(
                icon_paths=config.close_icon_paths,
                parent=self,
                button_size=QSize(42, config.height),
                icon_size=QSize(14, 14),
                hover_bg_color=config.close_btn_hover_color,
                pressed_bg_color=config.close_btn_pressed_color,
            )
        else:
            self._close_btn = QPushButton(config.close_symbol or "✕", self)
            self._close_btn.setObjectName("CustomCloseButton")
            self._close_btn.setFixedSize(40, config.height)
            self._close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._close_btn.clicked.connect(self._dialog.reject)

        title_layout.addWidget(self._icon_label)
        title_layout.addWidget(self._title_label, 1)
        title_layout.addWidget(self._close_btn)

        self.setStyleSheet(
            f"""
            QFrame#CustomTitleBar {{
                background-color: {config.titlebar_color};
                border: none;
                border-bottom: 1px solid {config.border_color};
            }}
            QLabel#CustomTitleLabel {{
                color: {config.title_text_color};
                font-weight: 600;
                font-size: 13px;
                background: transparent;
            }}
            QLabel#CustomTitleIcon {{
                background: transparent;
            }}
            QPushButton#CustomCloseButton {{
                background-color: {config.close_btn_color};
                color: {config.close_btn_text_color};
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#CustomCloseButton:hover {{
                background-color: {config.close_btn_hover_color};
                color: #FFFFFF;
            }}
            QPushButton#CustomCloseButton:pressed {{
                background-color: {config.close_btn_pressed_color};
                color: #FFFFFF;
            }}
            """
        )

    def set_title(self, title: str) -> None:
        """Memperbarui teks judul yang ditampilkan pada title bar.

        Args:
            title: Teks judul dialog baru.
        """
        self._title_label.setText(title)

    def set_icon(self, icon: QIcon) -> None:
        """Memperbarui ikon jendela yang ditampilkan pada sisi kiri title bar.

        Args:
            icon: Objek ikon yang akan dirender pada ukuran 16x16 piksel.
        """
        if not icon.isNull():
            pixmap = icon.pixmap(16, 16)
            if not pixmap.isNull():
                self._icon_label.setPixmap(pixmap)
                self._icon_label.show()
                return
        self._icon_label.clear()
        self._icon_label.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Memulai operasi geser jendela ketika tombol kiri mouse ditekan.

        Args:
            event: Event penekanan tombol mouse.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Memindahkan posisi dialog mengikuti pergerakan kursor saat digeser.

        Args:
            event: Event pergerakan kursor mouse.
        """
        if self._drag_offset is not None and bool(
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Mengakhiri operasi geser jendela saat tombol mouse dilepas.

        Args:
            event: Event pelepasan tombol mouse.
        """
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class CustomDialog(QDialog):
    """Pengganti drop-in QDialog dengan title bar kustom tanpa bingkai OS.

    Mendukung seluruh fungsionalitas standar QDialog seperti exec, accept,
    reject, setWindowTitle, setWindowIcon, serta pengaturan layout langsung
    melalui setLayout atau properti content_widget.
    """

    CLOSE_ICON_NORMAL: str = "icons/close.svg"
    CLOSE_ICON_HOVER: str = "icons/close_hover.svg"

    def __init__(
        self,
        parent: QWidget | None = None,
        flags: Qt.WindowType | None = None,
        *,
        titlebar_config: DialogTitleBarConfig | None = None,
    ) -> None:
        """Menginisialisasi CustomDialog dengan title bar dan area konten.

        Args:
            parent: Widget induk opsional untuk dialog.
            flags: Flag jendela tambahan yang digabungkan dengan frameless dialog.
            titlebar_config: Konfigurasi kustom opsional untuk gaya title bar.
        """
        base_flags = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        if flags is not None:
            base_flags |= flags
        super().__init__(parent, base_flags)

        resolved_config = self._resolve_config(titlebar_config)

        self._container: QFrame = QFrame(self)
        self._container.setObjectName("CustomDialogContainer")
        self._container.setStyleSheet(
            f"""
            QFrame#CustomDialogContainer {{
                background-color: {resolved_config.background_color};
                border: 1px solid {resolved_config.border_color};
                border-radius: 0px;
            }}
            """
        )

        self._title_bar: _CustomTitleBar = _CustomTitleBar(
            dialog=self,
            config=resolved_config,
        )

        self._content_widget: QWidget = QWidget(self._container)
        self._content_widget.setObjectName("CustomDialogContent")
        self._content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: transparent;
            }
            """
        )

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)
        container_layout.addWidget(self._title_bar)
        container_layout.addWidget(self._content_widget, 1)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._container)
        super().setLayout(outer_layout)

        self._update_titlebar_icon()

    @property
    def content_widget(self) -> QWidget:
        """Mengembalikan widget area konten di bawah title bar kustom.

        Returns:
            Widget penampung isi utama dialog.
        """
        return self._content_widget

    @property
    def title_bar(self) -> _CustomTitleBar:
        """Mengembalikan instance title bar kustom milik dialog.

        Returns:
            Instance _CustomTitleBar yang terpasang pada dialog.
        """
        return self._title_bar

    def _resolve_config(
        self,
        titlebar_config: DialogTitleBarConfig | None,
    ) -> DialogTitleBarConfig:
        """Menyusun konfigurasi akhir termasuk resolusi otomatis ikon tutup SVG.

        Args:
            titlebar_config: Konfigurasi awal yang diberikan pemanggil, jika ada.

        Returns:
            Instance DialogTitleBarConfig yang siap dipakai oleh title bar.
        """
        config = titlebar_config or DialogTitleBarConfig()
        if config.close_icon_paths is not None or config.close_symbol is not None:
            return config

        normal_path: Path = get_asset_path(self.CLOSE_ICON_NORMAL)
        hover_path: Path = get_asset_path(self.CLOSE_ICON_HOVER)
        if not (normal_path.exists() and hover_path.exists()):
            return config

        return DialogTitleBarConfig(
            titlebar_color=config.titlebar_color,
            title_text_color=config.title_text_color,
            close_btn_color=config.close_btn_color,
            close_btn_text_color=config.close_btn_text_color,
            close_btn_hover_color=config.close_btn_hover_color,
            close_btn_pressed_color=config.close_btn_pressed_color,
            border_color=config.border_color,
            background_color=config.background_color,
            height=config.height,
            close_symbol=config.close_symbol,
            close_icon_paths=ButtonIconPaths(
                normal=normal_path,
                hover=hover_path,
            ),
        )

    def _resolve_native_icon(self) -> QIcon:
        """Menentukan ikon jendela mengikuti hierarki dialog, parent, app, lalu style.

        Returns:
            Objek QIcon yang valid untuk ditampilkan di title bar.
        """
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

    def _update_titlebar_icon(self) -> None:
        """Menyelaraskan ikon pada title bar dengan ikon jendela aktif."""
        self._title_bar.set_icon(self._resolve_native_icon())

    def setLayout(self, arg__1: QLayout) -> None:
        """Menerapkan layout langsung ke area konten dialog di bawah title bar.

        Args:
            arg__1: Objek layout yang akan dipasang pada area konten.
        """
        self._content_widget.setLayout(arg__1)

    def layout(self) -> QLayout | None:
        """Mengembalikan layout yang terpasang pada area konten dialog.

        Returns:
            Objek QLayout milik area konten.
        """
        return self._content_widget.layout()

    def setWindowTitle(self, arg__1: str) -> None:
        """Menetapkan judul jendela sekaligus memperbarui teks pada title bar.

        Args:
            arg__1: Judul baru untuk dialog.
        """
        super().setWindowTitle(arg__1)
        self._title_bar.set_title(arg__1)

    def setWindowIcon(self, icon: QIcon | QPixmap) -> None:
        """Menetapkan ikon jendela sekaligus memperbarui ikon pada title bar.

        Args:
            icon: Ikon atau pixmap baru untuk dialog.
        """
        super().setWindowIcon(icon)
        self._update_titlebar_icon()

    def showEvent(self, event: QShowEvent) -> None:
        """Memastikan ikon title bar diperbarui setiap kali dialog ditampilkan.

        Args:
            event: Event kemunculan jendela dialog.
        """
        self._update_titlebar_icon()
        super().showEvent(event)