"""Modul antarmuka pengguna (UI) untuk halaman Riwayat Transaksi POS.

Modul ini menyediakan halaman Riwayat Transaksi berbasis PySide6 dengan kartu
ringkasan bergaya gradien, filter periode tanggal dengan kalender rentang kustom,
tabel berpola zebra hitam-putih kontras tinggi, navigasi halaman, serta tombol
ekspor Excel dan PDF tanpa logika backend maupun data dummy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import (
    QByteArray,
    QDate,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.customwindowtitlebar import (
    FramelessMainWindow,
    ICON_PATHS,
    TitleBarIconConfig,
)

TrendStatus = Literal["positive", "negative", "neutral"]

DATE_FILTER_OPTIONS: tuple[str, ...] = (
    "Hari Ini",
    "Minggu Ini",
    "Bulan Ini",
    "Custom",
)

PAYMENT_METHOD_OPTIONS: tuple[str, ...] = (
    "Semua Metode",
    "Tunai",
    "Qris",
    "Transfer",
    "Belum Lunas",
)

TABLE_COLUMNS: tuple[str, ...] = (
    "No",
    "Invoice",
    "Tanggal",
    "Metode Bayar",
    "Sub Total",
    "Diskon",
    "Pembulatan",
    "Total",
    "Aksi",
)

SVG_ICONS: dict[str, str] = {
    "receipt": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1'
        '-2-1-2 1-2-1-2 1Z"/>'
        '<path d="M8 7h8"/><path d="M8 11h8"/><path d="M8 15h5"/></svg>'
    ),
    "revenue": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="2" y="5" width="20" height="14" rx="2"/>'
        '<path d="M2 10h20"/><path d="M6 15h4"/><path d="M16 15h2"/></svg>'
    ),
    "average": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>'
    ),
    "search": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
    ),
    "filter": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>'
        "</svg>"
    ),
    "calendar": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/></svg>'
    ),
    "excel": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<path d="m9 13 6 6"/><path d="m15 13-6 6"/></svg>'
    ),
    "pdf": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<path d="M8 13h8"/><path d="M8 17h5"/></svg>'
    ),
}


def render_svg_pixmap(icon_key: str, size: int, color: str = "#FFFFFF") -> QPixmap:
    """Merender markup SVG bawaan menjadi objek QPixmap beresolusi tajam.

    Args:
        icon_key: Kunci nama ikon yang tersedia pada kamus SVG_ICONS.
        size: Dimensi lebar dan tinggi pixmap dalam piksel.
        color: Kode warna heksadesimal untuk garis ikon SVG.

    Returns:
        Objek QPixmap transparan berisi gambar vektor hasil render.
    """
    template = SVG_ICONS.get(icon_key, SVG_ICONS["receipt"])
    svg_bytes = template.format(color=color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_bytes))

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def render_svg_icon(icon_key: str, size: int = 16, color: str = "#FFFFFF") -> QIcon:
    """Membuat QIcon dari markup SVG bawaan.

    Args:
        icon_key: Kunci nama ikon yang tersedia pada kamus SVG_ICONS.
        size: Ukuran dimensi ikon dalam piksel.
        color: Kode warna heksadesimal untuk garis ikon SVG.

    Returns:
        Objek QIcon siap pakai untuk tombol atau aksi input.
    """
    return QIcon(render_svg_pixmap(icon_key, size, color))


def load_pixmap_from_path(icon_path: Path, size: int = 22) -> QPixmap | None:
    """Memuat file ikon eksternal menjadi QPixmap terukur secara aman.

    Args:
        icon_path: Path menuju file gambar atau SVG pada sistem file.
        size: Ukuran target lebar dan tinggi pixmap dalam piksel.

    Returns:
        Objek QPixmap jika file valid dan berhasil dimuat, atau None jika gagal.
    """
    resolved = icon_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        return None

    pixmap = QPixmap(str(resolved))
    if pixmap.isNull():
        return None

    return pixmap.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


@dataclass(frozen=True)
class SummaryCardStyle:
    """Konfigurasi tampilan visual untuk satu kartu ringkasan statistik.

    Attributes:
        title: Judul kartu yang ditampilkan pada header kiri.
        icon_key: Kunci ikon SVG bawaan yang ditampilkan pada header kanan.
        gradient_start: Warna awal gradien latar kartu.
        gradient_mid: Warna tengah gradien latar kartu.
        gradient_end: Warna akhir gradien latar kartu.
        border_color: Warna garis tepi normal kartu.
        hover_border_color: Warna garis tepi saat kursor diarahkan ke kartu.
        icon_bg_color: Warna latar lencana ikon dalam format RGBA/CSS.
        icon_color: Warna garis vektor ikon.
        default_value: Teks nilai utama bawaan sebelum backend mengisi data.
    """

    title: str
    icon_key: str
    gradient_start: str
    gradient_mid: str
    gradient_end: str
    border_color: str
    hover_border_color: str
    icon_bg_color: str
    icon_color: str
    default_value: str


@dataclass(frozen=True)
class FilterCriteria:
    """Struktur data parameter filter UI yang dikirim ke backend.

    Attributes:
        date_preset: Pilihan periode tanggal dari dropdown.
        start_date: Tanggal awal dalam format ISO (YYYY-MM-DD).
        end_date: Tanggal akhir dalam format ISO (YYYY-MM-DD).
        payment_method: Pilihan metode pembayaran yang dipilih pengguna.
        search_query: Kata kunci pencarian dari kolom input.
    """

    date_preset: str
    start_date: str
    end_date: str
    payment_method: str
    search_query: str


@dataclass(frozen=True)
class TransactionRowData:
    """Struktur data satu baris transaksi untuk ditampilkan pada tabel UI.

    Attributes:
        no: Nomor urut baris.
        invoice: Kode atau nomor faktur transaksi.
        tanggal: String tanggal dan waktu transaksi terformat.
        metode_bayar: Label metode pembayaran transaksi.
        sub_total: String nominal subtotal terformat.
        diskon: String nominal diskon terformat.
        pembulatan: String nominal pembulatan terformat.
        total: String nominal total akhir transaksi terformat.
    """

    no: int
    invoice: str
    tanggal: str
    metode_bayar: str
    sub_total: str
    diskon: str
    pembulatan: str
    total: str


SUMMARY_CARD_STYLES: tuple[SummaryCardStyle, SummaryCardStyle, SummaryCardStyle] = (
    SummaryCardStyle(
        title="Total Transaksi",
        icon_key="receipt",
        gradient_start="#1E3056",
        gradient_mid="#192340",
        gradient_end="#14182B",
        border_color="#355086",
        hover_border_color="#60A5FA",
        icon_bg_color="rgba(96, 165, 250, 0.18)",
        icon_color="#93C5FD",
        default_value="0",
    ),
    SummaryCardStyle(
        title="Total Revenue",
        icon_key="revenue",
        gradient_start="#123D36",
        gradient_mid="#132D2C",
        gradient_end="#131C23",
        border_color="#256D60",
        hover_border_color="#34D399",
        icon_bg_color="rgba(52, 211, 153, 0.18)",
        icon_color="#6EE7B7",
        default_value="Rp 0",
    ),
    SummaryCardStyle(
        title="Rata-Rata",
        icon_key="average",
        gradient_start="#392159",
        gradient_mid="#281C40",
        gradient_end="#1A162B",
        border_color="#664396",
        hover_border_color="#C084FC",
        icon_bg_color="rgba(192, 132, 252, 0.18)",
        icon_color="#D8B4FE",
        default_value="Rp 0",
    ),
)


class SummaryCardWidget(QFrame):
    """Kartu ringkasan statistik dengan latar gradien, ikon, nilai, dan pembanding.

    Komponen ini memiliki tiga bagian utama: header (judul kiri dan ikon kanan),
    body (nilai utama), serta footer (teks pembanding tren).
    """

    def __init__(
        self,
        style_config: SummaryCardStyle,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi kartu ringkasan sesuai konfigurasi visual.

        Args:
            style_config: Objek SummaryCardStyle penentu judul, ikon, dan gradien.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._style_config = style_config
        self._title_label = QLabel(style_config.title, self)
        self._icon_label = QLabel(self)
        self._value_label = QLabel(style_config.default_value, self)
        self._comparison_label = QLabel("0% dari minggu kemarin", self)

        self.setObjectName("SummaryCard")
        self.setFixedHeight(96)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._setup_ui()
        self._apply_styles()
        self.set_comparison("0% dari minggu kemarin", "neutral")

    def _setup_ui(self) -> None:
        """Menyusun tata letak vertikal header, body, dan footer pada kartu."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._title_label.setObjectName("CardTitle")
        self._icon_label.setObjectName("CardIconBadge")
        self._icon_label.setFixedSize(28, 28)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setPixmap(
            render_svg_pixmap(
                self._style_config.icon_key,
                15,
                self._style_config.icon_color,
            )
        )

        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        header_layout.addWidget(self._icon_label)

        self._value_label.setObjectName("CardValue")
        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._comparison_label.setObjectName("CardComparison")
        self._comparison_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addLayout(header_layout)
        layout.addWidget(self._value_label)
        layout.addWidget(self._comparison_label)

    def _apply_styles(self) -> None:
        """Menerapkan aturan QSS gradien dan tipografi ringkas untuk kartu."""
        cfg = self._style_config
        self.setStyleSheet(
            f"""
            QFrame#SummaryCard {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {cfg.gradient_start},
                    stop: 0.55 {cfg.gradient_mid},
                    stop: 1 {cfg.gradient_end}
                );
                border: 1px solid {cfg.border_color};
                border-radius: 12px;
            }}
            QFrame#SummaryCard:hover {{
                border: 1px solid {cfg.hover_border_color};
            }}
            QLabel#CardTitle {{
                color: #CBD5E1;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.3px;
                background: transparent;
            }}
            QLabel#CardIconBadge {{
                background-color: {cfg.icon_bg_color};
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            QLabel#CardValue {{
                color: #FFFFFF;
                font-size: 20px;
                font-weight: 700;
                background: transparent;
            }}
            """
        )

    def set_value(self, value_text: str) -> None:
        """Memperbarui teks nilai utama pada body kartu.

        Args:
            value_text: String nilai utama yang akan ditampilkan.
        """
        self._value_label.setText(value_text)

    def set_comparison(
        self,
        text: str,
        status: TrendStatus = "neutral",
    ) -> None:
        """Memperbarui teks pembanding beserta warna status pada footer kartu.

        Args:
            text: Teks pembanding, misalnya '+12.4% dari minggu kemarin'.
            status: Indikator tren ('positive', 'negative', atau 'neutral').
        """
        color_map: dict[TrendStatus, str] = {
            "positive": "#86EFAC",
            "negative": "#FDA4AF",
            "neutral": "#94A3B8",
        }
        accent = color_map[status]
        self._comparison_label.setText(text)
        self._comparison_label.setStyleSheet(
            f"""
            QLabel#CardComparison {{
                color: {accent};
                font-size: 11px;
                font-weight: 500;
                background: transparent;
            }}
            """
        )

    def set_icon_from_path(self, icon_path: Path) -> bool:
        """Mengganti ikon kartu menggunakan file gambar atau SVG kustom.

        Args:
            icon_path: Path menuju file aset ikon kustom.

        Returns:
            True jika ikon berhasil dimuat dan diterapkan, False jika gagal.
        """
        pixmap = load_pixmap_from_path(icon_path, size=15)
        if pixmap is None:
            return False
        self._icon_label.setPixmap(pixmap)
        return True

    def reset_display(self) -> None:
        """Mengembalikan nilai utama dan teks pembanding ke kondisi awal."""
        self.set_value(self._style_config.default_value)
        self.set_comparison("0% dari minggu kemarin", "neutral")


