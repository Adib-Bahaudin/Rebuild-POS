"""Dialog tampilan rincian item pembelian dan riwayat pembayaran cicilan nota."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog, DialogTitleBarConfig
from util.helper.formatrupiah import format_qty as format_quantity, format_rupiah
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

if TYPE_CHECKING:
    from core.tambah_stok_backend import PurchaseDetailBundle

_BASE = "#1E1E2E"
_MANTLE = "#181825"
_CRUST = "#11111B"
_SURFACE0 = "#313244"
_SURFACE1 = "#45475A"
_SURFACE2 = "#585B70"
_OVERLAY1 = "#7F849C"
_SUBTEXT = "#A6ADC8"
_TEXT = "#CDD6F4"
_BLUE = "#89B4FA"
_SAPPHIRE = "#74C7EC"
_LAVENDER = "#B4BEFE"
_MAUVE = "#CBA6F7"
_TEAL = "#94E2D5"
_PEACH = "#FAB387"
_GREEN = "#A6E3A1"
_YELLOW = "#F9E2AF"
_RED = "#F38BA8"

_STATUS_COLORS: dict[str, str] = {
    "COMPLETED": _GREEN,
    "DRAFT": _YELLOW,
    "CANCELLED": _RED,
    "VOID": _RED,
    "PAID": _GREEN,
    "PARTIAL": _PEACH,
    "PARTIALLY_PAID": _PEACH,
    "UNPAID": _RED,
}
_STATUS_FALLBACK = _OVERLAY1

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICON_RECEIPT = (
    '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1z"/>'
    '<path d="M8 8h8M8 12h8M8 16h5"/>'
)
_ICON_TRUCK = (
    '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/>'
    '<path d="M15 18H9"/>'
    '<path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35'
    'A1 1 0 0 0 17.52 8H14"/>'
    '<circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>'
)
_ICON_CALENDAR = (
    '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<path d="M16 2v4M8 2v4M3 10h18"/>'
)
_ICON_CLOCK = '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'
_ICON_NOTE = (
    '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"/>'
    '<path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/>'
)
_ICON_BOX = (
    '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8'
    'a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
    '<path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>'
)
_ICON_WALLET = (
    '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3'
    'a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
    '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'
)
_ICON_CARD = (
    '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>'
)
_ICON_INBOX = (
    '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
    '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89'
    'A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
)
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
_ICON_CLOSE = '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>'


def _alpha(hex_color: str, alpha_hex: str) -> str:
    """Mengubah warna #RRGGBB menjadi #AARRGGBB untuk QSS.

    Args:
        hex_color: Warna dasar format #RRGGBB.
        alpha_hex: Nilai alpha dua digit heksadesimal, misal "26".

    Returns:
        String warna format #AARRGGBB.
    """
    return f"#{alpha_hex}{hex_color.lstrip('#')}"


def _icon_label(parent: QWidget, body: str, color: str, size: int) -> QLabel:
    """Membuat QLabel transparan berisi ikon SVG.

    Args:
        parent: Widget induk.
        body: Potongan SVG ikon.
        color: Warna ikon.
        size: Ukuran ikon.

    Returns:
        QLabel berisi ikon.
    """
    label = QLabel(parent)
    label.setPixmap(
        render_svg_pixmap(
            _SVG_TEMPLATE.format(color=color, stroke=2.0, body=body),
            size=size,
            dpr=3.0,
        )
    )
    label.setStyleSheet("background: transparent;")
    return label


_DIALOG_QSS = f"""
QWidget#CustomDialogContent {{
    background-color: transparent;
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
}}

