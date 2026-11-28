"""Dialog pencatatan pembayaran piutang pelanggan atau utang supplier."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.relasi_backend import PaymentInputDTO, RelationInvoiceDTO, RelationProfileDTO
from util.customdialog import CustomDialog, DialogTitleBarConfig
from util.helper.formatrupiah import format_rupiah
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

RelationType = Literal["customer", "supplier"]

_TITLEBAR_CONFIG = DialogTitleBarConfig(
    titlebar_color="#181825",
    title_text_color="#CDD6F4",
    border_color="#313244",
    background_color="#1E1E2E",
)

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)
_ICON_WALLET = (
    '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3'
    'a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
    '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'
)
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
_ICON_CLOSE = '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>'

_DIALOG_QSS = """
QWidget#CustomDialogContent {
    background-color: transparent;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#headerCard, QFrame#formCard {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 12px;
}
QLabel#headerTitle {
    color: #CDD6F4;
    font-size: 16px;
    font-weight: 700;
    background: transparent;
}
QLabel#headerSubtitle {
    color: #A6ADC8;
    font-size: 12px;
    background: transparent;
}
QLabel#fieldLabel {
    color: #CDD6F4;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#metaHint {
    color: #A6ADC8;
    font-size: 11px;
    background: transparent;
}
QComboBox#fieldCombo, QLineEdit#fieldInput, QSpinBox#fieldSpin {
    background-color: #11111B;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 13px;
}
QComboBox#fieldCombo:focus, QLineEdit#fieldInput:focus, QSpinBox#fieldSpin:focus {
    border: 1px solid #A6E3A1;
}
QComboBox#fieldCombo QAbstractItemView {
    background-color: #11111B;
    color: #CDD6F4;
    border: 1px solid #45475A;
    selection-background-color: #313244;
}
QLabel#errorLabel {
    color: #F38BA8;
    background-color: rgba(243, 139, 168, 0.12);
    border: 1px solid rgba(243, 139, 168, 0.4);
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#fullBtn {
    background-color: rgba(166, 227, 161, 0.14);
    color: #A6E3A1;
    border: 1px solid rgba(166, 227, 161, 0.45);
    border-radius: 8px;
    padding: 0px 12px;
    min-height: 34px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#fullBtn:hover {
    background-color: rgba(166, 227, 161, 0.25);
}
QPushButton#secondaryBtn {
    background-color: transparent;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 8px;
    padding: 0px 16px;
    min-height: 36px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#secondaryBtn:hover {
    background-color: #313244;
}
QPushButton#primaryBtn {
    background-color: #A6E3A1;
    color: #11111B;
    border: none;
    border-radius: 8px;
    padding: 0px 18px;
    min-height: 36px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#primaryBtn:hover {
    background-color: #BDF0B8;
}
"""


class RelationPaymentDialog(CustomDialog):
    """Dialog pencatatan pembayaran cicilan atau pelunasan nota relasi."""

    def __init__(
        self,
        relation_type: RelationType,
        profile: RelationProfileDTO,
        unpaid_invoices: list[RelationInvoiceDTO],
        cashier_name: str = "KASIR",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationPaymentDialog.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            profile: Profil relasi pembayar atau penerima pembayaran.
            unpaid_invoices: Daftar nota belum lunas milik relasi.
            cashier_name: Nama kasir aktif untuk transaksi pelanggan.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self._relation_type = relation_type
        self._invoices = unpaid_invoices
        self._cashier_name = cashier_name.strip() or "KASIR"
        is_customer = relation_type == "customer"

        title = "Terima Pembayaran Piutang" if is_customer else "Bayar Utang Supplier"
        self.setWindowTitle(f"{title} - {profile.name}")
        self.setMinimumWidth(480)
        self.content_widget.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.setLayout(layout)

        header = QFrame(self.content_widget)
        header.setObjectName("headerCard")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(12, 10, 12, 10)
        header_row.setSpacing(12)

        icon_lbl = QLabel(header)
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "background-color: rgba(166, 227, 161, 0.16);"
            "border: 1px solid rgba(166, 227, 161, 0.35);"
            "border-radius: 10px;"
        )
        icon_lbl.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color="#A6E3A1", stroke=2.0, body=_ICON_WALLET),
                size=20,
                dpr=3.0,
            )
        )

        total_remaining = sum(inv.remaining_amount for inv in unpaid_invoices)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel(f"{title}: {profile.name}", header)
        title_lbl.setObjectName("headerTitle")
        sub_lbl = QLabel(
            f"{len(unpaid_invoices)} nota belum lunas  •  Total sisa {format_rupiah(total_remaining)}",
            header,
        )
        sub_lbl.setObjectName("headerSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        header_row.addWidget(icon_lbl)
        header_row.addLayout(title_col, 1)
        layout.addWidget(header)

        card = QFrame(self.content_widget)
        card.setObjectName("formCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(10)

        inv_lbl = QLabel("Pilih Nota Belum Lunas", card)
        inv_lbl.setObjectName("fieldLabel")
        self.invoice_combo = QComboBox(card)
        self.invoice_combo.setObjectName("fieldCombo")
        self.invoice_combo.setFixedHeight(36)
        for inv in unpaid_invoices:
            due = f" • Tempo {inv.due_date}" if inv.due_date else ""
            label = f"{inv.invoice_number} — Sisa {format_rupiah(inv.remaining_amount)}{due}"
            self.invoice_combo.addItem(label, inv.invoice_id)

        amt_lbl = QLabel("Nominal Pembayaran *", card)
        amt_lbl.setObjectName("fieldLabel")
        amt_row = QHBoxLayout()
        amt_row.setSpacing(8)
        self.amount_spin = QSpinBox(card)
        self.amount_spin.setObjectName("fieldSpin")
        self.amount_spin.setFixedHeight(36)
        self.amount_spin.setPrefix("Rp ")
        self.amount_spin.setGroupSeparatorShown(True)
        self.amount_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.full_btn = QPushButton("Bayar Penuh", card)
        self.full_btn.setObjectName("fullBtn")
        self.full_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        amt_row.addWidget(self.amount_spin, 1)
        amt_row.addWidget(self.full_btn)

        self.method_combo = QComboBox(card)
        self.method_combo.setObjectName("fieldCombo")
        self.method_combo.setFixedHeight(36)
        self.method_combo.addItems(["Tunai", "Transfer", "QRIS"])

        method_lbl = QLabel("Metode Pembayaran", card)
        method_lbl.setObjectName("fieldLabel")

        self.tendered_label = QLabel("Uang Diterima", card)
        self.tendered_label.setObjectName("fieldLabel")
        self.tendered_spin = QSpinBox(card)
        self.tendered_spin.setObjectName("fieldSpin")
        self.tendered_spin.setFixedHeight(36)
        self.tendered_spin.setPrefix("Rp ")
        self.tendered_spin.setGroupSeparatorShown(True)
        self.tendered_spin.setRange(0, 2_000_000_000)
        self.tendered_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.change_hint = QLabel("Kembalian: Rp 0", card)
        self.change_hint.setObjectName("metaHint")

        ref_lbl = QLabel("No. Referensi (Opsional)", card)
        ref_lbl.setObjectName("fieldLabel")
        self.reference_input = QLineEdit(card)
        self.reference_input.setObjectName("fieldInput")
        self.reference_input.setFixedHeight(36)
        self.reference_input.setPlaceholderText("Contoh: TRF-00123")

        notes_lbl = QLabel("Catatan (Opsional)", card)
        notes_lbl.setObjectName("fieldLabel")
        self.notes_input = QLineEdit(card)
        self.notes_input.setObjectName("fieldInput")
        self.notes_input.setFixedHeight(36)
        self.notes_input.setPlaceholderText("Catatan pembayaran...")

        form.addWidget(inv_lbl)
        form.addWidget(self.invoice_combo)
        form.addWidget(amt_lbl)
        form.addLayout(amt_row)
        form.addWidget(method_lbl)
        form.addWidget(self.method_combo)
        if is_customer:
            form.addWidget(self.tendered_label)
            form.addWidget(self.tendered_spin)
            form.addWidget(self.change_hint)
        else:
            self.tendered_label.setVisible(False)
            self.tendered_spin.setVisible(False)
            self.change_hint.setVisible(False)
        form.addWidget(ref_lbl)
        form.addWidget(self.reference_input)
        form.addWidget(notes_lbl)
        form.addWidget(self.notes_input)
        layout.addWidget(card)

        self.error_label = QLabel("", self.content_widget)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Batal", self.content_widget)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color="#CDD6F4", stroke=2.0, body=_ICON_CLOSE),
                size=14,
                dpr=3.0,
            )
        )
        cancel_btn.setIconSize(QSize(14, 14))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        submit_btn = QPushButton("Simpan Pembayaran", self.content_widget)
        submit_btn.setObjectName("primaryBtn")
        submit_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color="#11111B", stroke=2.4, body=_ICON_CHECK),
                size=15,
                dpr=3.0,
            )
        )
        submit_btn.setIconSize(QSize(15, 15))
        submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        submit_btn.setDefault(True)
        submit_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(submit_btn)
        layout.addLayout(btn_row)

        self.invoice_combo.currentIndexChanged.connect(self._sync_selected_invoice)
        self.full_btn.clicked.connect(self._fill_full_amount)
        self.amount_spin.valueChanged.connect(self._sync_tendered_and_change)
        self.tendered_spin.valueChanged.connect(self._sync_change_label)
        self.method_combo.currentTextChanged.connect(self._sync_method_state)

        self._sync_selected_invoice()
        self._sync_method_state()

    def _current_invoice(self) -> RelationInvoiceDTO:
        """Mengembalikan DTO nota yang sedang dipilih."""
        idx = max(0, self.invoice_combo.currentIndex())
        return self._invoices[idx]

    def _sync_selected_invoice(self) -> None:
        """Menyesuaikan batas maksimum nominal bayar sesuai sisa nota aktif."""
        inv = self._current_invoice()
        remaining = max(1, inv.remaining_amount)
        self.amount_spin.setRange(1, remaining)
        self.amount_spin.setValue(remaining)
        if self._relation_type == "customer":
            self.tendered_spin.setValue(remaining)
        self._sync_change_label()

    def _fill_full_amount(self) -> None:
        """Mengisi nominal bayar penuh sesuai sisa tagihan nota aktif."""
        inv = self._current_invoice()
        self.amount_spin.setValue(max(1, inv.remaining_amount))
        if self._relation_type == "customer":
            self.tendered_spin.setValue(self.amount_spin.value())

    def _sync_method_state(self) -> None:
        """Mengunci uang diterima sama dengan nominal jika metode non-tunai."""
        if self._relation_type != "customer":
            return
        is_cash = self.method_combo.currentText().strip().lower() == "tunai"
        self.tendered_spin.setEnabled(is_cash)
        if not is_cash:
            self.tendered_spin.setValue(self.amount_spin.value())
        self._sync_change_label()

    def _sync_tendered_and_change(self) -> None:
        """Menyelaraskan uang diterima dan kembalian saat nominal bayar berubah."""
        self.error_label.setVisible(False)
        if self._relation_type == "customer":
            is_cash = self.method_combo.currentText().strip().lower() == "tunai"
            if not is_cash or self.tendered_spin.value() < self.amount_spin.value():
                self.tendered_spin.setValue(self.amount_spin.value())
            self._sync_change_label()

    def _sync_change_label(self) -> None:
        """Memperbarui teks estimasi uang kembalian pelanggan."""
        if self._relation_type != "customer":
            return
        change = max(0, self.tendered_spin.value() - self.amount_spin.value())
        self.change_hint.setText(f"Kembalian: {format_rupiah(change)}")

    def _validate_and_accept(self) -> None:
        """Memvalidasi masukan pembayaran sebelum menutup dialog."""
        amount = self.amount_spin.value()
        if amount <= 0:
            self.error_label.setText("Nominal pembayaran harus lebih dari Rp 0.")
            self.error_label.setVisible(True)
            return
        if (
            self._relation_type == "customer"
            and self.tendered_spin.value() < amount
        ):
            self.error_label.setText(
                "Uang diterima tidak boleh kurang dari nominal pembayaran."
            )
            self.error_label.setVisible(True)
            self.tendered_spin.setFocus()
            return
        self.accept()

    def get_payment_input(self) -> PaymentInputDTO:
        """Mengembalikan payload PaymentInputDTO dari masukan pengguna."""
        inv = self._current_invoice()
        amount = self.amount_spin.value()
        method = self.method_combo.currentText().strip() or "Tunai"
        tendered = (
            self.tendered_spin.value()
            if self._relation_type == "customer"
            else amount
        )
        return PaymentInputDTO(
            invoice_id=inv.invoice_id,
            amount=amount,
            payment_method=method,
            reference_number=self.reference_input.text().strip(),
            notes=self.notes_input.text().strip(),
            tendered_amount=tendered,
            cashier_name=self._cashier_name,
        )
