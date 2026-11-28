"""Dialog formulir tambah/ubah profil dan konfirmasi arsip Pelanggan/Supplier."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.relasi_backend import (
    ArchiveImpactDTO,
    RelationInputDTO,
    RelationProfileDTO,
)
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
_ICON_USER = (
    '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>'
    '<circle cx="12" cy="7" r="4"/>'
)
_ICON_ALERT = (
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16'
    'a2 2 0 0 0 1.73-3Z"/>'
    '<path d="M12 9v4"/><path d="M12 17h.01"/>'
)
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
_ICON_CLOSE = '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>'

_DIALOG_QSS = """
QWidget#CustomDialogContent {
    background-color: transparent;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#headerCard {
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
QFrame#formCard {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 12px;
}
QLabel#fieldLabel {
    color: #CDD6F4;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLineEdit#fieldInput, QTextEdit#fieldText {
    background-color: #11111B;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit#fieldInput:focus, QTextEdit#fieldText:focus {
    border: 1px solid #89B4FA;
}
QCheckBox#activeCheck {
    color: #CDD6F4;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
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
QLabel#impactText {
    color: #CDD6F4;
    font-size: 13px;
    background: transparent;
}
QLabel#impactWarn {
    color: #F9E2AF;
    background-color: rgba(249, 226, 175, 0.10);
    border: 1px solid rgba(249, 226, 175, 0.35);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
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
    background-color: #89B4FA;
    color: #11111B;
    border: none;
    border-radius: 8px;
    padding: 0px 18px;
    min-height: 36px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#primaryBtn:hover {
    background-color: #A6C8FF;
}
QPushButton#dangerBtn {
    background-color: #F38BA8;
    color: #11111B;
    border: none;
    border-radius: 8px;
    padding: 0px 18px;
    min-height: 36px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#dangerBtn:hover {
    background-color: #F5A3BA;
}
"""


class RelationFormDialog(CustomDialog):
    """Dialog tambah atau edit profil pelanggan dan supplier."""

    def __init__(
        self,
        relation_type: RelationType,
        profile: RelationProfileDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi dialog formulir pelanggan atau supplier.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            profile: Profil relasi jika mode edit, atau None jika tambah baru.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self._relation_type = relation_type
        self._profile = profile
        entity = "Pelanggan" if relation_type == "customer" else "Supplier"
        is_edit = profile is not None

        self.setWindowTitle(f"{'Ubah' if is_edit else 'Tambah'} {entity}")
        self.setMinimumWidth(450)
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
            "background-color: rgba(137, 180, 250, 0.16);"
            "border: 1px solid rgba(137, 180, 250, 0.35);"
            "border-radius: 10px;"
        )
        icon_lbl.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color="#89B4FA", stroke=2.0, body=_ICON_USER),
                size=20,
                dpr=3.0,
            )
        )

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel(f"{'Ubah Profil' if is_edit else 'Tambah'} {entity}", header)
        title_lbl.setObjectName("headerTitle")
        subtitle_lbl = QLabel(
            f"Lengkapi identitas {entity.lower()} untuk pencatatan transaksi.",
            header,
        )
        subtitle_lbl.setObjectName("headerSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(subtitle_lbl)

        header_row.addWidget(icon_lbl)
        header_row.addLayout(title_col, 1)
        layout.addWidget(header)

        card = QFrame(self.content_widget)
        card.setObjectName("formCard")
        form_layout = QVBoxLayout(card)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(10)

        name_lbl = QLabel(f"Nama {entity} *", card)
        name_lbl.setObjectName("fieldLabel")
        self.name_input = QLineEdit(card)
        self.name_input.setObjectName("fieldInput")
        self.name_input.setFixedHeight(36)
        self.name_input.setPlaceholderText(f"Masukkan nama {entity.lower()}...")

        phone_lbl = QLabel("No. Telepon / WhatsApp", card)
        phone_lbl.setObjectName("fieldLabel")
        self.phone_input = QLineEdit(card)
        self.phone_input.setObjectName("fieldInput")
        self.phone_input.setFixedHeight(36)
        self.phone_input.setPlaceholderText("Contoh: 0812-3456-7890 (opsional)")

        address_lbl = QLabel("Alamat", card)
        address_lbl.setObjectName("fieldLabel")
        self.address_input = QTextEdit(card)
        self.address_input.setObjectName("fieldText")
        self.address_input.setFixedHeight(68)
        self.address_input.setPlaceholderText("Alamat lengkap atau catatan lokasi (opsional)")

        self.active_check = QCheckBox(f"{entity} Berstatus Aktif", card)
        self.active_check.setObjectName("activeCheck")
        self.active_check.setChecked(True)
        self.active_check.setVisible(is_edit)

        form_layout.addWidget(name_lbl)
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(phone_lbl)
        form_layout.addWidget(self.phone_input)
        form_layout.addWidget(address_lbl)
        form_layout.addWidget(self.address_input)
        if is_edit:
            form_layout.addWidget(self.active_check)
        layout.addWidget(card)

        self.error_label = QLabel("", self.content_widget)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        if profile is not None:
            self.name_input.setText(profile.name)
            self.phone_input.setText(profile.phone)
            self.address_input.setPlainText(profile.address)
            self.active_check.setChecked(profile.is_active)

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

        save_btn = QPushButton(
            "Simpan Perubahan" if is_edit else f"Simpan {entity}",
            self.content_widget,
        )
        save_btn.setObjectName("primaryBtn")
        save_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color="#11111B", stroke=2.4, body=_ICON_CHECK),
                size=15,
                dpr=3.0,
            )
        )
        save_btn.setIconSize(QSize(15, 15))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.name_input.textChanged.connect(lambda _t: self.error_label.setVisible(False))
        self.name_input.setFocus()

    def _validate_and_accept(self) -> None:
        """Memastikan nama relasi terisi sebelum menutup dialog."""
        if not self.name_input.text().strip():
            entity = "pelanggan" if self._relation_type == "customer" else "supplier"
            self.error_label.setText(f"Nama {entity} wajib diisi.")
            self.error_label.setVisible(True)
            self.name_input.setFocus()
            return
        self.accept()

    def get_payload(self) -> RelationInputDTO:
        """Mengembalikan data formulir dalam bentuk RelationInputDTO."""
        return RelationInputDTO(
            name=self.name_input.text().strip(),
            phone=self.phone_input.text().strip(),
            address=self.address_input.toPlainText().strip(),
            is_active=self.active_check.isChecked(),
        )


class RelationArchiveConfirmDialog(CustomDialog):
    """Dialog konfirmasi pengarsipan atau aktivasi kembali profil relasi."""

    def __init__(
        self,
        impact: ArchiveImpactDTO,
        target_active: bool,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi dialog konfirmasi perubahan status aktif relasi.

        Args:
            impact: Informasi dampak tagihan aktif sebelum mengubah status relasi.
            target_active: Status aktif tujuan setelah konfirmasi.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        entity = "Pelanggan" if impact.relation_type == "customer" else "Supplier"
        action_label = "Aktifkan Kembali" if target_active else "Arsipkan"

        self.setWindowTitle(f"{action_label} {entity}")
        self.setMinimumWidth(430)
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

        accent = "#A6E3A1" if target_active else "#F38BA8"
        icon_lbl = QLabel(header)
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background-color: rgba(243, 139, 168, 0.14);"
            f"border: 1px solid {accent}; border-radius: 9px;"
        )
        icon_lbl.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=accent, stroke=2.0, body=_ICON_ALERT),
                size=18,
                dpr=3.0,
            )
        )

        title_lbl = QLabel(f"Konfirmasi {action_label} {entity}", header)
        title_lbl.setObjectName("headerTitle")
        header_row.addWidget(icon_lbl)
        header_row.addWidget(title_lbl, 1)
        layout.addWidget(header)

        desc = QLabel(
            f"Apakah Anda yakin ingin {'mengaktifkan kembali' if target_active else 'mengarsipkan'} "
            f"<b>{impact.name}</b>?",
            self.content_widget,
        )
        desc.setObjectName("impactText")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        if not target_active and impact.outstanding_amount > 0:
            bill_label = "piutang" if impact.relation_type == "customer" else "utang"
            warn = QLabel(
                f"Perhatian: {entity} ini masih memiliki sisa {bill_label} sebesar "
                f"{format_rupiah(impact.outstanding_amount)} pada {impact.unpaid_invoice_count} nota "
                f"({impact.overdue_invoice_count} jatuh tempo). Data riwayat transaksi tetap aman.",
                self.content_widget,
            )
            warn.setObjectName("impactWarn")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Batal", self.content_widget)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton(f"Ya, {action_label}", self.content_widget)
        confirm_btn.setObjectName("primaryBtn" if target_active else "dangerBtn")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setDefault(True)
        confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)
