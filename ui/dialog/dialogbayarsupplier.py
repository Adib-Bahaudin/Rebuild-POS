"""Dialog pencatatan cicilan atau pelunasan hutang nota pembelian supplier."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.dialog._tambahstok_dialog_style import DIALOG_STYLESHEET
from ui.tambahstok import CurrencySpinBox, TambahStokPage
from util.helper.formatrupiah import format_rupiah

if TYPE_CHECKING:
    from core.tambah_stok_backend import PurchaseDetailBundle


class PurchasePaymentDialog(QDialog):
    """Dialog pencatatan cicilan atau pelunasan hutang nota pembelian supplier."""

    def __init__(
        self,
        bundle: PurchaseDetailBundle,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi PurchasePaymentDialog dengan ringkasan hutang nota.

        Args:
            bundle: Paket detail nota pembelian yang akan dibayarkan.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._remaining = bundle["remaining_amount"]
        self.setWindowTitle(f"Pelunasan Hutang - {bundle['invoice_number']}")
        self.setMinimumWidth(460)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"Bayar Cicilan / Pelunasan ({bundle['invoice_number']})", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            f"Supplier: {bundle['supplier_name']}  •  "
            f"Total: {format_rupiah(bundle['total'])}  •  "
            f"Sisa Hutang: {format_rupiah(self._remaining)}",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        amount_row = QHBoxLayout()
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.setSpacing(6)

        self.amount_spin = CurrencySpinBox(maximum=max(1, self._remaining), parent=card)
        self.amount_spin.setValue(self._remaining)
        self.amount_spin.setFixedHeight(32)

        full_btn = QPushButton("Lunasi Semua", card)
        full_btn.setObjectName("accentBtn")
        full_btn.setFixedHeight(32)
        full_btn.clicked.connect(self._set_full_remaining)

        amount_row.addWidget(self.amount_spin, 1)
        amount_row.addWidget(full_btn)

        self.method_combo = QComboBox(card)
        self.method_combo.addItems(list(TambahStokPage.PAYMENT_METHODS))
        self.method_combo.setFixedHeight(32)

        self.date_edit = QDateTimeEdit(QDateTime.currentDateTime(), card)
        self.date_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedHeight(32)

        self.reference_input = QLineEdit(card)
        self.reference_input.setPlaceholderText("No. resi / bukti transfer (opsional)")

        self.notes_input = QLineEdit(card)
        self.notes_input.setPlaceholderText("Catatan pembayaran cicilan (opsional)")

        form.addRow("Nominal Bayar *", amount_row)
        form.addRow("Metode Bayar", self.method_combo)
        form.addRow("Tanggal Bayar", self.date_edit)
        form.addRow("No. Referensi", self.reference_input)
        form.addRow("Catatan", self.notes_input)
        layout.addWidget(card)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        submit_btn = QPushButton("Simpan Pembayaran", self)
        submit_btn.setObjectName("primaryBtn")
        submit_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(submit_btn)
        layout.addLayout(btn_row)

    def _set_full_remaining(self) -> None:
        """Mengisi nominal pembayaran penuh sesuai sisa hutang nota."""
        self.amount_spin.setValue(self._remaining)

    def _validate_and_accept(self) -> None:
        """Memastikan nominal pembayaran valid sebelum menyimpan."""
        amount = self.amount_spin.value()
        if amount <= 0:
            self.error_label.setText("Nominal pembayaran harus lebih besar dari Rp 0.")
            self.error_label.setVisible(True)
            return
        if amount > self._remaining:
            self.error_label.setText(
                "Nominal pembayaran tidak boleh melebihi sisa hutang."
            )
            self.error_label.setVisible(True)
            return
        self.accept()

    def get_payment_data(self) -> tuple[int, str, str, str | None, str]:
        """Mengembalikan parameter pembayaran yang diisi pengguna.

        Returns:
            Tuple (amount, payment_method, payment_date, reference_number, notes).
        """
        ref = self.reference_input.text().strip()
        return (
            self.amount_spin.value(),
            self.method_combo.currentText(),
            self.date_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            ref if ref else None,
            self.notes_input.text().strip(),
        )
