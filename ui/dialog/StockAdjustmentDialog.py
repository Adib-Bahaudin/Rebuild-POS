"""Modul dialog stok awal dan penyesuaian opname FIFO berbasis CustomDialog.

Modul ini menyediakan antarmuka modal ringkas untuk mencatat penambahan stok
awal (OPENING_STOCK), penyesuaian masuk (ADJUSTMENT_IN), maupun penyesuaian
keluar berbasis FIFO (ADJUSTMENT_OUT) tanpa memuat logika query basis data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import (
    StockAdjustmentPayload,
    format_qty,
)
from util.customdialog import CustomDialog

AdjustmentType = Literal["OPENING_STOCK", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"]


@dataclass(frozen=True)
class StockItemOption:
    """Merepresentasikan satu pilihan barang beserta sisa stok aktifnya.

    Attributes:
        item_id: Primary key barang pada tabel items.
        sku: Kode SKU barang.
        name: Nama barang.
        base_unit_symbol: Simbol satuan dasar barang (misalnya 'Lbr', 'Pcs').
        current_stock: Total sisa stok saat ini dari seluruh layer FIFO aktif.
    """

    item_id: int
    sku: str
    name: str
    base_unit_symbol: str
    current_stock: float


class StockAdjustmentDialog(CustomDialog):
    """Dialog kustom untuk input stok awal dan penyesuaian stok opname FIFO.

    Menampilkan pemilih barang, ringkasan stok saat ini beserta estimasi hasil
    akhir, jenis mutasi stok, kuantitas, harga modal satuan, serta catatan.
    """

    def __init__(
        self,
        item_options: list[StockItemOption],
        preselected_item_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi StockAdjustmentDialog dengan daftar barang aktif.

        Args:
            item_options: Daftar barang yang dapat dipilih untuk disesuaikan stoknya.
            preselected_item_id: ID barang yang otomatis dipilih jika dibuka dari
                panel detail barang, atau None untuk memilih secara bebas.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._item_options: list[StockItemOption] = item_options
        self._option_by_id: dict[int, StockItemOption] = {
            opt.item_id: opt for opt in item_options
        }
        self._preselected_item_id: int | None = preselected_item_id
        self._result_payload: StockAdjustmentPayload | None = None

        self.setWindowTitle("Stok Awal / Penyesuaian Opname")
        self.setMinimumWidth(520)
        self.resize(540, 370)

        self._item_combo = QComboBox(self)
        self._type_combo = QComboBox(self)
        self._qty_spin = QDoubleSpinBox(self)
        self._cost_spin = QDoubleSpinBox(self)
        self._cost_hint_label = QLabel("", self)
        self._notes_input = QLineEdit(self)

        self._current_stock_val = QLabel("0", self)
        self._projected_stock_val = QLabel("0", self)

        self._error_label = QLabel("", self)
        self._cancel_btn = QPushButton("Batal", self)
        self._save_btn = QPushButton("Simpan Penyesuaian", self)

        self._setup_ui()
        self._apply_styles()
        self._populate_controls()
        self._connect_signals()
        self._sync_dynamic_ui()

    def _setup_ui(self) -> None:
        """Menyusun tata letak formulir penyesuaian stok yang padat dan rapi."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_item_and_preview_section())
        root_layout.addWidget(self._build_adjustment_form_section())

        self._error_label.setObjectName("FormErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root_layout.addWidget(self._error_label)

        root_layout.addStretch(1)
        root_layout.addLayout(self._build_footer_actions())
        self.setLayout(root_layout)

    def _build_item_and_preview_section(self) -> QFrame:
        """Membangun kartu pemilih barang dan strip pratinjau perubahan stok.

        Returns:
            Frame berisi dropdown barang serta indikator stok sebelum dan sesudah.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self._item_combo.setObjectName("FormCombo")

        preview_strip = QFrame(card)
        preview_strip.setObjectName("SummaryStrip")
        strip_layout = QHBoxLayout(preview_strip)
        strip_layout.setContentsMargins(8, 6, 8, 6)
        strip_layout.setSpacing(10)

        curr_box = QVBoxLayout()
        curr_box.setContentsMargins(0, 0, 0, 0)
        curr_box.setSpacing(1)
        curr_caption = QLabel("STOK SAAT INI", preview_strip)
        curr_caption.setObjectName("StripCaption")
        self._current_stock_val.setObjectName("StripValue")
        curr_box.addWidget(curr_caption)
        curr_box.addWidget(self._current_stock_val)

        divider = QFrame(preview_strip)
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("VerticalDivider")

        proj_box = QVBoxLayout()
        proj_box.setContentsMargins(0, 0, 0, 0)
        proj_box.setSpacing(1)
        proj_caption = QLabel("ESTIMASI SETELAH PENYESUAIAN", preview_strip)
        proj_caption.setObjectName("StripCaption")
        self._projected_stock_val.setObjectName("StripValueProjected")
        proj_box.addWidget(proj_caption)
        proj_box.addWidget(self._projected_stock_val)

        strip_layout.addLayout(curr_box, 1)
        strip_layout.addWidget(divider)
        strip_layout.addLayout(proj_box, 1)

        layout.addWidget(self._make_field_label("Barang Target *"))
        layout.addWidget(self._item_combo)
        layout.addWidget(preview_strip)
        return card

    def _build_adjustment_form_section(self) -> QFrame:
        """Membangun kartu input jenis mutasi, kuantitas, harga modal, dan catatan.

        Returns:
            Frame berisi kontrol input penyesuaian stok.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self._type_combo.setObjectName("FormCombo")

        self._qty_spin.setObjectName("FormSpin")
        self._qty_spin.setRange(0.001, 1_000_000.0)
        self._qty_spin.setDecimals(3)
        self._qty_spin.setSingleStep(1.0)
        self._qty_spin.setValue(1.0)

        self._cost_spin.setObjectName("FormSpin")
        self._cost_spin.setRange(0.0, 999_999_999.0)
        self._cost_spin.setDecimals(2)
        self._cost_spin.setSingleStep(100.0)
        self._cost_spin.setPrefix("Rp ")
        self._cost_spin.setValue(0.0)

        self._cost_hint_label.setObjectName("FieldHint")
        self._cost_hint_label.setWordWrap(True)

        self._notes_input.setObjectName("FormInput")
        self._notes_input.setPlaceholderText(
            "Contoh: Stok opname akhir bulan / stok awal toko / barang rusak"
        )

        grid.addWidget(self._make_field_label("Jenis Penyesuaian *"), 0, 0, 1, 2)
        grid.addWidget(self._type_combo, 1, 0, 1, 2)

        grid.addWidget(self._make_field_label("Kuantitas (Satuan Dasar) *"), 2, 0)
        grid.addWidget(self._make_field_label("Harga Modal / Satuan Dasar"), 2, 1)
        grid.addWidget(self._qty_spin, 3, 0)
        grid.addWidget(self._cost_spin, 3, 1)

        grid.addWidget(self._cost_hint_label, 4, 0, 1, 2)
        grid.addWidget(self._make_field_label("Catatan / Keterangan"), 5, 0, 1, 2)
        grid.addWidget(self._notes_input, 6, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return card

    def _build_footer_actions(self) -> QHBoxLayout:
        """Membangun baris tombol aksi Batal dan Simpan pada bagian bawah dialog.

        Returns:
            QHBoxLayout berisi tombol aksi sejajar kanan.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)

        self._cancel_btn.setObjectName("CancelBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._save_btn.setObjectName("SaveBtn")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        footer.addStretch(1)
        footer.addWidget(self._cancel_btn)
        footer.addWidget(self._save_btn)
        return footer

    def _make_field_label(self, text: str) -> QLabel:
        """Membuat label teks ringkas untuk judul kolom masukan.

        Args:
            text: Teks judul kolom masukan.

        Returns:
            Widget QLabel bergaya seragam.
        """
        label = QLabel(text, self)
        label.setObjectName("FieldLabel")
        return label

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #181825;
                color: #CDD6F4;
            }
            QFrame#FormSectionCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QFrame#SummaryStrip {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 5px;
            }
            QFrame#VerticalDivider {
                color: #313244;
                background-color: #313244;
                max-width: 1px;
            }
            QLabel#StripCaption {
                color: #6C7086;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.4px;
                background: transparent;
            }
            QLabel#StripValue {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#StripValueProjected {
                color: #4ADE80;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#FieldLabel {
                color: #9399B2;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#FieldHint {
                color: #7F849C;
                font-size: 10px;
                background: transparent;
            }
            QLabel#FormErrorLabel {
                background-color: rgba(239, 68, 68, 0.14);
                color: #FCA5A5;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLineEdit#FormInput,
            QComboBox#FormCombo,
            QDoubleSpinBox#FormSpin {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FormInput:focus,
            QComboBox#FormCombo:focus,
            QDoubleSpinBox#FormSpin:focus {
                border: 1px solid #3B82F6;
            }
            QDoubleSpinBox#FormSpin:disabled {
                color: #585B70;
                background-color: #161622;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QPushButton#CancelBtn {
                background-color: #252638;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CancelBtn:hover {
                background-color: #313244;
            }
            QPushButton#SaveBtn {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#SaveBtn:hover:enabled {
                background-color: #2563EB;
            }
            QPushButton#SaveBtn:pressed {
                background-color: #1D4ED8;
            }
            QPushButton#SaveBtn:disabled {
                background-color: #252638;
                color: #585B70;
            }
            """
        )

    def _populate_controls(self) -> None:
        """Mengisi daftar pilihan barang dan opsi jenis penyesuaian stok."""
        self._item_combo.clear()
        for opt in self._item_options:
            label = f"[{opt.sku}] {opt.name} ({opt.base_unit_symbol})"
            self._item_combo.addItem(label, opt.item_id)

        if self._preselected_item_id is not None:
            found_idx = self._item_combo.findData(self._preselected_item_id)
            if found_idx >= 0:
                self._item_combo.setCurrentIndex(found_idx)

        self._type_combo.clear()
        self._type_combo.addItem(
            "Penyesuaian Masuk (+ Tambah Layer FIFO)",
            "ADJUSTMENT_IN",
        )
        self._type_combo.addItem(
            "Penyesuaian Keluar (- Potong Layer FIFO)",
            "ADJUSTMENT_OUT",
        )
        self._type_combo.addItem(
            "Stok Awal (OPENING_STOCK)",
            "OPENING_STOCK",
        )

        has_items = len(self._item_options) > 0
        self._save_btn.setEnabled(has_items)
        if not has_items:
            self._show_error(
                "Belum ada data barang fisik. Tambahkan barang terlebih dahulu."
            )

    def _connect_signals(self) -> None:
        """Menghubungkan perubahan kontrol input dan tombol aksi dialog."""
        self._item_combo.currentIndexChanged.connect(self._sync_dynamic_ui)
        self._type_combo.currentIndexChanged.connect(self._sync_dynamic_ui)
        self._qty_spin.valueChanged.connect(self._update_stock_preview)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._handle_save_clicked)

    def _get_selected_option(self) -> StockItemOption | None:
        """Mengambil objek StockItemOption yang sedang terpilih di combobox.

        Returns:
            Objek StockItemOption terpilih atau None jika daftar kosong.
        """
        raw_id = self._item_combo.currentData()
        if isinstance(raw_id, int):
            return self._option_by_id.get(raw_id)
        return None

    def _get_selected_adjustment_type(self) -> AdjustmentType:
        """Mengambil nilai Literal jenis penyesuaian stok yang sedang terpilih.

        Returns:
            Salah satu dari 'OPENING_STOCK', 'ADJUSTMENT_IN', atau 'ADJUSTMENT_OUT'.
        """
        raw_type = self._type_combo.currentData()
        if raw_type == "OPENING_STOCK":
            return "OPENING_STOCK"
        if raw_type == "ADJUSTMENT_OUT":
            return "ADJUSTMENT_OUT"
        return "ADJUSTMENT_IN"

    def _sync_dynamic_ui(self) -> None:
        """Menyelaraskan simbol satuan, status input harga modal, dan pratinjau stok."""
        selected = self._get_selected_option()
        if selected is not None:
            symbol = selected.base_unit_symbol.strip()
            self._qty_spin.setSuffix(f" {symbol}" if symbol else "")
        else:
            self._qty_spin.setSuffix("")

        adj_type = self._get_selected_adjustment_type()
        is_stock_out = adj_type == "ADJUSTMENT_OUT"
        self._cost_spin.setEnabled(not is_stock_out)
        if is_stock_out:
            self._cost_hint_label.setText(
                "Harga modal untuk stok keluar dihitung otomatis dari layer FIFO terlama."
            )
        elif adj_type == "OPENING_STOCK":
            self._cost_hint_label.setText(
                "Masukkan harga beli/modal per satuan dasar untuk membentuk layer stok awal."
            )
        else:
            self._cost_hint_label.setText(
                "Masukkan harga modal per satuan dasar untuk batch penyesuaian stok masuk."
            )

        self._update_stock_preview()

    def _update_stock_preview(self) -> None:
        """Memperbarui indikator stok saat ini dan estimasi stok setelah penyesuaian."""
        selected = self._get_selected_option()
        if selected is None:
            self._current_stock_val.setText("-")
            self._projected_stock_val.setText("-")
            return

        symbol = selected.base_unit_symbol
        curr_qty = selected.current_stock
        delta_qty = float(self._qty_spin.value())
        adj_type = self._get_selected_adjustment_type()

        projected_qty = (
            curr_qty - delta_qty if adj_type == "ADJUSTMENT_OUT" else curr_qty + delta_qty
        )

        self._current_stock_val.setText(format_qty(curr_qty, symbol))
        self._projected_stock_val.setText(format_qty(projected_qty, symbol))

        if projected_qty < -1e-9:
            self._projected_stock_val.setStyleSheet(
                "color: #F87171; font-size: 13px; font-weight: 700; "
                "background: transparent;"
            )
        elif adj_type == "ADJUSTMENT_OUT":
            self._projected_stock_val.setStyleSheet(
                "color: #FBBF24; font-size: 13px; font-weight: 700; "
                "background: transparent;"
            )
        else:
            self._projected_stock_val.setStyleSheet(
                "color: #4ADE80; font-size: 13px; font-weight: 700; "
                "background: transparent;"
            )

    def _show_error(self, message: str) -> None:
        """Menampilkan pesan kesalahan validasi secara inline di dalam dialog.

        Args:
            message: Teks pesan kesalahan yang harus diperbaiki pengguna.
        """
        self._error_label.setText(message)
        self._error_label.show()

    def _build_validated_payload(self) -> StockAdjustmentPayload | None:
        """Memvalidasi seluruh isian formulir dan menyusun StockAdjustmentPayload.

        Returns:
            Objek StockAdjustmentPayload valid, atau None jika terdapat kesalahan.
        """
        selected = self._get_selected_option()
        if selected is None:
            self._show_error("Pilih barang target terlebih dahulu.")
            return None

        adj_type = self._get_selected_adjustment_type()
        qty = float(self._qty_spin.value())
        if qty <= 0:
            self._show_error("Kuantitas penyesuaian harus lebih dari 0.")
            self._qty_spin.setFocus()
            return None

        if adj_type == "ADJUSTMENT_OUT" and qty > selected.current_stock + 1e-9:
            self._show_error(
                f"Pengurangan ({format_qty(qty, selected.base_unit_symbol)}) melebihi "
                f"sisa stok tersedia ({format_qty(selected.current_stock, selected.base_unit_symbol)})."
            )
            self._qty_spin.setFocus()
            return None

        unit_cost = (
            0.0 if adj_type == "ADJUSTMENT_OUT" else float(self._cost_spin.value())
        )
        self._error_label.hide()
        return StockAdjustmentPayload(
            item_id=selected.item_id,
            adjustment_type=adj_type,
            quantity=qty,
            unit_cost=unit_cost,
            notes=self._notes_input.text().strip(),
        )

    def _handle_save_clicked(self) -> None:
        """Memvalidasi formulir lalu menutup dialog dengan status diterima."""
        payload = self._build_validated_payload()
        if payload is None:
            return
        self._result_payload = payload
        self.accept()

    def get_payload(self) -> StockAdjustmentPayload | None:
        """Mengembalikan muatan data penyesuaian stok setelah dialog diterima.

        Returns:
            Objek StockAdjustmentPayload jika pengguna menekan Simpan, atau None.
        """
        return self._result_payload

    @classmethod
    def get_adjustment_payload(
        cls,
        parent: QWidget,
        item_options: list[StockItemOption],
        preselected_item_id: int | None = None,
    ) -> StockAdjustmentPayload | None:
        """Membuka dialog secara modal dan mengembalikan StockAdjustmentPayload.

        Args:
            parent: Widget induk dialog.
            item_options: Daftar barang beserta sisa stok FIFO saat ini.
            preselected_item_id: ID barang yang langsung dipilih jika ada.

        Returns:
            StockAdjustmentPayload apabila pengguna menekan Simpan, atau None jika batal.
        """
        dialog = cls(
            item_options=item_options,
            preselected_item_id=preselected_item_id,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_payload()
        return None