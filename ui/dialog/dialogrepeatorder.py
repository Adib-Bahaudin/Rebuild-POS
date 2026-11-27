"""Dialog pemilih nota kulakan lama atau draft untuk dimuat ulang ke keranjang."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.dialog._tambahstok_dialog_style import DIALOG_STYLESHEET
from ui.tambahstok import PurchaseHistoryRow
from util.helper.formatrupiah import format_rupiah


class RepeatOrderDialog(QDialog):
    """Dialog pemilih nota kulakan lama atau draft untuk dimuat ulang ke keranjang."""

    def __init__(
        self,
        history_rows: list[PurchaseHistoryRow],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RepeatOrderDialog.

        Args:
            history_rows: Daftar nota pembelian yang tersedia untuk disalin.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._rows = history_rows
        self._selected_purchase_id: int | None = None

        self.setWindowTitle("Muat Ulang Nota Lama / Draft")
        self.setMinimumSize(700, 420)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Pilih Nota untuk Dimuat ke Keranjang", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Nota COMPLETED akan disalin dengan nomor faktur baru; nota DRAFT dibuka untuk "
            "dilanjutkan.",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget(len(history_rows), 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Tanggal", "No. Faktur", "Supplier", "Total", "Status"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        v_head = self.table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = self.table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for idx, row in enumerate(history_rows):
            date_item = QTableWidgetItem(row["purchase_date"])
            date_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(idx, 0, date_item)
            self.table.setItem(idx, 1, QTableWidgetItem(row["invoice_number"]))
            self.table.setItem(idx, 2, QTableWidgetItem(row["supplier_name"]))
            total_item = QTableWidgetItem(format_rupiah(row["total"]))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(idx, 3, total_item)
            self.table.setItem(idx, 4, QTableWidgetItem(row["status"]))

        self.table.itemDoubleClicked.connect(self._confirm_selection)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        load_btn = QPushButton("Muat ke Keranjang", self)
        load_btn.setObjectName("primaryBtn")
        load_btn.clicked.connect(self._confirm_selection)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

    def _confirm_selection(self) -> None:
        """Menyimpan ID nota yang dipilih baris aktif lalu menutup dialog."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
        first_item = self.table.item(current_row, 0)
        if first_item is None:
            return
        raw_id = first_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(raw_id, int):
            self._selected_purchase_id = raw_id
            self.accept()

    def get_selected_purchase_id(self) -> int | None:
        """Mengembalikan ID nota yang dipilih pengguna.

        Returns:
            ID pembelian atau None jika tidak ada yang dipilih.
        """
        return self._selected_purchase_id
