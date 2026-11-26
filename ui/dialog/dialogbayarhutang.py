"""Modul dialog antarmuka pengguna untuk pembayaran hutang atau cicilan transaksi."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.riwayat_backend import TransactionFullDetail, format_rupiah
from util.customdialog import CustomDialog

PAYMENT_METHOD_CHOICES: tuple[str, ...] = ("Tunai", "QRIS", "Transfer")

logger = logging.getLogger(__name__)


class DialogBayarHutang(CustomDialog):
    """Dialog modal untuk melihat riwayat cicilan dan mencatat pembayaran hutang."""

    def __init__(
        self,
        detail: TransactionFullDetail,
        parent: QWidget | None = None,
        read_only: bool = False,
    ) -> None:
        """Menginisialisasi dialog pembayaran hutang atau tampilan riwayat pembayaran.

        Args:
            detail: Objek TransactionFullDetail yang memuat rincian transaksi dan pembayaran.
            parent: Widget induk opsional.
            read_only: Jika True, hanya menampilkan ringkasan dan tabel riwayat pembayaran
                tanpa form input pembayaran baru.
        """
        super().__init__(parent=parent)
        self.detail: TransactionFullDetail = detail
        self._read_only: bool = read_only
        self._submitted_nominal: int = 0
        self._submitted_method: str = PAYMENT_METHOD_CHOICES[0]
        self._submitted_notes: str = ""

        if self._read_only:
            self.setWindowTitle(f"Riwayat Pembayaran - {detail.metadata.invoice_number}")
            self.setFixedSize(680, 420)
        else:
            self.setWindowTitle(f"Bayar Hutang - {detail.metadata.invoice_number}")
            self.setFixedSize(680, 600)

        self._setup_ui()
        logger.info(
            "DialogBayarHutang dibuka untuk invoice %s (read_only=%s, sisa=%d, riwayat=%d)",
            detail.metadata.invoice_number,
            self._read_only,
            detail.payment.remaining_amount,
            len(detail.payments),
        )

    @property
    def nominal(self) -> int:
        """Mengembalikan nominal pembayaran yang dikirimkan pengguna."""
        return self._submitted_nominal

    @property
    def payment_method(self) -> str:
        """Mengembalikan metode pembayaran yang dipilih pengguna."""
        return self._submitted_method

    @property
    def notes(self) -> str:
        """Mengembalikan catatan manual pembayaran yang dimasukkan pengguna."""
        return self._submitted_notes

    def _setup_ui(self) -> None:
        """Menyusun komponen antarmuka dialog pembayaran hutang."""
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._build_summary_card())

        history_title = "Riwayat Pembayaran" if self._read_only else "Riwayat Pembayaran Sebelumnya"
        history_label = QLabel(history_title, self)
        history_label.setStyleSheet(
            "color: #CDD6F4; font-size: 13px; font-weight: 600; background: transparent;"
        )
        main_layout.addWidget(history_label)

        self.payments_table = self._build_payments_table()
        main_layout.addWidget(self.payments_table, stretch=1)

        if not self._read_only:
            main_layout.addWidget(self._build_input_card())

            self.feedback_label = QLabel(self)
            self.feedback_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
            main_layout.addWidget(self.feedback_label)
            self._update_preview()

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        cancel_label = "Tutup" if self._read_only else "Batal"
        cancel_btn = QPushButton(cancel_label, self)
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
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
        cancel_btn.clicked.connect(self._on_cancel_clicked)

        self.submit_btn = QPushButton("Simpan Pembayaran", self)
        self.submit_btn.setFixedHeight(36)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #22C55E,
                    stop: 1 #16A34A
                );
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #4ADE80,
                    stop: 1 #22C55E
                );
            }
            QPushButton:pressed {
                background-color: #15803D;
            }
            """
        )
        self.submit_btn.clicked.connect(self._on_submit_clicked)

        footer_layout.addStretch()
        footer_layout.addWidget(cancel_btn)
        if not self._read_only:
            footer_layout.addWidget(self.submit_btn)
        else:
            self.submit_btn.hide()
        main_layout.addLayout(footer_layout)

    def _build_summary_card(self) -> QFrame:
        """Membangun kartu ringkasan tagihan dan sisa hutang faktur."""
        card = QFrame(self)
        card.setObjectName("DebtSummaryCard")
        card.setStyleSheet(
            """
            QFrame#DebtSummaryCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 10px 14px;
            }
            """
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        inv_lbl = QLabel(self.detail.metadata.invoice_number, card)
        inv_lbl.setStyleSheet("color: #60A5FA; font-size: 14px; font-weight: 700;")
        cust_lbl = QLabel(f"Pelanggan: {self.detail.metadata.customer_name}", card)
        cust_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px;")
        left_col.addWidget(inv_lbl)
        left_col.addWidget(cust_lbl)
        layout.addLayout(left_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(3)
        right_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        total_lbl = QLabel(f"Total Tagihan: {format_rupiah(self.detail.amounts.total)}", card)
        total_lbl.setStyleSheet("color: #A6ADC8; font-size: 12px;")
        total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        paid_lbl = QLabel(f"Sudah Dibayar: {format_rupiah(self.detail.payment.amount_paid)}", card)
        paid_lbl.setStyleSheet("color: #4ADE80; font-size: 12px;")
        paid_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        rem_lbl = QLabel(
            f"Sisa Hutang: {format_rupiah(self.detail.payment.remaining_amount)}",
            card,
        )
        rem_lbl.setStyleSheet("color: #F87171; font-size: 13px; font-weight: 700;")
        rem_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_col.addWidget(total_lbl)
        right_col.addWidget(paid_lbl)
        right_col.addWidget(rem_lbl)
        layout.addLayout(right_col, stretch=1)

        return card

    def _build_payments_table(self) -> QTableWidget:
        """Membangun tabel daftar detail pembayaran sebelumnya."""
        table = QTableWidget(self)
        table.setObjectName("PreviousPaymentsTable")
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["No", "Tanggal", "Kasir", "Metode", "Nominal", "Catatan"]
        )
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 38)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 138)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 80)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        table.setStyleSheet(
            """
            QTableWidget#PreviousPaymentsTable {
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

        payments = self.detail.payments
        table.setRowCount(len(payments))

        for idx, pay in enumerate(payments, start=1):
            col_no = QTableWidgetItem(str(idx))
            col_no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_date = QTableWidgetItem(pay.payment_date)
            col_date.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            col_cashier = QTableWidgetItem(pay.cashier_name.strip() or "KASIR")
            col_cashier.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_method = QTableWidgetItem(pay.payment_method)
            col_method.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_amount = QTableWidgetItem(format_rupiah(pay.amount))
            col_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            note_text = pay.notes.strip() or "-"
            col_notes = QTableWidgetItem(note_text)
            col_notes.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            table.setItem(idx - 1, 0, col_no)
            table.setItem(idx - 1, 1, col_date)
            table.setItem(idx - 1, 2, col_cashier)
            table.setItem(idx - 1, 3, col_method)
            table.setItem(idx - 1, 4, col_amount)
            table.setItem(idx - 1, 5, col_notes)
            table.setRowHeight(idx - 1, 30)

        return table

    def _build_input_card(self) -> QFrame:
        """Membangun panel input nominal pembayaran, metode bayar, dan catatan."""
        card = QFrame(self)
        card.setObjectName("DebtInputCard")
        card.setStyleSheet(
            """
            QFrame#DebtInputCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        nominal_col = QVBoxLayout()
        nominal_col.setSpacing(6)
        nominal_lbl = QLabel("Nominal Bayar (Rp)", card)
        nominal_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; font-weight: 600;")

        nominal_row = QHBoxLayout()
        nominal_row.setSpacing(8)

        self.nominal_input = QLineEdit(card)
        self.nominal_input.setObjectName("DebtNominalInput")
        self.nominal_input.setValidator(QIntValidator(1, 1_000_000_000, self))
        self.nominal_input.setPlaceholderText(
            f"Masukkan nominal (sisa {self.detail.payment.remaining_amount})"
        )
        self.nominal_input.setFixedHeight(36)
        self.nominal_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 0px 12px;
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
            """
        )
        self.nominal_input.textChanged.connect(self._update_preview)
        self.nominal_input.returnPressed.connect(self._on_submit_clicked)

        fill_btn = QPushButton("Pas", card)
        fill_btn.setFixedHeight(36)
        fill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fill_btn.setToolTip("Isi sesuai sisa hutang")
        fill_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #313244;
                color: #93C5FD;
                border: 1px solid #45475A;
                border-radius: 6px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
            }
            """
        )
        fill_btn.clicked.connect(self._fill_remaining_amount)

        nominal_row.addWidget(self.nominal_input, stretch=1)
        nominal_row.addWidget(fill_btn)
        nominal_col.addWidget(nominal_lbl)
        nominal_col.addLayout(nominal_row)

        method_col = QVBoxLayout()
        method_col.setSpacing(6)
        method_lbl = QLabel("Metode Bayar", card)
        method_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; font-weight: 600;")

        self.method_combo = QComboBox(card)
        self.method_combo.setObjectName("DebtMethodCombo")
        self.method_combo.addItems(list(PAYMENT_METHOD_CHOICES))
        self.method_combo.setFixedHeight(36)
        self.method_combo.setMinimumWidth(140)
        self.method_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.method_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 0px 12px;
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox:focus {
                border: 1px solid #3B82F6;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #3B82F6;
            }
            """
        )

        method_col.addWidget(method_lbl)
        method_col.addWidget(self.method_combo)

        top_row.addLayout(nominal_col, stretch=2)
        top_row.addLayout(method_col, stretch=1)
        card_layout.addLayout(top_row)

        notes_lbl = QLabel("Catatan Tambahan (Opsional)", card)
        notes_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; font-weight: 600;")

        self.notes_input = QTextEdit(card)
        self.notes_input.setObjectName("DebtNotesInput")
        self.notes_input.setFixedHeight(64)
        self.notes_input.setPlaceholderText(
            "Tambahkan catatan manual (catatan otomatis 'Pembayaran hutang' tetap dipertahankan)..."
        )
        self.notes_input.setStyleSheet(
            """
            QTextEdit {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 6px 10px;
                color: #CDD6F4;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #3B82F6;
            }
            """
        )

        card_layout.addWidget(notes_lbl)
        card_layout.addWidget(self.notes_input)
        return card

    def _fill_remaining_amount(self) -> None:
        """Mengisi input nominal dengan seluruh sisa hutang transaksi."""
        remaining = max(0, self.detail.payment.remaining_amount)
        if remaining > 0:
            self.nominal_input.setText(str(remaining))
            logger.debug(
                "Nominal diisi otomatis sesuai sisa hutang (%d) untuk invoice %s",
                remaining,
                self.detail.metadata.invoice_number,
            )

    def _parse_nominal(self) -> int:
        """Mengurai angka nominal dari QLineEdit secara aman."""
        raw = self.nominal_input.text().strip()
        if not raw:
            return 0
        try:
            return max(0, int(raw))
        except ValueError:
            return 0

    def _update_preview(self) -> None:
        """Memperbarui pratinjau sisa hutang atau kembalian secara langsung."""
        amount = self._parse_nominal()
        remaining = max(0, self.detail.payment.remaining_amount)
        if amount <= 0:
            self.feedback_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
            self.feedback_label.setText(
                f"Sisa tagihan saat ini: {format_rupiah(remaining)}"
            )
            return

        if amount >= remaining:
            change = amount - remaining
            self.feedback_label.setStyleSheet("color: #4ADE80; font-size: 12px; font-weight: 600;")
            self.feedback_label.setText(
                f"Status setelah bayar: LUNAS (Kembalian: {format_rupiah(change)})"
            )
        else:
            left = remaining - amount
            self.feedback_label.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: 600;")
            self.feedback_label.setText(
                f"Status setelah bayar: CICILAN (Sisa hutang: {format_rupiah(left)})"
            )

    def _on_cancel_clicked(self) -> None:
        """Mencatat pembatalan dialog pembayaran hutang lalu menutup dialog."""
        logger.debug(
            "Pembayaran hutang dibatalkan oleh pengguna untuk invoice %s",
            self.detail.metadata.invoice_number,
        )
        self.reject()

    def _on_submit_clicked(self) -> None:
        """Memvalidasi input dan menerima dialog jika nominal valid."""
        amount = self._parse_nominal()
        if amount <= 0:
            logger.warning(
                "Submit pembayaran hutang ditolak untuk invoice %s: nominal tidak valid (%r)",
                self.detail.metadata.invoice_number,
                self.nominal_input.text(),
            )
            self.feedback_label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: 600;")
            self.feedback_label.setText("Masukkan nominal pembayaran lebih dari Rp 0.")
            self.nominal_input.setFocus()
            return

        self._submitted_nominal = amount
        self._submitted_method = self.method_combo.currentText().strip() or "Tunai"
        self._submitted_notes = self.notes_input.toPlainText().strip()
        logger.info(
            "Pembayaran hutang disubmit dari dialog untuk invoice %s: nominal=%d, metode=%s, catatan=%r",
            self.detail.metadata.invoice_number,
            self._submitted_nominal,
            self._submitted_method,
            self._submitted_notes,
        )
        self.accept()
