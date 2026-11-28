"""Dialog ringkasan detail profil, daftar nota, dan riwayat pembayaran relasi."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from core.relasi_backend import RelationDetailDTO
from util.customdialog import CustomDialog, DialogTitleBarConfig
from util.helper.formatrupiah import format_rupiah
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_CENTER = Qt.AlignmentFlag.AlignCenter

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
_ICON_WALLET = (
    '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3'
    'a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
    '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'
)
_ICON_CLOSE = '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>'

_DIALOG_QSS = """
QWidget#CustomDialogContent {
    background-color: transparent;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#headerCard, QFrame#statCard, QFrame#sectionCard {
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
QLabel#headerMeta {
    color: #A6ADC8;
    font-size: 12px;
    background: transparent;
}
QLabel#statKey {
    color: #7F849C;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}
QLabel#statValue {
    color: #CDD6F4;
    font-size: 14px;
    font-weight: 800;
    background: transparent;
}
QLabel#sectionTitle {
    color: #A6ADC8;
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}
QLabel#sectionCount {
    color: #89B4FA;
    background-color: rgba(137, 180, 250, 0.14);
    border: 1px solid rgba(137, 180, 250, 0.35);
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
}
QTableWidget#dataTable {
    background-color: #11111B;
    alternate-background-color: #15151F;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 8px;
    gridline-color: transparent;
    font-size: 12px;
    outline: 0;
}
QHeaderView::section {
    background-color: #313244;
    color: #A6ADC8;
    border: none;
    padding: 4px 8px;
    min-height: 28px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#secondaryBtn {
    background-color: transparent;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 8px;
    padding: 0px 16px;
    min-height: 34px;
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
    min-height: 34px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#primaryBtn:hover {
    background-color: #BDF0B8;
}
"""


class RelationDetailDialog(CustomDialog):
    """Dialog tampilan detail profil, daftar nota, dan riwayat pembayaran relasi."""

    def __init__(
        self,
        detail: RelationDetailDTO,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationDetailDialog dengan data lengkap relasi.

        Args:
            detail: Objek RelationDetailDTO dari RelasiBackend.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self.pay_requested: bool = False
        profile = detail.profile
        is_customer = profile.relation_type == "customer"
        entity = "Pelanggan" if is_customer else "Supplier"
        bill_label = "SISA PIUTANG" if is_customer else "SISA UTANG"

        self.setWindowTitle(f"Detail {entity} - {profile.name}")
        self.setMinimumSize(840, 560)
        self.content_widget.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        self.setLayout(layout)

        header = QFrame(self.content_widget)
        header.setObjectName("headerCard")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(12, 10, 12, 10)
        header_row.setSpacing(12)

        badge = QLabel(header)
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background-color: rgba(137, 180, 250, 0.16);"
            "border: 1px solid rgba(137, 180, 250, 0.35);"
            "border-radius: 10px;"
        )
        badge.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color="#89B4FA", stroke=2.0, body=_ICON_USER),
                size=22,
                dpr=3.0,
            )
        )

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name_lbl = QLabel(profile.name, header)
        name_lbl.setObjectName("headerTitle")
        status_pill = QLabel("AKTIF" if profile.is_active else "ARSIP", header)
        pill_color = "#A6E3A1" if profile.is_active else "#7F849C"
        status_pill.setStyleSheet(
            f"color: {pill_color}; border: 1px solid {pill_color};"
            "border-radius: 8px; padding: 1px 8px; font-size: 10px; font-weight: 700;"
        )
        title_row.addWidget(name_lbl)
        title_row.addWidget(status_pill)
        title_row.addStretch(1)

        phone_text = profile.phone or "-"
        addr_text = profile.address or "-"
        meta_lbl = QLabel(
            f"{entity}  •  Telp: {phone_text}  •  Alamat: {addr_text}",
            header,
        )
        meta_lbl.setObjectName("headerMeta")
        meta_lbl.setWordWrap(True)

        info_col.addLayout(title_row)
        info_col.addWidget(meta_lbl)
        header_row.addWidget(badge)
        header_row.addLayout(info_col, 1)
        layout.addWidget(header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        due_text = detail.nearest_due_date or "-"
        if detail.is_overdue and detail.nearest_due_date:
            due_text = f"{detail.nearest_due_date} (Terlewat)"
        stat_items = (
            ("JUMLAH NOTA", f"{detail.transaction_count} Nota", "#89B4FA"),
            ("TOTAL TRANSAKSI", format_rupiah(detail.transaction_total), "#A6E3A1"),
            (
                bill_label,
                format_rupiah(detail.outstanding_amount),
                "#F38BA8" if detail.outstanding_amount > 0 else "#A6E3A1",
            ),
            (
                "JATUH TEMPO TERDEKAT",
                due_text,
                "#F38BA8" if detail.is_overdue else "#CDD6F4",
            ),
        )
        for key, value, accent in stat_items:
            stats_row.addWidget(self._stat_card(key, value, accent), 1)
        layout.addLayout(stats_row)

        inv_card, inv_layout = self._section_card(
            "DAFTAR NOTA TRANSAKSI",
            f"{len(detail.invoices)} nota",
        )
        inv_table = QTableWidget(len(detail.invoices), 7, inv_card)
        self._style_table(inv_table)
        inv_table.setHorizontalHeaderLabels(
            ["No. Faktur", "Tanggal", "Total", "Terbayar", "Sisa", "Status", "Jatuh Tempo"]
        )
        inv_head = inv_table.horizontalHeader()
        if inv_head is not None:
            for col in (0, 1, 2, 3, 4, 5):
                inv_head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            inv_head.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        bold = QFont()
        bold.setBold(True)
        for idx, inv in enumerate(detail.invoices):
            inv_table.setItem(idx, 0, QTableWidgetItem(inv.invoice_number))
            inv_table.setItem(idx, 1, QTableWidgetItem(inv.transaction_date))

            total_item = QTableWidgetItem(format_rupiah(inv.total))
            total_item.setTextAlignment(_RIGHT)
            paid_item = QTableWidgetItem(format_rupiah(inv.amount_paid))
            paid_item.setTextAlignment(_RIGHT)
            paid_item.setForeground(QColor("#A6E3A1"))
            rem_item = QTableWidgetItem(format_rupiah(inv.remaining_amount))
            rem_item.setTextAlignment(_RIGHT)
            rem_item.setFont(bold)
            rem_item.setForeground(
                QColor("#F38BA8" if inv.remaining_amount > 0 else "#A6E3A1")
            )
            status_item = QTableWidgetItem(inv.payment_status)
            status_item.setTextAlignment(_CENTER)
            due_item = QTableWidgetItem(inv.due_date or "-")
            if inv.is_overdue:
                due_item.setForeground(QColor("#F38BA8"))

            inv_table.setItem(idx, 2, total_item)
            inv_table.setItem(idx, 3, paid_item)
            inv_table.setItem(idx, 4, rem_item)
            inv_table.setItem(idx, 5, status_item)
            inv_table.setItem(idx, 6, due_item)

        inv_layout.addWidget(inv_table, 1)
        layout.addWidget(inv_card, 3)

        pay_card, pay_layout = self._section_card(
            "RIWAYAT PEMBAYARAN",
            f"{len(detail.payments)} pembayaran",
        )
        pay_table = QTableWidget(len(detail.payments), 6, pay_card)
        self._style_table(pay_table)
        pay_table.setHorizontalHeaderLabels(
            ["Tanggal", "No. Faktur", "Metode", "Nominal", "Referensi", "Catatan"]
        )
        pay_head = pay_table.horizontalHeader()
        if pay_head is not None:
            for col in (0, 1, 2, 3, 4):
                pay_head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            pay_head.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        for idx, pay in enumerate(detail.payments):
            pay_table.setItem(idx, 0, QTableWidgetItem(pay.payment_date))
            pay_table.setItem(idx, 1, QTableWidgetItem(pay.invoice_number))
            pay_table.setItem(idx, 2, QTableWidgetItem(pay.payment_method))
            amt_item = QTableWidgetItem(format_rupiah(pay.amount))
            amt_item.setTextAlignment(_RIGHT)
            amt_item.setFont(bold)
            amt_item.setForeground(QColor("#A6E3A1"))
            pay_table.setItem(idx, 3, amt_item)
            pay_table.setItem(idx, 4, QTableWidgetItem(pay.reference_number or "-"))
            pay_table.setItem(idx, 5, QTableWidgetItem(pay.notes or "-"))

        pay_layout.addWidget(pay_table, 1)
        layout.addWidget(pay_card, 2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        close_btn = QPushButton("Tutup", self.content_widget)
        close_btn.setObjectName("secondaryBtn")
        close_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color="#CDD6F4", stroke=2.0, body=_ICON_CLOSE),
                size=14,
                dpr=3.0,
            )
        )
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        if detail.outstanding_amount > 0:
            pay_btn = QPushButton(
                "Terima Pembayaran" if is_customer else "Bayar Utang",
                self.content_widget,
            )
            pay_btn.setObjectName("primaryBtn")
            pay_btn.setIcon(
                build_svg_icon(
                    _SVG_TEMPLATE.format(color="#11111B", stroke=2.2, body=_ICON_WALLET),
                    size=15,
                    dpr=3.0,
                )
            )
            pay_btn.setIconSize(QSize(15, 15))
            pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pay_btn.clicked.connect(self._request_payment)
            btn_row.addWidget(pay_btn)

        layout.addLayout(btn_row)

    def _stat_card(self, key: str, value: str, accent: str) -> QFrame:
        """Membuat kartu metrik ringkas."""
        card = QFrame(self.content_widget)
        card.setObjectName("statCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 7, 10, 8)
        box.setSpacing(2)
        key_lbl = QLabel(key, card)
        key_lbl.setObjectName("statKey")
        val_lbl = QLabel(value, card)
        val_lbl.setObjectName("statValue")
        val_lbl.setStyleSheet(f"color: {accent};")
        box.addWidget(key_lbl)
        box.addWidget(val_lbl)
        return card

    def _section_card(self, title: str, badge_text: str) -> tuple[QFrame, QVBoxLayout]:
        """Membuat kartu seksi tabel beserta judul dan badge jumlah."""
        card = QFrame(self.content_widget)
        card.setObjectName("sectionCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(6)
        head = QHBoxLayout()
        title_lbl = QLabel(title, card)
        title_lbl.setObjectName("sectionTitle")
        count_lbl = QLabel(badge_text, card)
        count_lbl.setObjectName("sectionCount")
        head.addWidget(title_lbl)
        head.addStretch(1)
        head.addWidget(count_lbl)
        box.addLayout(head)
        return card, box

    @staticmethod
    def _style_table(table: QTableWidget) -> None:
        """Menerapkan pengaturan dasar tabel read-only."""
        table.setObjectName("dataTable")
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setMinimumHeight(110)
        v_head = table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
            v_head.setDefaultSectionSize(30)

    def _request_payment(self) -> None:
        """Menandai permintaan pembayaran dari dialog detail dan menutup dialog."""
        self.pay_requested = True
        self.accept()
