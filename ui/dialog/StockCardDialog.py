"""Modul dialog kartu stok untuk menampilkan riwayat mutasi barang FIFO.

Modul ini menyediakan antarmuka modal baca-saja berbasis CustomDialog untuk
memantau catatan keluar-masuk stok dari tabel stock_movements lengkap dengan
ringkasan total masuk/keluar serta filter jenis mutasi dan pencarian catatan.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
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
    "PURCHASE": "#4ADE80",
    "OPENING_STOCK": "#60A5FA",
    "ADJUSTMENT_IN": "#34D399",
    "ADJUSTMENT_OUT": "#FBBF24",
    "SALE": "#F87171",
    "SERVICE_MATERIAL": "#C084FC",
    "SALES_RETURN": "#38BDF8",
}


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

    Menampilkan header identitas barang, strip ringkasan total masuk/keluar,
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
        self.setMinimumSize(700, 460)
        self.resize(760, 510)

        self._total_in_val = QLabel("0", self)
        self._total_out_val = QLabel("0", self)
        self._movement_count_val = QLabel("0", self)

        self._search_input = QLineEdit(self)
        self._type_combo = QComboBox(self)
        self._reset_btn = QPushButton("Reset", self)

        self._table = QTableWidget(0, 5, self)
        self._footer_info_label = QLabel("0 mutasi ditampilkan", self)
        self._close_btn = QPushButton("Tutup", self)

        self._setup_ui()
        self._apply_styles()
        self._populate_type_filter()
        self._connect_signals()
        self._apply_filters()

    def _setup_ui(self) -> None:
        """Menyusun tata letak dialog kartu stok yang padat dan mudah dipindai."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_header_summary_card())
        root_layout.addWidget(self._build_filter_bar())
        root_layout.addWidget(self._build_table_section(), 1)
        root_layout.addLayout(self._build_footer_bar())
        self.setLayout(root_layout)

    def _build_header_summary_card(self) -> QFrame:
        """Membangun kartu header identitas barang dan ringkasan angka mutasi.

        Returns:
            Frame berisi info barang serta total masuk, keluar, dan jumlah mutasi.
        """
        card = QFrame(self)
        card.setObjectName("HeaderSummaryCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)

        info_box = QVBoxLayout()
        info_box.setContentsMargins(0, 0, 0, 0)
        info_box.setSpacing(2)

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

        metrics_strip = QFrame(card)
        metrics_strip.setObjectName("MetricsStrip")
        strip_layout = QHBoxLayout(metrics_strip)
        strip_layout.setContentsMargins(10, 5, 10, 5)
        strip_layout.setSpacing(12)

        strip_layout.addLayout(
            self._make_metric_col("TOTAL MASUK", self._total_in_val, "MetricIn")
        )
        strip_layout.addWidget(self._make_v_divider(metrics_strip))
        strip_layout.addLayout(
            self._make_metric_col("TOTAL KELUAR", self._total_out_val, "MetricOut")
        )
        strip_layout.addWidget(self._make_v_divider(metrics_strip))
        strip_layout.addLayout(
            self._make_metric_col("MUTASI", self._movement_count_val, "MetricCount")
        )

        layout.addLayout(info_box, 1)
        layout.addWidget(metrics_strip)
        return card

    def _make_metric_col(
        self,
        caption: str,
        value_label: QLabel,
        value_obj_name: str,
    ) -> QVBoxLayout:
        """Membuat satu kolom indikator ringkas di dalam strip metrik.

        Args:
            caption: Judul kecil indikator.
            value_label: Widget QLabel penampil nilai metrik.
            value_obj_name: ObjectName untuk pewarnaan QSS spesifik.

        Returns:
            QVBoxLayout berisi label judul dan nilai.
        """
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        cap_label = QLabel(caption, self)
        cap_label.setObjectName("StripCaption")

        value_label.setObjectName(value_obj_name)
        col.addWidget(cap_label)
        col.addWidget(value_label)
        return col

    @staticmethod
    def _make_v_divider(parent: QWidget) -> QFrame:
        """Membuat garis pemisah vertikal tipis antar indikator.

        Args:
            parent: Widget induk garis pemisah.

        Returns:
            Frame vertikal berlebar 1 piksel.
        """
        divider = QFrame(parent)
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("VerticalDivider")
        return divider

    def _build_filter_bar(self) -> QFrame:
        """Membangun baris pencarian catatan dan filter jenis mutasi stok.

        Returns:
            Frame filter satu baris kompak.
        """
        bar = QFrame(self)
        bar.setObjectName("FilterBar")
        bar.setFixedHeight(36)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._search_input.setObjectName("FilterInput")
        self._search_input.setPlaceholderText("Cari catatan, nomor invoice, atau tanggal...")
        self._search_input.setClearButtonEnabled(True)

        self._type_combo.setObjectName("FilterCombo")
        self._type_combo.setMinimumWidth(165)

        self._reset_btn.setObjectName("GhostBtn")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self._search_input, 2)
        layout.addWidget(self._type_combo, 1)
        layout.addWidget(self._reset_btn)
        return bar

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
            v_header.setDefaultSectionSize(28)

        h_header = self._table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(28)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            self._table.setColumnWidth(0, 126)
            self._table.setColumnWidth(1, 118)
            self._table.setColumnWidth(2, 92)
            self._table.setColumnWidth(3, 92)

        return self._table

    def _build_footer_bar(self) -> QHBoxLayout:
        """Membangun baris bawah berisi status jumlah baris dan tombol Tutup.

        Returns:
            QHBoxLayout berisi informasi baris dan tombol tutup dialog.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)

        self._footer_info_label.setObjectName("FooterInfoLabel")

        self._close_btn.setObjectName("CloseFooterBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        footer.addWidget(self._footer_info_label)
        footer.addStretch(1)
        footer.addWidget(self._close_btn)
        return footer

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #181825;
                color: #CDD6F4;
            }
            QFrame#HeaderSummaryCard, QFrame#FilterBar {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QFrame#MetricsStrip {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 5px;
            }
            QFrame#VerticalDivider {
                color: #313244;
                background-color: #313244;
                max-width: 1px;
            }
            QLabel#SkuBadge {
                background-color: #252638;
                color: #89B4FA;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#StockBadge {
                background-color: rgba(59, 130, 246, 0.14);
                color: #93C5FD;
                border: 1px solid rgba(59, 130, 246, 0.30);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#ItemTitle {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#StripCaption {
                color: #6C7086;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.4px;
                background: transparent;
            }
            QLabel#MetricIn {
                color: #4ADE80;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#MetricOut {
                color: #F87171;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#MetricCount {
                color: #CDD6F4;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLineEdit#FilterInput, QComboBox#FilterCombo {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FilterInput:focus, QComboBox#FilterCombo:focus {
                border: 1px solid #3B82F6;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QPushButton#GhostBtn {
                background-color: transparent;
                color: #9399B2;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#GhostBtn:hover {
                background-color: #252638;
                color: #CDD6F4;
            }
            QTableWidget#StockCardTable {
                background-color: #1E1E2E;
                alternate-background-color: #222335;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                font-size: 11px;
                selection-background-color: rgba(59, 130, 246, 0.22);
                selection-color: #FFFFFF;
            }
            QTableWidget#StockCardTable::item {
                padding: 2px 7px;
                border-bottom: 1px solid #26273A;
            }
            QTableWidget#StockCardTable QHeaderView::section {
                background-color: #252638;
                color: #9399B2;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 3px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#FooterInfoLabel {
                color: #9399B2;
                font-size: 11px;
                background: transparent;
            }
            QPushButton#CloseFooterBtn {
                background-color: #252638;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 5px;
                padding: 5px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CloseFooterBtn:hover {
                background-color: #313244;
            }
            """
        )

    def _populate_type_filter(self) -> None:
        """Mengisi dropdown filter jenis mutasi termasuk tipe kustom bila ada."""
        self._type_combo.clear()
        self._type_combo.addItem("Semua Jenis Mutasi", "ALL")

        present_types = {rec.movement_type.strip().upper() for rec in self._all_records}
        ordered_keys = list(MOVEMENT_TYPE_LABELS.keys())
        for extra_type in sorted(present_types):
            if extra_type and extra_type not in MOVEMENT_TYPE_LABELS:
                ordered_keys.append(extra_type)

        for key in ordered_keys:
            label = MOVEMENT_TYPE_LABELS.get(key, key)
            self._type_combo.addItem(label, key)

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

        self._table.setRowCount(len(rows))
        mono_font = QFont("Consolas", 9)

        for idx, rec in enumerate(rows):
            date_item = QTableWidgetItem(rec.movement_date)
            date_item.setFont(mono_font)
            date_item.setForeground(QColor("#BAC2DE"))

            rec_type = rec.movement_type.strip().upper()
            type_label = MOVEMENT_TYPE_LABELS.get(rec_type, rec.movement_type)
            type_item = QTableWidgetItem(type_label)
            type_color = MOVEMENT_TYPE_COLORS.get(rec_type, "#CDD6F4")
            type_item.setForeground(QColor(type_color))

            in_text = (
                f"+{format_qty(rec.quantity_in, self._unit_symbol)}"
                if rec.quantity_in > 0
                else "-"
            )
            in_item = QTableWidgetItem(in_text)
            in_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            in_item.setForeground(
                QColor("#4ADE80" if rec.quantity_in > 0 else "#585B70")
            )

            out_text = (
                f"-{format_qty(rec.quantity_out, self._unit_symbol)}"
                if rec.quantity_out > 0
                else "-"
            )
            out_item = QTableWidgetItem(out_text)
            out_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            out_item.setForeground(
                QColor("#F87171" if rec.quantity_out > 0 else "#585B70")
            )

            notes_item = QTableWidgetItem(rec.notes if rec.notes else "-")
            if not rec.notes:
                notes_item.setForeground(QColor("#6C7086"))

            self._table.setItem(idx, 0, date_item)
            self._table.setItem(idx, 1, type_item)
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