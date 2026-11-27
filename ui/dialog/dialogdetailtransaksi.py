"""Modul dialog antarmuka pengguna untuk menampilkan detail lengkap transaksi POS.

Modul ini menyediakan kelas TransactionDetailDialog sebagai dialog modal untuk
menampilkan metadata faktur, daftar barang dan jasa, rincian nominal, status
pelunasan, serta tombol cetak struk.

Tampilan dibangun ulang dengan ikon SVG inline, kartu berwarna, dan tabel
read-only bergaya kustom. Logika sinyal, callback pembayaran, dan pembaruan
detail tidak berubah.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImageWriter, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
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
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap


class _C:
    """Konstanta palet warna dialog (turunan Catppuccin Mocha, lebih vivid)."""

    BASE = "#181825"
    SURFACE = "#1E1E2E"
    SURFACE_HI = "#252638"
    BORDER = "#313244"
    BORDER_HI = "#45475A"
    TEXT = "#CDD6F4"
    SUBTEXT = "#A6ADC8"
    MUTED = "#7F849C"
    BLUE = "#89B4FA"
    MAUVE = "#CBA6F7"
    GREEN = "#A6E3A1"
    PEACH = "#FAB387"
    YELLOW = "#F9E2AF"
    PINK = "#F38BA8"
    RED = "#F87171"
    TEAL = "#94E2D5"


def _rgba(hex_color: str, alpha: float) -> str:
    """Mengubah warna hex menjadi notasi rgba() QSS.

    Args:
        hex_color: Warna dalam format #RRGGBB.
        alpha: Opasitas 0.0 hingga 1.0.

    Returns:
        String warna rgba untuk QSS.
    """
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.2f})"


_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS: dict[str, str] = {
    "receipt": (
        '<path d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5L10 21l-2.5-1.5L5 21z"/>'
        '<path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h3"/>'
    ),
    "calendar": (
        '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4"/>'
        '<path d="M8 3v4"/><path d="M3 10h18"/>'
    ),
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users": (
        '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/>'
        '<path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14a6.5 6.5 0 0 1 3.5 6"/>'
    ),
    "card": (
        '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 10h19"/>'
        '<path d="M6.5 15h4"/>'
    ),
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16 10"/>',
    "alert_circle": '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5"/><path d="M12 16h.01"/>',
    "cart": (
        '<circle cx="9" cy="20" r="1.3"/><circle cx="18" cy="20" r="1.3"/>'
        '<path d="M2.5 3h3l2.6 12.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21.5 8H6.3"/>'
    ),
    "wallet": (
        '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/>'
        '<path d="M21 9h-5a3 3 0 0 0 0 6h5z"/><path d="M16 12h.01"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "printer": (
        '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/>'
        '<path d="M6 14h12v7H6z"/>'
    ),
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "cash": (
        '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>'
        '<path d="M6 12h.01"/><path d="M18 12h.01"/>'
    ),
    "coins_back": (
        '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>'
    ),
    "note": (
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'
    ),
    "calculator": (
        '<rect x="4" y="2.5" width="16" height="19" rx="2"/><path d="M8 7h8"/>'
        '<path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/>'
        '<path d="M8 16h.01"/><path d="M12 16h.01"/><path d="M16 16h.01"/>'
    ),
}


def _svg_pixmap(name: str, size: int, color: str, stroke: float = 2.0) -> QPixmap:
    """Merender ikon SVG inline menjadi QPixmap tajam (HiDPI-ready).

    Args:
        name: Kunci ikon pada kamus _ICONS.
        size: Ukuran sisi ikon dalam piksel logis.
        color: Warna goresan ikon.
        stroke: Ketebalan goresan.

    Returns:
        QPixmap transparan berisi ikon.
    """
    markup = _SVG_TEMPLATE.format(color=color, stroke=stroke, body=_ICONS[name])
    return render_svg_pixmap(markup, size=size)


def _svg_icon(name: str, color: str, size: int = 16) -> QIcon:
    """Membuat QIcon dari ikon SVG inline.

    Args:
        name: Kunci ikon pada kamus _ICONS.
        color: Warna goresan ikon.
        size: Ukuran ikon.

    Returns:
        Objek QIcon siap pakai.
    """
    markup = _SVG_TEMPLATE.format(color=color, stroke=2.0, body=_ICONS[name])
    return build_svg_icon(markup, size=size)


class _HoverIconButton(QPushButton):
    """Tombol berikon yang menukar warna ikon saat kursor berada di atasnya."""

    def __init__(
        self,
        text: str,
        icon_name: str,
        normal_color: str,
        hover_color: str,
        parent: QWidget | None = None,
        *,
        icon_size: int = 16,
    ) -> None:
        """Menginisialisasi tombol berikon dengan dua varian warna.

        Args:
            text: Teks tombol.
            icon_name: Kunci ikon pada kamus _ICONS.
            normal_color: Warna ikon normal.
            hover_color: Warna ikon saat hover.
            parent: Widget induk opsional.
            icon_size: Ukuran ikon.
        """
        super().__init__(text, parent)
        self._icon_normal = _svg_icon(icon_name, normal_color, icon_size)
        self._icon_hover = _svg_icon(icon_name, hover_color, icon_size)
        self.setIcon(self._icon_normal)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event: QEvent) -> None:  # type: ignore[override]
        """Mengganti ikon ke varian hover."""
        self.setIcon(self._icon_hover)
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: QEvent) -> None:
        """Mengembalikan ikon ke varian normal."""
        self.setIcon(self._icon_normal)
        super().leaveEvent(event)


_DIALOG_QSS = """
QWidget#CustomDialogContent {
    background-color: @BASE@;
    color: @TEXT@;
}

