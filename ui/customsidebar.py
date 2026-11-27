"""Modul komponen sidebar kustom untuk navigasi aplikasi POS."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from config import get_asset_path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QEnterEvent,
    QIcon,
    QPaintEvent,
    QPainter,
)
from PySide6.QtWidgets import (
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from util.customtooltip import TooltipPosition, attach_tooltip


@dataclass(frozen=True)
class SidebarIconPaths:
    """Menyimpan konfigurasi path ikon sidebar untuk status normal dan hover.

    Attributes:
        normal: Path file ikon untuk tampilan normal.
        hover: Path file ikon untuk tampilan hover atau aktif.
    """

    normal: Path
    hover: Path


SIDEBAR_ICONS_CONFIG: Dict[str, Dict[str, str]] = {
    "dashboard": {"normal": "assets/icons/Dash_Normal.png", "hover": "assets/icons/Dash_Hover.png"},
    "history": {"normal": "assets/icons/hist_normal.png", "hover": "assets/icons/hist_hover.png"},
    "restock": {"normal": "assets/icons/restock_normal.png", "hover": "assets/icons/restock_hover.png"},
    "product": {"normal": "assets/icons/prod_normal.png", "hover": "assets/icons/prod_hover.png"},
    "report": {"normal": "assets/icons/trx_normal.png", "hover": "assets/icons/trx_hover.png"},
    "people": {"normal": "assets/icons/cust_normal.png", "hover": "assets/icons/cust_hover.png"},
    "settings": {"normal": "assets/icons/set_normal.png", "hover": "assets/icons/set_hover.png"},
}

SIDEBAR_TOOLTIPS: dict[str, str] = {
    "dashboard": "Dashboard",
    "history": "Riwayat Transaksi",
    "restock": "Tambah Stok",
    "product": "Manajemen Produk",
    "report": "Laporan Penjualan",
    "people": "Data Pelanggan",
    "settings": "Pengaturan",
}

def validate_sidebar_icons(config: Dict[str, Dict[str, str]]) -> List[SidebarIconPaths]:
    """Memeriksa keberadaan file fisik ikon sebelum aplikasi dimuat.

    Args:
        config: Dictionary konfigurasi path ikon sidebar.

    Returns:
        List objek SidebarIconPaths yang telah tervalidasi.

    Raises:
        FileNotFoundError: Jika ada path ikon yang tidak ditemukan di disk.
    """
    validated_paths: List[SidebarIconPaths] = []
    for key, paths in config.items():
        normal_path = get_asset_path(paths["normal"])
        hover_path = get_asset_path(paths["hover"])

        if not normal_path.exists() or not normal_path.is_file():
            raise FileNotFoundError(
                f"GAGAL MEMUAT: Ikon Sidebar (normal) untuk '{key}' tidak ditemukan di {normal_path}"
            )
        if not hover_path.exists() or not hover_path.is_file():
            raise FileNotFoundError(
                f"GAGAL MEMUAT: Ikon Sidebar (hover) untuk '{key}' tidak ditemukan di {hover_path}"
            )

        validated_paths.append(SidebarIconPaths(normal=normal_path, hover=hover_path))

    return validated_paths


class SidebarButton(QPushButton):
    """Tombol sidebar kustom dengan dukungan animasi transisi ikon cross-fade.

    Attributes:
        is_active: Status penanda apakah tombol ini sedang aktif dipilih.
    """

    def __init__(
        self,
        icon_paths: SidebarIconPaths,
        is_active: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Menginisialisasi tombol sidebar dengan konfigurasi ikon dan animasi hover.

        Args:
            icon_paths: Pasangan path ikon normal dan hover.
            is_active: Status awal keaktifan tombol.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = is_active

        self._normal_icon = QIcon(str(icon_paths.normal))
        self._hover_icon = QIcon(str(icon_paths.hover))

        self._hover_progress: float = 1.0 if is_active else 0.0

        self._animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def get_hover_progress(self) -> float:
        """Mengembalikan nilai progress animasi hover saat ini."""
        return self._hover_progress

    def set_hover_progress(self, value: float) -> None:
        """Menyetel nilai progress animasi hover dan memicu render ulang."""
        self._hover_progress = value
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Menangani pergerakan kursor mouse memasuki area tombol."""
        if not self.is_active:
            self._animation.stop()
            self._animation.setStartValue(self._hover_progress)
            self._animation.setEndValue(1.0)
            self._animation.start()
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Menangani pergerakan kursor mouse meninggalkan area tombol."""
        if not self.is_active:
            self._animation.stop()
            self._animation.setStartValue(self._hover_progress)
            self._animation.setEndValue(0.0)
            self._animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar tombol dengan efek transisi opacity antara ikon normal dan hover."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        icon_size = QSize(24, 24)
        dpr = self.devicePixelRatioF()
        target_pixel_size = QSize(int(icon_size.width() * dpr), int(icon_size.height() * dpr))

        x_pos = (self.width() - icon_size.width()) // 2
        y_pos = (self.height() - icon_size.height()) // 2
        target_rect = QRect(x_pos, y_pos, icon_size.width(), icon_size.height())

        if self._hover_progress < 1.0:
            normal_pixmap = self._normal_icon.pixmap(target_pixel_size)
            normal_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(1.0 - self._hover_progress)
            painter.drawPixmap(target_rect, normal_pixmap)

        if self._hover_progress > 0.0:
            hover_pixmap = self._hover_icon.pixmap(target_pixel_size)
            hover_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(self._hover_progress)
            painter.drawPixmap(target_rect, hover_pixmap)

        painter.end()


class Sidebar(QFrame):
    """Area navigasi di sisi kiri aplikasi.

    Menampilkan ikon navigasi vertikal tanpa label teks untuk mempertahankan 
    tampilan yang ringkas (compact).

    Signals:
        nav_changed: Dipancarkan saat salah satu tombol navigasi diklik dengan membawa string key menu.
    """

    nav_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi sidebar dan menyusun ikon navigasi.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setFixedWidth(55)
        self.setStyleSheet(
            """
            Sidebar {
                background-color: #11111B;
                border-right: 1px solid #313244;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 10px 0;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #313244;
            }
            QPushButton[active="true"] {
                background-color: rgba(46, 204, 113, 0.15);
                border-left: 3px solid #2ECC71;
                border-radius: 6px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 13, 6, 13)
        layout.setSpacing(6)

        validated_icons = validate_sidebar_icons(SIDEBAR_ICONS_CONFIG)
        self.nav_buttons: Dict[str, SidebarButton] = {}

        for i, key in enumerate(SIDEBAR_ICONS_CONFIG):
            icon_paths = validated_icons[i]
            is_active = (i == 0)

            btn = SidebarButton(icon_paths, is_active=is_active)
            attach_tooltip(
                btn,
                SIDEBAR_TOOLTIPS.get(key, key.title()),
                position=TooltipPosition.RIGHT,
            )
            if is_active:
                btn.setProperty("active", "true")

            btn.clicked.connect(lambda checked=False, k=key: self._on_button_clicked(k))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def _on_button_clicked(self, key: str) -> None:
        """Menangani klik tombol navigasi dan memancarkan sinyal menu terpilih.

        Args:
            key: Kunci pengenal navigasi yang diklik.
        """
        self.set_active_nav(key)
        self.nav_changed.emit(key)

    def set_active_nav(self, active_key: str) -> None:
        """Mengatur tombol sidebar aktif berdasarkan kunci menu.

        Args:
            active_key: Kunci menu navigasi yang akan diaktifkan.
        """
        for key, btn in self.nav_buttons.items():
            is_target = (key == active_key)
            btn.is_active = is_target
            btn.setProperty("active", "true" if is_target else "false")
            btn.set_hover_progress(1.0 if is_target else 0.0)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
