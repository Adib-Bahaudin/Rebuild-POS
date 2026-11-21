"""Modul shell utama aplikasi POS yang mengintegrasikan CustomTitleBar dan Sidebar."""

import logging
from typing import Callable, Dict, Optional, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.customsidebar import Sidebar
from ui.customwindowtitlebar import FramelessMainWindow, TitleBarIconConfig

logger = logging.getLogger(__name__)


def create_placeholder_page(
    title: str,
    description: str = "Halaman ini sedang dalam tahap pengembangan.",
) -> QWidget:
    """Membuat widget placeholder sederhana untuk halaman yang belum diimplementasikan.

    Args:
        title: Nama judul halaman placeholder.
        description: Deskripsi status kesiapan halaman.

    Returns:
        Widget QWidget yang telah ditata dengan gaya visual aplikasi.
    """
    widget = QWidget()
    widget.setStyleSheet("background-color: #11111B;")

    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(12)

    title_label = QLabel(title.upper())
    title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #CDD6F4;")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    desc_label = QLabel(description)
    desc_label.setStyleSheet("font-size: 13px; color: #6C7086;")
    desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(title_label)
    layout.addWidget(desc_label)

    return widget


class MainShell(FramelessMainWindow):
    """Jendela utama aplikasi POS yang mengintegrasikan CustomTitleBar dan Sidebar dengan QStackedWidget.

    Setiap halaman yang dimuat ke dalam MainShell akan otomatis memiliki CustomTitleBar
    di bagian atas dan Sidebar navigasi di sebelah kiri.

    Signals:
        page_changed: Dipancarkan saat navigasi halaman berubah membawa key pengenal menu.
    """

    page_changed = Signal(str)

    def __init__(
        self,
        icon_config: TitleBarIconConfig,
        page_title: str = "Dashboard Penjualan",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Menginisialisasi MainShell dan menyusun kontainer sidebar serta stack halaman.

        Args:
            icon_config: Objek TitleBarIconConfig berisi konfigurasi path ikon title bar.
            page_title: Judul awal yang ditampilkan pada title bar jendela.
            parent: Widget induk opsional.
        """
        super().__init__(icon_config=icon_config, page_title=page_title, parent=parent)

        self._page_factories: Dict[str, Callable[[], QWidget]] = {}
        self._page_titles: Dict[str, str] = {}
        self._page_cache: Dict[str, QWidget] = {}

        self._container = QWidget(self)
        self._container.setObjectName("MainShellContainer")
        self._container.setStyleSheet("background-color: #11111B;")

        container_layout = QHBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.sidebar = Sidebar(self._container)
        self.stacked_widget = QStackedWidget(self._container)
        self.stacked_widget.setStyleSheet("background-color: #11111B;")

        container_layout.addWidget(self.sidebar)
        container_layout.addWidget(self.stacked_widget, stretch=1)

        self.set_content_widget(self._container)

        self.sidebar.nav_changed.connect(self.navigate_to)

    def register_page(
        self,
        key: str,
        page_or_factory: Union[QWidget, Callable[[], QWidget]],
        title: str = "",
    ) -> None:
        """Mendaftarkan halaman atau fungsi factory halaman ke dalam shell navigasi.

        Args:
            key: Kunci pengenal navigasi yang sesuai dengan item menu sidebar.
            page_or_factory: Instance QWidget atau callable factory tanpa argumen yang menghasilkan QWidget.
            title: Judul halaman untuk pembaruan CustomTitleBar saat halaman dibuka.

        Raises:
            TypeError: Jika page_or_factory bukan berupa QWidget atau Callable.
        """
        if title:
            self._page_titles[key] = title

        if isinstance(page_or_factory, QWidget):
            self._prepare_and_add_page(key, page_or_factory)
        elif callable(page_or_factory):
            self._page_factories[key] = page_or_factory
        else:
            raise TypeError("page_or_factory harus berupa QWidget atau Callable[[], QWidget]")

    def add_page(
        self,
        key: str,
        page_or_factory: Union[QWidget, Callable[[], QWidget]],
        title: str = "",
    ) -> None:
        """Alias untuk method register_page.

        Args:
            key: Kunci pengenal navigasi.
            page_or_factory: Instance QWidget atau callable factory penghasil QWidget.
            title: Judul halaman untuk pembaruan CustomTitleBar.
        """
        self.register_page(key, page_or_factory, title)

    def _prepare_and_add_page(self, key: str, widget: QWidget) -> None:
        """Menyiapkan widget halaman sebelum dimasukkan ke dalam QStackedWidget.

        Menangani halaman yang memiliki atribut sidebar internal (seperti DashboardPOS)
        dengan menyembunyikannya agar tidak terjadi duplikasi tampilan sidebar.

        Args:
            key: Kunci pengenal navigasi.
            widget: Objek QWidget halaman yang akan ditambahkan.
        """
        if hasattr(widget, "sidebar"):
            sidebar_attr = getattr(widget, "sidebar")
            if isinstance(sidebar_attr, QWidget):
                sidebar_attr.hide()

        self._page_cache[key] = widget
        self.stacked_widget.addWidget(widget)

    def navigate_to(self, key: str) -> None:
        """Berpindah ke halaman berdasarkan kunci navigasi menu sidebar.

        Mendukung lazy loading di mana factory dieksekusi saat halaman pertama kali dibuka,
        lalu hasilnya disimpan di cache agar state halaman tidak hilang saat berganti menu.

        Args:
            key: Kunci pengenal navigasi menu target.
        """
        target_widget: Optional[QWidget] = self._page_cache.get(key)

        if target_widget is None and key in self._page_factories:
            try:
                factory = self._page_factories[key]
                target_widget = factory()
                self._prepare_and_add_page(key, target_widget)
            except Exception:
                logger.exception("Gagal membuat instance halaman untuk menu '%s'", key)
                return

        if target_widget is None:
            logger.warning("Halaman navigasi untuk kunci '%s' tidak ditemukan", key)
            return

        self.stacked_widget.setCurrentWidget(target_widget)

        page_title = self._page_titles.get(key)
        if page_title:
            self.setWindowTitle(page_title)

        self.sidebar.set_active_nav(key)

        if hasattr(target_widget, "on_page_entered"):
            hook = getattr(target_widget, "on_page_entered")
            if callable(hook):
                try:
                    hook()
                except Exception:
                    logger.exception(
                        "Terjadi kesalahan saat memanggil on_page_entered pada halaman '%s'",
                        key,
                    )

        self.page_changed.emit(key)

    def get_current_page(self) -> Optional[QWidget]:
        """Mengembalikan instance QWidget dari halaman yang sedang aktif.

        Returns:
            Instance QWidget aktif atau None jika belum ada halaman.
        """
        return self.stacked_widget.currentWidget()

    def get_page(self, key: str) -> Optional[QWidget]:
        """Mengambil instance halaman yang sudah diinstansiasi di cache.

        Args:
            key: Kunci pengenal navigasi.

        Returns:
            Instance QWidget jika sudah pernah dimuat, atau None.
        """
        return self._page_cache.get(key)