/* ---------- Kartu header ---------- */
QFrame#DetailHeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 @BLUE_A@, stop:0.55 @MAUVE_A@, stop:1 @PINK_A@);
    border: 1px solid @BLUE_B@;
    border-radius: 12px;
}
QLabel#InvoiceBadge {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #3B82F6, stop:1 #A855F7);
    border-radius: 12px;
}
QLabel#InvoiceCaption {
    color: @SUBTEXT@;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}
QLabel#InvoiceNumber {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    background: transparent;
}
QLabel#StatusPaid, QLabel#StatusUnpaid {
    border-radius: 11px;
    padding: 4px 11px;
    font-size: 11px;
    font-weight: 800;
}
QLabel#StatusPaid {
    background-color: @GREEN_A@;
    color: @GREEN@;
    border: 1px solid @GREEN_B@;
}
QLabel#StatusUnpaid {
    background-color: @RED_A@;
    color: @RED@;
    border: 1px solid @RED_B@;
}
QFrame#MetaTile {
    background-color: @BASE_A@;
    border: 1px solid @BORDER@;
    border-radius: 9px;
}
QLabel#MetaCaption {
    color: @MUTED@;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}
QLabel#MetaValue {
    color: @TEXT@;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

/* ---------- Kartu item ---------- */
QFrame#ItemsCard, QFrame#DetailTotalsCard {
    background-color: @SURFACE@;
    border: 1px solid @BORDER@;
    border-radius: 12px;
}
QLabel#SectionTitle {
    color: @TEXT@;
    font-size: 12px;
    font-weight: 700;
    background: transparent;
}
QLabel#SectionSubtitle {
    color: @MUTED@;
    font-size: 10px;
    background: transparent;
}
QLabel#CountChip {
    background-color: @BLUE_A@;
    color: @BLUE@;
    border: 1px solid @BLUE_B@;
    border-radius: 9px;
    padding: 2px 9px;
    font-size: 10px;
    font-weight: 700;
}
QTableWidget#DetailItemsTable {
    background-color: @BASE@;
    alternate-background-color: #1C1C2B;
    color: @TEXT@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
    font-size: 12px;
    gridline-color: transparent;
    outline: 0;
}
QTableWidget#DetailItemsTable::item {
    padding: 0 8px;
    border: none;
}
QTableWidget#DetailItemsTable::item:hover {
    background-color: @BLUE_H@;
}
QTableWidget#DetailItemsTable QHeaderView {
    background-color: transparent;
}
QTableWidget#DetailItemsTable QHeaderView::section {
    background-color: @SURFACE_HI@;
    color: @MUTED@;
    border: none;
    border-bottom: 1px solid @BORDER@;
    padding: 0 8px;
    font-size: 10px;
    font-weight: 700;
}
QTableWidget#DetailItemsTable QTableCornerButton::section {
    background-color: @SURFACE_HI@;
    border: none;
}

