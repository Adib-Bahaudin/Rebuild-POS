"""Dialog tampilan rincian item pembelian dan riwayat pembayaran cicilan nota."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
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
from util.helper.formatrupiah import format_qty as format_quantity, format_rupiah

if TYPE_CHECKING:
    from core.tambah_stok_backend import PurchaseDetailBundle


class PurchaseDetailDialog(QDialog):
    """Dialog tampilan rincian item pembelian dan riwayat pembayaran cicilan nota.

    Attributes:
        pay_requested: Menandakan pengguna menekan tombol lanjut ke pelunasan hutang.
    """

    def __init__(
        self,
        bundle: PurchaseDetailBundle,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi PurchaseDetailDialog.

        Args:
            bundle: Paket lengkap nota pembelian dari TambahStokService.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.pay_requested: bool = False
        self.setWindowTitle(f"Detail Nota Kulakan - {bundle['invoice_number']}")
        self.setMinimumSize(780, 520)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_card = QFrame(self)
        header_card.setObjectName("dialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(4)

        title = QLabel(
            f"Nota {bundle['invoice_number']}  ({bundle['status']} - {bundle['payment_status']})",
            header_card,
        )
        title.setObjectName("dialogTitle")

        due_info = bundle["due_date"] if bundle["due_date"] else "-"
        meta = QLabel(
            f"Supplier: {bundle['supplier_name']}  •  Tanggal: {bundle['purchase_date']}  •  "
            f"Jatuh Tempo: {due_info}",
            header_card,
        )
        meta.setObjectName("dialogSubtitle")

        totals = QLabel(
            f"Subtotal: {format_rupiah(bundle['subtotal'])}  •  "
            f"Diskon: {format_rupiah(bundle['discount'])}  •  "
            f"Total: {format_rupiah(bundle['total'])}  •  "
            f"Dibayar: {format_rupiah(bundle['amount_paid'])}  •  "
            f"Sisa Hutang: {format_rupiah(bundle['remaining_amount'])}",
            header_card,
        )
        totals.setObjectName("fieldLabel")
        totals.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(meta)
        header_layout.addWidget(totals)
        if bundle["notes"]:
            note_lbl = QLabel(f"Catatan: {bundle['notes']}", header_card)
            note_lbl.setObjectName("dialogSubtitle")
            header_layout.addWidget(note_lbl)
        layout.addWidget(header_card)

        items_label = QLabel("Rincian Barang Masuk (FIFO)", self)
        items_label.setObjectName("fieldLabel")
        layout.addWidget(items_label)

        lines_table = QTableWidget(len(bundle["lines"]), 6, self)
        lines_table.setHorizontalHeaderLabels(
            ["SKU", "Barang", "Satuan", "Qty Beli", "Stok Masuk", "Subtotal"]
        )
        lines_table.setAlternatingRowColors(True)
        lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v_head = lines_table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = lines_table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for row_idx, line in enumerate(bundle["lines"]):
            lines_table.setItem(row_idx, 0, QTableWidgetItem(line["sku"]))
            lines_table.setItem(row_idx, 1, QTableWidgetItem(line["item_name"]))
            lines_table.setItem(row_idx, 2, QTableWidgetItem(line["variant_name"]))
            qty_item = QTableWidgetItem(format_quantity(line["quantity"]))
            qty_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            base_item = QTableWidgetItem(
                f"{format_quantity(line['base_quantity'])} {line['base_unit_symbol']}"
            )
            base_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            sub_item = QTableWidgetItem(format_rupiah(line["subtotal"]))
            sub_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lines_table.setItem(row_idx, 3, qty_item)
            lines_table.setItem(row_idx, 4, base_item)
            lines_table.setItem(row_idx, 5, sub_item)
        layout.addWidget(lines_table, 3)

        pay_label = QLabel("Riwayat Pembayaran & Cicilan", self)
        pay_label.setObjectName("fieldLabel")
        layout.addWidget(pay_label)

        pay_table = QTableWidget(len(bundle["payments"]), 5, self)
        pay_table.setHorizontalHeaderLabels(
            ["Tanggal Bayar", "Metode", "Nominal", "No. Referensi", "Catatan"]
        )
        pay_table.setAlternatingRowColors(True)
        pay_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pay_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        pv_head = pay_table.verticalHeader()
        if pv_head is not None:
            pv_head.setVisible(False)
        ph_head = pay_table.horizontalHeader()
        if ph_head is not None:
            ph_head.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for row_idx, payment in enumerate(bundle["payments"]):
            pay_table.setItem(row_idx, 0, QTableWidgetItem(payment["payment_date"]))
            pay_table.setItem(row_idx, 1, QTableWidgetItem(payment["payment_method"]))
            amt_item = QTableWidgetItem(format_rupiah(payment["amount"]))
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            pay_table.setItem(row_idx, 2, amt_item)
            pay_table.setItem(
                row_idx, 3, QTableWidgetItem(payment["reference_number"] or "-")
            )
            pay_table.setItem(row_idx, 4, QTableWidgetItem(payment["notes"] or "-"))
        layout.addWidget(pay_table, 2)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        can_pay = (
            bundle["status"] == "COMPLETED"
            and bundle["payment_status"] != "PAID"
            and bundle["remaining_amount"] > 0
        )
        if can_pay:
            pay_btn = QPushButton("Bayar Cicilan / Pelunasan", self)
            pay_btn.setObjectName("primaryBtn")
            pay_btn.clicked.connect(self._request_payment)
            btn_row.addWidget(pay_btn)

        close_btn = QPushButton("Tutup", self)
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _request_payment(self) -> None:
        """Menandai permintaan pelunasan hutang dan menutup dialog detail."""
        self.pay_requested = True
        self.accept()
