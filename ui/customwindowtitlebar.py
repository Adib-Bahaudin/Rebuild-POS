"""Modul custom title bar dan jendela utama tanpa bingkai (frameless) untuk PySide6."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import ctypes.wintypes
from pathlib import Path
from typing import Dict, Optional

from config import get_asset_path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QAbstractAnimation,
)
from PySide6.QtGui import (
    QCloseEvent,
    QEnterEvent,
    QIcon,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QApplication,
)


@dataclass(frozen=True)
class ButtonIconPaths:
    """Menyimpan konfigurasi path ikon untuk status normal dan hover.

    Attributes:
        normal: Lokasi file ikon untuk tampilan normal.
        hover: Lokasi file ikon ketika kursor berada di atas tombol.
    """

    normal: Path
    hover: Path


@dataclass(frozen=True)
class TitleBarIconConfig:
    """Konfigurasi terpusat untuk seluruh aset ikon pada Custom Title Bar.

    Attributes:
        minimize: Pasangan path ikon untuk tombol minimize.
        maximize: Pasangan path ikon untuk tombol maximize.
        restore: Pasangan path ikon untuk tombol restore.
        close: Pasangan path ikon untuk tombol close.
    """

    minimize: ButtonIconPaths
    maximize: ButtonIconPaths
    restore: ButtonIconPaths
    close: ButtonIconPaths

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Dict[str, str]]) -> "TitleBarIconConfig":
        """Membuat instance TitleBarIconConfig dari dictionary konfigurasi.

        Args:
            config_dict: Dictionary bersarang yang memetakan nama tombol ke path
                ikon normal dan hover.

        Returns:
            Objek TitleBarIconConfig yang telah tervalidasi strukturnya.

        Raises:
            KeyError: Jika kunci tombol atau status ikon tidak lengkap.
        """
        return cls(
            minimize=ButtonIconPaths(
                normal=get_asset_path(config_dict["minimize"]["normal"]),
                hover=get_asset_path(config_dict["minimize"]["hover"]),
            ),
            maximize=ButtonIconPaths(
                normal=get_asset_path(config_dict["maximize"]["normal"]),
                hover=get_asset_path(config_dict["maximize"]["hover"]),
            ),
            restore=ButtonIconPaths(
                normal=get_asset_path(config_dict["restore"]["normal"]),
                hover=get_asset_path(config_dict["restore"]["hover"]),
            ),
            close=ButtonIconPaths(
                normal=get_asset_path(config_dict["close"]["normal"]),
                hover=get_asset_path(config_dict["close"]["hover"]),
            ),
        )


ICON_PATHS: Dict[str, Dict[str, str]] = {
    "minimize": {
        "normal": "assets/icons/minimize.svg",
        "hover": "assets/icons/minimize_hover.svg",
    },
    "maximize": {
        "normal": "assets/icons/maximize.svg",
        "hover": "assets/icons/maximize_hover.svg",
    },
    "restore": {
        "normal": "assets/icons/restore.svg",
        "hover": "assets/icons/restore_hover.svg",
    },
    "close": {
        "normal": "assets/icons/close.svg",
        "hover": "assets/icons/close_hover.svg",
    },
}


class IconLoadError(Exception):
    """Pengecualian khusus ketika file aset ikon gagal dimuat atau tidak valid."""


class TitleBarButton(QPushButton):
    """Tombol kontrol title bar dengan dukungan animasi transisi ikon custom.

    Attributes:
        icon_size: Ukuran dimensi render ikon di dalam tombol.
    """

    def __init__(
        self,
        icon_paths: ButtonIconPaths,
        parent: Optional[QWidget] = None,
        button_size: QSize = QSize(46, 36),
        icon_size: QSize = QSize(16, 16),
        hover_bg_color: str = "rgba(255, 255, 255, 0.08)",
        pressed_bg_color: str = "rgba(255, 255, 255, 0.14)",
    ) -> None:
        """Menginisialisasi TitleBarButton dengan aset ikon dan animasi hover.

        Args:
            icon_paths: Objek ButtonIconPaths yang berisi lokasi ikon normal dan hover.
            parent: Widget induk dari tombol ini.
            button_size: Ukuran tetap (fixed size) area tombol.
            icon_size: Ukuran dimensi ikon yang digambar di tengah tombol.
            hover_bg_color: Warna latar tombol dalam format CSS saat status hover.
            pressed_bg_color: Warna latar tombol dalam format CSS saat ditekan.

        Raises:
            FileNotFoundError: Jika salah satu file ikon tidak ditemukan pada disk.
            IconLoadError: Jika file ditemukan namun gagal dimuat oleh QIcon.
        """
        super().__init__(parent)
        self._hover_progress: float = 0.0
        self.icon_size: QSize = icon_size
        self._normal_icon: QIcon = QIcon()
        self._hover_icon: QIcon = QIcon()

        self.setFixedSize(button_size)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._apply_stylesheet(hover_bg_color, pressed_bg_color)
        self.set_icon_pair(icon_paths)

        self._animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _apply_stylesheet(self, hover_bg: str, pressed_bg: str) -> None:
        """Menerapkan aturan gaya visual dasar pada tombol.

        Args:
            hover_bg: Nilai warna CSS saat pointer berada di atas tombol.
            pressed_bg: Nilai warna CSS saat tombol ditekan.
        """
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
            """
        )

    @staticmethod
    def _load_validated_icon(icon_path: Path) -> QIcon:
        """Memvalidasi keberadaan dan memuat file gambar menjadi objek QIcon.

        Args:
            icon_path: Objek Path menuju lokasi file ikon.

        Returns:
            Objek QIcon yang siap dirender.

        Raises:
            FileNotFoundError: Jika path file tidak ditemukan atau bukan sebuah file.
            IconLoadError: Jika QIcon gagal membaca isi gambar atau menghasilkan pixmap kosong.
        """
        resolved_path = icon_path.expanduser().resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            raise FileNotFoundError(
                f"File aset ikon tidak ditemukan pada jalur: '{resolved_path}'"
            )

        icon = QIcon(str(resolved_path))
        probe_pixmap = icon.pixmap(QSize(16, 16))
        if icon.isNull() or probe_pixmap.isNull():
            raise IconLoadError(
                f"Gagal memuat atau merender aset ikon dari file: '{resolved_path}'. "
                "Pastikan format file didukung oleh modul imageformats/svg PySide6."
            )
        return icon

    def set_icon_pair(self, icon_paths: ButtonIconPaths) -> None:
        """Mengatur atau memperbarui pasangan ikon normal dan hover pada tombol.

        Args:
            icon_paths: Objek ButtonIconPaths baru yang akan digunakan.

        Raises:
            FileNotFoundError: Jika file ikon normal atau hover tidak ditemukan.
            IconLoadError: Jika file ikon korup atau formatnya tidak didukung.
        """
        self._normal_icon = self._load_validated_icon(icon_paths.normal)
        self._hover_icon = self._load_validated_icon(icon_paths.hover)
        self.update()

    def get_hover_progress(self) -> float:
        """Mengambil nilai progres transisi hover saat ini.

        Returns:
            Nilai float dalam rentang 0.0 (normal) hingga 1.0 (hover penuh).
        """
        return self._hover_progress

    def set_hover_progress(self, value: float) -> None:
        """Mengatur nilai progres transisi hover dan memicu penggambaran ulang.

        Args:
            value: Nilai float antara 0.0 dan 1.0.
        """
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Menangani event saat kursor mouse memasuki area tombol.

        Args:
            event: Objek QEnterEvent dari sistem event Qt.
        """
        self._animation.stop()
        self._animation.setStartValue(self._hover_progress)
        self._animation.setEndValue(1.0)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Menangani event saat kursor mouse meninggalkan area tombol.

        Args:
            event: Objek QEvent dari sistem event Qt.
        """
        self._animation.stop()
        self._animation.setStartValue(self._hover_progress)
        self._animation.setEndValue(0.0)
        self._animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Menangani klik mouse pada tombol dan menghentikan propagasi ke title bar.

        Args:
            event: Objek QMouseEvent yang berisi informasi tombol dan posisi klik.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Mencegah pergerakan mouse di atas tombol memicu window dragging.

        Args:
            event: Objek QMouseEvent saat kursor bergerak di atas tombol.
        """
        event.accept()
        super().mouseMoveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar latar belakang tombol serta merender transisi cross-fade ikon.

        Args:
            event: Objek QPaintEvent dari siklus render Qt.
        """
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        dpr = self.devicePixelRatioF()
        target_pixel_size = QSize(
            int(self.icon_size.width() * dpr),
            int(self.icon_size.height() * dpr),
        )

        x_pos = (self.width() - self.icon_size.width()) // 2
        y_pos = (self.height() - self.icon_size.height()) // 2
        target_rect = QRect(
            x_pos,
            y_pos,
            self.icon_size.width(),
            self.icon_size.height(),
        )

        if self._hover_progress < 1.0 and not self._normal_icon.isNull():
            normal_pixmap = self._normal_icon.pixmap(target_pixel_size)
            normal_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(1.0 - self._hover_progress)
            painter.drawPixmap(target_rect, normal_pixmap)

        if self._hover_progress > 0.0 and not self._hover_icon.isNull():
            hover_pixmap = self._hover_icon.pixmap(target_pixel_size)
            hover_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(self._hover_progress)
            painter.drawPixmap(target_rect, hover_pixmap)

        painter.end()


