"""Modul dialog kartu stok untuk menampilkan riwayat mutasi barang FIFO.

Modul ini menyediakan antarmuka modal baca-saja berbasis CustomDialog untuk
memantau catatan keluar-masuk stok dari tabel stock_movements lengkap dengan
ringkasan total masuk/keluar, badge jenis mutasi berwarna, filter kustom,
serta pencarian catatan.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPaintEvent, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyleOptionComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import StockMovementRecord, format_qty
from util.customdialog import CustomDialog

MOVEMENT_TYPE_LABELS: dict[str, str] = {
    "PURCHASE": "Pembelian",
    "OPENING_STOCK": "Stok Awal",
    "ADJUSTMENT_IN": "Opname Masuk",
    "ADJUSTMENT_OUT": "Opname Keluar",
    "SALE": "Penjualan",
    "SERVICE_MATERIAL": "Bahan Jasa",
    "SALES_RETURN": "Retur Jual",
}

MOVEMENT_TYPE_COLORS: dict[str, str] = {
    "PURCHASE": "#34D399",
    "OPENING_STOCK": "#38BDF8",
    "ADJUSTMENT_IN": "#10B981",
    "ADJUSTMENT_OUT": "#FBBF24",
    "SALE": "#FB7185",
    "SERVICE_MATERIAL": "#C084FC",
    "SALES_RETURN": "#60A5FA",
}

_MOVEMENT_BADGE_STYLES: dict[str, tuple[str, str, str]] = {
    "PURCHASE": (
        "#34D399",
        "rgba(52, 211, 153, 0.14)",
        "rgba(52, 211, 153, 0.34)",
    ),
    "OPENING_STOCK": (
        "#38BDF8",
        "rgba(56, 189, 248, 0.14)",
        "rgba(56, 189, 248, 0.34)",
    ),
    "ADJUSTMENT_IN": (
        "#6EE7B7",
        "rgba(16, 185, 129, 0.14)",
        "rgba(16, 185, 129, 0.34)",
    ),
    "ADJUSTMENT_OUT": (
        "#FCD34D",
        "rgba(245, 158, 11, 0.14)",
        "rgba(245, 158, 11, 0.34)",
    ),
    "SALE": (
        "#FDA4AF",
        "rgba(244, 63, 94, 0.14)",
        "rgba(244, 63, 94, 0.34)",
    ),
    "SERVICE_MATERIAL": (
        "#D8B4FE",
        "rgba(192, 132, 252, 0.14)",
        "rgba(192, 132, 252, 0.34)",
    ),
    "SALES_RETURN": (
        "#93C5FD",
        "rgba(96, 165, 250, 0.14)",
        "rgba(96, 165, 250, 0.34)",
    ),
}


def _svg_template(icon_key: str, color: str) -> str:
    """Menghasilkan markup SVG vektor berdasarkan kunci ikon dan warna.

    Args:
        icon_key: Nama kunci ikon yang diminta.
        color: Warna stroke atau fill SVG dalam format CSS/hex.

    Returns:
        String markup XML SVG yang siap dirender oleh QSvgRenderer.
    """
    icons: dict[str, str] = {
        "clipboard_list": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'
            f'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
            f'<path d="M12 11h4"/>'
            f'<path d="M12 16h4"/>'
            f'<path d="M8 11h.01"/>'
            f'<path d="M8 16h.01"/>'
            f"</svg>"
        ),
        "arrow_down_left": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M12 8v8"/>'
            f'<path d="m8 12 4 4 4-4"/>'
            f"</svg>"
        ),
        "arrow_up_right": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M12 16V8"/>'
            f'<path d="m8 12 4-4 4 4"/>'
            f"</svg>"
        ),
        "layers": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.1" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
            f'<polyline points="2 12 12 17 22 12"/>'
            f'<polyline points="2 17 12 22 22 17"/>'
            f"</svg>"
        ),
        "search": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="11" cy="11" r="7"/>'
            f'<path d="m21 21-4.3-4.3"/>'
            f"</svg>"
        ),
        "rotate_ccw": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>'
            f'<path d="M3 3v5h5"/>'
            f"</svg>"
        ),
        "chevron_down": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="6 9 12 15 18 9"/>'
            f"</svg>"
        ),
        "dot": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
            f'<circle cx="8" cy="8" r="4.5" fill="{color}"/>'
            f"</svg>"
        ),
        "inbox": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
            f'<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
            f"</svg>"
        ),
        "info": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.1" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M12 16v-4"/>'
            f'<path d="M12 8h.01"/>'
            f"</svg>"
        ),
        "close": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M18 6 6 18"/>'
            f'<path d="m6 6 12 12"/>'
            f"</svg>"
        ),
    }
    return icons.get(icon_key, icons["clipboard_list"])


def _render_svg_pixmap(icon_key: str, color: str, size: int) -> QPixmap:
    """Merender markup SVG menjadi objek QPixmap transparan beresolusi tajam.

    Args:
        icon_key: Kunci ikon SVG yang akan dirender.
        color: Warna stroke/fill ikon dalam format CSS/hex.
        size: Ukuran sisi pixmap persegi dalam piksel.

    Returns:
        Objek QPixmap hasil rendering SVG.
    """
    svg_bytes = QByteArray(_svg_template(icon_key, color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _render_svg_icon(icon_key: str, color: str, size: int = 16) -> QIcon:
    """Membuat QIcon dari rendering SVG inline.

    Args:
        icon_key: Kunci ikon SVG yang akan dirender.
        color: Warna stroke/fill ikon dalam format CSS/hex.
        size: Ukuran ikon dalam piksel.

    Returns:
        Objek QIcon yang siap dipasang pada tombol atau widget Qt.
    """
    return QIcon(_render_svg_pixmap(icon_key, color, size))


def _paint_centered_svg(
    painter: QPainter,
    rect: QRectF,
    icon_key: str,
    color: str,
    icon_size: float,
) -> None:
    """Menggambar ikon SVG tepat di tengah area persegi panjang yang ditentukan.

    Args:
        painter: Instance QPainter aktif.
        rect: Area target tempat ikon dipusatkan.
        icon_key: Kunci ikon SVG yang akan digambar.
        color: Warna stroke ikon dalam format CSS/hex.
        icon_size: Lebar dan tinggi ikon dalam piksel.
    """
    svg_bytes = QByteArray(_svg_template(icon_key, color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    x_pos = rect.x() + (rect.width() - icon_size) / 2.0
    y_pos = rect.y() + (rect.height() - icon_size) / 2.0
    renderer.render(painter, QRectF(x_pos, y_pos, icon_size, icon_size))


class _StyledComboBox(QComboBox):
    """QComboBox kustom dengan popup modern membulat dan ikon chevron SVG."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi _StyledComboBox beserta tampilan popup kustom.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        popup_view = QListView(self)
        popup_view.setObjectName("ComboPopupView")
        popup_view.setSpacing(2)
        popup_view.setUniformItemSizes(True)
        popup_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setView(popup_view)

    def showPopup(self) -> None:
        """Menampilkan daftar dropdown dengan sudut membulat dan jarak vertikal."""
        super().showPopup()
        view = self.view()
        if view is None:
            return
        popup_window = view.window()
        if popup_window is not None:
            popup_window.setWindowFlags(
                Qt.WindowType.Popup
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.NoDropShadowWindowHint
            )
            popup_window.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground,
                True,
            )
            target_pos = self.mapToGlobal(QPoint(0, self.height() + 4))
            popup_window.move(target_pos)
            popup_window.setMinimumWidth(self.width())
            popup_window.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar combobox beserta ikon chevron bawah SVG di area tombol.

        Args:
            event: Event penggambaran widget Qt.
        """
        super().paintEvent(event)
        style = self.style()
        if style is None:
            return
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow_rect = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if not arrow_rect.isValid():
            return
        color = "#9399B2" if self.isEnabled() else "#585B70"
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_centered_svg(
            painter,
            QRectF(arrow_rect),
            "chevron_down",
            color,
            13.0,
        )
        painter.end()


@dataclass(frozen=True)
class StockCardItemInfo:
    """Informasi identitas ringkas barang yang ditampilkan pada header kartu stok.

    Attributes:
        item_id: Primary key barang pada tabel items.
        sku: Kode SKU barang.
        name: Nama lengkap barang.
        base_unit_symbol: Simbol satuan dasar barang (misalnya 'Lbr', 'Pcs').
        current_stock_text: Teks total sisa stok aktif saat ini.
    """

    item_id: int
    sku: str
    name: str
    base_unit_symbol: str
    current_stock_text: str


class StockCardDialog(CustomDialog):
    """Dialog kustom baca-saja untuk menelusuri riwayat mutasi stok barang.

    Menampilkan header identitas barang, kartu ringkasan total masuk/keluar,
    filter jenis mutasi serta pencarian cepat, dan tabel riwayat mutasi stok.
    """

    def __init__(
        self,
        records: list[StockMovementRecord],
        item_info: StockCardItemInfo | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi StockCardDialog dengan daftar riwayat mutasi stok.

        Args:
            records: Daftar objek StockMovementRecord dari backend.
            item_info: Informasi identitas barang opsional untuk header dialog.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._all_records: list[StockMovementRecord] = list(records)
        self._item_info: StockCardItemInfo | None = item_info
        self._unit_symbol: str = (
            item_info.base_unit_symbol.strip() if item_info is not None else ""
        )

        title_suffix = (
            f" - {item_info.sku}" if item_info is not None and item_info.sku else ""
        )
        self.setWindowTitle(f"Kartu Stok{title_suffix}")
        self.setMinimumSize(760, 500)
        self.resize(820, 560)

        self._total_in_val = QLabel("0", self)
        self._total_out_val = QLabel("0", self)
        self._movement_count_val = QLabel("0", self)

        self._search_input = QLineEdit(self)
        self._type_combo = _StyledComboBox(self)
        self._reset_btn = QPushButton("Reset", self)

        self._table_stack = QStackedWidget(self)
        self._table = QTableWidget(0, 5, self)
        self._empty_title_label = QLabel("Belum ada riwayat mutasi stok", self)
        self._empty_desc_label = QLabel("", self)

        self._footer_info_label = QLabel("0 mutasi ditampilkan", self)
        self._close_btn = QPushButton("Tutup", self)

        self._setup_ui()
        self._apply_styles()
        self._populate_type_filter()
        self._connect_signals()
        self._apply_filters()

    def _setup_ui(self) -> None:
        """Menyusun tata letak dialog kartu stok yang lapang dan mudah dipindai."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header_summary_card())
        root_layout.addWidget(self._build_filter_bar())
        root_layout.addWidget(self._build_table_container(), 1)
        root_layout.addLayout(self._build_footer_bar())
        self.setLayout(root_layout)

    def _build_header_summary_card(self) -> QFrame:
        """Membangun kartu header identitas barang dan ringkasan angka mutasi.

        Returns:
            Frame berisi info barang serta kartu total masuk, keluar, dan mutasi.
        """
        card = QFrame(self)
        card.setObjectName("HeaderSummaryCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        icon_badge = QLabel(card)
        icon_badge.setObjectName("HeaderIconBadge")
        icon_badge.setFixedSize(42, 42)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setPixmap(_render_svg_pixmap("clipboard_list", "#38BDF8", 22))

        info_box = QVBoxLayout()
        info_box.setContentsMargins(0, 0, 0, 0)
        info_box.setSpacing(5)

        top_meta = QHBoxLayout()
        top_meta.setContentsMargins(0, 0, 0, 0)
        top_meta.setSpacing(6)

        sku_text = self._item_info.sku if self._item_info is not None else "ITEM"
        sku_badge = QLabel(sku_text, card)
        sku_badge.setObjectName("SkuBadge")

        stock_text = (
            f"Stok Aktif: {self._item_info.current_stock_text}"
            if self._item_info is not None
            else "Riwayat Mutasi"
        )
        stock_badge = QLabel(stock_text, card)
        stock_badge.setObjectName("StockBadge")

        top_meta.addWidget(sku_badge)
        top_meta.addWidget(stock_badge)
        top_meta.addStretch(1)

        name_text = (
            self._item_info.name
            if self._item_info is not None
            else "Kartu Stok Barang"
        )
        name_label = QLabel(name_text, card)
        name_label.setObjectName("ItemTitle")

        info_box.addLayout(top_meta)
        info_box.addWidget(name_label)

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(8)

        metrics_row.addWidget(
            self._make_metric_card(
                caption="TOTAL MASUK",
                value_label=self._total_in_val,
                value_obj_name="MetricIn",
                icon_key="arrow_down_left",
                accent_color="#34D399",
                card_obj_name="MetricCardIn",
            )
        )
        metrics_row.addWidget(
            self._make_metric_card(
                caption="TOTAL KELUAR",
                value_label=self._total_out_val,
                value_obj_name="MetricOut",
                icon_key="arrow_up_right",
                accent_color="#FB7185",
                card_obj_name="MetricCardOut",
            )
        )
        metrics_row.addWidget(
            self._make_metric_card(
                caption="MUTASI",
                value_label=self._movement_count_val,
                value_obj_name="MetricCount",
                icon_key="layers",
                accent_color="#A78BFA",
                card_obj_name="MetricCardCount",
            )
        )

        layout.addWidget(icon_badge)
        layout.addLayout(info_box, 1)
        layout.addLayout(metrics_row)
        return card

    def _make_metric_card(
        self,
        caption: str,
        value_label: QLabel,
        value_obj_name: str,
        icon_key: str,
        accent_color: str,
        card_obj_name: str,
    ) -> QFrame:
        """Membuat kartu metrik mini berwarna lembut dengan ikon SVG.

        Args:
            caption: Judul kecil indikator.
            value_label: Widget QLabel penampil nilai metrik.
            value_obj_name: ObjectName untuk pewarnaan QSS nilai.
            icon_key: Kunci ikon SVG untuk indikator.
            accent_color: Warna aksen ikon SVG dalam format hex.
            card_obj_name: ObjectName frame kartu metrik.

        Returns:
            Frame kartu metrik berisi ikon, judul, dan nilai.
        """
        metric_card = QFrame(self)
        metric_card.setObjectName(card_obj_name)
        metric_card.setMinimumWidth(104)

        outer = QHBoxLayout(metric_card)
        outer.setContentsMargins(10, 7, 10, 7)
        outer.setSpacing(8)

        icon_label = QLabel(metric_card)
        icon_label.setObjectName("TransparentIcon")
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(_render_svg_pixmap(icon_key, accent_color, 18))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        cap_label = QLabel(caption, metric_card)
        cap_label.setObjectName("StripCaption")

        value_label.setObjectName(value_obj_name)
        text_col.addWidget(cap_label)
        text_col.addWidget(value_label)

        outer.addWidget(icon_label)
        outer.addLayout(text_col)
        return metric_card

    def _build_filter_bar(self) -> QFrame:
        """Membangun baris pencarian catatan dan filter jenis mutasi stok.

        Returns:
            Frame filter satu baris modern.
        """
        bar = QFrame(self)
        bar.setObjectName("FilterBar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._search_input.setObjectName("FilterInput")
        self._search_input.setPlaceholderText(
            "Cari catatan, nomor invoice, atau tanggal..."
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.addAction(
            _render_svg_icon("search", "#7F849C", 15),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self._type_combo.setObjectName("FilterCombo")
        self._type_combo.setMinimumWidth(195)
        self._type_combo.setCursor(Qt.CursorShape.PointingHandCursor)

        self._reset_btn.setObjectName("ResetBtn")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setIcon(_render_svg_icon("rotate_ccw", "#BAC2DE", 14))
        self._reset_btn.setIconSize(QSize(14, 14))

        layout.addWidget(self._search_input, 2)
        layout.addWidget(self._type_combo, 1)
        layout.addWidget(self._reset_btn)
        return bar

    def _build_table_container(self) -> QFrame:
        """Membangun wadah kartu tabel beserta tampilan kosong saat tanpa data.

        Returns:
            Frame pembungkus QStackedWidget berisi tabel dan empty state.
        """
        container = QFrame(self)
        container.setObjectName("TableCard")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self._table_stack.setObjectName("TableStack")
        self._table_stack.addWidget(self._build_table_section())
        self._table_stack.addWidget(self._build_empty_state_widget())

        layout.addWidget(self._table_stack)
        return container

    def _build_empty_state_widget(self) -> QWidget:
        """Membangun tampilan kosong yang ramah saat tidak ada baris mutasi.

        Returns:
            Widget penampil ikon dan keterangan kondisi kosong.
        """
        empty_widget = QWidget(self)
        empty_widget.setObjectName("EmptyStateWidget")
        layout = QVBoxLayout(empty_widget)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_holder = QLabel(empty_widget)
        icon_holder.setObjectName("EmptyIconBadge")
        icon_holder.setFixedSize(56, 56)
        icon_holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_holder.setPixmap(_render_svg_pixmap("inbox", "#7F849C", 28))

        self._empty_title_label.setObjectName("EmptyTitle")
        self._empty_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_desc_label.setObjectName("EmptyDesc")
        self._empty_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_desc_label.setWordWrap(True)

        layout.addWidget(icon_holder, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_title_label)
        layout.addWidget(self._empty_desc_label)
        return empty_widget

    def _build_table_section(self) -> QTableWidget:
        """Mengonfigurasi tabel riwayat keluar-masuk stok barang.

        Returns:
            Widget QTableWidget baca-saja siap diisi baris mutasi.
        """
        self._table.setObjectName("StockCardTable")
        self._table.setHorizontalHeaderLabels(
            ["Tanggal & Waktu", "Jenis Mutasi", "Masuk", "Keluar", "Catatan / Referensi"]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        v_header = self._table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(38)

        h_header = self._table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(34)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            self._table.setColumnWidth(0, 140)
            self._table.setColumnWidth(1, 138)
            self._table.setColumnWidth(2, 102)
            self._table.setColumnWidth(3, 102)

        return self._table

    def _build_footer_bar(self) -> QHBoxLayout:
        """Membangun baris bawah berisi status jumlah baris dan tombol Tutup.

        Returns:
            QHBoxLayout berisi informasi baris dan tombol tutup dialog.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(2, 2, 2, 0)
        footer.setSpacing(8)

        info_icon = QLabel(self)
        info_icon.setObjectName("TransparentIcon")
        info_icon.setFixedSize(16, 16)
        info_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_icon.setPixmap(_render_svg_pixmap("info", "#60A5FA", 14))

        self._footer_info_label.setObjectName("FooterInfoLabel")

        self._close_btn.setObjectName("CloseFooterBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setIcon(_render_svg_icon("close", "#CDD6F4", 14))
        self._close_btn.setIconSize(QSize(14, 14))

        footer.addWidget(info_icon)
        footer.addWidget(self._footer_info_label)
        footer.addStretch(1)
        footer.addWidget(self._close_btn)
        return footer

    def _make_movement_badge(self, rec_type: str, label_text: str) -> QWidget:
        """Membuat widget badge pill berwarna lembut untuk kolom jenis mutasi.

        Args:
            rec_type: Kode jenis mutasi dalam huruf kapital.
            label_text: Teks label mutasi yang ditampilkan.

        Returns:
            Widget pembungkus transparan berisi badge pill jenis mutasi.
        """
        text_color, bg_color, border_color = _MOVEMENT_BADGE_STYLES.get(
            rec_type,
            (
                MOVEMENT_TYPE_COLORS.get(rec_type, "#CDD6F4"),
                "rgba(148, 163, 184, 0.14)",
                "rgba(148, 163, 184, 0.30)",
            ),
        )

        wrapper = QWidget(self._table)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        wrapper.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel(label_text, wrapper)
        badge.setStyleSheet(
            f"background-color: {bg_color}; "
            f"color: {text_color}; "
            f"border: 1px solid {border_color}; "
            f"border-radius: 10px; "
            f"padding: 2px 9px; "
            f"font-size: 10px; "
            f"font-weight: 700;"
        )
        layout.addWidget(badge)
        return wrapper

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap modern serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #161622;
                color: #CDD6F4;
            }
            QFrame#HeaderSummaryCard,
            QFrame#FilterBar,
            QFrame#TableCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QLabel#HeaderIconBadge {
                background-color: rgba(56, 189, 248, 0.14);
                border: 1px solid rgba(56, 189, 248, 0.36);
                border-radius: 10px;
            }
            QLabel#TransparentIcon {
                background: transparent;
                border: none;
            }
            QFrame#MetricCardIn {
                background-color: rgba(16, 185, 129, 0.10);
                border: 1px solid rgba(16, 185, 129, 0.28);
                border-radius: 8px;
            }
            QFrame#MetricCardOut {
                background-color: rgba(244, 63, 94, 0.10);
                border: 1px solid rgba(244, 63, 94, 0.28);
                border-radius: 8px;
            }
            QFrame#MetricCardCount {
                background-color: rgba(167, 139, 250, 0.10);
                border: 1px solid rgba(167, 139, 250, 0.28);
                border-radius: 8px;
            }
            QLabel#SkuBadge {
                background-color: #252638;
                color: #89B4FA;
                border: 1px solid #3B3D54;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#StockBadge {
                background-color: rgba(56, 189, 248, 0.14);
                color: #7DD3FC;
                border: 1px solid rgba(56, 189, 248, 0.34);
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#ItemTitle {
                color: #F5F7FF;
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#StripCaption {
                color: #9399B2;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: transparent;
            }
            QLabel#MetricIn {
                color: #34D399;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#MetricOut {
                color: #FB7185;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#MetricCount {
                color: #DDD6FE;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLineEdit#FilterInput,
            QComboBox#FilterCombo {
                background-color: #14141F;
                color: #F1F5F9;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FilterInput:hover,
            QComboBox#FilterCombo:hover {
                border-color: #45475A;
            }
            QLineEdit#FilterInput:focus,
            QComboBox#FilterCombo:focus,
            QComboBox#FilterCombo:on {
                border: 1.5px solid #38BDF8;
                background-color: #181826;
            }
            QComboBox#FilterCombo::drop-down {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 28px;
                margin: 2px 2px 2px 0px;
                border-left: 1px solid #2A2B3D;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background-color: #1B1B2A;
            }
            QComboBox#FilterCombo::drop-down:hover {
                background-color: #26273B;
            }
            QComboBox#FilterCombo::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }
            QListView#ComboPopupView {
                background-color: #1A1B2B;
                color: #CDD6F4;
                border: 1px solid #3E405B;
                border-radius: 9px;
                padding: 5px;
                outline: none;
                font-size: 12px;
            }
            QListView#ComboPopupView::item {
                padding: 7px 10px;
                border-radius: 6px;
                color: #CDD6F4;
                background-color: transparent;
            }
            QListView#ComboPopupView::item:hover {
                background-color: #26283E;
                color: #FFFFFF;
            }
            QListView#ComboPopupView::item:selected {
                background-color: rgba(56, 189, 248, 0.20);
                color: #7DD3FC;
                font-weight: 600;
            }
            QPushButton#ResetBtn {
                background-color: #161622;
                color: #BAC2DE;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#ResetBtn:hover {
                background-color: #26283E;
                color: #FFFFFF;
                border-color: #45475A;
            }
            QPushButton#ResetBtn:pressed {
                background-color: #1E1E2E;
            }
            QStackedWidget#TableStack,
            QWidget#EmptyStateWidget {
                background: transparent;
                border: none;
            }
            QLabel#EmptyIconBadge {
                background-color: #161622;
                border: 1px solid #313244;
                border-radius: 28px;
            }
            QLabel#EmptyTitle {
                color: #E2E8F0;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#EmptyDesc {
                color: #7F849C;
                font-size: 11px;
                background: transparent;
            }
            QTableWidget#StockCardTable {
                background-color: transparent;
                alternate-background-color: rgba(255, 255, 255, 0.025);
                color: #CDD6F4;
                border: none;
                border-radius: 9px;
                font-size: 12px;
                selection-background-color: rgba(56, 189, 248, 0.16);
                selection-color: #FFFFFF;
            }
            QTableWidget#StockCardTable::item {
                padding: 4px 10px;
                border-bottom: 1px solid #26273A;
            }
            QTableWidget#StockCardTable QHeaderView::section {
                background-color: #232436;
                color: #9399B2;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 6px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }
            QTableWidget#StockCardTable QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0px;
            }
            QTableWidget#StockCardTable QScrollBar::handle:vertical {
                background: #3B3D54;
                border-radius: 4px;
                min-height: 28px;
            }
            QTableWidget#StockCardTable QScrollBar::handle:vertical:hover {
                background: #585B70;
            }
            QTableWidget#StockCardTable QScrollBar::add-line:vertical,
            QTableWidget#StockCardTable QScrollBar::sub-line:vertical,
            QTableWidget#StockCardTable QScrollBar::add-page:vertical,
            QTableWidget#StockCardTable QScrollBar::sub-page:vertical {
                background: none;
                height: 0px;
            }
            QLabel#FooterInfoLabel {
                color: #A6ADC8;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QPushButton#CloseFooterBtn {
                background-color: #232436;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 7px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CloseFooterBtn:hover {
                background-color: #313244;
                border-color: #585B70;
                color: #FFFFFF;
            }
            QPushButton#CloseFooterBtn:pressed {
                background-color: #1E1E2E;
            }
            """
        )

    def _populate_type_filter(self) -> None:
        """Mengisi dropdown filter jenis mutasi lengkap dengan ikon warna."""
        self._type_combo.clear()
        self._type_combo.addItem(
            _render_svg_icon("dot", "#9399B2", 12),
            "Semua Jenis Mutasi",
            "ALL",
        )

        present_types = {rec.movement_type.strip().upper() for rec in self._all_records}
        ordered_keys = list(MOVEMENT_TYPE_LABELS.keys())
        for extra_type in sorted(present_types):
            if extra_type and extra_type not in MOVEMENT_TYPE_LABELS:
                ordered_keys.append(extra_type)

        for key in ordered_keys:
            label = MOVEMENT_TYPE_LABELS.get(key, key)
            dot_color = MOVEMENT_TYPE_COLORS.get(key, "#CDD6F4")
            self._type_combo.addItem(
                _render_svg_icon("dot", dot_color, 12),
                label,
                key,
            )

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal pencarian, filter dropdown, reset, dan tutup."""
        self._search_input.textChanged.connect(self._apply_filters)
        self._type_combo.currentIndexChanged.connect(self._apply_filters)
        self._reset_btn.clicked.connect(self._reset_filters)
        self._close_btn.clicked.connect(self.accept)

    def _reset_filters(self) -> None:
        """Mengembalikan kata kunci pencarian dan filter jenis mutasi ke default."""
        self._search_input.clear()
        self._type_combo.setCurrentIndex(0)

    def _apply_filters(self) -> None:
        """Menyaring daftar mutasi secara lokal lalu memperbarui tabel dan ringkasan."""
        query = self._search_input.text().strip().lower()
        raw_type = self._type_combo.currentData()
        selected_type = str(raw_type) if raw_type is not None else "ALL"

        filtered: list[StockMovementRecord] = []
        for rec in self._all_records:
            rec_type = rec.movement_type.strip().upper()
            if selected_type != "ALL" and rec_type != selected_type:
                continue
            if query:
                searchable = (
                    f"{rec.movement_date} {rec_type} "
                    f"{MOVEMENT_TYPE_LABELS.get(rec_type, '')} {rec.notes}"
                ).lower()
                if query not in searchable:
                    continue
            filtered.append(rec)

        self._render_rows(filtered)

    def _render_rows(self, rows: list[StockMovementRecord]) -> None:
        """Merender daftar mutasi terfilter ke tabel serta memperbarui metrik.

        Args:
            rows: Daftar StockMovementRecord yang lolos filter aktif.
        """
        total_in = sum(rec.quantity_in for rec in rows)
        total_out = sum(rec.quantity_out for rec in rows)

        self._total_in_val.setText(format_qty(total_in, self._unit_symbol))
        self._total_out_val.setText(format_qty(total_out, self._unit_symbol))
        self._movement_count_val.setText(str(len(rows)))
        self._footer_info_label.setText(
            f"Menampilkan {len(rows)} dari {len(self._all_records)} mutasi"
        )

        if not rows:
            if not self._all_records:
                self._empty_title_label.setText("Belum ada riwayat mutasi stok")
                self._empty_desc_label.setText(
                    "Mutasi masuk, keluar, dan penyesuaian opname untuk barang ini akan tampil di sini."
                )
            else:
                self._empty_title_label.setText("Tidak ada mutasi yang cocok")
                self._empty_desc_label.setText(
                    "Coba ubah kata kunci pencarian atau tekan Reset untuk melihat semua riwayat."
                )
            self._table_stack.setCurrentIndex(1)
            return

        self._table_stack.setCurrentIndex(0)
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))

        mono_font = QFont("Consolas", 9)
        qty_font = QFont()
        qty_font.setBold(True)

        for idx, rec in enumerate(rows):
            date_item = QTableWidgetItem(rec.movement_date)
            date_item.setFont(mono_font)
            date_item.setForeground(QColor("#BAC2DE"))

            rec_type = rec.movement_type.strip().upper()
            type_label = MOVEMENT_TYPE_LABELS.get(rec_type, rec.movement_type)
            type_placeholder = QTableWidgetItem("")
            type_badge = self._make_movement_badge(rec_type, type_label)

            has_in = rec.quantity_in > 0
            in_text = (
                f"+{format_qty(rec.quantity_in, self._unit_symbol)}"
                if has_in
                else "-"
            )
            in_item = QTableWidgetItem(in_text)
            in_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if has_in:
                in_item.setFont(qty_font)
            in_item.setForeground(QColor("#34D399" if has_in else "#585B70"))

            has_out = rec.quantity_out > 0
            out_text = (
                f"-{format_qty(rec.quantity_out, self._unit_symbol)}"
                if has_out
                else "-"
            )
            out_item = QTableWidgetItem(out_text)
            out_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if has_out:
                out_item.setFont(qty_font)
            out_item.setForeground(QColor("#FB7185" if has_out else "#585B70"))

            notes_item = QTableWidgetItem(rec.notes if rec.notes else "-")
            notes_item.setForeground(
                QColor("#CDD6F4" if rec.notes else "#6C7086")
            )

            self._table.setItem(idx, 0, date_item)
            self._table.setItem(idx, 1, type_placeholder)
            self._table.setCellWidget(idx, 1, type_badge)
            self._table.setItem(idx, 2, in_item)
            self._table.setItem(idx, 3, out_item)
            self._table.setItem(idx, 4, notes_item)

    @classmethod
    def show_stock_card(
        cls,
        parent: QWidget,
        records: list[StockMovementRecord],
        item_info: StockCardItemInfo | None = None,
    ) -> None:
        """Membuka dialog kartu stok secara modal untuk satu barang.

        Args:
            parent: Widget induk dialog.
            records: Daftar catatan StockMovementRecord hasil query backend.
            item_info: Informasi identitas barang opsional untuk ditampilkan di header.
        """
        dialog = cls(records=records, item_info=item_info, parent=parent)
        dialog.exec()