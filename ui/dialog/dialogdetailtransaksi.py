"""Modul dialog antarmuka pengguna untuk menampilkan detail lengkap transaksi POS.

Modul ini menyediakan kelas TransactionDetailDialog sebagai dialog modal untuk
menampilkan metadata faktur, daftar barang dan jasa, rincian nominal, status
pelunasan, serta tombol cetak struk.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from core.riwayat_backend import TransactionFullDetail, format_rupiah
from ui.dialog.dialogbayarhutang import DialogBayarHutang
from util.customdialog import CustomDialog


class TransactionDetailDialog(CustomDialog):
    """Dialog modal elegan untuk menampilkan rincian lengkap satu faktur transaksi."""

    print_requested = Signal(object)
    debt_payment_submitted = Signal(str, int, str, str)

    def __init__(
        self,
        detail: TransactionFullDetail,
        parent: QWidget | None = None,
        payment_handler: Callable[[str, int, str, str], TransactionFullDetail | None] | None = None,
    ) -> None:
        """Menginisialisasi dialog detail transaksi.

        Args:
            detail: Objek TransactionFullDetail yang memuat rincian transaksi lengkap.
            parent: Widget induk opsional.
            payment_handler: Callback opsional untuk memproses pembayaran hutang
                dan mengembalikan TransactionFullDetail terbaru.
        """
        super().__init__(parent=parent)
        self.detail: TransactionFullDetail = detail
        self._payment_handler = payment_handler

        self.setWindowTitle(f"Detail Transaksi - {detail.metadata.invoice_number}")
        self.setFixedSize(680, 640)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Menyusun antarmuka dan komponen tata letak dialog detail."""
        self._main_layout = QVBoxLayout(self.content_widget)
        self._main_layout.setContentsMargins(20, 16, 20, 20)
        self._main_layout.setSpacing(14)

        self._header_card = self._build_header_card()
        self._main_layout.addWidget(self._header_card)

        self._items_table = self._build_items_table()
        self._main_layout.addWidget(self._items_table, stretch=1)

        self._totals_card = self._build_totals_card()
        self._main_layout.addWidget(self._totals_card)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        self.pay_debt_btn = QPushButton("Bayar Hutang", self)
        self.pay_debt_btn.setObjectName("PayDebtButton")
        self.pay_debt_btn.setFixedHeight(36)
        self.pay_debt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pay_debt_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #F59E0B,
                    stop: 1 #D97706
                );
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #FBBF24,
                    stop: 1 #F59E0B
                );
            }
            QPushButton:pressed {
                background-color: #B45309;
            }
            """
        )
        self.pay_debt_btn.clicked.connect(self._on_pay_debt_clicked)
        self.pay_debt_btn.setVisible(self._is_unpaid())

        self.view_payments_btn = QPushButton("Lihat Pembayaran", self)
        self.view_payments_btn.setObjectName("ViewPaymentsButton")
        self.view_payments_btn.setFixedHeight(36)
        self.view_payments_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_payments_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #10B981,
                    stop: 1 #059669
                );
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #34D399,
                    stop: 1 #10B981
                );
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            """
        )
        self.view_payments_btn.clicked.connect(self._on_view_payments_clicked)
        self.view_payments_btn.setVisible(self._can_view_payments())

        print_btn = QPushButton("Cetak Struk", self)
        print_btn.setFixedHeight(36)
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3B82F6,
                    stop: 1 #2563EB
                );
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #60A5FA,
                    stop: 1 #3B82F6
                );
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            """
        )
        print_btn.clicked.connect(self._on_print_clicked)

        close_btn = QPushButton("Tutup", self)
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 6px;
                padding: 0px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
                border-color: #585B70;
            }
            QPushButton:pressed {
                background-color: #1E1E2E;
            }
            """
        )
        close_btn.clicked.connect(self.accept)

        footer_layout.addWidget(self.pay_debt_btn)
        footer_layout.addWidget(self.view_payments_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(print_btn)
        footer_layout.addWidget(close_btn)
        self._main_layout.addLayout(footer_layout)

    def _build_header_card(self) -> QFrame:
        """Membangun kartu informasi metadata faktur."""
        card = QFrame(self)
        card.setObjectName("DetailHeaderCard")
        card.setStyleSheet(
            """
            QFrame#DetailHeaderCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(5)

        invoice_label = QLabel(self.detail.metadata.invoice_number, card)
        invoice_label.setStyleSheet("color: #60A5FA; font-size: 16px; font-weight: 700; background: transparent;")

        date_label = QLabel(f"Waktu: {self.detail.metadata.sale_date}", card)
        date_label.setStyleSheet("color: #A6ADC8; font-size: 12px; background: transparent;")

        left_col.addWidget(invoice_label)
        left_col.addWidget(date_label)
        layout.addLayout(left_col, stretch=2)

        mid_col = QVBoxLayout()
        mid_col.setSpacing(5)

        cashier_label = QLabel(f"Kasir: {self.detail.metadata.cashier_name}", card)
        cashier_label.setStyleSheet("color: #CDD6F4; font-size: 12px; background: transparent;")

        customer_label = QLabel(f"Pelanggan: {self.detail.metadata.customer_name}", card)
        customer_label.setStyleSheet("color: #CDD6F4; font-size: 12px; background: transparent;")

        mid_col.addWidget(cashier_label)
        mid_col.addWidget(customer_label)
        layout.addLayout(mid_col, stretch=2)

        right_col = QVBoxLayout()
        right_col.setSpacing(5)
        right_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        status_text = self.detail.payment.payment_status.upper()
        if status_text == "PAID":
            badge_text = "LUNAS"
            badge_style = "background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid #16A34A;"
        else:
            badge_text = "BELUM LUNAS"
            badge_style = "background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid #DC2626;"

        badge = QLabel(f" {badge_text} ", card)
        badge.setStyleSheet(
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; {badge_style}"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        method_label = QLabel(f"Metode: {self.detail.payment.payment_method}", card)
        method_label.setStyleSheet("color: #BAC2DE; font-size: 12px; font-weight: 600; background: transparent; border: 1px solid #BAC2DE;")
        method_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        method_label.setFixedWidth(120)

        right_col.addWidget(badge)
        right_col.addWidget(method_label)
        layout.addLayout(right_col, stretch=1)

        return card

    def _build_items_table(self) -> QTableWidget:
        """Membangun tabel daftar barang dan jasa pada faktur."""
        table = QTableWidget(self)
        table.setObjectName("DetailItemsTable")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["No", "Barang / Jasa", "Qty", "Harga", "Subtotal"])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 60)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 120)

        table.setStyleSheet(
            """
            QTableWidget#DetailItemsTable {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
                color: #CDD6F4;
            }
            QHeaderView::section {
                background-color: #1E1E2E;
                color: #A6ADC8;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 6px 8px;
            }
            """
        )

        items = self.detail.items
        table.setRowCount(len(items))

        for idx, it in enumerate(items, start=1):
            qty_str = (
                f"{int(it.quantity)}"
                if it.quantity.is_integer()
                else f"{it.quantity:.2f}"
            )
            col_no = QTableWidgetItem(str(idx))
            col_no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_desc = QTableWidgetItem(it.description)
            col_desc.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            col_qty = QTableWidgetItem(qty_str)
            col_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_price = QTableWidgetItem(format_rupiah(it.unit_price))
            col_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            col_sub = QTableWidgetItem(format_rupiah(it.subtotal))
            col_sub.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            table.setItem(idx - 1, 0, col_no)
            table.setItem(idx - 1, 1, col_desc)
            table.setItem(idx - 1, 2, col_qty)
            table.setItem(idx - 1, 3, col_price)
            table.setItem(idx - 1, 4, col_sub)
            table.setRowHeight(idx - 1, 32)

        return table

    def _build_totals_card(self) -> QFrame:
        """Membangun kartu ringkasan nominal subtotal, diskon, pembulatan, dan total."""
        card = QFrame(self)
        card.setObjectName("DetailTotalsCard")
        card.setStyleSheet(
            """
            QFrame#DetailTotalsCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 5px 7px;
            }
            """
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 5, 14, 5)
        layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)

        paid_str = format_rupiah(self.detail.payment.amount_paid)
        change_str = format_rupiah(self.detail.payment.change_amount)

        left_layout.addStretch()

        bayar_label = QLabel(f"Jumlah Diterima: {paid_str}", card)
        bayar_label.setStyleSheet("color: #A6ADC8; font-size: 12px; background: transparent;")

        kembalian_label = QLabel(f"Kembalian: {change_str}", card)
        kembalian_label.setStyleSheet("color: #A6ADC8; font-size: 12px; background: transparent;")

        left_layout.addWidget(bayar_label)
        left_layout.addWidget(kembalian_label)

        if self.detail.payment.payment_status.strip().upper() != "PAID":
            remaining_str = format_rupiah(self.detail.payment.remaining_amount)
            unpaid_label = QLabel(f"Belum Terbayarkan: {remaining_str}", card)
            unpaid_label.setObjectName("DetailUnpaidLabel")
            unpaid_label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: 600; background: transparent;")
            left_layout.addWidget(unpaid_label)

        if self.detail.metadata.notes:
            notes_label = QLabel(f"Catatan: {self.detail.metadata.notes}", card)
            notes_label.setStyleSheet("color: #9399B2; font-size: 11px; font-style: italic;")
            left_layout.addWidget(notes_label)

        layout.addLayout(left_layout, stretch=1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.addStretch()

        subtotal_str = format_rupiah(self.detail.amounts.subtotal)
        discount_str = format_rupiah(self.detail.amounts.discount)
        tip_str = format_rupiah(self.detail.amounts.tip)
        rounding_str = format_rupiah(self.detail.amounts.rounding, show_sign=True)
        total_str = format_rupiah(self.detail.amounts.total)

        sub_label = QLabel(f"Subtotal: {subtotal_str}", card)
        sub_label.setStyleSheet("color: #CDD6F4; font-size: 12px; background: transparent;")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.addWidget(sub_label)

        if self.detail.amounts.discount > 0:
            disc_label = QLabel(f"Diskon: -{discount_str}", card)
            disc_label.setStyleSheet("color: #F87171; font-size: 12px; background: transparent;")
            disc_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(disc_label)

        if self.detail.amounts.tip > 0:
            tip_label = QLabel(f"Tip: +{tip_str}", card)
            tip_label.setStyleSheet("color: #A6ADC8; font-size: 12px; background: transparent;")
            tip_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(tip_label)

        if self.detail.amounts.rounding != 0:
            round_label = QLabel(f"Pembulatan: {rounding_str}", card)
            round_label.setStyleSheet("color: #A6ADC8; font-size: 12px; background: transparent;")
            round_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(round_label)

        total_label = QLabel(f"TOTAL: {total_str}", card)
        total_label.setStyleSheet("color: #4ADE80; font-size: 16px; font-weight: 700; background: transparent;")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_layout.addWidget(total_label)

        layout.addLayout(right_layout, stretch=1)
        return card

    def _is_unpaid(self) -> bool:
        """Memeriksa apakah status pembayaran transaksi belum berstatus PAID."""
        return self.detail.payment.payment_status.strip().upper() != "PAID"

    def _can_view_payments(self) -> bool:
        """Memeriksa apakah transaksi Hutang/Cicilan sudah berstatus PAID."""
        is_paid = not self._is_unpaid()
        is_debt_method = (
            self.detail.payment.payment_method.strip().lower() in ("hutang", "cicilan")
        )
        return is_paid and is_debt_method

    def update_detail(self, detail: TransactionFullDetail) -> None:
        """Memperbarui tampilan dialog dengan data transaksi terbaru."""
        self.detail = detail

        new_header = self._build_header_card()
        self._main_layout.replaceWidget(self._header_card, new_header)
        self._header_card.deleteLater()
        self._header_card = new_header

        new_totals = self._build_totals_card()
        self._main_layout.replaceWidget(self._totals_card, new_totals)
        self._totals_card.deleteLater()
        self._totals_card = new_totals

        self.pay_debt_btn.setVisible(self._is_unpaid())
        self.view_payments_btn.setVisible(self._can_view_payments())

    def _on_view_payments_clicked(self) -> None:
        """Membuka dialog riwayat pembayaran dalam mode baca-saja."""
        dialog = DialogBayarHutang(detail=self.detail, parent=self, read_only=True)
        dialog.exec()

    def _on_pay_debt_clicked(self) -> None:
        """Membuka dialog pembayaran hutang dan memproses pembayaran jika disetujui."""
        dialog = DialogBayarHutang(detail=self.detail, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        amount = dialog.nominal
        method = dialog.payment_method
        notes = dialog.notes
        if self._payment_handler is not None:
            updated = self._payment_handler(
                self.detail.metadata.invoice_number,
                amount,
                method,
                notes,
            )
            if updated is not None:
                self.update_detail(updated)

        self.debt_payment_submitted.emit(
            self.detail.metadata.invoice_number,
            amount,
            method,
            notes,
        )

    def _on_print_clicked(self) -> None:
        """Memancarkan sinyal print_requested dan menutup dialog."""
        self.print_requested.emit(self.detail)
        self.accept()