class SummaryCardsContainer(QWidget):
    """Kontainer horizontal untuk menampilkan tiga kartu statistik utama.

    Attributes:
        card_total_transaksi: Kartu statistik jumlah total transaksi.
        card_total_revenue: Kartu statistik total pendapatan (revenue).
        card_rata_rata: Kartu statistik rata-rata nilai transaksi.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi tiga kartu ringkasan dengan tata letak sejajar.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.card_total_transaksi = SummaryCardWidget(SUMMARY_CARD_STYLES[0], self)
        self.card_total_revenue = SummaryCardWidget(SUMMARY_CARD_STYLES[1], self)
        self.card_rata_rata = SummaryCardWidget(SUMMARY_CARD_STYLES[2], self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self.card_total_transaksi, stretch=1)
        layout.addWidget(self.card_total_revenue, stretch=1)
        layout.addWidget(self.card_rata_rata, stretch=1)

    def update_values(
        self,
        total_transaksi: str,
        total_revenue: str,
        rata_rata: str,
    ) -> None:
        """Memperbarui nilai utama ketiga kartu secara bersamaan.

        Args:
            total_transaksi: String nilai total transaksi.
            total_revenue: String nilai total revenue terformat.
            rata_rata: String nilai rata-rata transaksi terformat.
        """
        self.card_total_transaksi.set_value(total_transaksi)
        self.card_total_revenue.set_value(total_revenue)
        self.card_rata_rata.set_value(rata_rata)

    def reset_all(self) -> None:
        """Mengembalikan seluruh kartu ringkasan ke kondisi tampilan bawaan."""
        self.card_total_transaksi.reset_display()
        self.card_total_revenue.reset_display()
        self.card_rata_rata.reset_display()


class DateRangeCalendarPanel(QFrame):
    """Panel kalender ganda untuk memilih tanggal awal dan tanggal akhir.

    Panel ini tampil otomatis saat pengguna memilih opsi 'Custom' pada dropdown
    periode tanggal di filter bar.

    Signals:
        date_range_applied: Dipancarkan saat rentang tanggal diterapkan, membawa
            pasangan QDate (tanggal_awal, tanggal_akhir).
        panel_closed: Dipancarkan saat panel kalender ditutup oleh pengguna.
    """

    date_range_applied = Signal(QDate, QDate)
    panel_closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi panel pemilih rentang tanggal berbasis QCalendarWidget.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._start_calendar = QCalendarWidget(self)
        self._end_calendar = QCalendarWidget(self)
        self._summary_label = QLabel(self)
        self._apply_button = QPushButton("Terapkan Rentang", self)
        self._close_button = QPushButton("Tutup", self)

        self.setObjectName("DateRangeCalendarPanel")
        self._configure_calendars()
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._refresh_summary_text()

    def _configure_calendars(self) -> None:
        """Mengatur konfigurasi dasar kedua widget kalender."""
        today = QDate.currentDate()
        for calendar in (self._start_calendar, self._end_calendar):
            calendar.setGridVisible(False)
            calendar.setVerticalHeaderFormat(
                QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
            )
            calendar.setHorizontalHeaderFormat(
                QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
            )
            calendar.setFixedHeight(215)
            calendar.setSelectedDate(today)

    def _setup_ui(self) -> None:
        """Menyusun kalender tanggal awal, tanggal akhir, dan tombol aksi."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        calendars_layout = QHBoxLayout()
        calendars_layout.setSpacing(20)

        start_column = QVBoxLayout()
        start_column.setSpacing(6)
        start_title = QLabel("Tanggal Awal", self)
        start_title.setObjectName("CalendarSectionTitle")
        start_column.addWidget(start_title)
        start_column.addWidget(self._start_calendar)

        end_column = QVBoxLayout()
        end_column.setSpacing(6)
        end_title = QLabel("Tanggal Akhir", self)
        end_title.setObjectName("CalendarSectionTitle")
        end_column.addWidget(end_title)
        end_column.addWidget(self._end_calendar)

        calendars_layout.addLayout(start_column, stretch=1)
        calendars_layout.addLayout(end_column, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self._summary_label.setObjectName("CalendarSummaryLabel")
        self._close_button.setObjectName("CalendarSecondaryButton")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.setFixedHeight(34)

        self._apply_button.setObjectName("CalendarPrimaryButton")
        self._apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_button.setFixedHeight(34)

        footer_layout.addWidget(self._summary_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self._close_button)
        footer_layout.addWidget(self._apply_button)

        main_layout.addLayout(calendars_layout)
        main_layout.addLayout(footer_layout)

    def _apply_styles(self) -> None:
        """Menerapkan gaya visual gelap modern untuk panel dan QCalendarWidget."""
        self.setStyleSheet(
            """
            QFrame#DateRangeCalendarPanel {
                background-color: #161622;
                border: 1px solid #313244;
                border-radius: 12px;
            }
            QLabel#CalendarSectionTitle {
                color: #89B4FA;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.4px;
                background: transparent;
            }
            QLabel#CalendarSummaryLabel {
                color: #BAC2DE;
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #1E1E2E;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #CDD6F4;
                background-color: transparent;
                font-size: 12px;
                font-weight: 600;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #313244;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
            }
            QCalendarWidget QMenu {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #45475A;
            }
            QCalendarWidget QSpinBox {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #181825;
                color: #CDD6F4;
                font-size: 12px;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                border: 1px solid #313244;
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                outline: none;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #585B70;
            }
            QPushButton#CalendarPrimaryButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 0px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CalendarPrimaryButton:hover {
                background-color: #3B82F6;
            }
            QPushButton#CalendarSecondaryButton {
                background-color: #242538;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CalendarSecondaryButton:hover {
                background-color: #313244;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan event pemilihan tanggal dan klik tombol pada panel."""
        self._start_calendar.selectionChanged.connect(self._on_start_date_changed)
        self._end_calendar.selectionChanged.connect(self._on_end_date_changed)
        self._apply_button.clicked.connect(self._on_apply_clicked)
        self._close_button.clicked.connect(self.panel_closed.emit)

    def _on_start_date_changed(self) -> None:
        """Menjaga agar tanggal akhir tidak lebih awal dari tanggal awal."""
        start_date = self._start_calendar.selectedDate()
        end_date = self._end_calendar.selectedDate()
        if end_date < start_date:
            self._end_calendar.setSelectedDate(start_date)
        self._refresh_summary_text()

    def _on_end_date_changed(self) -> None:
        """Menjaga agar tanggal awal tidak melampaui tanggal akhir."""
        start_date = self._start_calendar.selectedDate()
        end_date = self._end_calendar.selectedDate()
        if start_date > end_date:
            self._start_calendar.setSelectedDate(end_date)
        self._refresh_summary_text()

    def _refresh_summary_text(self) -> None:
        """Memperbarui label pratinjau rentang tanggal terpilih."""
        start_str = self._start_calendar.selectedDate().toString("dd MMM yyyy")
        end_str = self._end_calendar.selectedDate().toString("dd MMM yyyy")
        self._summary_label.setText(f"Rentang dipilih: {start_str}  —  {end_str}")

    def _on_apply_clicked(self) -> None:
        """Memancarkan sinyal penerapan rentang tanggal terpilih."""
        self.date_range_applied.emit(
            self._start_calendar.selectedDate(),
            self._end_calendar.selectedDate(),
        )

    def get_date_range(self) -> tuple[QDate, QDate]:
        """Mengembalikan pasangan tanggal awal dan tanggal akhir yang dipilih.

        Returns:
            Tuple berisi (tanggal_awal, tanggal_akhir) bertipe QDate.
        """
        return (
            self._start_calendar.selectedDate(),
            self._end_calendar.selectedDate(),
        )

    def set_date_range(self, start_date: QDate, end_date: QDate) -> None:
        """Menetapkan tanggal awal dan tanggal akhir pada kedua kalender.

        Args:
            start_date: Objek QDate untuk tanggal awal.
            end_date: Objek QDate untuk tanggal akhir.
        """
        if end_date < start_date:
            end_date = start_date
        self._start_calendar.setSelectedDate(start_date)
        self._end_calendar.setSelectedDate(end_date)
        self._refresh_summary_text()


class FilterBarWidget(QFrame):
    """Bar filter transaksi berisi periode tanggal, metode bayar, pencarian, dan tombol.

    Signals:
        filter_requested: Dipancarkan saat tombol Filter ditekan atau Enter pada pencarian.
        search_text_changed: Dipancarkan saat teks kolom pencarian berubah.
        custom_date_changed: Dipancarkan saat rentang tanggal kustom diterapkan.
    """

    filter_requested = Signal(object)
    search_text_changed = Signal(str)
    custom_date_changed = Signal(QDate, QDate)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi seluruh kontrol input dan panel kalender pada filter bar.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.date_combo = QComboBox(self)
        self.payment_combo = QComboBox(self)
        self.search_input = QLineEdit(self)
        self.filter_button = QPushButton("Filter", self)
        self.custom_date_button = QPushButton(self)
        self.date_range_panel = DateRangeCalendarPanel(self)

        self.setObjectName("FilterBarContainer")
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._sync_custom_date_button_label()

    def _setup_ui(self) -> None:
        """Menyusun kontrol filter secara horizontal serta panel kalender di bawahnya."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 7, 16, 7)
        root_layout.setSpacing(0)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        self.date_combo.addItems(list(DATE_FILTER_OPTIONS))
        self.date_combo.setMinimumWidth(148)
        self.date_combo.setFixedHeight(38)
        self.date_combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self.custom_date_button.setObjectName("CustomDateToggleButton")
        self.custom_date_button.setIcon(render_svg_icon("calendar", 15, "#93C5FD"))
        self.custom_date_button.setFixedHeight(38)
        self.custom_date_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_date_button.setVisible(False)

        self.payment_combo.addItems(list(PAYMENT_METHOD_OPTIONS))
        self.payment_combo.setMinimumWidth(155)
        self.payment_combo.setFixedHeight(38)
        self.payment_combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self.search_input.setPlaceholderText("Cari nomor invoice atau catatan transaksi...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(38)
        self.search_input.addAction(
            render_svg_icon("search", 15, "#94A3B8"),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self.filter_button.setObjectName("PrimaryFilterButton")
        self.filter_button.setIcon(render_svg_icon("filter", 15, "#FFFFFF"))
        self.filter_button.setIconSize(QSize(15, 15))
        self.filter_button.setFixedHeight(38)
        self.filter_button.setMinimumWidth(108)
        self.filter_button.setCursor(Qt.CursorShape.PointingHandCursor)

        controls_layout.addLayout(self._wrap_labeled_field("Tanggal", self.date_combo))
        controls_layout.addLayout(
            self._wrap_labeled_field("Rentang Custom", self.custom_date_button)
        )
        controls_layout.addLayout(
            self._wrap_labeled_field("Metode Bayar", self.payment_combo)
        )
        controls_layout.addLayout(
            self._wrap_labeled_field("Pencarian", self.search_input),
            stretch=1,
        )

        button_column = QVBoxLayout()
        button_column.setContentsMargins(0, 0, 0, 0)
        button_column.setSpacing(5)
        spacer_label = QLabel("", self)
        spacer_label.setObjectName("FilterFieldLabel")
        button_column.addWidget(spacer_label)
        button_column.addWidget(self.filter_button)
        controls_layout.addLayout(button_column)

        self.date_range_panel.setVisible(False)

        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self.date_range_panel)

    def _wrap_labeled_field(self, label_text: str, widget: QWidget) -> QVBoxLayout:
        """Membungkus widget input dengan label kecil di bagian atasnya.

        Args:
            label_text: Teks label keterangan untuk kontrol input.
            widget: Widget kontrol yang akan dibungkus.

        Returns:
            Objek QVBoxLayout berisi label dan widget kontrol.
        """
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(5)

        label = QLabel(label_text, self)
        label.setObjectName("FilterFieldLabel")
        if widget is self.custom_date_button:
            label.setVisible(False)
            self.custom_date_button.setProperty("linked_label", label)

        column.addWidget(label)
        column.addWidget(widget)
        return column

    def _apply_styles(self) -> None:
        """Menerapkan gaya QSS konsisten untuk bar filter dan seluruh inputnya."""
        self.setStyleSheet(
            """
            QFrame#FilterBarContainer {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 12px;
            }
            QLabel#FilterFieldLabel {
                color: #9399B2;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.3px;
                background: transparent;
            }
            QComboBox, QLineEdit {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 0px 12px;
                font-size: 13px;
            }
            QComboBox:hover, QLineEdit:hover {
                border-color: #45475A;
            }
            QComboBox:focus, QLineEdit:focus {
                border-color: #60A5FA;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 6px;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
            }
            QPushButton#CustomDateToggleButton {
                background-color: #1E293B;
                color: #BFDBFE;
                border: 1px solid #3B82F6;
                border-radius: 8px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CustomDateToggleButton:hover {
                background-color: #243552;
            }
            QPushButton#PrimaryFilterButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3B82F6,
                    stop: 1 #2563EB
                );
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#PrimaryFilterButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #60A5FA,
                    stop: 1 #3B82F6
                );
            }
            QPushButton#PrimaryFilterButton:pressed {
                background-color: #1D4ED8;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh sinyal interaksi kontrol filter."""
        self.date_combo.currentTextChanged.connect(self._on_date_preset_changed)
        self.custom_date_button.clicked.connect(self._toggle_date_panel)
        self.date_range_panel.date_range_applied.connect(self._on_custom_date_applied)
        self.date_range_panel.panel_closed.connect(self._hide_date_panel)
        self.filter_button.clicked.connect(self._emit_filter_request)
        self.search_input.returnPressed.connect(self._emit_filter_request)
        self.search_input.textChanged.connect(self.search_text_changed.emit)

    def _set_custom_controls_visible(self, visible: bool) -> None:
        """Mengatur visibilitas tombol rentang kustom beserta labelnya.

        Args:
            visible: True untuk menampilkan, False untuk menyembunyikan.
        """
        self.custom_date_button.setVisible(visible)
        linked_label = self.custom_date_button.property("linked_label")
        if isinstance(linked_label, QLabel):
            linked_label.setVisible(visible)

    def _on_date_preset_changed(self, selected_text: str) -> None:
        """Menampilkan atau menyembunyikan kalender rentang sesuai pilihan tanggal.

        Args:
            selected_text: Teks opsi periode yang dipilih dari dropdown.
        """
        is_custom = selected_text == "Custom"
        self._set_custom_controls_visible(is_custom)
        self.date_range_panel.setVisible(is_custom)
        if is_custom:
            self._sync_custom_date_button_label()

    def _toggle_date_panel(self) -> None:
        """Mengubah status tampil atau sembunyi panel kalender kustom."""
        self.date_range_panel.setVisible(not self.date_range_panel.isVisible())

    def _hide_date_panel(self) -> None:
        """Menyembunyikan panel kalender kustom."""
        self.date_range_panel.setVisible(False)

    def _on_custom_date_applied(self, start_date: QDate, end_date: QDate) -> None:
        """Memperbarui label tombol rentang dan menutup panel saat diterapkan.

        Args:
            start_date: Tanggal awal yang dipilih pengguna.
            end_date: Tanggal akhir yang dipilih pengguna.
        """
        self._sync_custom_date_button_label()
        self.date_range_panel.setVisible(False)
        self.custom_date_changed.emit(start_date, end_date)

    def _sync_custom_date_button_label(self) -> None:
        """Menyinkronkan teks tombol rentang kustom dengan tanggal pada kalender."""
        start_date, end_date = self.date_range_panel.get_date_range()
        self.custom_date_button.setText(
            f"{start_date.toString('dd/MM/yyyy')} - {end_date.toString('dd/MM/yyyy')}"
        )

    def _emit_filter_request(self) -> None:
        """Memancarkan sinyal permintaan filter membawa objek FilterCriteria."""
        self.filter_requested.emit(self.get_filter_criteria())

    def get_filter_criteria(self) -> FilterCriteria:
        """Mengambil seluruh nilai filter aktif saat ini dari komponen UI.

        Returns:
            Objek FilterCriteria berisi periode, rentang tanggal, metode bayar,
            dan kata kunci pencarian.
        """
        start_date, end_date = self.date_range_panel.get_date_range()
        return FilterCriteria(
            date_preset=self.date_combo.currentText(),
            start_date=start_date.toString("yyyy-MM-dd"),
            end_date=end_date.toString("yyyy-MM-dd"),
            payment_method=self.payment_combo.currentText(),
            search_query=self.search_input.text().strip(),
        )

    def reset_filters(self) -> None:
        """Mengembalikan seluruh pilihan filter ke kondisi bawaan."""
        today = QDate.currentDate()
        self.date_combo.setCurrentIndex(0)
        self.payment_combo.setCurrentIndex(0)
        self.search_input.clear()
        self.date_range_panel.set_date_range(today, today)
        self.date_range_panel.setVisible(False)
        self._set_custom_controls_visible(False)
        self._sync_custom_date_button_label()


