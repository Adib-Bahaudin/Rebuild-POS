from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QSpacerItem,
    QSizePolicy,
)

@dataclass(frozen=True)
class VisibilityIconConfig:
    """Menyimpan konfigurasi path ikon untuk fitur visibilitas Access Key.

    Attributes:
        normal: Lokasi file ikon ketika karakter tersembunyi (default).
        pressed: Lokasi file ikon ketika tombol ditekan dan karakter ditampilkan.
    """

    normal: Path
    pressed: Path


class AccessKeyInput(QFrame):
    """Komponen antarmuka kustom untuk kolom input Access Key.

    Menggabungkan QLineEdit dan QPushButton di dalam satu QFrame untuk
    menciptakan tampilan kolom input modern dengan tombol visibilitas terintegrasi.
    """

    def __init__(
        self, icon_config: VisibilityIconConfig, parent: Optional[QWidget] = None
    ) -> None:
        """Menginisialisasi komponen input Access Key beserta interaksi visibilitasnya.

        Args:
            icon_config: Objek VisibilityIconConfig yang berisi path ikon custom.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._icon_config: VisibilityIconConfig = icon_config

        self.setFixedHeight(45)
        self.setObjectName("AccessKeyContainer")
        self.setStyleSheet(
            """
            QFrame#AccessKeyContainer {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QFrame#AccessKeyContainer:focus-within {
                border: 1px solid #89B4FA;
            }
            """
        )

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 0, 8, 0)
        self._layout.setSpacing(8)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Enter your access key")
        self.input_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_field.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.input_field.setStyleSheet(
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                color: #CDD6F4;
                font-size: 14px;
                font-weight: 500;
            }
            """
        )

        self.visibility_button = QPushButton(self)
        self.visibility_button.setFixedSize(QSize(28, 28))
        self.visibility_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.visibility_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.visibility_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            """
        )

        self._layout.addWidget(self.input_field)
        self._layout.addWidget(self.visibility_button)

        self._apply_icon(self._icon_config.normal)
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal tombol dengan logika visibilitas karakter."""
        self.visibility_button.pressed.connect(self._show_key)
        self.visibility_button.released.connect(self._hide_key)

    def _apply_icon(self, icon_path: Path) -> None:
        """Menerapkan ikon ke tombol berdasarkan path yang diberikan.

        Args:
            icon_path: Path menuju file aset ikon.
        """
        resolved_path = icon_path.expanduser().resolve()
        if resolved_path.exists() and resolved_path.is_file():
            self.visibility_button.setIcon(QIcon(str(resolved_path)))
            self.visibility_button.setIconSize(QSize(18, 18))
        else:
            self.visibility_button.setText("O" if "normal" in str(icon_path) else "X")

    def _show_key(self) -> None:
        """Menampilkan karakter input dan mengubah status ikon menjadi pressed."""
        self.input_field.setEchoMode(QLineEdit.EchoMode.Normal)
        self._apply_icon(self._icon_config.pressed)

    def _hide_key(self) -> None:
        """Menyembunyikan karakter input dan mengembalikan status ikon menjadi normal."""
        self.input_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_icon(self._icon_config.normal)

    def get_key(self) -> str:
        """Mengambil teks Access Key yang telah dimasukkan oleh pengguna.

        Returns:
            String yang berisi Access Key.
        """
        return self.input_field.text().strip()