/* ---------- Header ---------- */
QFrame#headerCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2E74C7EC, stop:0.55 #2289B4FA, stop:1 #14CBA6F7);
    border: 1px solid #4D74C7EC;
    border-radius: 14px;
}}
QLabel#headerBadge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_SAPPHIRE}, stop:1 {_MAUVE});
    border-radius: 11px;
}}
QLabel#headerKicker {{
    color: {_SUBTEXT};
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}}
QLabel#headerTitle {{
    color: {_TEXT};
    font-size: 16px;
    font-weight: 800;
    background: transparent;
}}
QFrame#metaChip {{
    background-color: #33181825;
    border: 1px solid #3345475A;
    border-radius: 8px;
}}
QLabel#metaKey {{
    color: {_OVERLAY1};
    font-size: 11px;
    background: transparent;
}}
QLabel#metaValue {{
    color: {_TEXT};
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}}

/* ---------- Kartu nominal ---------- */
QFrame#amountCard {{
    background-color: {_MANTLE};
    border: 1px solid {_SURFACE0};
    border-radius: 12px;
}}
QLabel#amountKey {{
    color: {_OVERLAY1};
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}}
QLabel#amountValue {{
    color: {_TEXT};
    font-size: 14px;
    font-weight: 800;
    background: transparent;
}}

/* ---------- Progres pelunasan ---------- */
QFrame#progressCard {{
    background-color: {_MANTLE};
    border: 1px solid {_SURFACE0};
    border-radius: 12px;
}}
QLabel#progressTitle {{
    color: {_SUBTEXT};
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}}
QLabel#progressPct {{
    font-size: 12px;
    font-weight: 800;
    background: transparent;
}}
QProgressBar#payProgress {{
    background-color: {_CRUST};
    border: 1px solid {_SURFACE0};
    border-radius: 5px;
    max-height: 10px;
    min-height: 10px;
}}
QProgressBar#payProgress::chunk {{
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {_TEAL}, stop:1 {_GREEN});
}}

/* ---------- Catatan ---------- */
QFrame#noteCard {{
    background-color: #14F9E2AF;
    border: 1px solid #40F9E2AF;
    border-left: 3px solid {_YELLOW};
    border-radius: 10px;
}}
QLabel#noteText {{
    color: {_TEXT};
    font-size: 12px;
    background: transparent;
}}

/* ---------- Kartu tabel ---------- */
QFrame#sectionCard {{
    background-color: {_MANTLE};
    border: 1px solid {_SURFACE0};
    border-radius: 14px;
}}
QLabel#sectionTitle {{
    color: {_OVERLAY1};
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}}
QLabel#sectionCount {{
    color: {_LAVENDER};
    background-color: #1FB4BEFE;
    border: 1px solid #4DB4BEFE;
    border-radius: 8px;
    padding: 1px 9px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#sectionTotal {{
    color: {_GREEN};
    background-color: #1FA6E3A1;
    border: 1px solid #4DA6E3A1;
    border-radius: 8px;
    padding: 1px 9px;
    font-size: 10px;
    font-weight: 700;
}}

QTableWidget#dataTable {{
    background-color: {_CRUST};
    alternate-background-color: #15151F;
    color: {_TEXT};
    border: 1px solid {_SURFACE0};
    border-radius: 10px;
    gridline-color: transparent;
    font-size: 12px;
    outline: 0;
    selection-background-color: #3389B4FA;
    selection-color: {_TEXT};
}}
QTableWidget#dataTable::item {{
    padding: 0px 10px;
    border: none;
    border-bottom: 1px solid #1C1C2A;
}}
QTableWidget#dataTable::item:hover {{
    background-color: #1AB4BEFE;
}}
QTableWidget#dataTable::item:selected {{
    background-color: #3389B4FA;
    border-bottom: 1px solid #5589B4FA;
}}
QHeaderView {{
    background-color: transparent;
    border: none;
}}
QHeaderView::section {{
    background-color: {_SURFACE0};
    color: {_SUBTEXT};
    border: none;
    border-bottom: 1px solid {_SURFACE1};
    padding: 0px 10px;
    min-height: 32px;
    font-size: 11px;
    font-weight: 700;
}}
QHeaderView::section:first {{
    border-top-left-radius: 9px;
}}
QHeaderView::section:last {{
    border-top-right-radius: 9px;
}}
QTableCornerButton::section {{
    background-color: {_SURFACE0};
    border: none;
}}