class CustomTitleBar(QWidget):
    """Komponen Custom Title Bar modular untuk menggantikan title bar bawaan OS.

    Attributes:
        TITLE_PREFIX: Prefix tetap yang selalu ditampilkan di awal judul.
        DEFAULT_PAGE_TITLE: Teks halaman default ketika tidak ada judul spesifik.
        logo_label: Widget QLabel yang menampilkan ikon logo di pojok kiri.
        title_label: Widget QLabel yang menampilkan teks judul jendela di tengah.
        minimize_button: Tombol untuk meminimalkan jendela.
        maximize_restore_button: Tombol adaptif untuk memaksimalkan atau memulihkan jendela.
        close_button: Tombol untuk menutup jendela utama.
    """

    TITLE_PREFIX: str = "POS - Barokah Copy & Printing"
    DEFAULT_PAGE_TITLE: str = "TITLEBAR"
    LOGO_PATH: str = "icons/B_Logo.svg"

    def __init__(
        self,
        parent_window: QWidget,
        icon_config: TitleBarIconConfig,
        page_title: str = "",
        bar_height: int = 36,
    ) -> None:
        """Menginisialisasi CustomTitleBar dan menghubungkannya dengan jendela induk.

        Args:
            parent_window: Jendela utama (QMainWindow atau QWidget) yang dikontrol.
            icon_config: Konfigurasi path ikon untuk seluruh tombol kontrol.
            page_title: Bagian judul halaman yang dapat berubah-ubah. Jika kosong,
                akan menggunakan DEFAULT_PAGE_TITLE.
            bar_height: Tinggi tetap (fixed height) dari title bar dalam satuan piksel.
        """
        super().__init__(parent_window)
        self._parent_window: QWidget = parent_window
        self._icon_config: TitleBarIconConfig = icon_config
        self._drag_offset: Optional[QPoint] = None
        self._is_maximized_state: bool = False
        self._page_title: str = page_title or self.DEFAULT_PAGE_TITLE

        self.setFixedHeight(bar_height)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            CustomTitleBar {
                background-color: #1E1E2E;
                border-bottom: 1px solid #313244;
            }
            QLabel#TitleBarLogo {
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QLabel#TitleBarLabel {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
            """
        )

        logo_size = bar_height - 8
        self.logo_label = QLabel(self)
        self.logo_label.setObjectName("TitleBarLogo")
        self.logo_label.setFixedSize(bar_height, bar_height)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

        logo_pixmap = QPixmap(str(get_asset_path(self.LOGO_PATH)))
        if not logo_pixmap.isNull():
            scaled_pixmap = logo_pixmap.scaled(
                QSize(logo_size, logo_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(scaled_pixmap)

        self.title_label = QLabel(self._build_full_title(), self)
        self.title_label.setObjectName("TitleBarLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        button_size = QSize(46, bar_height)
        icon_size = QSize(16, 16)

        self.minimize_button = TitleBarButton(
            icon_paths=self._icon_config.minimize,
            parent=self,
            button_size=button_size,
            icon_size=icon_size,
        )
        self.maximize_restore_button = TitleBarButton(
            icon_paths=self._icon_config.maximize,
            parent=self,
            button_size=button_size,
            icon_size=icon_size,
        )
        self.close_button = TitleBarButton(
            icon_paths=self._icon_config.close,
            parent=self,
            button_size=button_size,
            icon_size=icon_size,
            hover_bg_color="#E81123",
            pressed_bg_color="#F1707A",
        )

        self._setup_layout()
        self._connect_signals()
        self._parent_window.installEventFilter(self)
        self.sync_window_state()

    def _build_full_title(self) -> str:
        """Menyusun teks judul lengkap dari prefix tetap dan judul halaman.

        Returns:
            String judul dalam format "POS - Barokah Copy & Printing - {page_title}".
        """
        return f"{self.TITLE_PREFIX} - {self._page_title}"

    def _setup_layout(self) -> None:
        """Menyusun tata letak horizontal: logo kiri, judul tengah, tombol kanan."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.logo_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_restore_button)
        layout.addWidget(self.close_button)

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal klik tombol serta sinyal judul jendela ke slot terkait."""
        self.minimize_button.clicked.connect(self.minimize_window)
        self.maximize_restore_button.clicked.connect(self.toggle_maximize_restore)
        self.close_button.clicked.connect(self.close_window)
        self._parent_window.windowTitleChanged.connect(self.set_title)

    def set_title(self, page_title: str) -> None:
        """Memperbarui bagian judul halaman yang ditampilkan pada title bar.

        Judul lengkap akan menjadi "POS - Barokah Copy & Printing - {page_title}".

        Args:
            page_title: String judul halaman baru. Jika kosong, menggunakan
                DEFAULT_PAGE_TITLE.
        """
        self._page_title = page_title or self.DEFAULT_PAGE_TITLE
        self.title_label.setText(self._build_full_title())

    def update_icon_config(self, new_config: TitleBarIconConfig) -> None:
        """Memperbarui seluruh aset ikon tombol secara dinamis saat runtime.

        Args:
            new_config: Objek TitleBarIconConfig dengan path aset baru.
        """
        self._icon_config = new_config
        self.minimize_button.set_icon_pair(self._icon_config.minimize)
        self.close_button.set_icon_pair(self._icon_config.close)
        self.sync_window_state(force_update=True)

    def minimize_window(self) -> None:
        """Meminimalkan jendela induk ke taskbar atau dock sistem operasi."""
        self._parent_window.showMinimized()

    def toggle_maximize_restore(self) -> None:
        """Mengubah status jendela induk antara kondisi maximize dan normal (restore)."""
        if self._parent_window.isMaximized():
            self._parent_window.showNormal()
        else:
            self._parent_window.showMaximized()
        self.sync_window_state()

    def close_window(self) -> None:
        """Menutup jendela induk dengan memicu siklus penutupan standar Qt."""
        self._parent_window.close()

    def sync_window_state(self, force_update: bool = True) -> None:
        """Menyinkronkan ikon tombol maximize/restore dengan status jendela terkini.

        Args:
            force_update: Jika True, memaksa pembaruan ikon meskipun status maximize
                tidak berubah.
        """
        parent_window = getattr(self, "_parent_window", None)
        if parent_window is None:
            return

        currently_maximized = bool(
            parent_window.windowState() & Qt.WindowState.WindowMaximized
        )
        if not force_update and currently_maximized == self._is_maximized_state:
            return

        self._is_maximized_state = currently_maximized
        if currently_maximized:
            self.maximize_restore_button.set_icon_pair(self._icon_config.restore)
        else:
            self.maximize_restore_button.set_icon_pair(self._icon_config.maximize)

    def _is_interactive_button_area(self, local_pos: QPoint) -> bool:
        """Memeriksa apakah koordinat lokal berada di atas salah satu tombol kontrol.

        Args:
            local_pos: Titik koordinat relatif terhadap CustomTitleBar.

        Returns:
            True jika posisi berada di atas tombol kontrol, False jika di area kosong.
        """
        child = self.childAt(local_pos)
        return isinstance(child, QPushButton)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Memantau perubahan status jendela induk untuk menyinkronkan ikon tombol.

        Args:
            watched: Objek yang sedang dipantau oleh filter event.
            event: Objek QEvent yang dikirimkan ke objek tersebut.

        Returns:
            Boolean hasil pemrosesan eventFilter kelas induk.
        """
        parent_window = getattr(self, "_parent_window", None)
        if (
            parent_window is not None
            and watched is parent_window
            and event.type() == QEvent.Type.WindowStateChange
        ):
            self.sync_window_state()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Menangani awal proses penggeseran jendela ketika area kosong title bar ditekan.

        Args:
            event: Objek QMouseEvent saat tombol mouse ditekan.
        """
        local_pos = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._is_interactive_button_area(local_pos)
        ):
            window_handle = self._parent_window.windowHandle()
            if window_handle is not None and window_handle.startSystemMove():
                self._drag_offset = None
                event.accept()
                return

            if not self._parent_window.isMaximized():
                global_pos = event.globalPosition().toPoint()
                self._drag_offset = (
                    global_pos - self._parent_window.frameGeometry().topLeft()
                )
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Menangani pergerakan jendela manual sebagai fallback jika sistem move tidak aktif.

        Args:
            event: Objek QMouseEvent saat kursor digerakkan.
        """
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and not self._parent_window.isMaximized()
        ):
            global_pos = event.globalPosition().toPoint()
            self._parent_window.move(global_pos - self._drag_offset)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Mengakhiri status penggeseran jendela ketika tombol mouse dilepas.

        Args:
            event: Objek QMouseEvent saat tombol mouse dilepaskan.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Menangani aksi klik ganda pada title bar untuk toggle maximize dan restore.

        Args:
            event: Objek QMouseEvent saat terjadi klik ganda.
        """
        local_pos = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._is_interactive_button_area(local_pos)
        ):
            self.toggle_maximize_restore()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)


class FramelessMainWindow(QMainWindow):
    """Jendela utama tanpa bingkai OS yang mengintegrasikan CustomTitleBar.

    Attributes:
        title_bar: Instance CustomTitleBar yang terpasang di bagian atas jendela.
        content_area: Widget kontainer untuk menempatkan komponen utama aplikasi.
    """

    RESIZE_MARGIN: int = 6

    def __init__(
        self,
        icon_config: TitleBarIconConfig,
        page_title: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Menginisialisasi jendela utama frameless beserta tata letak kontainer.

        Args:
            icon_config: Objek TitleBarIconConfig berisi path seluruh ikon tombol.
            page_title: Bagian judul halaman yang dapat berubah pada title bar.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setWindowTitle(page_title)
        self._transition_anim: Optional[QAbstractAnimation] = None
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setMinimumSize(1200, 640)
        self.setMouseTracking(True)

        self._root_container = QWidget(self)
        self._root_container.setObjectName("RootContainer")
        self._root_container.setMouseTracking(True)
        self._root_container.setStyleSheet(
            """
            QWidget#RootContainer {
                background-color: #181825;
                border: 1px solid #313244;
            }
            """
        )

        self._root_layout = QVBoxLayout(self._root_container)
        self._root_layout.setContentsMargins(1, 1, 1, 1)
        self._root_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(
            parent_window=self,
            icon_config=icon_config,
            page_title=page_title,
        )

        self.content_area = QWidget(self._root_container)
        self.content_area.setMouseTracking(True)
        self.content_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._root_layout.addWidget(self.title_bar)
        self._root_layout.addWidget(self.content_area)

        super().setCentralWidget(self._root_container)
        self.installEventFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._show_initial_window_state()

    def _is_taskbar_visible(self) -> bool:
        """Mendeteksi apakah taskbar Windows saat ini terlihat (tidak disembunyikan).

        Menggunakan Windows Shell API (SHAppBarMessage + ABM_GETTASKBARPOS)
        untuk mendapatkan posisi dan ukuran taskbar. Jika lebar atau tinggi
        taskbar adalah nol, dianggap taskbar sedang dalam kondisi auto-hide
        atau tidak terdeteksi.

        Returns:
            True jika taskbar terdeteksi dan memiliki ukuran > 0, False jika tidak.
        """
        try:
            class APPBARDATA(ctypes.Structure):
                """Struktur data Windows API untuk membaca posisi dan ukuran taskbar."""

                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("hWnd", ctypes.wintypes.HWND),
                    ("uCallbackMessage", ctypes.wintypes.UINT),
                    ("uEdge", ctypes.wintypes.UINT),
                    ("rc", ctypes.wintypes.RECT),
                    ("lParam", ctypes.wintypes.LPARAM),
                ]

            ABM_GETTASKBARPOS = 0x00000005
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(abd)
            result = ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS, ctypes.byref(abd))
            if not result:
                return False
            width = abd.rc.right - abd.rc.left
            height = abd.rc.bottom - abd.rc.top
            return width > 0 and height > 0
        except Exception:
            return False

    def _show_initial_window_state(self) -> None:
        """Menampilkan jendela dalam kondisi awal.

        Jika taskbar Windows terdeteksi dan terlihat, jendela ditampilkan
        dalam mode maximized agar tidak menutupi taskbar. Jika taskbar tidak
        terdeteksi (mis. dalam kondisi auto-hide atau tersembunyi), jendela
        ditampilkan dalam mode fullscreen.
        """
        if self._is_taskbar_visible():
            self.showMaximized()
        else:
            self.showFullScreen()

    def set_content_widget(self, widget: QWidget) -> None:
        """Menetapkan widget konten aplikasi di bawah area Custom Title Bar.

        Args:
            widget: Komponen QWidget yang akan menjadi isi utama aplikasi.
        """
        self._root_layout.removeWidget(self.content_area)
        self.content_area.deleteLater()
        self.content_area = widget
        self.content_area.setParent(self._root_container)
        self.content_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._root_layout.addWidget(self.content_area)

    def changeEvent(self, event: QEvent) -> None:
        """Menyesuaikan ketebalan margin bingkai saat status maximize berubah.

        Args:
            event: Objek QEvent yang menandakan perubahan status pada jendela.
        """
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMaximized():
                self._root_layout.setContentsMargins(0, 0, 0, 0)
            else:
                self._root_layout.setContentsMargins(1, 1, 1, 1)
            self.title_bar.sync_window_state()
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Menghapus event filter dari QApplication saat jendela ditutup."""
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Memantau pergerakan kursor global untuk mengatur bentuk kursor resize tepi jendela."""
        if not self.isVisible():
            return super().eventFilter(watched, event)
        if (
            isinstance(event, QMouseEvent)
            and event.type() == QEvent.Type.MouseMove
            and not event.buttons()
        ):
            if isinstance(watched, QWidget) and watched.window() is self:
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)
                edges = self._detect_resize_edges(local_pos)
                self._update_cursor_shape(edges)
        return super().eventFilter(watched, event)

    def _detect_resize_edges(self, pos: QPoint) -> Qt.Edge:
        """Mendeteksi sisi atau sudut tepi jendela berdasarkan koordinat kursor.

        Args:
            pos: Posisi kursor relatif terhadap jendela utama.

        Returns:
            Kombinasi flag Qt.Edges yang menunjukkan sisi resize aktif.
        """
        edges = Qt.Edge(0)
        if self.isMaximized():
            return edges

        margin = self.RESIZE_MARGIN
        if pos.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= self.width() - margin:
            edges |= Qt.Edge.RightEdge

        if pos.y() <= margin:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= self.height() - margin:
            edges |= Qt.Edge.BottomEdge

        return edges

    def _update_cursor_shape(self, edges: Qt.Edge) -> None:
        """Mengubah bentuk kursor mouse sesuai sisi tepi jendela yang terdeteksi.

        Args:
            edges: Kombinasi flag Qt.Edges hasil deteksi posisi kursor.
        """
        if edges == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge) or edges == (
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge
        ):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges == (Qt.Edge.RightEdge | Qt.Edge.TopEdge) or edges == (
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge
        ):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Memulai operasi pengubahan ukuran jendela (resize) dari tepi frameless window.

        Args:
            event: Objek QMouseEvent ketika tombol mouse ditekan.
        """
        if event.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            edges = self._detect_resize_edges(event.position().toPoint())
            if edges and self.windowHandle() is not None:
                if self.windowHandle().startSystemResize(edges):
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Memperbarui indikator kursor saat pointer mendekati batas tepi jendela.

        Args:
            event: Objek QMouseEvent ketika kursor bergerak.
        """
        if not event.buttons():
            edges = self._detect_resize_edges(event.position().toPoint())
            self._update_cursor_shape(edges)
        super().mouseMoveEvent(event)