class LoginContent(QWidget):
    """Menampung seluruh elemen antarmuka utama pada proses login.

    Memiliki form input, tombol login, serta tombol bantuan sekunder.
    """

    login_requested = Signal(str)
    create_key_requested = Signal()

    def __init__(
        self, icon_config: VisibilityIconConfig, parent: Optional[QWidget] = None
    ) -> None:
        """Menginisialisasi layout dan komponen form login.

        Args:
            icon_config: Konfigurasi ikon untuk komponen input key.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setFixedWidth(360)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._setup_headers()
        self.key_input = AccessKeyInput(icon_config=icon_config, parent=self)
        self._setup_buttons()

        self._layout.addWidget(self.title_label)
        self._layout.addWidget(self.subtitle_label)
        self._layout.addSpacing(16)
        self._layout.addWidget(self.key_input)
        self._layout.addSpacing(8)
        self._layout.addWidget(self.login_button)
        self._layout.addWidget(self.create_key_button)

        self._connect_signals()

    def _setup_headers(self) -> None:
        """Membangun komponen teks judul dan subjudul pada form login."""
        self.title_label = QLabel("License Activation", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #CDD6F4;
                font-size: 24px;
                font-weight: 700;
            }
            """
        )

        self.subtitle_label = QLabel("Masukkan Access Key Anda untuk melanjutkan", self)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            """
            QLabel {
                color: #BAC2DE;
                font-size: 13px;
                font-weight: 400;
            }
            """
        )

    def _setup_buttons(self) -> None:
        """Membangun tombol aksi utama dan sekunder dengan gaya spesifik."""
        self.login_button = QPushButton("Verify & Login", self)
        self.login_button.setFixedHeight(45)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.setStyleSheet(
            """
            QPushButton {
                background-color: #89B4FA;
                color: #11111B;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #B4BEFE;
            }
            QPushButton:pressed {
                background-color: #74C7EC;
            }
            """
        )

        self.create_key_button = QPushButton("Get Access Key", self)
        self.create_key_button.setFixedHeight(36)
        self.create_key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_key_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #89B4FA;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(137, 180, 250, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(137, 180, 250, 0.2);
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan klik internal tombol ke sinyal emisi publik class."""
        self.login_button.clicked.connect(
            lambda: self.login_requested.emit(self.key_input.get_key())
        )
        self.create_key_button.clicked.connect(self.create_key_requested.emit)


class LoginFooter(QWidget):
    """Menampilkan informasi ringkas pada bagian paling bawah halaman login."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi layout footer berisi dua baris teks.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 24)
        self._layout.setSpacing(4)

        self.info_label = QLabel("Membutuhkan koneksi internet untuk validasi lisensi.", self)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.copyright_label = QLabel("© 2026 Barokah Copy & Printing. All rights reserved.", self)
        self.copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer_style = """
            QLabel {
                color: #7F849C;
                font-size: 11px;
                font-weight: 400;
            }
        """
        self.info_label.setStyleSheet(footer_style)
        self.copyright_label.setStyleSheet(footer_style)

        self._layout.addWidget(self.info_label)
        self._layout.addWidget(self.copyright_label)


class LoginPage(QWidget):
    """Halaman utama Login yang menggabungkan Main Content dan Footer.

    Dirancang agar kompatibel penuh saat disisipkan ke dalam CustomTitleBar
    melalui metode set_content_widget.
    """

    login_requested = Signal(str)
    create_key_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Mengonfigurasi hierarki visual halaman login secara keseluruhan.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            LoginPage {
                background-color: transparent;
            }
            """
        )

        icon_config = VisibilityIconConfig(
            normal=Path("assets/icons/eye_normal.svg"),
            pressed=Path("assets/icons/eye_pressed.svg"),
        )

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self.content_container = LoginContent(icon_config=icon_config, parent=self)
        self.footer_container = LoginFooter(parent=self)

        self.content_container.login_requested.connect(self.login_requested.emit)
        self.content_container.create_key_requested.connect(
            self.create_key_requested.emit
        )

        top_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        bottom_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        content_center_layout = QHBoxLayout()
        content_center_layout.addStretch()
        content_center_layout.addWidget(self.content_container)
        content_center_layout.addStretch()

        self._main_layout.addItem(top_spacer)
        self._main_layout.addLayout(content_center_layout)
        self._main_layout.addItem(bottom_spacer)
        self._main_layout.addWidget(self.footer_container)