class ZebraRowDelegate(QStyledItemDelegate):
    """Delegate kustom untuk merender pola baris zebra hitam dan putih kontras tinggi.

    Baris ganjil (nomor urut 1, 3, 5, ...) digambar dengan latar hitam dan teks
    putih, sedangkan baris genap (nomor urut 2, 4, 6, ...) digambar dengan latar
    putih dan teks hitam agar seluruh data terbaca tajam.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi palet warna baris ganjil, genap, dan terpilih.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._odd_bg = QColor("#12121A")
        self._odd_text = QColor("#F8FAFC")
        self._even_bg = QColor("#FFFFFF")
        self._even_text = QColor("#11111B")
        self._selected_bg = QColor("#2563EB")
        self._selected_text = QColor("#FFFFFF")

    @staticmethod
    def is_odd_visual_row(row_index: int) -> bool:
        """Menentukan apakah indeks baris termasuk baris ganjil secara visual.

        Args:
            row_index: Indeks baris berbasis nol dari model tabel.

        Returns:
            True untuk baris 1, 3, 5 (indeks genap), False untuk baris 2, 4, 6.
        """
        return row_index % 2 == 0

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar latar zebra hitam-putih, garis pemisah, dan teks sel tabel.

        Args:
            painter: Objek QPainter aktif untuk proses menggambar sel.
            option: Informasi gaya, dimensi, dan status visual sel.
            index: Indeks model baris dan kolom yang sedang dirender.
        """
        painter.save()

        is_odd = self.is_odd_visual_row(index.row())
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            bg_color = self._selected_bg
            text_color = self._selected_text
            divider_color = QColor("#1D4ED8")
        elif is_odd:
            bg_color = QColor("#1E2233") if is_hovered else self._odd_bg
            text_color = self._odd_text
            divider_color = QColor("#27273A")
        else:
            bg_color = QColor("#EBF2FF") if is_hovered else self._even_bg
            text_color = self._even_text
            divider_color = QColor("#CBD5E1")

        painter.fillRect(option.rect, bg_color)

        pen = QPen(divider_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(
            option.rect.bottomLeft(),
            option.rect.bottomRight(),
        )

        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        if raw_text is not None and str(raw_text) != "":
            text_str = str(raw_text)
            text_rect = option.rect.adjusted(12, 0, -12, 0)
            alignment_flags = self._resolve_alignment(index)

            painter.setFont(option.font)
            painter.setPen(text_color)
            metrics = QFontMetrics(option.font)
            elided = metrics.elidedText(
                text_str,
                Qt.TextElideMode.ElideRight,
                max(0, text_rect.width()),
            )
            painter.drawText(text_rect, alignment_flags, elided)

        painter.restore()

    @staticmethod
    def _resolve_alignment(index: QModelIndex | QPersistentModelIndex) -> int:
        """Mengambil flag perataan teks sel dalam bentuk integer aman untuk QPainter.

        Args:
            index: Indeks model sel yang sedang diproses.

        Returns:
            Nilai integer kombinasi flag perataan Qt.
        """
        raw_alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if isinstance(raw_alignment, Qt.AlignmentFlag):
            return int(raw_alignment.value)
        if isinstance(raw_alignment, int):
            return raw_alignment
        default_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return int(default_align.value)


class TransactionTableWidget(QTableWidget):
    """Tabel daftar riwayat transaksi dengan pola baris zebra hitam dan putih.

    Signals:
        detail_requested: Dipancarkan saat tombol Detail pada kolom Aksi diklik.
        print_requested: Dipancarkan saat tombol Cetak pada kolom Aksi diklik.
    """

    detail_requested = Signal(str)
    print_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi struktur kolom, header, delegate zebra, dan gaya tabel.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(0, len(TABLE_COLUMNS), parent)
        self._zebra_delegate = ZebraRowDelegate(self)

        self.setObjectName("TransactionTable")
        self.setHorizontalHeaderLabels(list(TABLE_COLUMNS))
        self.setItemDelegate(self._zebra_delegate)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self._configure_headers()
        self._apply_styles()

    def _configure_headers(self) -> None:
        """Mengatur ukuran, mode resize, dan perilaku header tabel."""
        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setHighlightSections(False)
            h_header.setFixedHeight(44)
            h_header.setStretchLastSection(False)

            column_widths: dict[str, int] = {
                "No": 54,
                "Tanggal": 142,
                "Metode Bayar": 122,
                "Sub Total": 125,
                "Diskon": 108,
                "Pembulatan": 108,
                "Total": 130,
                "Aksi": 148,
            }
            for col_index, col_name in enumerate(TABLE_COLUMNS):
                if col_name == "Invoice":
                    h_header.setSectionResizeMode(
                        col_index,
                        QHeaderView.ResizeMode.Stretch,
                    )
                else:
                    h_header.setSectionResizeMode(
                        col_index,
                        QHeaderView.ResizeMode.Fixed,
                    )
                    h_header.resizeSection(
                        col_index,
                        column_widths.get(col_name, 120),
                    )

        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(44)

    def _apply_styles(self) -> None:
        """Menerapkan gaya QSS untuk bingkai, viewport, dan header tabel."""
        self.setStyleSheet(
            """
            QTableWidget#TransactionTable {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 12px;
                font-size: 13px;
                outline: none;
            }
            QHeaderView::section {
                background-color: #1E1E2E;
                color: #BAC2DE;
                font-size: 12px;
                font-weight: 700;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #313244;
            }
            QTableCornerButton::section {
                background-color: #1E1E2E;
                border: none;
            }
            """
        )

    def clear_rows(self) -> None:
        """Menghapus seluruh baris data dari tabel tanpa mengubah header kolom."""
        self.setRowCount(0)

    def create_action_widget(self, invoice_no: str) -> QWidget:
        """Membuat widget tombol aksi standar (Detail dan Cetak) untuk satu baris.

        Args:
            invoice_no: Nomor invoice yang akan dikirimkan melalui sinyal tombol.

        Returns:
            Widget kontainer transparan berisi tombol aksi kontras tinggi.
        """
        container = QWidget(self)
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detail_btn = QPushButton("Detail", container)
        detail_btn.setFixedHeight(28)
        detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3B82F6;
            }
            """
        )

        print_btn = QPushButton("Cetak", container)
        print_btn.setFixedHeight(28)
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #334155;
                color: #F8FAFC;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 0px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            """
        )

        def emit_detail() -> None:
            """Memancarkan sinyal detail untuk invoice terkait."""
            self.detail_requested.emit(invoice_no)

        def emit_print() -> None:
            """Memancarkan sinyal cetak struk untuk invoice terkait."""
            self.print_requested.emit(invoice_no)

        detail_btn.clicked.connect(emit_detail)
        print_btn.clicked.connect(emit_print)

        layout.addWidget(detail_btn)
        layout.addWidget(print_btn)
        return container

    def add_transaction_row(self, row_data: TransactionRowData) -> int:
        """Menambahkan satu baris transaksi ke bagian akhir tabel.

        Args:
            row_data: Objek TransactionRowData berisi nilai untuk setiap kolom.

        Returns:
            Indeks baris baru yang telah ditambahkan ke dalam tabel.
        """
        row_index = self.rowCount()
        self.insertRow(row_index)

        values: tuple[tuple[str, Qt.AlignmentFlag], ...] = (
            (str(row_data.no), Qt.AlignmentFlag.AlignCenter),
            (
                row_data.invoice,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            ),
            (row_data.tanggal, Qt.AlignmentFlag.AlignCenter),
            (row_data.metode_bayar, Qt.AlignmentFlag.AlignCenter),
            (
                row_data.sub_total,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ),
            (
                row_data.diskon,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ),
            (
                row_data.pembulatan,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ),
            (
                row_data.total,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ),
        )

        for col_index, (text_value, alignment) in enumerate(values):
            item = QTableWidgetItem(text_value)
            item.setTextAlignment(alignment)
            self.setItem(row_index, col_index, item)

        action_col = len(TABLE_COLUMNS) - 1
        self.setItem(row_index, action_col, QTableWidgetItem(""))
        self.setCellWidget(
            row_index,
            action_col,
            self.create_action_widget(row_data.invoice),
        )
        return row_index

    def set_transactions(self, rows: list[TransactionRowData]) -> None:
        """Mengganti seluruh isi baris tabel dengan daftar transaksi baru.

        Args:
            rows: Daftar objek TransactionRowData yang akan dirender ke tabel.
        """
        self.clear_rows()
        for row_data in rows:
            self.add_transaction_row(row_data)

    def set_row_action_widget(self, row: int, widget: QWidget) -> None:
        """Menempatkan widget aksi kustom pada kolom Aksi baris tertentu.

        Args:
            row: Indeks baris target.
            widget: Widget kustom yang akan dipasang di kolom Aksi.
        """
        if 0 <= row < self.rowCount():
            action_col = len(TABLE_COLUMNS) - 1
            self.setCellWidget(row, action_col, widget)