/* ---------- Empty state ---------- */
QFrame#emptyState {{
    background-color: {_CRUST};
    border: 1px dashed {_SURFACE1};
    border-radius: 10px;
}}
QLabel#emptyTitle {{
    color: {_TEXT};
    font-size: 12px;
    font-weight: 700;
    background: transparent;
}}
QLabel#emptyText {{
    color: {_OVERLAY1};
    font-size: 11px;
    background: transparent;
}}

/* ---------- Scrollbar ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0px;
}}
QScrollBar::handle:vertical {{
    background: {_SURFACE1};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {_SURFACE2};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_SURFACE1};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {_SURFACE2};
}}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
    width: 0px;
    height: 0px;
}}

/* ---------- Tombol ---------- */
QPushButton#secondaryBtn {{
    background-color: transparent;
    color: {_TEXT};
    border: 1px solid {_SURFACE1};
    border-radius: 9px;
    padding: 0px 16px;
    min-height: 34px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#secondaryBtn:hover {{
    background-color: {_SURFACE0};
    border: 1px solid {_SURFACE2};
}}
QPushButton#secondaryBtn:pressed {{
    background-color: {_SURFACE1};
}}
QPushButton#primaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {_TEAL}, stop:1 {_GREEN});
    color: {_CRUST};
    border: none;
    border-radius: 9px;
    padding: 0px 18px;
    min-height: 34px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ADEDE3, stop:1 #BDF0B8);
}}
QPushButton#primaryBtn:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7BCCBF, stop:1 #8CCB87);
}}
QPushButton#primaryBtn:focus, QPushButton#secondaryBtn:focus {{
    outline: none;
}}
"""

_TITLEBAR_CONFIG = DialogTitleBarConfig(
    titlebar_color=_MANTLE,
    title_text_color=_TEXT,
    border_color=_SURFACE0,
    background_color=_BASE,
)


class PurchaseDetailDialog(CustomDialog):
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
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self.pay_requested: bool = False
        self.setWindowTitle(f"Detail Nota Kulakan - {bundle['invoice_number']}")
        self.setMinimumSize(900, 600)

        content = self.content_widget
        content.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)
        self.setLayout(layout)

        layout.addWidget(self._build_header(content, bundle))
        layout.addLayout(self._build_amount_row(content, bundle))

        if bundle["notes"]:
            layout.addWidget(self._build_note(content, bundle["notes"]))

        lines_card, lines_layout = self._build_section(
            content,
            _ICON_BOX,
            "RINCIAN BARANG MASUK (FIFO)",
            f"{len(bundle['lines'])} item",
            format_rupiah(bundle["subtotal"]),
        )
        lines_table = QTableWidget(len(bundle["lines"]), 6, lines_card)
        self._style_table(lines_table)
        lines_table.setHorizontalHeaderLabels(
            ["SKU", "Barang", "Satuan", "Qty Beli", "Stok Masuk", "Subtotal"]
        )
        h_head = lines_table.horizontalHeader()
        if h_head is not None:
            for col in (0, 2, 3, 4, 5):
                h_head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            h_head.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        sku_font = QFont("Consolas")
        sku_font.setStyleHint(QFont.StyleHint.Monospace)
        bold = QFont()
        bold.setBold(True)
        item_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_BLUE, stroke=2.0, body=_ICON_BOX),
            size=14,
            dpr=3.0,
        )

        for row_idx, line in enumerate(bundle["lines"]):
            sku_item = QTableWidgetItem(line["sku"])
            sku_item.setFont(sku_font)
            sku_item.setForeground(QColor(_OVERLAY1))
            lines_table.setItem(row_idx, 0, sku_item)

            name_item = QTableWidgetItem(line["item_name"])
            name_item.setIcon(item_icon)
            name_item.setToolTip(line["item_name"])
            lines_table.setItem(row_idx, 1, name_item)

            unit_item = QTableWidgetItem(line["variant_name"])
            unit_item.setForeground(QColor(_LAVENDER))
            lines_table.setItem(row_idx, 2, unit_item)

            qty_item = QTableWidgetItem(format_quantity(line["quantity"]))
            qty_item.setTextAlignment(_RIGHT)
            qty_item.setFont(bold)
            base_item = QTableWidgetItem(
                f"{format_quantity(line['base_quantity'])} {line['base_unit_symbol']}"
            )
            base_item.setTextAlignment(_RIGHT)
            base_item.setForeground(QColor(_TEAL))
            sub_item = QTableWidgetItem(format_rupiah(line["subtotal"]))
            sub_item.setTextAlignment(_RIGHT)
            sub_item.setFont(bold)
            sub_item.setForeground(QColor(_GREEN))
            lines_table.setItem(row_idx, 3, qty_item)
            lines_table.setItem(row_idx, 4, base_item)
            lines_table.setItem(row_idx, 5, sub_item)

        self._align_headers(lines_table, (3, 4, 5))
        lines_layout.addWidget(lines_table, 1)
        layout.addWidget(lines_card, 3)

        paid_total = sum(p["amount"] for p in bundle["payments"])
        pay_card, pay_layout = self._build_section(
            content,
            _ICON_CARD,
            "RIWAYAT PEMBAYARAN & CICILAN",
            f"{len(bundle['payments'])} transaksi",
            format_rupiah(paid_total),
        )
        pay_table = QTableWidget(len(bundle["payments"]), 5, pay_card)
        self._style_table(pay_table)
        pay_table.setHorizontalHeaderLabels(
            ["Tanggal Bayar", "Metode", "Nominal", "No. Referensi", "Catatan"]
        )
        ph_head = pay_table.horizontalHeader()
        if ph_head is not None:
            for col in (0, 1, 2, 3):
                ph_head.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            ph_head.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        date_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_BLUE, stroke=2.0, body=_ICON_CALENDAR),
            size=14,
            dpr=3.0,
        )
        method_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_PEACH, stroke=2.0, body=_ICON_WALLET),
            size=14,
            dpr=3.0,
        )

        for row_idx, payment in enumerate(bundle["payments"]):
            date_item = QTableWidgetItem(payment["payment_date"])
            date_item.setIcon(date_icon)
            date_item.setForeground(QColor(_SUBTEXT))
            pay_table.setItem(row_idx, 0, date_item)

            method_item = QTableWidgetItem(payment["payment_method"])
            method_item.setIcon(method_icon)
            method_item.setFont(bold)
            method_item.setForeground(QColor(_PEACH))
            pay_table.setItem(row_idx, 1, method_item)

            amt_item = QTableWidgetItem(format_rupiah(payment["amount"]))
            amt_item.setTextAlignment(_RIGHT)
            amt_item.setFont(bold)
            amt_item.setForeground(QColor(_GREEN))
            pay_table.setItem(row_idx, 2, amt_item)

            ref_item = QTableWidgetItem(payment["reference_number"] or "-")
            ref_item.setForeground(QColor(_LAVENDER))
            pay_table.setItem(row_idx, 3, ref_item)

            note_item = QTableWidgetItem(payment["notes"] or "-")
            note_item.setForeground(QColor(_SUBTEXT))
            note_item.setToolTip(payment["notes"] or "")
            pay_table.setItem(row_idx, 4, note_item)

        self._align_headers(pay_table, (2,))
        if bundle["payments"]:
            pay_layout.addWidget(pay_table, 1)
        else:
            pay_table.setVisible(False)
            pay_layout.addWidget(
                self._build_empty_state(
                    pay_card,
                    "Belum ada pembayaran",
                    "Cicilan atau pelunasan yang dicatat akan tampil di sini.",
                ),
                1,
            )
        layout.addWidget(pay_card, 2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        close_btn = QPushButton("Tutup", content)
        close_btn.setObjectName("secondaryBtn")
        close_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color=_TEXT, stroke=2.0, body=_ICON_CLOSE),
                size=14,
                dpr=3.0,
            )
        )
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        can_pay = (
            bundle["status"] == "COMPLETED"
            and bundle["payment_status"] != "PAID"
            and bundle["remaining_amount"] > 0
        )
        if can_pay:
            pay_btn = QPushButton("Bayar Cicilan / Pelunasan", content)
            pay_btn.setObjectName("primaryBtn")
            pay_btn.setIcon(
                build_svg_icon(
                    _SVG_TEMPLATE.format(color=_CRUST, stroke=2.2, body=_ICON_WALLET),
                    size=16,
                    dpr=3.0,
                )
            )
            pay_btn.setIconSize(QSize(16, 16))
            pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pay_btn.clicked.connect(self._request_payment)
            btn_row.addWidget(pay_btn)

        layout.addLayout(btn_row)
        close_btn.setFocus()

    @staticmethod
    def _status_pill(parent: QWidget, text: str) -> QLabel:
        """Membuat pill berwarna untuk status nota atau status pembayaran.

        Args:
            parent: Widget induk.
            text: Teks status.

        Returns:
            QLabel berbentuk pill.
        """
        color = _STATUS_COLORS.get(str(text).upper(), _STATUS_FALLBACK)
        pill = QLabel(f"●  {text}", parent)
        pill.setTextFormat(Qt.TextFormat.PlainText)
        pill.setStyleSheet(
            f"color: {color};"
            f"background-color: {_alpha(color, '26')};"
            f"border: 1px solid {_alpha(color, '66')};"
            "border-radius: 10px; padding: 2px 10px;"
            "font-size: 10px; font-weight: 800;"
        )
        return pill

    @staticmethod
    def _meta_chip(parent: QWidget, icon: str, color: str, key: str, value: str) -> QFrame:
        """Membuat chip informasi kecil berikon untuk header.

        Args:
            parent: Widget induk.
            icon: Potongan SVG ikon.
            color: Warna ikon.
            key: Label informasi.
            value: Nilai informasi.

        Returns:
            QFrame chip informasi.
        """
        chip = QFrame(parent)
        chip.setObjectName("metaChip")
        box = QHBoxLayout(chip)
        box.setContentsMargins(6, 2, 8, 2)
        box.setSpacing(5)
        key_label = QLabel(key, chip)
        key_label.setObjectName("metaKey")
        value_label = QLabel(value, chip)
        value_label.setObjectName("metaValue")
        value_label.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(_icon_label(chip, icon, color, 13))
        box.addWidget(key_label)
        box.addWidget(value_label)
        return chip

    def _build_header(self, parent: QWidget, bundle: PurchaseDetailBundle) -> QFrame:
        """Membangun kartu header: badge, nomor nota, pill status, dan meta info.

        Args:
            parent: Widget induk header.
            bundle: Data nota pembelian.

        Returns:
            QFrame header.
        """
        header = QFrame(parent)
        header.setObjectName("headerCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 9, 12, 9)
        header_layout.setSpacing(12)

        badge = QLabel(header)
        badge.setObjectName("headerBadge")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.0, body=_ICON_RECEIPT),
                size=22,
                dpr=3.0,
            )
        )
        glow = QGraphicsDropShadowEffect(badge)
        glow.setBlurRadius(22)
        glow.setOffset(0, 3)
        glow.setColor(QColor(116, 199, 236, 110))
        badge.setGraphicsEffect(glow)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)

        kicker = QLabel("NOTA KULAKAN", header)
        kicker.setObjectName("headerKicker")

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(bundle["invoice_number"], header)
        title.setObjectName("headerTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(title)
        title_row.addWidget(self._status_pill(header, bundle["status"]))
        title_row.addWidget(self._status_pill(header, bundle["payment_status"]))
        title_row.addStretch(1)

        due_info = bundle["due_date"] if bundle["due_date"] else "-"
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta_row.addWidget(
            self._meta_chip(header, _ICON_TRUCK, _TEAL, "Supplier", bundle["supplier_name"])
        )
        meta_row.addWidget(
            self._meta_chip(header, _ICON_CALENDAR, _BLUE, "Tanggal", bundle["purchase_date"])
        )
        due_color = _PEACH if bundle["due_date"] else _OVERLAY1
        meta_row.addWidget(
            self._meta_chip(header, _ICON_CLOCK, due_color, "Jatuh Tempo", due_info)
        )
        meta_row.addStretch(1)

        text_box.addWidget(kicker)
        text_box.addLayout(title_row)
        text_box.addLayout(meta_row)

        header_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(text_box, 1)
        return header

    def _build_amount_row(self, parent: QWidget, bundle: PurchaseDetailBundle) -> QHBoxLayout:
        """Membangun baris kartu nominal dan kartu progres pelunasan.

        Args:
            parent: Widget induk.
            bundle: Data nota pembelian.

        Returns:
            QHBoxLayout berisi kartu-kartu nominal.
        """
        row = QHBoxLayout()
        row.setSpacing(10)

        remaining = bundle["remaining_amount"]
        cards = (
            ("SUBTOTAL", format_rupiah(bundle["subtotal"]), _BLUE),
            ("DISKON", format_rupiah(bundle["discount"]), _MAUVE),
            ("TOTAL", format_rupiah(bundle["total"]), _LAVENDER),
            ("DIBAYAR", format_rupiah(bundle["amount_paid"]), _GREEN),
            ("SISA HUTANG", format_rupiah(remaining), _RED if remaining > 0 else _GREEN),
        )
        for key, value, accent in cards:
            row.addWidget(self._amount_card(parent, key, value, accent), 1)

        total = bundle["total"]
        paid = bundle["amount_paid"]
        pct = 100 if total <= 0 else max(0, min(100, round(paid / total * 100)))

        progress_card = QFrame(parent)
        progress_card.setObjectName("progressCard")
        progress_card.setMinimumWidth(170)
        box = QVBoxLayout(progress_card)
        box.setContentsMargins(10, 6, 10, 7)
        box.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(6)
        title = QLabel("Pelunasan", progress_card)
        title.setObjectName("progressTitle")
        pct_color = _GREEN if pct >= 100 else (_PEACH if pct > 0 else _RED)
        pct_label = QLabel(f"{pct}%", progress_card)
        pct_label.setObjectName("progressPct")
        pct_label.setStyleSheet(f"color: {pct_color};")
        top.addWidget(_icon_label(progress_card, _ICON_CHECK, pct_color, 13))
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(pct_label)

        bar = QProgressBar(progress_card)
        bar.setObjectName("payProgress")
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)

        box.addLayout(top)
        box.addWidget(bar)
        row.addWidget(progress_card, 1)
        return row

    @staticmethod
    def _amount_card(parent: QWidget, key: str, value: str, accent: str) -> QFrame:
        """Membuat satu kartu nominal dengan garis aksen di atas.

        Args:
            parent: Widget induk.
            key: Label nominal.
            value: Nilai nominal terformat.
            accent: Warna aksen.

        Returns:
            QFrame kartu nominal.
        """
        card = QFrame(parent)
        card.setObjectName("amountCard")
        card.setStyleSheet(f"QFrame#amountCard {{ border-top: 2px solid {accent}; }}")
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 6, 10, 7)
        box.setSpacing(2)
        key_label = QLabel(key, card)
        key_label.setObjectName("amountKey")
        value_label = QLabel(value, card)
        value_label.setObjectName("amountValue")
        value_label.setStyleSheet(f"color: {accent};")
        box.addWidget(key_label)
        box.addWidget(value_label)
        return card

    @staticmethod
    def _build_note(parent: QWidget, notes: str) -> QFrame:
        """Membangun kotak catatan nota bergaya callout.

        Args:
            parent: Widget induk.
            notes: Isi catatan.

        Returns:
            QFrame catatan.
        """
        card = QFrame(parent)
        card.setObjectName("noteCard")
        box = QHBoxLayout(card)
        box.setContentsMargins(10, 6, 10, 6)
        box.setSpacing(8)
        text = QLabel(f"Catatan: {notes}", card)
        text.setObjectName("noteText")
        text.setTextFormat(Qt.TextFormat.PlainText)
        text.setWordWrap(True)
        box.addWidget(_icon_label(card, _ICON_NOTE, _YELLOW, 15), 0, Qt.AlignmentFlag.AlignTop)
        box.addWidget(text, 1)
        return card

    @staticmethod
    def _build_section(
        parent: QWidget, icon: str, title: str, count: str, total: str
    ) -> tuple[QFrame, QVBoxLayout]:
        """Membangun kartu seksi tabel beserta judul, chip jumlah, dan chip total.

        Args:
            parent: Widget induk.
            icon: Potongan SVG ikon judul.
            title: Judul seksi.
            count: Teks chip jumlah baris.
            total: Teks chip total nominal.

        Returns:
            Tuple (kartu seksi, layout isi kartu).
        """
        card = QFrame(parent)
        card.setObjectName("sectionCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        title_label = QLabel(title, card)
        title_label.setObjectName("sectionTitle")
        count_label = QLabel(count, card)
        count_label.setObjectName("sectionCount")
        total_label = QLabel(total, card)
        total_label.setObjectName("sectionTotal")
        head.addWidget(_icon_label(card, icon, _OVERLAY1, 14))
        head.addWidget(title_label)
        head.addStretch(1)
        head.addWidget(count_label)
        head.addWidget(total_label)
        box.addLayout(head)
        return card, box

    @staticmethod
    def _style_table(table: QTableWidget) -> None:
        """Menerapkan pengaturan tampilan seragam pada tabel data.

        Args:
            table: Tabel yang akan diatur.
        """
        table.setObjectName("dataTable")
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setIconSize(QSize(14, 14))
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setMinimumHeight(110)
        v_head = table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
            v_head.setDefaultSectionSize(32)
        h_head = table.horizontalHeader()
        if h_head is not None:
            h_head.setHighlightSections(False)
            h_head.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_head.setMinimumSectionSize(80)

    @staticmethod
    def _align_headers(table: QTableWidget, columns: tuple[int, ...]) -> None:
        """Meratakan kanan judul kolom angka agar sejajar dengan isinya.

        Args:
            table: Tabel target.
            columns: Indeks kolom yang dirata kanan.
        """
        for col in columns:
            header_item = table.horizontalHeaderItem(col)
            if header_item is not None:
                header_item.setTextAlignment(_RIGHT)

    @staticmethod
    def _build_empty_state(parent: QWidget, title: str, text: str) -> QFrame:
        """Membangun tampilan kosong untuk tabel tanpa data.

        Args:
            parent: Widget induk.
            title: Judul pesan kosong.
            text: Keterangan pesan kosong.

        Returns:
            QFrame empty state.
        """
        empty = QFrame(parent)
        empty.setObjectName("emptyState")
        empty.setMinimumHeight(80)
        box = QVBoxLayout(empty)
        box.setContentsMargins(16, 10, 16, 10)
        box.setSpacing(4)
        icon = _icon_label(empty, _ICON_INBOX, _OVERLAY1, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title, empty)
        title_label.setObjectName("emptyTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(text, empty)
        text_label.setObjectName("emptyText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addStretch(1)
        box.addWidget(icon)
        box.addWidget(title_label)
        box.addWidget(text_label)
        box.addStretch(1)
        return empty

    def _request_payment(self) -> None:
        """Menandai permintaan pelunasan hutang dan menutup dialog detail."""
        self.pay_requested = True
        self.accept()