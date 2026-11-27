"""Dialog pemilihan banyak barang sekaligus untuk halaman Tambah Stok."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
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

from ui.dialog._tambahstok_dialog_style import DIALOG_STYLESHEET
from ui.tambahstok import CatalogItemData
from util.helper.formatrupiah import format_qty as format_quantity

if TYPE_CHECKING:
    from core.tambah_stok_backend import BulkCatalogItemView


class BulkItemPickerDialog(QDialog):
    """Dialog pemilihan banyak barang sekaligus dengan filter kategori dan stok menipis."""

    def __init__(
        self,
        items: list[BulkCatalogItemView],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi BulkItemPickerDialog.

        Args:
            items: Daftar barang katalog lengkap beserta nama kategorinya.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._all_items = items
        self._filtered_items: list[BulkCatalogItemView] = list(items)
        self._selected_ids: set[int] = set()

        self.setWindowTitle("Pilih Banyak Barang Sekaligus")
        self.setMinimumSize(760, 500)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Pilih Banyak Barang (Bulk Picker)", self)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Cari SKU atau nama barang...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.category_combo = QComboBox(self)
        self.category_combo.addItem("Semua Kategori", "")
        categories = sorted({entry["category_name"] for entry in items})
        for cat in categories:
            self.category_combo.addItem(cat, cat)
        self.category_combo.currentIndexChanged.connect(self._apply_filter)

        self.low_stock_check = QCheckBox("Hanya Stok <= 10", self)
        self.low_stock_check.toggled.connect(self._apply_filter)

        select_visible_btn = QPushButton("Centang Semua Tampil", self)
        select_visible_btn.setObjectName("secondaryBtn")
        select_visible_btn.clicked.connect(self._select_all_visible)

        filter_row.addWidget(self.search_input, 1)
        filter_row.addWidget(self.category_combo)
        filter_row.addWidget(self.low_stock_check)
        filter_row.addWidget(select_visible_btn)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Pilih", "SKU", "Nama Barang", "Kategori", "Sisa Stok"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v_head = self.table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = self.table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 56)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 120)
        self.table.itemChanged.connect(self._handle_item_checked)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.count_label = QLabel("0 barang dipilih", self)
        self.count_label.setObjectName("dialogSubtitle")
        btn_row.addWidget(self.count_label)
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Tambahkan ke Keranjang", self)
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

        self._render_table()

    def _apply_filter(self) -> None:
        """Menyaring daftar barang sesuai teks pencarian, kategori, dan batas stok."""
        query = self.search_input.text().strip().lower()
        selected_category = str(self.category_combo.currentData() or "")
        only_low = self.low_stock_check.isChecked()

        filtered: list[BulkCatalogItemView] = []
        for entry in self._all_items:
            item = entry["catalog_item"]
            if selected_category and entry["category_name"] != selected_category:
                continue
            if only_low and item["current_stock"] > 10.0:
                continue
            if query and (
                query not in item["sku"].lower() and query not in item["name"].lower()
            ):
                continue
            filtered.append(entry)

        self._filtered_items = filtered
        self._render_table()

    def _render_table(self) -> None:
        """Merender ulang isi tabel dialog tanpa memicu sinyal itemChanged palsu."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._filtered_items))
        for row_idx, entry in enumerate(self._filtered_items):
            item = entry["catalog_item"]
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setData(Qt.ItemDataRole.UserRole, item["item_id"])
            is_checked = item["item_id"] in self._selected_ids
            check_item.setCheckState(
                Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
            )
            self.table.setItem(row_idx, 0, check_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(item["sku"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item["name"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(entry["category_name"]))

            stock_item = QTableWidgetItem(
                f"{format_quantity(item['current_stock'])} {item['base_unit_symbol']}"
            )
            stock_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row_idx, 4, stock_item)
        self.table.blockSignals(False)
        self._update_selected_count()

    def _handle_item_checked(self, item: QTableWidgetItem) -> None:
        """Memperbarui himpunan ID barang terpilih saat checkbox berubah.

        Args:
            item: Objek sel tabel yang status centangnya berubah.
        """
        if item.column() != 0:
            return
        raw_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(raw_id, int):
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(raw_id)
        else:
            self._selected_ids.discard(raw_id)
        self._update_selected_count()

    def _select_all_visible(self) -> None:
        """Mencentang seluruh barang yang sedang tampil setelah filter."""
        for entry in self._filtered_items:
            self._selected_ids.add(entry["catalog_item"]["item_id"])
        self._render_table()

    def _update_selected_count(self) -> None:
        """Memperbarui teks jumlah barang terpilih pada footer dialog."""
        self.count_label.setText(f"{len(self._selected_ids)} barang dipilih")

    def get_selected_items(self) -> list[CatalogItemData]:
        """Mengembalikan daftar CatalogItemData yang dicentang pengguna.

        Returns:
            Daftar CatalogItemData siap ditambahkan ke keranjang belanja.
        """
        return [
            entry["catalog_item"]
            for entry in self._all_items
            if entry["catalog_item"]["item_id"] in self._selected_ids
        ]