class PaginationWidget(QWidget):
    """Komponen navigasi halaman (pagination) di sisi kiri footer.

    Signals:
        page_changed: Dipancarkan saat pengguna berpindah halaman membawa nomor halaman baru.
    """

    page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi tombol navigasi dan indikator halaman aktif.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._prev_button = QPushButton("‹ Sebelumnya", self)
        self._page_badge = QLabel("1", self)
        self._next_button = QPushButton("Berikutnya ›", self)
        self._page_label = QLabel("Halaman 1 dari 1", self)
        self._total_label = QLabel("Total 0 data", self)
        self._current_page: int = 1
        self._total_pages: int = 1

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._sync_controls()

    def _setup_ui(self) -> None:
        """Menyusun tombol sebelumnya, nomor halaman, tombol berikutnya, dan ringkasan."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._prev_button.setObjectName("NavPageButton")
        self._prev_button.setFixedHeight(30)
        self._prev_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._page_badge.setObjectName("ActivePageBadge")
        self._page_badge.setFixedSize(30, 30)
        self._page_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._next_button.setObjectName("NavPageButton")
        self._next_button.setFixedHeight(30)
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._page_label.setObjectName("PageMetaLabel")
        self._total_label.setObjectName("PageTotalLabel")

        layout.addWidget(self._prev_button)
        layout.addWidget(self._page_badge)
        layout.addWidget(self._next_button)
        layout.addSpacing(8)
        layout.addWidget(self._page_label)
        layout.addWidget(self._total_label)

    def _apply_styles(self) -> None:
        """Menerapkan gaya visual untuk tombol dan badge navigasi halaman."""
        self.setStyleSheet(
            """
            QPushButton#NavPageButton {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#NavPageButton:hover:enabled {
                background-color: #2A2B3D;
                border-color: #60A5FA;
            }
            QPushButton#NavPageButton:disabled {
                background-color: #161622;
                color: #585B70;
                border-color: #242536;
            }
            QLabel#ActivePageBadge {
                background-color: #2563EB;
                color: #FFFFFF;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#PageMetaLabel {
                color: #BAC2DE;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#PageTotalLabel {
                color: #7F849C;
                font-size: 12px;
                padding-left: 6px;
                background: transparent;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan aksi klik tombol navigasi sebelumnya dan berikutnya."""
        self._prev_button.clicked.connect(self._go_previous)
        self._next_button.clicked.connect(self._go_next)

    def _go_previous(self) -> None:
        """Berpindah ke halaman sebelumnya jika masih tersedia."""
        if self._current_page > 1:
            self._current_page -= 1
            self._sync_controls()
            self.page_changed.emit(self._current_page)

    def _go_next(self) -> None:
        """Berpindah ke halaman berikutnya jika masih tersedia."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._sync_controls()
            self.page_changed.emit(self._current_page)

    def _sync_controls(self) -> None:
        """Menyinkronkan teks indikator dan status aktif tombol navigasi."""
        self._page_badge.setText(str(self._current_page))
        self._page_label.setText(
            f"Halaman {self._current_page} dari {self._total_pages}"
        )
        self._prev_button.setEnabled(self._current_page > 1)
        self._next_button.setEnabled(self._current_page < self._total_pages)

    def set_pagination(
        self,
        current_page: int,
        total_pages: int,
        total_items: int = 0,
    ) -> None:
        """Memperbarui status paginasi dari hasil query backend.

        Args:
            current_page: Nomor halaman aktif saat ini (minimal 1).
            total_pages: Jumlah seluruh halaman yang tersedia (minimal 1).
            total_items: Jumlah total catatan data transaksi.
        """
        self._total_pages = max(1, total_pages)
        self._current_page = max(1, min(current_page, self._total_pages))
        self._total_label.setText(f"•  Total {max(0, total_items)} data")
        self._sync_controls()

    def get_current_page(self) -> int:
        """Mengembalikan nomor halaman yang sedang aktif.

        Returns:
            Nomor halaman aktif bertipe integer.
        """
        return self._current_page

    def reset_pagination(self) -> None:
        """Mengembalikan paginasi ke halaman pertama dengan nol data."""
        self.set_pagination(current_page=1, total_pages=1, total_items=0)


