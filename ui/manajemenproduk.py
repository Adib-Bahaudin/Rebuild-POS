"""Modul antarmuka manajemen produk (barang dan jasa) berbasis PySide6.

Modul ini menyediakan komponen UI murni untuk halaman manajemen produk yang
mendukung tampilan multi-satuan, pelacakan stok FIFO, komposisi bahan jasa,
filter terpadu, paginasi, serta panel detail cepat tanpa menyertakan logika
basis data secara langsung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
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


@dataclass(frozen=True)
class ProductMetricsData:
    """Menyimpan data ringkasan indikator utama pada bagian atas halaman.

    Attributes:
        active_catalog_count: Jumlah total barang dan jasa yang berstatus aktif.
        active_catalog_sub: Keterangan singkat rincian jumlah barang dan jasa.
        low_stock_count: Jumlah barang dengan stok menipis atau habis.
        low_stock_sub: Keterangan tambahan kondisi stok kritis.
        inventory_value_text: Teks nominal total nilai aset stok FIFO.
        inventory_value_sub: Keterangan jumlah batch layer FIFO aktif.
        inactive_count: Jumlah produk atau jasa yang diarsipkan.
        inactive_sub: Keterangan tambahan terkait katalog nonaktif.
    """

    active_catalog_count: int = 0
    active_catalog_sub: str = "0 barang · 0 jasa"
    low_stock_count: int = 0
    low_stock_sub: str = "Perlu restok segera"
    inventory_value_text: str = "Rp 0"
    inventory_value_sub: str = "Kalkulasi layer FIFO aktif"
    inactive_count: int = 0
    inactive_sub: str = "Disembunyikan dari kasir"


@dataclass(frozen=True)
class CategoryOption:
    """Merepresentasikan satu opsi kategori untuk dropdown filter.

    Attributes:
        category_id: Identitas unik kategori dari basis data.
        label: Nama kategori termasuk format hierarki bila memiliki induk.
    """

    category_id: int
    label: str


@dataclass(frozen=True)
class ItemRowData:
    """Data ringkas satu baris barang fisik pada tabel utama.

    Attributes:
        item_id: Identitas unik item.
        sku: Kode SKU barang.
        name: Nama barang.
        category_name: Nama kategori barang.
        default_price_text: Teks harga jual satuan default terformat.
        unit_summary: Informasi satuan default dan jumlah varian satuan lain.
        stock_text: Teks jumlah sisa stok beserta simbol satuan dasar.
        stock_state: Status visual ketersediaan stok ('ok', 'low', atau 'empty').
        is_active: Status aktif item pada katalog penjualan.
    """

    item_id: int
    sku: str
    name: str
    category_name: str
    default_price_text: str
    unit_summary: str
    stock_text: str
    stock_state: Literal["ok", "low", "empty"]
    is_active: bool


@dataclass(frozen=True)
class ItemUnitDetail:
    """Data satu baris variasi satuan jual pada panel detail barang.

    Attributes:
        variant_name: Nama varian satuan jual.
        unit_symbol: Simbol satuan.
        conversion_qty: Nilai faktor konversi ke satuan dasar.
        selling_price_text: Teks harga jual terformat.
        is_default: Penanda apakah varian merupakan satuan utama kasir.
        is_active: Status aktif varian satuan.
    """

    variant_name: str
    unit_symbol: str
    conversion_qty: float
    selling_price_text: str
    is_default: bool
    is_active: bool


@dataclass(frozen=True)
class InventoryLayerDetail:
    """Data satu baris batch layer stok FIFO pada panel detail barang.

    Attributes:
        received_at: Tanggal penerimaan stok.
        source_type: Jenis sumber masuk stok (misalnya PURCHASE atau OPENING_STOCK).
        remaining_qty_text: Sisa kuantitas pada layer beserta simbol satuan.
        unit_cost_text: Harga modal satuan pada batch tersebut.
    """

    received_at: str
    source_type: str
    remaining_qty_text: str
    unit_cost_text: str


@dataclass(frozen=True)
class ItemFullDetail:
    """Data lengkap satu barang untuk ditampilkan pada panel detail kanan.

    Attributes:
        item_id: Identitas unik barang.
        sku: Kode SKU barang.
        name: Nama lengkap barang.
        category_name: Nama kategori barang.
        base_unit_name: Nama dan simbol satuan dasar.
        description: Deskripsi opsional barang.
        total_stock_text: Total sisa stok gabungan seluruh layer aktif.
        total_value_text: Total nilai aset modal FIFO barang tersebut.
        is_active: Status aktif barang.
        units: Daftar variasi satuan jual barang.
        fifo_layers: Daftar layer stok FIFO yang masih memiliki sisa.
    """

    item_id: int
    sku: str
    name: str
    category_name: str
    base_unit_name: str
    description: str
    total_stock_text: str
    total_value_text: str
    is_active: bool
    units: list[ItemUnitDetail] = field(default_factory=list)
    fifo_layers: list[InventoryLayerDetail] = field(default_factory=list)


@dataclass(frozen=True)
class ServiceRowData:
    """Data ringkas satu baris layanan jasa pada tabel utama.

    Attributes:
        service_id: Identitas unik jasa.
        sku: Kode SKU jasa.
        name: Nama layanan jasa.
        selling_price_text: Teks harga jual jasa terformat.
        material_summary: Ringkasan jumlah bahan baku terkait.
        is_active: Status aktif jasa pada katalog kasir.
    """

    service_id: int
    sku: str
    name: str
    selling_price_text: str
    material_summary: str
    is_active: bool


@dataclass(frozen=True)
class ServiceMaterialDetail:
    """Data satu baris komposisi bahan baku pada panel detail jasa.

    Attributes:
        item_sku: Kode SKU bahan baku.
        item_name: Nama barang bahan baku.
        quantity_text: Takaran pemakaian per satu kali transaksi jasa.
        estimated_cost_text: Estimasi biaya modal bahan berdasarkan FIFO.
    """

    item_sku: str
    item_name: str
    quantity_text: str
    estimated_cost_text: str


@dataclass(frozen=True)
class ServiceFullDetail:
    """Data lengkap satu layanan jasa untuk ditampilkan pada panel detail kanan.

    Attributes:
        service_id: Identitas unik jasa.
        sku: Kode SKU jasa.
        name: Nama lengkap jasa.
        description: Deskripsi layanan jasa.
        selling_price_text: Harga jual layanan terformat.
        estimated_hpp_text: Estimasi total modal bahan per layanan.
        is_active: Status aktif jasa.
        materials: Daftar komposisi bahan baku yang memotong stok.
    """

    service_id: int
    sku: str
    name: str
    description: str
    selling_price_text: str
    estimated_hpp_text: str
    is_active: bool
    materials: list[ServiceMaterialDetail] = field(default_factory=list)


@dataclass(frozen=True)
class ProductFilterState:
    """Keadaan terkini dari seluruh kontrol filter pada halaman produk.

    Attributes:
        active_tab: Tab aktif saat ini ('items' atau 'services').
        search_text: Kata kunci pencarian SKU atau nama.
        category_id: Identitas kategori terpilih atau None untuk semua kategori.
        stock_filter: Filter kondisi stok ('ALL', 'AVAILABLE', 'LOW', 'EMPTY').
        status_filter: Filter status aktif ('ALL', 'ACTIVE', 'INACTIVE').
    """

    active_tab: Literal["items", "services"]
    search_text: str
    category_id: int | None
    stock_filter: str
    status_filter: str


class _FullRowGradientDelegate(QStyledItemDelegate):
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if option.state & QStyle.StateFlag.State_Selected:
            view = option.widget
            viewport = (
                view.viewport()
                if isinstance(view, QAbstractItemView)
                else None
            )
            total_width = (
                viewport.width()
                if viewport is not None
                else option.rect.right()
            )
            grad = QLinearGradient(
                0,
                option.rect.top(),
                max(1, total_width),
                option.rect.top(),
            )
            grad.setColorAt(0.0, QColor(59, 130, 246, 82))
            grad.setColorAt(0.55, QColor(14, 165, 233, 66))
            grad.setColorAt(1.0, QColor(6, 182, 212, 48))

            painter.save()
            painter.fillRect(option.rect, grad)
            painter.restore()

            clean_opt = QStyleOptionViewItem(option)
            clean_opt.state &= ~QStyle.StateFlag.State_HasFocus
            super().paint(painter, clean_opt, index)
            return

        super().paint(painter, option, index)


class CompactMetricCard(QFrame):
    """Kartu indikator ringkas dengan tata letak padat untuk metrik produk.

    Attributes:
        accent_color: Kode warna aksen strip kiri kartu.
    """

    def __init__(
        self,
        title: str,
        initial_value: str = "0",
        initial_subtitle: str = "",
        accent_color: str = "#3B82F6",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi CompactMetricCard dengan judul dan nilai awal.

        Args:
            title: Judul singkat indikator.
            initial_value: Teks nilai utama awal.
            initial_subtitle: Teks keterangan pendukung di bawah nilai utama.
            accent_color: Warna garis aksen di sisi kiri kartu.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.accent_color = accent_color
        self.setObjectName("CompactMetricCard")
        self.setFixedHeight(58)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._title_label = QLabel(title.upper(), self)
        self._value_label = QLabel(initial_value, self)
        self._subtitle_label = QLabel(initial_subtitle, self)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Menyusun tata letak vertikal ringkas untuk teks indikator."""
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        accent_gradients = {
            "#3B82F6": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #60A5FA, stop:1 #2563EB)",
            "#F59E0B": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FBBF24, stop:1 #D97706)",
            "#22C55E": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4ADE80, stop:1 #16A34A)",
            "#94A3B8": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #CBD5E1, stop:1 #64748B)",
        }
        accent_bg = accent_gradients.get(self.accent_color, self.accent_color)

        accent_bar = QFrame(self)
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(
            f"background: {accent_bg}; border: none; "
            "border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
        )

        content_widget = QWidget(self)
        content_widget.setObjectName("MetricContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 6, 10, 6)
        content_layout.setSpacing(1)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self._title_label.setObjectName("MetricTitle")
        self._subtitle_label.setObjectName("MetricSubtitle")
        self._subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        top_row.addWidget(self._title_label)
        top_row.addStretch(1)
        top_row.addWidget(self._subtitle_label)

        self._value_label.setObjectName("MetricValue")

        content_layout.addLayout(top_row)
        content_layout.addWidget(self._value_label)

        root_layout.addWidget(accent_bar)
        root_layout.addWidget(content_widget, 1)

    def _apply_styles(self) -> None:
        """Menerapkan gaya QSS ringkas pada kartu metrik."""
        card_themes = {
            "#3B82F6": (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E3A5F, stop:0.55 #1B2C4B, stop:1 #162038)",
                "#3B5B8C",
            ),
            "#F59E0B": (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4A3116, stop:0.55 #35251A, stop:1 #241B1E)",
                "#785124",
            ),
            "#22C55E": (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #144332, stop:0.55 #16332C, stop:1 #142228)",
                "#2B6E52",
            ),
            "#94A3B8": (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B304D, stop:0.55 #24273E, stop:1 #1C1E30)",
                "#484E73",
            ),
        }
        card_bg, card_border = card_themes.get(
            self.accent_color,
            (
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #282C47, stop:1 #1C1E30)",
                "#3D4266",
            ),
        )
        self.setStyleSheet(
            f"""
            QFrame#CompactMetricCard {{
                background: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
            QWidget#MetricContent {{
                background: transparent;
                border: none;
            }}
            QLabel#MetricTitle {{
                color: #CBD5E1;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.4px;
                background: transparent;
            }}
            QLabel#MetricValue {{
                color: #F8FAFC;
                font-size: 17px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#MetricSubtitle {{
                color: #A6B2CC;
                font-size: 10px;
                background: transparent;
            }}
            QWidget#TableCellContainer {{
                background-color: transparent;
                border: none;
            }}
            """
        )

    def update_metric(self, value: str, subtitle: str) -> None:
        """Memperbarui teks nilai utama dan keterangan pendukung kartu.

        Args:
            value: Teks nilai indikator terbaru.
            subtitle: Teks keterangan pendukung terbaru.
        """
        self._value_label.setText(value)
        self._subtitle_label.setText(subtitle)


class ProductDetailPanel(QFrame):
    """Panel samping kanan untuk menampilkan rincian cepat barang atau jasa.

    Attributes:
        edit_item_requested: Sinyal untuk mengedit barang yang sedang tampil.
        stock_card_requested: Sinyal untuk membuka kartu stok barang terpilih.
        adjust_stock_requested: Sinyal untuk penyesuaian stok barang terpilih.
        edit_service_requested: Sinyal untuk mengedit jasa yang sedang tampil.
    """

    edit_item_requested = Signal(int)
    stock_card_requested = Signal(int)
    adjust_stock_requested = Signal(int)
    edit_service_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi ProductDetailPanel dengan tampilan kosong awal.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(300)
        self._current_item_id: int | None = None
        self._current_service_id: int | None = None

        self._stack = QStackedWidget(self)

        self._item_sku_badge = QLabel("-", self)
        self._item_status_badge = QLabel("-", self)
        self._item_name_label = QLabel("-", self)
        self._item_meta_label = QLabel("-", self)
        self._item_desc_label = QLabel("-", self)
        self._item_stock_val = QLabel("0", self)
        self._item_asset_val = QLabel("Rp 0", self)
        self._units_table = QTableWidget(0, 4, self)
        self._layers_table = QTableWidget(0, 4, self)

        self._service_sku_badge = QLabel("-", self)
        self._service_status_badge = QLabel("-", self)
        self._service_name_label = QLabel("-", self)
        self._service_desc_label = QLabel("-", self)
        self._service_price_val = QLabel("Rp 0", self)
        self._service_hpp_val = QLabel("Rp 0", self)
        self._materials_table = QTableWidget(0, 3, self)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Menyusun tumpukan halaman kosong, detail barang, dan detail jasa."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack.addWidget(self._build_empty_page())
        self._stack.addWidget(self._build_item_detail_page())
        self._stack.addWidget(self._build_service_detail_page())
        self._stack.setCurrentIndex(0)

        layout.addWidget(self._stack)

    def _build_empty_page(self) -> QWidget:
        """Membangun halaman placeholder ketika belum ada baris yang dipilih.

        Returns:
            Widget placeholder berpusat dengan pesan instruksi ringkas.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)
        layout.addStretch(1)

        title = QLabel("Detail Produk", page)
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(
            "Pilih salah satu baris barang atau jasa di tabel kiri "
            "untuk melihat variasi satuan, layer FIFO, atau komposisi bahan.",
            page,
        )
        hint.setObjectName("EmptyHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _configure_mini_table(
        self,
        table: QTableWidget,
        headers: list[str],
        stretch_col: int,
    ) -> None:
        """Mengonfigurasi tabel mini agar padat, baca-saja, dan proporsional.

        Args:
            table: Objek QTableWidget yang akan dikonfigurasi.
            headers: Daftar judul kolom tabel.
            stretch_col: Indeks kolom yang otomatis meluas mengisi sisa lebar.
        """
        table.setObjectName("MiniTable")
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        v_header = table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(25)

        h_header = table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(25)
            h_header.setHighlightSections(False)
            for idx in range(len(headers)):
                mode = (
                    QHeaderView.ResizeMode.Stretch
                    if idx == stretch_col
                    else QHeaderView.ResizeMode.ResizeToContents
                )
                h_header.setSectionResizeMode(idx, mode)

    def _build_item_detail_page(self) -> QWidget:
        """Membangun halaman rincian lengkap untuk barang fisik.

        Returns:
            Widget panel detail barang berisi info, satuan, dan layer FIFO.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(6)
        self._item_sku_badge.setObjectName("SkuBadge")
        self._item_status_badge.setObjectName("StatusBadge")
        badge_row.addWidget(self._item_sku_badge)
        badge_row.addWidget(self._item_status_badge)
        badge_row.addStretch(1)

        self._item_name_label.setObjectName("DetailTitle")
        self._item_name_label.setWordWrap(True)
        self._item_meta_label.setObjectName("DetailMeta")
        self._item_desc_label.setObjectName("DetailDesc")
        self._item_desc_label.setWordWrap(True)

        summary_strip = QFrame(page)
        summary_strip.setObjectName("SummaryStrip")
        strip_layout = QHBoxLayout(summary_strip)
        strip_layout.setContentsMargins(8, 6, 8, 6)
        strip_layout.setSpacing(10)

        stock_box = QVBoxLayout()
        stock_box.setSpacing(1)
        stock_lbl = QLabel("TOTAL STOK", summary_strip)
        stock_lbl.setObjectName("StripCaption")
        self._item_stock_val.setObjectName("StripValue")
        stock_box.addWidget(stock_lbl)
        stock_box.addWidget(self._item_stock_val)

        divider = QFrame(summary_strip)
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("VerticalDivider")

        asset_box = QVBoxLayout()
        asset_box.setSpacing(1)
        asset_lbl = QLabel("NILAI MODAL (FIFO)", summary_strip)
        asset_lbl.setObjectName("StripCaption")
        self._item_asset_val.setObjectName("StripValue")
        asset_box.addWidget(asset_lbl)
        asset_box.addWidget(self._item_asset_val)

        strip_layout.addLayout(stock_box, 1)
        strip_layout.addWidget(divider)
        strip_layout.addLayout(asset_box, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(5)

        btn_edit = QPushButton("Edit Barang", page)
        btn_edit.setObjectName("DetailPrimaryBtn")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(self._emit_edit_current_item)

        btn_adjust = QPushButton("Sesuaikan Stok", page)
        btn_adjust.setObjectName("DetailSecondaryBtn")
        btn_adjust.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_adjust.clicked.connect(self._emit_adjust_current_item)

        btn_card = QPushButton("Kartu Stok", page)
        btn_card.setObjectName("DetailSecondaryBtn")
        btn_card.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_card.clicked.connect(self._emit_stock_card_current_item)

        action_row.addWidget(btn_edit)
        action_row.addWidget(btn_adjust)
        action_row.addWidget(btn_card)

        units_title = QLabel("Variasi Satuan Jual", page)
        units_title.setObjectName("SectionHeader")
        self._configure_mini_table(
            self._units_table,
            ["Varian", "Konv.", "Harga", "Default"],
            stretch_col=0,
        )

        layers_title = QLabel("Layer Stok FIFO Aktif", page)
        layers_title.setObjectName("SectionHeader")
        self._configure_mini_table(
            self._layers_table,
            ["Masuk", "Sumber", "Sisa", "Modal"],
            stretch_col=1,
        )

        layout.addLayout(badge_row)
        layout.addWidget(self._item_name_label)
        layout.addWidget(self._item_meta_label)
        layout.addWidget(self._item_desc_label)
        layout.addWidget(summary_strip)
        layout.addLayout(action_row)
        layout.addWidget(units_title)
        layout.addWidget(self._units_table, 1)
        layout.addWidget(layers_title)
        layout.addWidget(self._layers_table, 1)
        return page

    def _build_service_detail_page(self) -> QWidget:
        """Membangun halaman rincian lengkap untuk layanan jasa.

        Returns:
            Widget panel detail jasa berisi info harga dan komposisi bahan baku.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(6)
        self._service_sku_badge.setObjectName("SkuBadge")
        self._service_status_badge.setObjectName("StatusBadge")
        badge_row.addWidget(self._service_sku_badge)
        badge_row.addWidget(self._service_status_badge)
        badge_row.addStretch(1)

        self._service_name_label.setObjectName("DetailTitle")
        self._service_name_label.setWordWrap(True)
        self._service_desc_label.setObjectName("DetailDesc")
        self._service_desc_label.setWordWrap(True)

        summary_strip = QFrame(page)
        summary_strip.setObjectName("SummaryStrip")
        strip_layout = QHBoxLayout(summary_strip)
        strip_layout.setContentsMargins(8, 6, 8, 6)
        strip_layout.setSpacing(10)

        price_box = QVBoxLayout()
        price_box.setSpacing(1)
        price_lbl = QLabel("HARGA JUAL", summary_strip)
        price_lbl.setObjectName("StripCaption")
        self._service_price_val.setObjectName("StripValue")
        price_box.addWidget(price_lbl)
        price_box.addWidget(self._service_price_val)

        divider = QFrame(summary_strip)
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("VerticalDivider")

        hpp_box = QVBoxLayout()
        hpp_box.setSpacing(1)
        hpp_lbl = QLabel("EST. MODAL BAHAN", summary_strip)
        hpp_lbl.setObjectName("StripCaption")
        self._service_hpp_val.setObjectName("StripValue")
        hpp_box.addWidget(hpp_lbl)
        hpp_box.addWidget(self._service_hpp_val)

        strip_layout.addLayout(price_box, 1)
        strip_layout.addWidget(divider)
        strip_layout.addLayout(hpp_box, 1)

        btn_edit_service = QPushButton("Edit Jasa & Bahan Baku", page)
        btn_edit_service.setObjectName("DetailPrimaryBtn")
        btn_edit_service.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit_service.clicked.connect(self._emit_edit_current_service)

        materials_title = QLabel("Komposisi Bahan Baku (Potong Stok)", page)
        materials_title.setObjectName("SectionHeader")
        self._configure_mini_table(
            self._materials_table,
            ["Bahan Baku", "Takaran", "Est. Modal"],
            stretch_col=0,
        )

        layout.addLayout(badge_row)
        layout.addWidget(self._service_name_label)
        layout.addWidget(self._service_desc_label)
        layout.addWidget(summary_strip)
        layout.addWidget(btn_edit_service)
        layout.addWidget(materials_title)
        layout.addWidget(self._materials_table, 1)
        return page

    def _apply_styles(self) -> None:
        """Menerapkan gaya QSS pada panel detail dan seluruh sub-komponennya."""
        self.setStyleSheet(
            """
            QFrame#DetailPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #202236, stop:0.5 #1B1D2E, stop:1 #161726);
                border: 1px solid #343854;
                border-radius: 6px;
            }
            QLabel#EmptyTitle {
                color: #E2E8F0;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#EmptyHint {
                color: #838BA8;
                font-size: 11px;
                background: transparent;
            }
            QLabel#SkuBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #222B47, stop:1 #1E293B);
                color: #7DD3FC;
                border: 1px solid #384B73;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#StatusBadge {
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#DetailTitle {
                color: #F1F5F9;
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#DetailMeta {
                color: #A6B0CE;
                font-size: 11px;
                background: transparent;
            }
            QLabel#DetailDesc {
                color: #8A93B2;
                font-size: 11px;
                background: transparent;
            }
            QFrame#SummaryStrip {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #151726, stop:1 #1D2238);
                border: 1px solid #343B59;
                border-radius: 5px;
            }
            QFrame#VerticalDivider {
                color: #343B59;
                background-color: #343B59;
                max-width: 1px;
            }
            QLabel#StripCaption {
                color: #848EAD;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.4px;
                background: transparent;
            }
            QLabel#StripValue {
                color: #F1F5F9;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#SectionHeader {
                color: #C4CEEC;
                font-size: 11px;
                font-weight: 700;
                padding-top: 2px;
                background: transparent;
            }
            QPushButton#DetailPrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #06B6D4);
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#DetailPrimaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60A5FA, stop:1 #22D3EE);
            }
            QPushButton#DetailSecondaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #292C44, stop:1 #202235);
                color: #E2E8F0;
                border: 1px solid #3E4366;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#DetailSecondaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #353959, stop:1 #2A2D46);
            }
            QTableWidget#MiniTable {
                background-color: #161724;
                alternate-background-color: #1C1E2E;
                color: #E2E8F0;
                border: 1px solid #323652;
                border-radius: 4px;
                font-size: 11px;
            }
            QTableWidget#MiniTable::item {
                padding: 2px 5px;
                border-bottom: 1px solid #26293F;
            }
            QTableWidget#MiniTable QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #262940, stop:1 #1F2135);
                color: #A6B0CE;
                border: none;
                border-bottom: 1px solid #343854;
                padding: 2px 5px;
                font-size: 10px;
                font-weight: 700;
            }
            """
        )

    def _apply_status_badge_style(self, badge: QLabel, is_active: bool) -> None:
        """Mengatur warna dan teks badge status aktif atau nonaktif.

        Args:
            badge: Label target yang menampilkan status.
            is_active: Status aktif entitas.
        """
        if is_active:
            badge.setText("AKTIF")
            badge.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.16); color: #4ADE80; "
                "border: 1px solid rgba(34, 197, 94, 0.35); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: 700;"
            )
        else:
            badge.setText("ARSIP")
            badge.setStyleSheet(
                "background-color: rgba(148, 163, 184, 0.16); color: #94A3B8; "
                "border: 1px solid rgba(148, 163, 184, 0.30); border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px; font-weight: 700;"
            )

    def _emit_edit_current_item(self) -> None:
        """Memancarkan sinyal edit untuk barang yang sedang dibuka."""
        if self._current_item_id is not None:
            self.edit_item_requested.emit(self._current_item_id)

    def _emit_adjust_current_item(self) -> None:
        """Memancarkan sinyal penyesuaian stok untuk barang yang sedang dibuka."""
        if self._current_item_id is not None:
            self.adjust_stock_requested.emit(self._current_item_id)

    def _emit_stock_card_current_item(self) -> None:
        """Memancarkan sinyal buka kartu stok untuk barang yang sedang dibuka."""
        if self._current_item_id is not None:
            self.stock_card_requested.emit(self._current_item_id)

    def _emit_edit_current_service(self) -> None:
        """Memancarkan sinyal edit untuk layanan jasa yang sedang dibuka."""
        if self._current_service_id is not None:
            self.edit_service_requested.emit(self._current_service_id)

    def clear_detail(self) -> None:
        """Mengembalikan panel detail ke status kosong awal."""
        self._current_item_id = None
        self._current_service_id = None
        self._stack.setCurrentIndex(0)

    def show_item_detail(self, detail: ItemFullDetail) -> None:
        """Menampilkan data lengkap barang fisik pada panel detail.

        Args:
            detail: Objek ItemFullDetail berisi informasi satuan dan layer FIFO.
        """
        self._current_item_id = detail.item_id
        self._current_service_id = None

        self._item_sku_badge.setText(detail.sku)
        self._apply_status_badge_style(self._item_status_badge, detail.is_active)
        self._item_name_label.setText(detail.name)
        self._item_meta_label.setText(
            f"{detail.category_name} · Satuan dasar: {detail.base_unit_name}"
        )
        desc_text = detail.description.strip()
        self._item_desc_label.setText(desc_text if desc_text else "Tidak ada deskripsi.")
        self._item_stock_val.setText(detail.total_stock_text)
        self._item_asset_val.setText(detail.total_value_text)

        self._units_table.setRowCount(len(detail.units))
        for row_idx, unit in enumerate(detail.units):
            conv_str = (
                f"{unit.conversion_qty:g} {unit.unit_symbol}"
                if unit.unit_symbol
                else f"{unit.conversion_qty:g}"
            )
            default_mark = "Utama" if unit.is_default else "-"
            values = [
                unit.variant_name,
                conv_str,
                unit.selling_price_text,
                default_mark,
            ]
            for col_idx, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if col_idx in (1, 2):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                elif col_idx == 3:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if unit.is_default:
                        cell.setForeground(QColor("#4ADE80"))
                if not unit.is_active:
                    cell.setForeground(QColor("#6C7086"))
                self._units_table.setItem(row_idx, col_idx, cell)

        self._layers_table.setRowCount(len(detail.fifo_layers))
        for row_idx, layer in enumerate(detail.fifo_layers):
            values = [
                layer.received_at,
                layer.source_type,
                layer.remaining_qty_text,
                layer.unit_cost_text,
            ]
            for col_idx, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if col_idx in (2, 3):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._layers_table.setItem(row_idx, col_idx, cell)

        self._stack.setCurrentIndex(1)

    def show_service_detail(self, detail: ServiceFullDetail) -> None:
        """Menampilkan data lengkap layanan jasa pada panel detail.

        Args:
            detail: Objek ServiceFullDetail berisi harga dan komposisi bahan baku.
        """
        self._current_service_id = detail.service_id
        self._current_item_id = None

        self._service_sku_badge.setText(detail.sku)
        self._apply_status_badge_style(self._service_status_badge, detail.is_active)
        self._service_name_label.setText(detail.name)
        desc_text = detail.description.strip()
        self._service_desc_label.setText(
            desc_text if desc_text else "Tidak ada deskripsi layanan."
        )
        self._service_price_val.setText(detail.selling_price_text)
        self._service_hpp_val.setText(detail.estimated_hpp_text)

        self._materials_table.setRowCount(len(detail.materials))
        for row_idx, material in enumerate(detail.materials):
            material_label = f"{material.item_name} ({material.item_sku})"
            values = [
                material_label,
                material.quantity_text,
                material.estimated_cost_text,
            ]
            for col_idx, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if col_idx in (1, 2):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._materials_table.setItem(row_idx, col_idx, cell)

        self._stack.setCurrentIndex(2)


class ManajemenProdukPage(QWidget):
    """Halaman utama UI Manajemen Produk untuk barang fisik dan layanan jasa.

    Komponen ini hanya menangani tampilan dan interaksi antarmuka, lalu
    memancarkan sinyal terstruktur agar dapat dihubungkan ke backend terpisah.

    Attributes:
        add_item_requested: Dipancarkan saat tombol tambah barang ditekan.
        add_service_requested: Dipancarkan saat tombol tambah jasa ditekan.
        adjust_stock_global_requested: Dipancarkan saat tombol stok/opname ditekan.
        manage_master_requested: Dipancarkan saat tombol kategori & satuan ditekan.
        refresh_requested: Dipancarkan saat tombol muat ulang ditekan.
        filter_changed: Dipancarkan membawa objek ProductFilterState setiap filter berubah.
        item_selected: Dipancarkan membawa item_id saat baris barang dipilih.
        service_selected: Dipancarkan membawa service_id saat baris jasa dipilih.
        edit_item_requested: Dipancarkan membawa item_id saat tombol edit barang ditekan.
        stock_card_requested: Dipancarkan membawa item_id saat tombol kartu stok ditekan.
        adjust_item_stock_requested: Dipancarkan membawa item_id dari panel detail.
        toggle_item_status_requested: Dipancarkan membawa (item_id, target_active).
        edit_service_requested: Dipancarkan membawa service_id saat tombol edit jasa ditekan.
        toggle_service_status_requested: Dipancarkan membawa (service_id, target_active).
        page_changed: Dipancarkan membawa nomor halaman tujuan paginasi.
    """

    add_item_requested = Signal()
    add_service_requested = Signal()
    adjust_stock_global_requested = Signal()
    manage_master_requested = Signal()
    refresh_requested = Signal()
    filter_changed = Signal(object)
    item_selected = Signal(int)
    service_selected = Signal(int)
    edit_item_requested = Signal(int)
    stock_card_requested = Signal(int)
    adjust_item_stock_requested = Signal(int)
    toggle_item_status_requested = Signal(int, bool)
    edit_service_requested = Signal(int)
    toggle_service_status_requested = Signal(int, bool)
    page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi seluruh komponen UI halaman Manajemen Produk.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("ManajemenProdukPage")
        self._active_tab: Literal["items", "services"] = "items"
        self._current_page: int = 1
        self._total_pages: int = 1
        self._is_updating_filters: bool = False

        self._tab_items_btn = QPushButton("Barang Fisik", self)
        self._tab_services_btn = QPushButton("Layanan / Jasa", self)
        self._primary_add_btn = QPushButton("+ Tambah Barang", self)
        self._stock_opname_btn = QPushButton("Stok Awal / Opname", self)
        self._master_data_btn = QPushButton("Kategori & Satuan", self)
        self._refresh_btn = QPushButton("Muat Ulang", self)

        self._card_active = CompactMetricCard(
            "Katalog Aktif", "0", "0 barang · 0 jasa", "#3B82F6", self
        )
        self._card_low_stock = CompactMetricCard(
            "Stok Kritis / Habis", "0", "Perlu restok segera", "#F59E0B", self
        )
        self._card_asset_val = CompactMetricCard(
            "Nilai Aset Stok", "Rp 0", "Layer FIFO aktif", "#22C55E", self
        )
        self._card_inactive = CompactMetricCard(
            "Nonaktif / Arsip", "0", "Disembunyikan kasir", "#94A3B8", self
        )

        self._search_input = QLineEdit(self)
        self._category_combo = QComboBox(self)
        self._stock_combo = QComboBox(self)
        self._status_combo = QComboBox(self)
        self._reset_filter_btn = QPushButton("Reset", self)

        self._table_stack = QStackedWidget(self)
        self._items_table = QTableWidget(0, 7, self)
        self._services_table = QTableWidget(0, 6, self)
        self._detail_panel = ProductDetailPanel(self)

        self._page_info_label = QLabel("Menampilkan 0 data", self)
        self._page_indicator_label = QLabel("Hal 1 / 1", self)
        self._prev_page_btn = QPushButton("Sebelumnya", self)
        self._next_page_btn = QPushButton("Berikutnya", self)

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Menyusun tata letak utama yang padat, rapi, dan proporsional."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_header_bar())
        root_layout.addLayout(self._build_metrics_row())
        root_layout.addWidget(self._build_filter_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("MainSplitter")
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        master_card = self._build_master_table_card()
        splitter.addWidget(master_card)
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([780, 340])

        root_layout.addWidget(splitter, 1)

    def _build_header_bar(self) -> QFrame:
        """Membangun baris judul, pengalih tab, dan tombol aksi utama.

        Returns:
            Frame header satu baris berdesain kompak.
        """
        header = QFrame(self)
        header.setObjectName("HeaderBar")
        header.setFixedHeight(40)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        title_label = QLabel("Manajemen Produk", header)
        title_label.setObjectName("PageTitle")

        tab_container = QFrame(header)
        tab_container.setObjectName("TabSegmented")
        tab_layout = QHBoxLayout(tab_container)
        tab_layout.setContentsMargins(2, 2, 2, 2)
        tab_layout.setSpacing(2)

        self._tab_items_btn.setObjectName("SegmentBtn")
        self._tab_items_btn.setCheckable(True)
        self._tab_items_btn.setChecked(True)
        self._tab_items_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._tab_services_btn.setObjectName("SegmentBtn")
        self._tab_services_btn.setCheckable(True)
        self._tab_services_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        tab_layout.addWidget(self._tab_items_btn)
        tab_layout.addWidget(self._tab_services_btn)

        self._primary_add_btn.setObjectName("PrimaryActionBtn")
        self._primary_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._stock_opname_btn.setObjectName("SecondaryActionBtn")
        self._stock_opname_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._master_data_btn.setObjectName("SecondaryActionBtn")
        self._master_data_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._refresh_btn.setObjectName("GhostActionBtn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(title_label)
        layout.addWidget(tab_container)
        layout.addStretch(1)
        layout.addWidget(self._master_data_btn)
        layout.addWidget(self._stock_opname_btn)
        layout.addWidget(self._refresh_btn)
        layout.addWidget(self._primary_add_btn)
        return header

    def _build_metrics_row(self) -> QHBoxLayout:
        """Membangun deretan empat kartu indikator metrik sejajar.

        Returns:
            QHBoxLayout berisi empat CompactMetricCard dengan proporsi setara.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._card_active, 1)
        row.addWidget(self._card_low_stock, 1)
        row.addWidget(self._card_asset_val, 1)
        row.addWidget(self._card_inactive, 1)
        return row

    def _build_filter_bar(self) -> QFrame:
        """Membangun baris pencarian cepat dan filter atribut produk.

        Returns:
            Frame filter satu baris yang responsif terhadap tab aktif.
        """
        bar = QFrame(self)
        bar.setObjectName("FilterBar")
        bar.setFixedHeight(38)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._search_input.setObjectName("FilterInput")
        self._search_input.setPlaceholderText("Cari SKU atau nama produk...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(220)

        self._category_combo.setObjectName("FilterCombo")
        self._category_combo.setMinimumWidth(155)
        self._category_combo.addItem("Semua Kategori", None)

        self._stock_combo.setObjectName("FilterCombo")
        self._stock_combo.setMinimumWidth(135)
        self._stock_combo.addItem("Semua Stok", "ALL")
        self._stock_combo.addItem("Stok Tersedia", "AVAILABLE")
        self._stock_combo.addItem("Stok Menipis", "LOW")
        self._stock_combo.addItem("Stok Habis (0)", "EMPTY")

        self._status_combo.setObjectName("FilterCombo")
        self._status_combo.setMinimumWidth(120)
        self._status_combo.addItem("Semua Status", "ALL")
        self._status_combo.addItem("Aktif", "ACTIVE")
        self._status_combo.addItem("Arsip / Nonaktif", "INACTIVE")

        self._reset_filter_btn.setObjectName("GhostActionBtn")
        self._reset_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self._search_input, 2)
        layout.addWidget(self._category_combo, 1)
        layout.addWidget(self._stock_combo, 1)
        layout.addWidget(self._status_combo, 1)
        layout.addWidget(self._reset_filter_btn)
        return bar

    def _build_master_table_card(self) -> QFrame:
        """Membangun kontainer tabel utama barang/jasa beserta kontrol paginasi.

        Returns:
            Frame berisi QStackedWidget tabel utama dan footer paginasi.
        """
        card = QFrame(self)
        card.setObjectName("TableCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._configure_items_table()
        self._configure_services_table()

        self._table_stack.addWidget(self._items_table)
        self._table_stack.addWidget(self._services_table)
        self._table_stack.setCurrentIndex(0)

        footer = QFrame(card)
        footer.setObjectName("PaginationBar")
        footer.setFixedHeight(32)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 3, 10, 3)
        footer_layout.setSpacing(6)

        self._page_info_label.setObjectName("PageInfoLabel")
        self._page_indicator_label.setObjectName("PageIndicatorLabel")

        self._prev_page_btn.setObjectName("PaginationBtn")
        self._prev_page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_page_btn.setEnabled(False)

        self._next_page_btn.setObjectName("PaginationBtn")
        self._next_page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_page_btn.setEnabled(False)

        footer_layout.addWidget(self._page_info_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._prev_page_btn)
        footer_layout.addWidget(self._page_indicator_label)
        footer_layout.addWidget(self._next_page_btn)

        layout.addWidget(self._table_stack, 1)
        layout.addWidget(footer)
        return card

    def _configure_base_table(self, table: QTableWidget) -> None:
        """Menerapkan pengaturan perilaku standar pada tabel daftar utama.

        Args:
            table: Objek QTableWidget target.
        """
        table.setObjectName("MasterTable")
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setItemDelegate(_FullRowGradientDelegate(table))

        v_header = table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(32)

        h_header = table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(30)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def _configure_items_table(self) -> None:
        """Mengonfigurasi struktur dan proporsi kolom tabel barang fisik."""
        self._configure_base_table(self._items_table)
        self._items_table.setHorizontalHeaderLabels(
            [
                "SKU",
                "Nama Produk",
                "Kategori",
                "Harga / Satuan",
                "Sisa Stok",
                "Status",
                "Aksi",
            ]
        )
        header = self._items_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            self._items_table.setColumnWidth(1, 240)
            self._items_table.setColumnWidth(2, 160)
            self._items_table.setColumnWidth(5, 68)
            self._items_table.setColumnWidth(6, 148)
        viewport = self._items_table.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)

    def _update_items_table_column_widths(self) -> None:
        viewport = self._items_table.viewport()
        if viewport is None:
            return
        available = viewport.width()
        other_width = sum(
            self._items_table.columnWidth(col) for col in (0, 3, 4, 5, 6)
        )
        remaining = available - other_width
        if remaining > 0:
            name_width = int(remaining * 3 / 5)
            cat_width = remaining - name_width
            self._items_table.setColumnWidth(1, name_width)
            self._items_table.setColumnWidth(2, cat_width)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self._items_table.viewport()
            and event.type() in (QEvent.Type.Resize, QEvent.Type.Show)
        ):
            self._update_items_table_column_widths()
        return super().eventFilter(watched, event)

    def _configure_services_table(self) -> None:
        """Mengonfigurasi struktur dan proporsi kolom tabel layanan jasa."""
        self._configure_base_table(self._services_table)
        self._services_table.setHorizontalHeaderLabels(
            [
                "SKU",
                "Nama Layanan / Jasa",
                "Harga Jual",
                "Bahan Baku",
                "Status",
                "Aksi",
            ]
        )
        header = self._services_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self._services_table.setColumnWidth(4, 68)
            self._services_table.setColumnWidth(5, 110)

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS terpusat pada halaman Manajemen Produk."""
        self.setStyleSheet(
            """
            QWidget#ManajemenProdukPage {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #11111B, stop:0.5 #151624, stop:1 #18192A);
                color: #E2E8F0;
            }
            QFrame#HeaderBar, QFrame#FilterBar, QFrame#TableCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E1E2E, stop:0.6 #202236, stop:1 #1B2235);
                border: 1px solid #343752;
                border-radius: 6px;
            }
            QLabel#PageTitle {
                color: #F1F5F9;
                font-size: 14px;
                font-weight: 700;
                padding-right: 6px;
                background: transparent;
            }
            QFrame#TabSegmented {
                background-color: #131420;
                border: 1px solid #313550;
                border-radius: 5px;
            }
            QPushButton#SegmentBtn {
                background-color: transparent;
                color: #9AA3C2;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#SegmentBtn:hover {
                color: #E2E8F0;
            }
            QPushButton#SegmentBtn:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #0EA5E9);
                color: #FFFFFF;
            }
            QPushButton#PrimaryActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:0.55 #2563EB, stop:1 #06B6D4);
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 5px 11px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#PrimaryActionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #60A5FA, stop:0.55 #3B82F6, stop:1 #22D3EE);
            }
            QPushButton#PrimaryActionBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1D4ED8, stop:1 #0891B2);
            }
            QPushButton#SecondaryActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2A2D45, stop:1 #202236);
                color: #E2E8F0;
                border: 1px solid #3E4366;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#SecondaryActionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #353959, stop:1 #2A2D46);
            }
            QPushButton#GhostActionBtn {
                background-color: transparent;
                color: #A2ACC9;
                border: 1px solid #363A57;
                border-radius: 5px;
                padding: 5px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#GhostActionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #262940, stop:1 #2A2F4A);
                color: #F1F5F9;
            }
            QLineEdit#FilterInput, QComboBox#FilterCombo {
                background-color: #141522;
                color: #E2E8F0;
                border: 1px solid #323652;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FilterInput:focus, QComboBox#FilterCombo:focus {
                border: 1px solid #38BDF8;
            }
            QComboBox#FilterCombo::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox#FilterCombo QAbstractItemView {
                background-color: #1B1D2E;
                color: #E2E8F0;
                border: 1px solid #3B405E;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }
            QSplitter#MainSplitter::handle {
                background-color: transparent;
            }
            QTableWidget#MasterTable {
                background-color: #1B1C2C;
                alternate-background-color: #212236;
                color: #E2E8F0;
                border: none;
                font-size: 12px;
                selection-background-color: transparent;
                selection-color: #FFFFFF;
            }
            QTableWidget#MasterTable::item {
                padding: 2px 8px;
                border-bottom: 1px solid #282A40;
            }
            QTableWidget#MasterTable QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #272940, stop:1 #202236);
                color: #A6B1D1;
                border: none;
                border-bottom: 1px solid #383C59;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#PaginationBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #181928, stop:1 #1E2033);
                border-top: 1px solid #323652;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QLabel#PageInfoLabel, QLabel#PageIndicatorLabel {
                color: #9AA3C2;
                font-size: 11px;
                background: transparent;
            }
            QPushButton#PaginationBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #282B42, stop:1 #202235);
                color: #E2E8F0;
                border: 1px solid #383C59;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton#PaginationBtn:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #343856, stop:1 #2A2D45);
            }
            QPushButton#PaginationBtn:disabled {
                color: #585B70;
                background: #1B1C2B;
            }
            QPushButton#RowActionEdit {
                background-color: rgba(59, 130, 246, 0.16);
                color: #7DD3FC;
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#RowActionEdit:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #06B6D4);
                color: #FFFFFF;
            }
            QPushButton#RowActionStock {
                background-color: rgba(34, 197, 94, 0.14);
                color: #34D399;
                border: 1px solid rgba(34, 197, 94, 0.30);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#RowActionStock:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22C55E, stop:1 #10B981);
                color: #0F172A;
            }
            QPushButton#RowActionArchive {
                background-color: rgba(245, 158, 11, 0.14);
                color: #FBBF24;
                border: 1px solid rgba(245, 158, 11, 0.30);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#RowActionArchive:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #EA580C);
                color: #0F172A;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh event internal widget ke slot dan sinyal publik."""
        self._tab_items_btn.clicked.connect(
            lambda _checked=False: self._switch_tab("items")
        )
        self._tab_services_btn.clicked.connect(
            lambda _checked=False: self._switch_tab("services")
        )
        self._primary_add_btn.clicked.connect(self._handle_primary_add_clicked)
        self._stock_opname_btn.clicked.connect(
            self.adjust_stock_global_requested.emit
        )
        self._master_data_btn.clicked.connect(self.manage_master_requested.emit)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)

        self._search_input.textChanged.connect(self._emit_filter_state)
        self._category_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._stock_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._status_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._reset_filter_btn.clicked.connect(self._reset_filters)

        self._items_table.itemSelectionChanged.connect(
            self._handle_item_row_selected
        )
        self._services_table.itemSelectionChanged.connect(
            self._handle_service_row_selected
        )

        self._prev_page_btn.clicked.connect(self._go_prev_page)
        self._next_page_btn.clicked.connect(self._go_next_page)

        self._detail_panel.edit_item_requested.connect(
            self.edit_item_requested.emit
        )
        self._detail_panel.stock_card_requested.connect(
            self.stock_card_requested.emit
        )
        self._detail_panel.adjust_stock_requested.connect(
            self.adjust_item_stock_requested.emit
        )
        self._detail_panel.edit_service_requested.connect(
            self.edit_service_requested.emit
        )

    def _switch_tab(self, tab: Literal["items", "services"]) -> None:
        """Mengubah tampilan aktif antara tab barang fisik dan tab layanan jasa.

        Args:
            tab: Nama tab tujuan ('items' atau 'services').
        """
        if self._active_tab == tab:
            self._tab_items_btn.setChecked(tab == "items")
            self._tab_services_btn.setChecked(tab == "services")
            return

        self._active_tab = tab
        is_items = tab == "items"

        self._tab_items_btn.setChecked(is_items)
        self._tab_services_btn.setChecked(not is_items)
        self._table_stack.setCurrentIndex(0 if is_items else 1)

        self._primary_add_btn.setText(
            "+ Tambah Barang" if is_items else "+ Tambah Jasa"
        )
        self._stock_opname_btn.setVisible(is_items)
        self._category_combo.setVisible(is_items)
        self._stock_combo.setVisible(is_items)
        self._search_input.setPlaceholderText(
            "Cari SKU atau nama barang..."
            if is_items
            else "Cari SKU atau nama jasa..."
        )

        self._detail_panel.clear_detail()
        self._emit_filter_state()

    def _handle_primary_add_clicked(self) -> None:
        """Memancarkan sinyal tambah barang atau tambah jasa sesuai tab aktif."""
        if self._active_tab == "items":
            self.add_item_requested.emit()
        else:
            self.add_service_requested.emit()

    def get_filter_state(self) -> ProductFilterState:
        """Mengambil snapshot kondisi seluruh kontrol filter saat ini.

        Returns:
            Objek ProductFilterState yang siap dikirim ke lapisan backend.
        """
        raw_cat = self._category_combo.currentData()
        category_id = raw_cat if isinstance(raw_cat, int) else None

        raw_stock = self._stock_combo.currentData()
        stock_filter = str(raw_stock) if raw_stock is not None else "ALL"

        raw_status = self._status_combo.currentData()
        status_filter = str(raw_status) if raw_status is not None else "ALL"

        return ProductFilterState(
            active_tab=self._active_tab,
            search_text=self._search_input.text().strip(),
            category_id=category_id,
            stock_filter=stock_filter,
            status_filter=status_filter,
        )

    def _emit_filter_state(self) -> None:
        """Memancarkan sinyal perubahan filter bila tidak dalam proses update internal."""
        if self._is_updating_filters:
            return
        self.filter_changed.emit(self.get_filter_state())

    def _reset_filters(self) -> None:
        """Mengembalikan seluruh kontrol filter ke nilai bawaan dan memicu pembaruan."""
        self._is_updating_filters = True
        self._search_input.clear()
        self._category_combo.setCurrentIndex(0)
        self._stock_combo.setCurrentIndex(0)
        self._status_combo.setCurrentIndex(0)
        self._is_updating_filters = False
        self._emit_filter_state()

    def _handle_item_row_selected(self) -> None:
        """Membaca identitas barang dari baris terpilih dan memancarkan sinyal."""
        row = self._items_table.currentRow()
        if row < 0:
            return
        first_cell = self._items_table.item(row, 0)
        if first_cell is None:
            return
        item_id = first_cell.data(Qt.ItemDataRole.UserRole)
        if isinstance(item_id, int):
            self.item_selected.emit(item_id)

    def _handle_service_row_selected(self) -> None:
        """Membaca identitas jasa dari baris terpilih dan memancarkan sinyal."""
        row = self._services_table.currentRow()
        if row < 0:
            return
        first_cell = self._services_table.item(row, 0)
        if first_cell is None:
            return
        service_id = first_cell.data(Qt.ItemDataRole.UserRole)
        if isinstance(service_id, int):
            self.service_selected.emit(service_id)

    def _go_prev_page(self) -> None:
        """Meminta halaman sebelumnya jika halaman aktif lebih besar dari satu."""
        if self._current_page > 1:
            self.page_changed.emit(self._current_page - 1)

    def _go_next_page(self) -> None:
        """Meminta halaman berikutnya jika belum mencapai halaman terakhir."""
        if self._current_page < self._total_pages:
            self.page_changed.emit(self._current_page + 1)

    def _create_cell_container(self) -> QWidget:
        """Membuat kontainer transparan agar menyatu dengan latar baris tabel.

        Returns:
            Widget kontainer dengan latar belakang transparan penuh.
        """
        container = QWidget(self)
        container.setObjectName("TableCellContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        container.setAutoFillBackground(False)
        return container

    def _create_status_widget(self, is_active: bool) -> QWidget:
        """Membuat widget badge status terpusat untuk sel tabel.

        Args:
            is_active: Menentukan apakah badge bertuliskan Aktif atau Arsip.

        Returns:
            Widget kontainer transparan berisi QLabel badge status.
        """
        container = self._create_cell_container()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("Aktif" if is_active else "Arsip", container)
        if is_active:
            badge.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.16); color: #4ADE80; "
                "border: 1px solid rgba(34, 197, 94, 0.30); "
                "border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
        else:
            badge.setStyleSheet(
                "background-color: rgba(148, 163, 184, 0.16); color: #94A3B8; "
                "border: 1px solid rgba(148, 163, 184, 0.28); "
                "border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
        layout.addWidget(badge)
        return container

    def _create_item_action_widget(self, row: ItemRowData) -> QWidget:
        """Membuat tombol aksi ringkas per baris pada tabel barang fisik.

        Args:
            row: Data baris barang terkait.

        Returns:
            Widget kontainer transparan berisi tombol Edit, Stok, dan Arsip/Aktifkan.
        """
        container = self._create_cell_container()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        btn_edit = QPushButton("Edit", container)
        btn_edit.setObjectName("RowActionEdit")
        btn_edit.setFixedHeight(22)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(
            lambda _checked=False, item_id=row.item_id: self.edit_item_requested.emit(
                item_id
            )
        )

        btn_stock = QPushButton("Stok", container)
        btn_stock.setObjectName("RowActionStock")
        btn_stock.setFixedHeight(22)
        btn_stock.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_stock.clicked.connect(
            lambda _checked=False, item_id=row.item_id: self.stock_card_requested.emit(
                item_id
            )
        )

        toggle_label = "Arsip" if row.is_active else "Aktif"
        btn_toggle = QPushButton(toggle_label, container)
        btn_toggle.setObjectName("RowActionArchive")
        btn_toggle.setFixedHeight(22)
        btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_toggle.clicked.connect(
            lambda _checked=False, item_id=row.item_id, target=not row.is_active: (
                self.toggle_item_status_requested.emit(item_id, target)
            )
        )

        layout.addWidget(btn_edit)
        layout.addWidget(btn_stock)
        layout.addWidget(btn_toggle)
        return container

    def _create_service_action_widget(self, row: ServiceRowData) -> QWidget:
        """Membuat tombol aksi ringkas per baris pada tabel layanan jasa.

        Args:
            row: Data baris jasa terkait.

        Returns:
            Widget kontainer transparan berisi tombol Edit dan Arsip/Aktifkan.
        """
        container = self._create_cell_container()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        btn_edit = QPushButton("Edit", container)
        btn_edit.setObjectName("RowActionEdit")
        btn_edit.setFixedHeight(22)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(
            lambda _checked=False, sid=row.service_id: self.edit_service_requested.emit(
                sid
            )
        )

        toggle_label = "Arsip" if row.is_active else "Aktif"
        btn_toggle = QPushButton(toggle_label, container)
        btn_toggle.setObjectName("RowActionArchive")
        btn_toggle.setFixedHeight(22)
        btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_toggle.clicked.connect(
            lambda _checked=False, sid=row.service_id, target=not row.is_active: (
                self.toggle_service_status_requested.emit(sid, target)
            )
        )

        layout.addWidget(btn_edit)
        layout.addWidget(btn_toggle)
        return container

    def set_metrics(self, metrics: ProductMetricsData) -> None:
        """Memperbarui nilai seluruh kartu metrik pada bagian atas halaman.

        Args:
            metrics: Objek ProductMetricsData dari backend.
        """
        self._card_active.update_metric(
            str(metrics.active_catalog_count), metrics.active_catalog_sub
        )
        self._card_low_stock.update_metric(
            str(metrics.low_stock_count), metrics.low_stock_sub
        )
        self._card_asset_val.update_metric(
            metrics.inventory_value_text, metrics.inventory_value_sub
        )
        self._card_inactive.update_metric(
            str(metrics.inactive_count), metrics.inactive_sub
        )

    def set_categories(self, categories: list[CategoryOption]) -> None:
        """Mengisi ulang daftar kategori pada dropdown filter.

        Args:
            categories: Daftar objek CategoryOption dari basis data.
        """
        self._is_updating_filters = True
        current_data = self._category_combo.currentData()
        self._category_combo.clear()
        self._category_combo.addItem("Semua Kategori", None)
        for cat in categories:
            self._category_combo.addItem(cat.label, cat.category_id)
        restored_index = self._category_combo.findData(current_data)
        self._category_combo.setCurrentIndex(max(0, restored_index))
        self._is_updating_filters = False

    def set_items(self, rows: list[ItemRowData]) -> None:
        """Mengisi tabel barang fisik dengan data terbaru dari backend.

        Args:
            rows: Daftar objek ItemRowData untuk dirender pada tabel.
        """
        self._items_table.blockSignals(True)
        self._items_table.setRowCount(len(rows))
        mono_font = QFont("Consolas", 9)

        for idx, row in enumerate(rows):
            sku_item = QTableWidgetItem(row.sku)
            sku_item.setFont(mono_font)
            sku_item.setForeground(QColor("#7DD3FC"))
            sku_item.setData(Qt.ItemDataRole.UserRole, row.item_id)

            name_item = QTableWidgetItem(row.name)
            cat_item = QTableWidgetItem(row.category_name)
            cat_item.setForeground(QColor("#9AA3C2"))

            unit_summary = row.unit_summary.strip()
            if " · " in unit_summary:
                unit_part, variant_part = unit_summary.split(" · ", 1)
                variant_text = variant_part.lstrip("+").strip()
                price_text = f"{row.default_price_text}/{unit_part.strip()} ({variant_text})"
            elif unit_summary:
                price_text = f"{row.default_price_text}/{unit_summary}"
            else:
                price_text = row.default_price_text

            price_item = QTableWidgetItem(price_text)

            stock_item = QTableWidgetItem(row.stock_text)
            stock_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if row.stock_state == "empty":
                stock_item.setForeground(QColor("#FB7185"))
            elif row.stock_state == "low":
                stock_item.setForeground(QColor("#FBBF24"))
            else:
                stock_item.setForeground(QColor("#34D399"))

            self._items_table.setItem(idx, 0, sku_item)
            self._items_table.setItem(idx, 1, name_item)
            self._items_table.setItem(idx, 2, cat_item)
            self._items_table.setItem(idx, 3, price_item)
            self._items_table.setItem(idx, 4, stock_item)
            self._items_table.setCellWidget(
                idx, 5, self._create_status_widget(row.is_active)
            )
            self._items_table.setCellWidget(
                idx, 6, self._create_item_action_widget(row)
            )

        self._items_table.blockSignals(False)
        self._update_items_table_column_widths()

    def set_services(self, rows: list[ServiceRowData]) -> None:
        """Mengisi tabel layanan jasa dengan data terbaru dari backend.

        Args:
            rows: Daftar objek ServiceRowData untuk dirender pada tabel.
        """
        self._services_table.blockSignals(True)
        self._services_table.setRowCount(len(rows))
        mono_font = QFont("Consolas", 9)

        for idx, row in enumerate(rows):
            sku_item = QTableWidgetItem(row.sku)
            sku_item.setFont(mono_font)
            sku_item.setForeground(QColor("#7DD3FC"))
            sku_item.setData(Qt.ItemDataRole.UserRole, row.service_id)

            name_item = QTableWidgetItem(row.name)

            price_item = QTableWidgetItem(row.selling_price_text)
            price_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            mat_item = QTableWidgetItem(row.material_summary)
            mat_item.setForeground(QColor("#9AA3C2"))

            self._services_table.setItem(idx, 0, sku_item)
            self._services_table.setItem(idx, 1, name_item)
            self._services_table.setItem(idx, 2, price_item)
            self._services_table.setItem(idx, 3, mat_item)
            self._services_table.setCellWidget(
                idx, 4, self._create_status_widget(row.is_active)
            )
            self._services_table.setCellWidget(
                idx, 5, self._create_service_action_widget(row)
            )

        self._services_table.blockSignals(False)

    def set_item_detail(self, detail: ItemFullDetail) -> None:
        """Meneruskan detail lengkap barang ke panel samping kanan.

        Args:
            detail: Objek ItemFullDetail dari backend.
        """
        self._detail_panel.show_item_detail(detail)

    def set_service_detail(self, detail: ServiceFullDetail) -> None:
        """Meneruskan detail lengkap layanan jasa ke panel samping kanan.

        Args:
            detail: Objek ServiceFullDetail dari backend.
        """
        self._detail_panel.show_service_detail(detail)

    def clear_detail_panel(self) -> None:
        """Mengosongkan panel detail samping kanan."""
        self._detail_panel.clear_detail()

    def set_pagination(
        self,
        current_page: int,
        total_pages: int,
        total_records: int,
        shown_records: int,
    ) -> None:
        """Memperbarui indikator teks dan status tombol navigasi paginasi.

        Args:
            current_page: Nomor halaman yang sedang aktif.
            total_pages: Jumlah total halaman yang tersedia.
            total_records: Total keseluruhan baris data sesuai filter.
            shown_records: Jumlah baris yang sedang ditampilkan pada halaman aktif.
        """
        self._current_page = max(1, current_page)
        self._total_pages = max(1, total_pages)

        self._page_info_label.setText(
            f"Menampilkan {shown_records} dari {total_records} data"
        )
        self._page_indicator_label.setText(
            f"Hal {self._current_page} / {self._total_pages}"
        )
        self._prev_page_btn.setEnabled(self._current_page > 1)
        self._next_page_btn.setEnabled(self._current_page < self._total_pages)


class ManajemenProdukWindow(FramelessMainWindow):
    """Jendela mandiri tanpa bingkai OS untuk menampilkan ManajemenProdukPage.

    Attributes:
        page: Instance ManajemenProdukPage yang terpasang sebagai konten utama.
    """

    def __init__(
        self,
        icon_config: TitleBarIconConfig,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi jendela frameless dengan CustomTitleBar.

        Args:
            icon_config: Konfigurasi path ikon tombol kontrol title bar.
            parent: Widget induk opsional.
        """
        super().__init__(
            icon_config=icon_config,
            page_title="Manajemen Produk",
            parent=parent,
        )
        self.page = ManajemenProdukPage(self)
        self.set_content_widget(self.page)