/* ---------- Kartu total ---------- */
QFrame#PaymentPanel {
    background-color: @BASE@;
    border: 1px solid @BORDER@;
    border-radius: 9px;
}
QLabel#RowCaption {
    color: @SUBTEXT@;
    font-size: 12px;
    background: transparent;
}
QLabel#RowValue {
    color: @TEXT@;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#RowValueDiscount {
    color: @RED@;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#RowValueTip {
    color: @TEAL@;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QFrame#DetailUnpaidBox {
    background-color: @RED_A@;
    border: 1px solid @RED_B@;
    border-radius: 7px;
}
QLabel#DetailUnpaidLabel {
    color: @RED@;
    font-size: 12px;
    font-weight: 700;
    background: transparent;
}
QLabel#DetailUnpaidCaption {
    color: #FCA5A5;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}
QFrame#NotesBox {
    background-color: @YELLOW_A@;
    border: 1px solid @YELLOW_B@;
    border-radius: 7px;
}
QLabel#NotesLabel {
    color: @YELLOW@;
    font-size: 11px;
    font-style: italic;
    background: transparent;
}
QFrame#Divider {
    background-color: @BORDER@;
    border: none;
    max-height: 1px;
    min-height: 1px;
}
QFrame#TotalBox {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 @GREEN_A@, stop:1 @TEAL_A@);
    border: 1px solid @GREEN_B@;
    border-radius: 9px;
}
QLabel#TotalCaption {
    color: @GREEN@;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    background: transparent;
}
QLabel#TotalValue {
    color: #FFFFFF;
    font-size: 19px;
    font-weight: 800;
    background: transparent;
}

/* ---------- Tombol ---------- */
QPushButton#PayDebtButton,
QPushButton#ViewPaymentsButton,
QPushButton#PrintButton,
QPushButton#CloseButton {
    border-radius: 8px;
    padding: 0px 16px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#PayDebtButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F59E0B, stop:1 #F97316);
    color: #FFFFFF;
    border: none;
}
QPushButton#PayDebtButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FBBF24, stop:1 #FB923C);
}
QPushButton#PayDebtButton:pressed { background: #C2410C; }
QPushButton#ViewPaymentsButton {
    background-color: @GREEN_A@;
    color: @GREEN@;
    border: 1px solid @GREEN_B@;
}
QPushButton#ViewPaymentsButton:hover {
    background-color: #10B981;
    color: #FFFFFF;
    border-color: #10B981;
}
QPushButton#ViewPaymentsButton:pressed { background-color: #047857; }
QPushButton#PrintButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #8B5CF6);
    color: #FFFFFF;
    border: none;
}
QPushButton#PrintButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #7C3AED);
}
QPushButton#PrintButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #6D28D9);
}
QPushButton#CloseButton {
    background-color: @SURFACE_HI@;
    color: @TEXT@;
    border: 1px solid #3B3D54;
}
QPushButton#CloseButton:hover {
    background-color: @BORDER@;
    border-color: @BORDER_HI@;
    color: #FFFFFF;
}
QPushButton#CloseButton:pressed { background-color: @SURFACE@; }