class FooterBarWidget(QFrame):
    """Kontainer bagian bawah halaman berisi navigation_page dan tombol ekspor.

    Attributes:
        navigation_page: Komponen paginasi di sisi kiri footer.
        export_excel: Tombol untuk memicu ekspor data ke format Excel.
        export_pdf: Tombol untuk memicu ekspor data ke format PDF.

    Signals:
        page_changed: Meneruskan sinyal perpindahan halaman dari navigation_page.
        export_excel_requested: Dipancarkan saat tombol export_excel diklik.
        export_pdf_requested: Dipancarkan saat tombol export_pdf diklik.
    """

    page_changed = Signal(int)
    export_excel_requested = Signal()
    export_pdf_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi kontainer footer dengan navigasi dan tombol ekspor.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.navigation_page = PaginationWidget(self)
        self.export_excel = QPushButton("Export Excel", self)
        self.export_pdf = QPushButton("Export PDF", self)

        self.setObjectName("FooterBarContainer")
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Menyusun navigation_page di kiri serta tombol ekspor di kanan."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        self.export_excel.setObjectName("ExportExcelButton")
        self.export_excel.setIcon(render_svg_icon("excel", 16, "#FFFFFF"))
        self.export_excel.setIconSize(QSize(16, 16))
        self.export_excel.setFixedHeight(30)
        self.export_excel.setMinimumWidth(138)
        self.export_excel.setCursor(Qt.CursorShape.PointingHandCursor)

        self.export_pdf.setObjectName("ExportPdfButton")
        self.export_pdf.setIcon(render_svg_icon("pdf", 16, "#FFFFFF"))
        self.export_pdf.setIconSize(QSize(16, 16))
        self.export_pdf.setFixedHeight(30)
        self.export_pdf.setMinimumWidth(132)
        self.export_pdf.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.navigation_page)
        layout.addStretch()
        layout.addWidget(self.export_excel)
        layout.addWidget(self.export_pdf)

    def _apply_styles(self) -> None:
        """Menerapkan gaya visual untuk kontainer footer dan kedua tombol ekspor."""
        self.setStyleSheet(
            """
            QFrame#FooterBarContainer {
                background-color: #181825;
                border-radius: 12px;
            }
            QPushButton#ExportExcelButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #16A34A,
                    stop: 1 #15803D
                );
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 0px 16px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#ExportExcelButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #22C55E,
                    stop: 1 #16A34A
                );
            }
            QPushButton#ExportExcelButton:pressed {
                background-color: #166534;
            }
            QPushButton#ExportPdfButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #DC2626,
                    stop: 1 #B91C1C
                );
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 0px 16px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#ExportPdfButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #EF4444,
                    stop: 1 #DC2626
                );
            }
            QPushButton#ExportPdfButton:pressed {
                background-color: #991B1B;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal internal footer ke sinyal publik."""
        self.navigation_page.page_changed.connect(self.page_changed.emit)
        self.export_excel.clicked.connect(self.export_excel_requested.emit)
        self.export_pdf.clicked.connect(self.export_pdf_requested.emit)

    def set_export_enabled(self, enabled: bool) -> None:
        """Mengaktifkan atau menonaktifkan kedua tombol ekspor secara bersamaan.

        Args:
            enabled: True untuk mengaktifkan tombol, False untuk menonaktifkan.
        """
        self.export_excel.setEnabled(enabled)
        self.export_pdf.setEnabled(enabled)


class RiwayatTransaksiPage(QWidget):
    """Halaman utama UI Riwayat Transaksi untuk didaftarkan ke dalam MainShell.

    Halaman ini menyusun header, tiga kartu statistik gradien, filter bar dengan
    pemilih rentang kalender kustom, tabel zebra hitam-putih, serta bar navigasi
    halaman dan tombol ekspor Excel/PDF.

    Signals:
        page_entered: Dipancarkan setiap kali halaman aktif melalui MainShell.
        filter_requested: Dipancarkan saat filter dijalankan membawa FilterCriteria.
        search_text_changed: Dipancarkan saat teks kolom pencarian berubah.
        page_changed: Dipancarkan saat nomor halaman pada navigation_page berubah.
        export_excel_requested: Dipancarkan saat tombol export_excel diklik.
        export_pdf_requested: Dipancarkan saat tombol export_pdf diklik.
        detail_requested: Dipancarkan saat tombol Detail pada baris tabel diklik.
        print_requested: Dipancarkan saat tombol Cetak pada baris tabel diklik.
    """

    page_entered = Signal()
    filter_requested = Signal(object)
    search_text_changed = Signal(str)
    page_changed = Signal(int)
    export_excel_requested = Signal()
    export_pdf_requested = Signal()
    detail_requested = Signal(str)
    print_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi halaman Riwayat Transaksi beserta seluruh komponennya.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._header_widget = self._build_header()
        self.summary_cards = SummaryCardsContainer(self)
        self.filter_bar = FilterBarWidget(self)
        self.table = TransactionTableWidget(self)
        self._footer_bar = FooterBarWidget(self)

        self.setObjectName("RiwayatTransaksiPage")
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()

    def _build_header(self) -> QWidget:
        """Membangun bagian header atas halaman bertuliskan Riwayat Transaksi.

        Returns:
            Widget header yang berisi indikator aksen, judul, dan subjudul.
        """
        header = QWidget(self)
        header.setObjectName("PageHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(12)

        accent_bar = QFrame(header)
        accent_bar.setObjectName("HeaderAccentBar")
        accent_bar.setFixedSize(5, 36)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)

        title_label = QLabel("Riwayat Transaksi", header)
        title_label.setObjectName("PageTitleLabel")

        subtitle_label = QLabel(
            "Pantau ringkasan penjualan, filter periode transaksi, dan ekspor laporan.",
            header,
        )
        subtitle_label.setObjectName("PageSubtitleLabel")

        text_column.addWidget(title_label)
        text_column.addWidget(subtitle_label)

        layout.addWidget(accent_bar)
        layout.addLayout(text_column)
        layout.addStretch()
        return header

    def _setup_ui(self) -> None:
        """Menyusun tata letak vertikal seluruh bagian halaman Riwayat Transaksi."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 1)
        layout.setSpacing(8)

        layout.addWidget(self._header_widget)
        layout.addWidget(self.summary_cards)
        layout.addWidget(self.filter_bar)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self._footer_bar)

    def _apply_styles(self) -> None:
        """Menerapkan warna latar belakang dan tipografi header halaman."""
        self.setStyleSheet(
            """
            QWidget#RiwayatTransaksiPage {
                background-color: #11111B;
            }
            QWidget#PageHeader {
                background: transparent;
            }
            QFrame#HeaderAccentBar {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60A5FA,
                    stop: 1 #8B5CF6
                );
                border-radius: 2px;
            }
            QLabel#PageTitleLabel {
                color: #F8FAFC;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 0.3px;
                background: transparent;
            }
            QLabel#PageSubtitleLabel {
                color: #9399B2;
                font-size: 12px;
                background: transparent;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal dari subkomponen ke sinyal tingkat halaman."""
        self.filter_bar.filter_requested.connect(self.filter_requested.emit)
        self.filter_bar.search_text_changed.connect(self.search_text_changed.emit)
        self.table.detail_requested.connect(self.detail_requested.emit)
        self.table.print_requested.connect(self.print_requested.emit)
        self._footer_bar.page_changed.connect(self.page_changed.emit)
        self._footer_bar.export_excel_requested.connect(
            self.export_excel_requested.emit
        )
        self._footer_bar.export_pdf_requested.connect(self.export_pdf_requested.emit)

    @property
    def navigation_page(self) -> PaginationWidget:
        """Mengembalikan widget navigasi halaman di sisi kiri footer."""
        return self._footer_bar.navigation_page

    @property
    def export_excel(self) -> QPushButton:
        """Mengembalikan tombol ekspor Excel di sisi kanan footer."""
        return self._footer_bar.export_excel

    @property
    def export_pdf(self) -> QPushButton:
        """Mengembalikan tombol ekspor PDF di sisi kanan footer."""
        return self._footer_bar.export_pdf

    @property
    def card_total_transaksi(self) -> SummaryCardWidget:
        """Mengembalikan referensi kartu statistik Total Transaksi."""
        return self.summary_cards.card_total_transaksi

    @property
    def card_total_revenue(self) -> SummaryCardWidget:
        """Mengembalikan referensi kartu statistik Total Revenue."""
        return self.summary_cards.card_total_revenue

    @property
    def card_rata_rata(self) -> SummaryCardWidget:
        """Mengembalikan referensi kartu statistik Rata-Rata."""
        return self.summary_cards.card_rata_rata

    def on_page_entered(self) -> None:
        """Hook siklus hidup yang dipanggil otomatis oleh MainShell saat halaman dibuka."""
        self.page_entered.emit()

    def get_filter_criteria(self) -> FilterCriteria:
        """Mengambil kriteria filter aktif dari filter bar.

        Returns:
            Objek FilterCriteria berisi seluruh nilai filter UI saat ini.
        """
        return self.filter_bar.get_filter_criteria()

    def set_summary_values(
        self,
        total_transaksi: str,
        total_revenue: str,
        rata_rata: str,
    ) -> None:
        """Memperbarui nilai utama ketiga kartu statistik di bagian atas.

        Args:
            total_transaksi: Teks jumlah total transaksi.
            total_revenue: Teks total pendapatan terformat.
            rata_rata: Teks rata-rata nominal transaksi terformat.
        """
        self.summary_cards.update_values(total_transaksi, total_revenue, rata_rata)

    def set_transactions(self, rows: list[TransactionRowData]) -> None:
        """Mengisi baris tabel dengan daftar data transaksi dari backend.

        Args:
            rows: Daftar objek TransactionRowData untuk ditampilkan pada tabel.
        """
        self.table.set_transactions(rows)

    def set_pagination(
        self,
        current_page: int,
        total_pages: int,
        total_items: int = 0,
    ) -> None:
        """Memperbarui tampilan navigasi halaman di footer.

        Args:
            current_page: Nomor halaman aktif.
            total_pages: Jumlah total halaman.
            total_items: Jumlah total baris data keseluruhan.
        """
        self.navigation_page.set_pagination(current_page, total_pages, total_items)

    def clear_view(self) -> None:
        """Mengosongkan tabel dan mengatur ulang kartu, filter, serta paginasi."""
        self.summary_cards.reset_all()
        self.filter_bar.reset_filters()
        self.table.clear_rows()
        self.navigation_page.reset_pagination()


class RiwayatTransaksiWindow(FramelessMainWindow):
    """Jendela standalone Riwayat Transaksi dengan CustomTitleBar bawaan proyek.

    Attributes:
        page: Instance RiwayatTransaksiPage yang dimuat ke dalam area konten jendela.
    """

    def __init__(
        self,
        icon_config: TitleBarIconConfig | None = None,
        page_title: str = "Riwayat Transaksi",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi jendela frameless beserta halaman Riwayat Transaksi.

        Args:
            icon_config: Konfigurasi path ikon title bar. Jika None, akan memuat
                konfigurasi standar dari ICON_PATHS.
            page_title: Judul halaman yang ditampilkan pada CustomTitleBar.
            parent: Widget induk opsional.
        """
        resolved_config = (
            icon_config
            if icon_config is not None
            else TitleBarIconConfig.from_dict(ICON_PATHS)
        )
        super().__init__(
            icon_config=resolved_config,
            page_title=page_title,
            parent=parent,
        )
        self.page = RiwayatTransaksiPage(self)
        self.set_content_widget(self.page)