/* ---------- Scrollbar ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 0;
}
QScrollBar::handle:vertical {
    background: @BORDER_HI@;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: @BLUE@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}
QToolTip {
    background-color: @SURFACE_HI@;
    color: @TEXT@;
    border: 1px solid @BORDER_HI@;
    padding: 5px 8px;
}
"""


def _build_qss() -> str:
    """Mengganti token warna pada template QSS dialog.

    Returns:
        String QSS final.
    """
    tokens = {
        "@BASE_A@": _rgba(_C.BASE, 0.55),
        "@BASE@": _C.BASE,
        "@SURFACE_HI@": _C.SURFACE_HI,
        "@SURFACE@": _C.SURFACE,
        "@BORDER_HI@": _C.BORDER_HI,
        "@BORDER@": _C.BORDER,
        "@SUBTEXT@": _C.SUBTEXT,
        "@MUTED@": _C.MUTED,
        "@TEXT@": _C.TEXT,
        "@BLUE_A@": _rgba(_C.BLUE, 0.16),
        "@BLUE_B@": _rgba(_C.BLUE, 0.32),
        "@BLUE_H@": _rgba(_C.BLUE, 0.08),
        "@BLUE@": _C.BLUE,
        "@MAUVE_A@": _rgba(_C.MAUVE, 0.13),
        "@PINK_A@": _rgba(_C.PINK, 0.10),
        "@GREEN_A@": _rgba(_C.GREEN, 0.12),
        "@GREEN_B@": _rgba(_C.GREEN, 0.38),
        "@GREEN@": _C.GREEN,
        "@TEAL_A@": _rgba(_C.TEAL, 0.08),
        "@TEAL@": _C.TEAL,
        "@RED_A@": _rgba(_C.RED, 0.12),
        "@RED_B@": _rgba(_C.RED, 0.38),
        "@RED@": _C.RED,
        "@YELLOW_A@": _rgba(_C.YELLOW, 0.07),
        "@YELLOW_B@": _rgba(_C.YELLOW, 0.25),
        "@YELLOW@": _C.YELLOW,
    }
    qss = _DIALOG_QSS
    for key, value in tokens.items():
        qss = qss.replace(key, value)
    return qss


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
        self.setMinimumSize(700, 540)
        self.resize(740, 580)
        self.content_widget.setStyleSheet(_build_qss())
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Menyusun antarmuka dan komponen tata letak dialog detail."""
        self._main_layout = QVBoxLayout(self.content_widget)
        self._main_layout.setContentsMargins(12, 8, 12, 10)
        self._main_layout.setSpacing(8)

        self._header_card = self._build_header_card()
        self._main_layout.addWidget(self._header_card)

        self._items_table = self._build_items_table()
        self._main_layout.addWidget(self._wrap_items_card(self._items_table), stretch=1)

        self._totals_card = self._build_totals_card()
        self._main_layout.addWidget(self._totals_card)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(8)

        self.pay_debt_btn = _HoverIconButton("Bayar Hutang", "wallet", "#FFFFFF", "#FFFFFF", self)
        self.pay_debt_btn.setObjectName("PayDebtButton")
        self.pay_debt_btn.setFixedHeight(34)
        self.pay_debt_btn.clicked.connect(self._on_pay_debt_clicked)
        self.pay_debt_btn.setVisible(self._is_unpaid())

        self.view_payments_btn = _HoverIconButton(
            "Lihat Pembayaran", "history", _C.GREEN, "#FFFFFF", self
        )
        self.view_payments_btn.setObjectName("ViewPaymentsButton")
        self.view_payments_btn.setFixedHeight(34)
        self.view_payments_btn.clicked.connect(self._on_view_payments_clicked)
        self.view_payments_btn.setVisible(self._can_view_payments())

        print_btn = _HoverIconButton("Cetak Struk", "printer", "#FFFFFF", "#FFFFFF", self)
        print_btn.setObjectName("PrintButton")
        print_btn.setFixedHeight(34)
        print_btn.setMinimumWidth(130)
        print_btn.clicked.connect(self._on_print_clicked)

        close_btn = _HoverIconButton("Tutup", "close", _C.SUBTEXT, "#FFFFFF", self, icon_size=14)
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedHeight(34)
        close_btn.setMinimumWidth(96)
        close_btn.clicked.connect(self.accept)

        footer_layout.addWidget(self.pay_debt_btn)
        footer_layout.addWidget(self.view_payments_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(print_btn)
        footer_layout.addWidget(close_btn)
        self._main_layout.addLayout(footer_layout)

    def _make_icon_badge(self, parent: QWidget, icon: str, accent: str, size: int = 28) -> QLabel:
        """Membuat lencana ikon persegi membulat dengan warna aksen.

        Args:
            parent: Widget induk.
            icon: Kunci ikon SVG.
            accent: Warna aksen ikon dan latar.
            size: Ukuran sisi lencana.

        Returns:
            QLabel berisi ikon.
        """
        badge = QLabel(parent)
        badge.setFixedSize(size, size)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(_svg_pixmap(icon, int(size * 0.55), accent, 2.2))
        badge.setStyleSheet(
            f"background-color: {_rgba(accent, 0.15)};"
            f"border: 1px solid {_rgba(accent, 0.38)};"
            "border-radius: 8px;"
        )
        return badge

    def _make_meta_tile(self, parent: QWidget, icon: str, accent: str, caption: str, value: str) -> QFrame:
        """Membuat ubin metadata kecil berisi ikon, keterangan, dan nilai.

        Args:
            parent: Widget induk.
            icon: Kunci ikon SVG.
            accent: Warna aksen ikon.
            caption: Teks keterangan kecil di atas nilai.
            value: Nilai metadata.

        Returns:
            Frame ubin metadata.
        """
        tile = QFrame(parent)
        tile.setObjectName("MetaTile")
        layout = QHBoxLayout(tile)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        cap = QLabel(caption.upper(), tile)
        cap.setObjectName("MetaCaption")
        val = QLabel(value, tile)
        val.setObjectName("MetaValue")
        val.setToolTip(value)
        text_col.addWidget(cap)
        text_col.addWidget(val)

        layout.addWidget(self._make_icon_badge(tile, icon, accent, 22))
        layout.addLayout(text_col, 1)
        return tile

    def _build_header_card(self) -> QFrame:
        """Membangun kartu informasi metadata faktur."""
        meta = self.detail.metadata
        card = QFrame(self)
        card.setObjectName("DetailHeaderCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        badge = QLabel(card)
        badge.setObjectName("InvoiceBadge")
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(_svg_pixmap("receipt", 18, "#FFFFFF", 2.0))

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)
        caption = QLabel("NOMOR FAKTUR", card)
        caption.setObjectName("InvoiceCaption")
        invoice_label = QLabel(meta.invoice_number, card)
        invoice_label.setObjectName("InvoiceNumber")
        invoice_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_col.addWidget(caption)
        title_col.addWidget(invoice_label)

        is_paid = self.detail.payment.payment_status.upper() == "PAID"
        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(0)
        status = QLabel(card)
        status.setObjectName("StatusPaid" if is_paid else "StatusUnpaid")
        status_color = _C.GREEN if is_paid else _C.RED
        icon_name = "check_circle" if is_paid else "alert_circle"
        status.setTextFormat(Qt.TextFormat.RichText)
        status.setText(
            f'<table cellspacing="0" cellpadding="0"><tr>'
            f'<td valign="middle">{self._inline_icon_html(icon_name, status_color)}</td>'
            f'<td valign="middle">&nbsp;{"LUNAS" if is_paid else "BELUM LUNAS"}</td>'
            f"</tr></table>"
        )
        status.setFixedHeight(26)
        status_wrap.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)

        top_row.addWidget(badge)
        top_row.addLayout(title_col, 1)
        top_row.addLayout(status_wrap)
        top_row.setAlignment(status_wrap, Qt.AlignmentFlag.AlignTop)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(self._make_meta_tile(card, "calendar", _C.BLUE, "Waktu", str(meta.sale_date)), 0, 0)
        grid.addWidget(self._make_meta_tile(card, "user", _C.MAUVE, "Kasir", str(meta.cashier_name)), 0, 1)
        grid.addWidget(
            self._make_meta_tile(card, "users", _C.PEACH, "Pelanggan", str(meta.customer_name)), 1, 0
        )
        grid.addWidget(
            self._make_meta_tile(
                card, "card", _C.TEAL, "Metode Bayar", str(self.detail.payment.payment_method)
            ),
            1,
            1,
        )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        outer.addLayout(top_row)
        outer.addLayout(grid)
        return card

    @staticmethod
    def _inline_icon_html(icon: str, color: str, size: int = 14) -> str:
        """Membuat potongan HTML <img> berisi ikon SVG untuk label RichText.

        Args:
            icon: Kunci ikon SVG.
            color: Warna ikon.
            size: Ukuran ikon.

        Returns:
            String HTML tag img dengan data URI base64 PNG.
        """
        pixmap = _svg_pixmap(icon, size, color, 2.4)
        buffer = QByteArray()
        device = QBuffer(buffer)
        device.open(QIODevice.OpenModeFlag.WriteOnly)
        writer = QImageWriter(device, QByteArray(b"PNG"))
        writer.write(pixmap.toImage())
        device.close()
        b64 = bytes(buffer.toBase64().data()).decode("ascii")
        return f'<img src="data:image/png;base64,{b64}" width="{size}" height="{size}">'

    def _wrap_items_card(self, table: QTableWidget) -> QFrame:
        """Membungkus tabel item dalam kartu berjudul.

        Args:
            table: Tabel item faktur.

        Returns:
            Frame kartu berisi judul seksi dan tabel.
        """
        card = QFrame(self)
        card.setObjectName("ItemsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        title = QLabel("Daftar Barang & Jasa", card)
        title.setObjectName("SectionTitle")
        sub = QLabel("Rincian item yang tercatat pada faktur ini", card)
        sub.setObjectName("SectionSubtitle")
        text_col.addWidget(title)
        text_col.addWidget(sub)

        count = QLabel(f"{len(self.detail.items)} item", card)
        count.setObjectName("CountChip")

        header.addWidget(self._make_icon_badge(card, "cart", _C.BLUE, 24))
        header.addLayout(text_col, 1)
        header.addWidget(count, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header)
        layout.addWidget(table, 1)
        return card

    def _build_items_table(self) -> QTableWidget:
        """Membangun tabel daftar barang dan jasa pada faktur (read-only)."""
        table = QTableWidget(self)
        table.setObjectName("DetailItemsTable")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["NO", "BARANG / JASA", "QTY", "HARGA", "SUBTOTAL"])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setMinimumHeight(110)

        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        table.setTabKeyNavigation(False)

        header = table.horizontalHeader()
        header.setFixedHeight(26)
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setSectionsMovable(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 44)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 64)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 132)

        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for col, align in (
            (0, Qt.AlignmentFlag.AlignCenter),
            (1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            (2, Qt.AlignmentFlag.AlignCenter),
            (3, align_right),
            (4, align_right),
        ):
            head_item = table.horizontalHeaderItem(col)
            if head_item is not None:
                head_item.setTextAlignment(align)

        read_only_flags = Qt.ItemFlag.ItemIsEnabled
        bold = QFont()
        bold.setBold(True)

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
            col_no.setForeground(QColor(_C.MUTED))

            col_desc = QTableWidgetItem(it.description)
            col_desc.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            col_desc.setToolTip(it.description)

            col_qty = QTableWidgetItem(qty_str)
            col_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            col_qty.setForeground(QColor(_C.BLUE))
            col_qty.setFont(bold)

            col_price = QTableWidgetItem(format_rupiah(it.unit_price))
            col_price.setTextAlignment(align_right)
            col_price.setForeground(QColor(_C.SUBTEXT))

            col_sub = QTableWidgetItem(format_rupiah(it.subtotal))
            col_sub.setTextAlignment(align_right)
            col_sub.setForeground(QColor(_C.GREEN))
            col_sub.setFont(bold)

            for col, cell in enumerate((col_no, col_desc, col_qty, col_price, col_sub)):
                cell.setFlags(read_only_flags)
                table.setItem(idx - 1, col, cell)
            table.setRowHeight(idx - 1, 28)

        return table

    def _make_amount_row(self, parent: QWidget, caption: str, value: str, value_name: str = "RowValue") -> QHBoxLayout:
        """Membuat baris label-nilai rata kiri-kanan untuk ringkasan nominal.

        Args:
            parent: Widget induk.
            caption: Teks keterangan.
            value: Teks nilai nominal.
            value_name: objectName label nilai untuk pewarnaan QSS.

        Returns:
            QHBoxLayout berisi dua label.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        cap = QLabel(caption, parent)
        cap.setObjectName("RowCaption")
        val = QLabel(value, parent)
        val.setObjectName(value_name)
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(cap)
        row.addStretch(1)
        row.addWidget(val)
        return row

    def _make_icon_row(self, parent: QWidget, icon: str, accent: str, caption: str, value: str) -> QHBoxLayout:
        """Membuat baris berikon untuk panel informasi pembayaran.

        Args:
            parent: Widget induk.
            icon: Kunci ikon SVG.
            accent: Warna ikon.
            caption: Teks keterangan.
            value: Teks nilai nominal.

        Returns:
            QHBoxLayout berisi ikon, keterangan, dan nilai.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        icon_label = QLabel(parent)
        icon_label.setPixmap(_svg_pixmap(icon, 15, accent))
        icon_label.setStyleSheet("background: transparent;")
        cap = QLabel(caption, parent)
        cap.setObjectName("RowCaption")
        val = QLabel(value, parent)
        val.setObjectName("RowValue")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(icon_label)
        row.addWidget(cap)
        row.addStretch(1)
        row.addWidget(val)
        return row

    def _build_totals_card(self) -> QFrame:
        """Membangun kartu ringkasan nominal subtotal, diskon, pembulatan, dan total."""
        card = QFrame(self)
        card.setObjectName("DetailTotalsCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        left_panel = QFrame(card)
        left_panel.setObjectName("PaymentPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 8, 10, 8)
        left_layout.setSpacing(5)

        paid_str = format_rupiah(self.detail.payment.amount_paid)
        change_str = format_rupiah(self.detail.payment.change_amount)

        left_layout.addLayout(self._make_icon_row(left_panel, "cash", _C.GREEN, "Jumlah Diterima", paid_str))
        left_layout.addLayout(self._make_icon_row(left_panel, "coins_back", _C.PEACH, "Kembalian", change_str))

        if self.detail.payment.payment_status.strip().upper() != "PAID":
            remaining_str = format_rupiah(self.detail.payment.remaining_amount)
            unpaid_box = QFrame(left_panel)
            unpaid_box.setObjectName("DetailUnpaidBox")
            unpaid_layout = QHBoxLayout(unpaid_box)
            unpaid_layout.setContentsMargins(9, 6, 10, 6)
            unpaid_layout.setSpacing(8)
            unpaid_icon = QLabel(unpaid_box)
            unpaid_icon.setPixmap(_svg_pixmap("alert_circle", 15, _C.RED))
            unpaid_icon.setStyleSheet("background: transparent;")
            unpaid_caption = QLabel("Belum Terbayarkan", unpaid_box)
            unpaid_caption.setObjectName("DetailUnpaidCaption")
            unpaid_label = QLabel(remaining_str, unpaid_box)
            unpaid_label.setObjectName("DetailUnpaidLabel")
            unpaid_layout.addWidget(unpaid_icon)
            unpaid_layout.addWidget(unpaid_caption)
            unpaid_layout.addStretch(1)
            unpaid_layout.addWidget(unpaid_label)
            left_layout.addWidget(unpaid_box)

        if self.detail.metadata.notes:
            notes_box = QFrame(left_panel)
            notes_box.setObjectName("NotesBox")
            notes_layout = QHBoxLayout(notes_box)
            notes_layout.setContentsMargins(9, 6, 10, 6)
            notes_layout.setSpacing(8)
            notes_icon = QLabel(notes_box)
            notes_icon.setPixmap(_svg_pixmap("note", 14, _C.YELLOW))
            notes_icon.setStyleSheet("background: transparent;")
            notes_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
            notes_label = QLabel(str(self.detail.metadata.notes), notes_box)
            notes_label.setTextFormat(Qt.TextFormat.PlainText)
            notes_label.setObjectName("NotesLabel")
            notes_label.setWordWrap(True)
            notes_layout.addWidget(notes_icon, 0, Qt.AlignmentFlag.AlignTop)
            notes_layout.addWidget(notes_label, 1)
            left_layout.addWidget(notes_box)

        left_layout.addStretch(1)
        layout.addWidget(left_panel, stretch=1)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(2, 0, 0, 0)
        right_layout.setSpacing(4)

        subtotal_str = format_rupiah(self.detail.amounts.subtotal)
        discount_str = format_rupiah(self.detail.amounts.discount)
        tip_str = format_rupiah(self.detail.amounts.tip)
        rounding_str = format_rupiah(self.detail.amounts.rounding, show_sign=True)
        total_str = format_rupiah(self.detail.amounts.total)

        right_layout.addLayout(self._make_amount_row(card, "Subtotal", subtotal_str))

        if self.detail.amounts.discount > 0:
            right_layout.addLayout(
                self._make_amount_row(card, "Diskon", f"-{discount_str}", "RowValueDiscount")
            )

        if self.detail.amounts.tip > 0:
            right_layout.addLayout(self._make_amount_row(card, "Tip", f"+{tip_str}", "RowValueTip"))

        if self.detail.amounts.rounding != 0:
            right_layout.addLayout(self._make_amount_row(card, "Pembulatan", rounding_str))

        right_layout.addStretch(1)

        total_box = QFrame(card)
        total_box.setObjectName("TotalBox")
        total_layout = QHBoxLayout(total_box)
        total_layout.setContentsMargins(10, 6, 10, 6)
        total_layout.setSpacing(8)
        total_icon = QLabel(total_box)
        total_icon.setPixmap(_svg_pixmap("calculator", 18, _C.GREEN))
        total_icon.setStyleSheet("background: transparent;")
        total_caption = QLabel("TOTAL", total_box)
        total_caption.setObjectName("TotalCaption")
        total_label = QLabel(total_str, total_box)
        total_label.setObjectName("TotalValue")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_layout.addWidget(total_icon)
        total_layout.addWidget(total_caption)
        total_layout.addStretch(1)
        total_layout.addWidget(total_label)

        right_layout.addWidget(total_box)
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
        self._header_card.hide()
        self._header_card.deleteLater()
        self._header_card = new_header

        new_totals = self._build_totals_card()
        self._main_layout.replaceWidget(self._totals_card, new_totals)
        self._totals_card.hide()
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