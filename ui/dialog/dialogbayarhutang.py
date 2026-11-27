"""Modul dialog antarmuka pengguna untuk pembayaran hutang atau cicilan transaksi.

Tampilan dibangun ulang dengan ikon SVG inline, kartu ringkasan berwarna,
progress pelunasan, pemilih metode bayar bergaya segmen, dan tabel riwayat
read-only. Logika validasi, properti hasil, dan pencatatan log tidak berubah.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, QEvent, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QIntValidator,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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


# ---------------------------------------------------------------------------
# Palet warna
# ---------------------------------------------------------------------------
class _C:
    """Konstanta palet warna dialog (turunan Catppuccin Mocha, lebih vivid)."""

    CRUST = "#11111B"
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


# ---------------------------------------------------------------------------
# Ikon SVG inline
# ---------------------------------------------------------------------------
_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS: dict[str, str] = {
    "wallet": (
        '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/>'
        '<path d="M21 9h-5a3 3 0 0 0 0 6h5z"/><path d="M16 12h.01"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>'
    ),
    "users": (
        '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/>'
        '<path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14a6.5 6.5 0 0 1 3.5 6"/>'
    ),
    "receipt": (
        '<path d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5L10 21l-2.5-1.5L5 21z"/>'
        '<path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h3"/>'
    ),
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16 10"/>',
    "alert_circle": '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5"/><path d="M12 16h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "cash": (
        '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>'
        '<path d="M6 12h.01"/><path d="M18 12h.01"/>'
    ),
    "qris": (
        '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3z"/>'
        '<path d="M21 14v.01"/><path d="M21 21h-4v-4"/>'
    ),
    "bank": (
        '<path d="M3 10 12 4l9 6"/><path d="M5 10v8"/><path d="M9.5 10v8"/>'
        '<path d="M14.5 10v8"/><path d="M19 10v8"/><path d="M3 21h18"/>'
    ),
    "coins": (
        '<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1 1 10.3 18"/>'
        '<path d="M7 6h1v4"/>'
    ),
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "note": (
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'
    ),
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "inbox": (
        '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
    ),
}

_METHOD_ICONS: dict[str, tuple[str, str]] = {
    "tunai": ("cash", _C.GREEN),
    "qris": ("qris", _C.MAUVE),
    "transfer": ("bank", _C.BLUE),
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
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    dpr = 2.0
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def _svg_icon(name: str, color: str, size: int = 16) -> QIcon:
    """Membuat QIcon dari ikon SVG inline.

    Args:
        name: Kunci ikon pada kamus _ICONS.
        color: Warna goresan ikon.
        size: Ukuran ikon.

    Returns:
        Objek QIcon siap pakai.
    """
    return QIcon(_svg_pixmap(name, size, color))


# ---------------------------------------------------------------------------
# Widget kustom
# ---------------------------------------------------------------------------
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


class _ProgressBar(QWidget):
    """Bar progres pelunasan bergradien yang digambar kustom."""

    def __init__(self, ratio: float, parent: QWidget | None = None) -> None:
        """Menginisialisasi bar progres.

        Args:
            ratio: Rasio progres 0.0 hingga 1.0.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, ratio))
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar track dan isi progres."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_C.BORDER))
        painter.drawRoundedRect(rect, radius, radius)
        if self._ratio > 0:
            fill = QRectF(rect.left(), rect.top(), max(rect.height(), rect.width() * self._ratio), rect.height())
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0.0, QColor("#22C55E"))
            grad.setColorAt(1.0, QColor(_C.TEAL))
            painter.setBrush(grad)
            painter.drawRoundedRect(fill, radius, radius)
        painter.end()


_DIALOG_QSS = """
QWidget#CustomDialogContent {
    background-color: @BASE@;
    color: @TEXT@;
}

/* ---------- Kartu ringkasan ---------- */
QFrame#DebtSummaryCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 @PEACH_A@, stop:0.5 @PINK_A@, stop:1 @MAUVE_A@);
    border: 1px solid @PEACH_B@;
    border-radius: 12px;
}
QFrame#DebtSummaryCard[readOnly="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 @GREEN_A@, stop:0.5 @TEAL_A@, stop:1 @BLUE_A@);
    border: 1px solid @GREEN_B@;
}
QLabel#HeaderBadge {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #EC4899);
    border-radius: 12px;
}
QLabel#HeaderBadgeRead {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #3B82F6);
    border-radius: 12px;
}
QLabel#HeaderCaption {
    color: @SUBTEXT@;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}
QLabel#HeaderInvoice {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    background: transparent;
}
QLabel#HeaderCustomer {
    color: @TEXT@;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QFrame#StatTile {
    background-color: @BASE_A@;
    border: 1px solid @BORDER@;
    border-radius: 9px;
}
QLabel#StatCaption {
    color: @MUTED@;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}
QLabel#StatValueTotal, QLabel#StatValuePaid, QLabel#StatValueRemain {
    font-size: 13px;
    font-weight: 800;
    background: transparent;
}
QLabel#StatValueTotal { color: @BLUE@; }
QLabel#StatValuePaid { color: @GREEN@; }
QLabel#StatValueRemain { color: @RED@; }
QLabel#ProgressText {
    color: @SUBTEXT@;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}

/* ---------- Kartu umum ---------- */
QFrame#HistoryCard, QFrame#DebtInputCard {
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
QLabel#FieldLabel {
    color: @SUBTEXT@;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ---------- Tabel riwayat ---------- */
QTableWidget#PreviousPaymentsTable {
    background-color: @BASE@;
    alternate-background-color: #1C1C2B;
    color: @TEXT@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
    font-size: 12px;
    gridline-color: transparent;
    outline: 0;
}
QTableWidget#PreviousPaymentsTable::item {
    padding: 0 6px;
    border: none;
}
QTableWidget#PreviousPaymentsTable::item:hover {
    background-color: @BLUE_H@;
}
QTableWidget#PreviousPaymentsTable QHeaderView {
    background-color: transparent;
}
QTableWidget#PreviousPaymentsTable QHeaderView::section {
    background-color: @SURFACE_HI@;
    color: @MUTED@;
    border: none;
    border-bottom: 1px solid @BORDER@;
    padding: 0 6px;
    font-size: 10px;
    font-weight: 700;
}
QFrame#EmptyState {
    background-color: @BASE@;
    border: 1px dashed @BORDER_HI@;
    border-radius: 8px;
}
QLabel#EmptyTitle {
    color: @SUBTEXT@;
    font-size: 12px;
    font-weight: 700;
    background: transparent;
}
QLabel#EmptySubtitle {
    color: @MUTED@;
    font-size: 11px;
    background: transparent;
}

/* ---------- Input ---------- */
QFrame#NominalWrap {
    background-color: @CRUST@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
}
QFrame#NominalWrap:hover { border: 1px solid @BORDER_HI@; }
QLabel#NominalPrefix {
    color: @GREEN@;
    font-size: 14px;
    font-weight: 800;
    background: transparent;
    padding-left: 4px;
}
QLineEdit#DebtNominalInput {
    background: transparent;
    border: none;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
    padding: 0 4px;
    selection-background-color: #3B82F6;
}
QPushButton#FillButton {
    background-color: @BLUE_A@;
    color: @BLUE@;
    border: 1px solid @BLUE_B@;
    border-radius: 6px;
    padding: 0 10px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#FillButton:hover {
    background-color: #3B82F6;
    color: #FFFFFF;
    border-color: #3B82F6;
}
QPushButton#MethodSegment {
    background-color: @CRUST@;
    color: @SUBTEXT@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
    padding: 0 10px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
}
QPushButton#MethodSegment:hover {
    border-color: @BORDER_HI@;
    color: @TEXT@;
}
QPushButton#MethodSegment:checked {
    background-color: @BLUE_A@;
    color: #FFFFFF;
    border: 1px solid @BLUE@;
}
QTextEdit#DebtNotesInput {
    background-color: @CRUST@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
    padding: 4px 6px;
    color: @TEXT@;
    font-size: 12px;
    selection-background-color: #3B82F6;
}
QTextEdit#DebtNotesInput:hover { border: 1px solid @BORDER_HI@; }
QTextEdit#DebtNotesInput:focus { border: 1px solid @BLUE@; }

/* ---------- Feedback ---------- */
QFrame#FeedbackBox {
    border-radius: 8px;
    background-color: @SURFACE@;
    border: 1px solid @BORDER@;
}
QFrame#FeedbackBox[state="paid"] {
    background-color: @GREEN_A@;
    border: 1px solid @GREEN_B@;
}
QFrame#FeedbackBox[state="partial"] {
    background-color: @YELLOW_A@;
    border: 1px solid @YELLOW_B@;
}
QFrame#FeedbackBox[state="error"] {
    background-color: @RED_A@;
    border: 1px solid @RED_B@;
}
QLabel#FeedbackLabel {
    background: transparent;
    font-size: 12px;
    color: @SUBTEXT@;
}
QLabel#FeedbackLabel[state="paid"] { color: @GREEN@; font-weight: 700; }
QLabel#FeedbackLabel[state="partial"] { color: #FBBF24; font-weight: 700; }
QLabel#FeedbackLabel[state="error"] { color: @RED@; font-weight: 700; }

/* ---------- Tombol ---------- */
QPushButton#CancelButton, QPushButton#SubmitButton {
    border-radius: 8px;
    padding: 0px 18px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#CancelButton {
    background-color: @SURFACE_HI@;
    color: @TEXT@;
    border: 1px solid #3B3D54;
}
QPushButton#CancelButton:hover {
    background-color: @BORDER@;
    border-color: @BORDER_HI@;
    color: #FFFFFF;
}
QPushButton#CancelButton:pressed { background-color: @SURFACE@; }
QPushButton#SubmitButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22C55E, stop:1 #14B8A6);
    color: #FFFFFF;
    border: none;
}
QPushButton#SubmitButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4ADE80, stop:1 #2DD4BF);
}
QPushButton#SubmitButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #15803D, stop:1 #0F766E);
}

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
        "@CRUST@": _C.CRUST,
        "@BASE@": _C.BASE,
        "@SURFACE_HI@": _C.SURFACE_HI,
        "@SURFACE@": _C.SURFACE,
        "@BORDER_HI@": _C.BORDER_HI,
        "@BORDER@": _C.BORDER,
        "@SUBTEXT@": _C.SUBTEXT,
        "@MUTED@": _C.MUTED,
        "@TEXT@": _C.TEXT,
        "@BLUE_A@": _rgba(_C.BLUE, 0.16),
        "@BLUE_B@": _rgba(_C.BLUE, 0.34),
        "@BLUE_H@": _rgba(_C.BLUE, 0.08),
        "@BLUE@": _C.BLUE,
        "@MAUVE_A@": _rgba(_C.MAUVE, 0.10),
        "@PINK_A@": _rgba(_C.PINK, 0.10),
        "@PEACH_A@": _rgba(_C.PEACH, 0.16),
        "@PEACH_B@": _rgba(_C.PEACH, 0.34),
        "@GREEN_A@": _rgba(_C.GREEN, 0.12),
        "@GREEN_B@": _rgba(_C.GREEN, 0.38),
        "@GREEN@": _C.GREEN,
        "@TEAL_A@": _rgba(_C.TEAL, 0.08),
        "@RED_A@": _rgba(_C.RED, 0.12),
        "@RED_B@": _rgba(_C.RED, 0.38),
        "@RED@": _C.RED,
        "@YELLOW_A@": _rgba(_C.YELLOW, 0.09),
        "@YELLOW_B@": _rgba(_C.YELLOW, 0.32),
    }
    qss = _DIALOG_QSS
    for key, value in tokens.items():
        qss = qss.replace(key, value)
    return qss


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
            self.setMinimumSize(700, 420)
            self.resize(740, 450)
        else:
            self.setWindowTitle(f"Bayar Hutang - {detail.metadata.invoice_number}")
            self.setMinimumSize(700, 540)
            self.resize(740, 580)

        self.content_widget.setStyleSheet(_build_qss())
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

    # ------------------------------------------------------------------
    # Penyusunan UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Menyusun komponen antarmuka dialog pembayaran hutang."""
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(12, 8, 12, 10)
        main_layout.setSpacing(7)

        main_layout.addWidget(self._build_summary_card())

        self.payments_table = self._build_payments_table()
        main_layout.addWidget(self._wrap_history_card(self.payments_table), stretch=1)

        if not self._read_only:
            main_layout.addWidget(self._build_input_card())

            self._feedback_box = QFrame(self)
            self._feedback_box.setObjectName("FeedbackBox")
            feedback_layout = QHBoxLayout(self._feedback_box)
            feedback_layout.setContentsMargins(10, 5, 10, 5)
            feedback_layout.setSpacing(8)
            self._feedback_icon = QLabel(self._feedback_box)
            self._feedback_icon.setFixedSize(16, 16)
            self._feedback_icon.setStyleSheet("background: transparent;")
            self.feedback_label = QLabel(self._feedback_box)
            self.feedback_label.setObjectName("FeedbackLabel")
            self.feedback_label.setWordWrap(True)
            feedback_layout.addWidget(self._feedback_icon)
            feedback_layout.addWidget(self.feedback_label, 1)
            main_layout.addWidget(self._feedback_box)
            self._update_preview()

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(8)

        cancel_label = "Tutup" if self._read_only else "Batal"
        cancel_btn = _HoverIconButton(cancel_label, "close", _C.SUBTEXT, "#FFFFFF", self, icon_size=14)
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(96)
        cancel_btn.clicked.connect(self._on_cancel_clicked)

        self.submit_btn = _HoverIconButton("Simpan Pembayaran", "check", "#FFFFFF", "#FFFFFF", self)
        self.submit_btn.setObjectName("SubmitButton")
        self.submit_btn.setFixedHeight(34)
        self.submit_btn.setMinimumWidth(170)
        self.submit_btn.clicked.connect(self._on_submit_clicked)

        footer_layout.addStretch()
        footer_layout.addWidget(cancel_btn)
        if not self._read_only:
            footer_layout.addWidget(self.submit_btn)
        else:
            self.submit_btn.hide()
        main_layout.addLayout(footer_layout)

    def _make_icon_badge(self, parent: QWidget, icon: str, accent: str, size: int = 24) -> QLabel:
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

    def _make_section_header(
        self, parent: QWidget, icon: str, accent: str, title: str, subtitle: str
    ) -> QHBoxLayout:
        """Membangun baris judul seksi dengan ikon, judul, dan keterangan.

        Args:
            parent: Widget induk.
            icon: Kunci ikon SVG.
            accent: Warna aksen seksi.
            title: Judul seksi.
            subtitle: Keterangan singkat seksi.

        Returns:
            QHBoxLayout yang masih bisa ditambahi widget di sisi kanan.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        title_lbl = QLabel(title, parent)
        title_lbl.setObjectName("SectionTitle")
        sub_lbl = QLabel(subtitle, parent)
        sub_lbl.setObjectName("SectionSubtitle")
        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)
        row.addWidget(self._make_icon_badge(parent, icon, accent))
        row.addLayout(text_col, 1)
        return row

    def _make_stat_tile(self, parent: QWidget, caption: str, value: str, value_name: str) -> QFrame:
        """Membuat ubin statistik nominal.

        Args:
            parent: Widget induk.
            caption: Teks keterangan.
            value: Nilai nominal.
            value_name: objectName label nilai untuk pewarnaan QSS.

        Returns:
            Frame ubin statistik.
        """
        tile = QFrame(parent)
        tile.setObjectName("StatTile")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)
        cap = QLabel(caption.upper(), tile)
        cap.setObjectName("StatCaption")
        val = QLabel(value, tile)
        val.setObjectName(value_name)
        layout.addWidget(cap)
        layout.addWidget(val)
        return tile

    def _build_summary_card(self) -> QFrame:
        """Membangun kartu ringkasan tagihan dan sisa hutang faktur."""
        card = QFrame(self)
        card.setObjectName("DebtSummaryCard")
        card.setProperty("readOnly", "true" if self._read_only else "false")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        badge = QLabel(card)
        badge.setObjectName("HeaderBadgeRead" if self._read_only else "HeaderBadge")
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(_svg_pixmap("history" if self._read_only else "wallet", 18, "#FFFFFF", 2.0))

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        caption = QLabel("RIWAYAT PEMBAYARAN" if self._read_only else "PEMBAYARAN HUTANG", card)
        caption.setObjectName("HeaderCaption")
        inv_lbl = QLabel(self.detail.metadata.invoice_number, card)
        inv_lbl.setObjectName("HeaderInvoice")
        inv_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_col.addWidget(caption)
        title_col.addWidget(inv_lbl)

        cust_row = QHBoxLayout()
        cust_row.setSpacing(6)
        cust_icon = QLabel(card)
        cust_icon.setPixmap(_svg_pixmap("users", 15, _C.PEACH))
        cust_icon.setStyleSheet("background: transparent;")
        cust_lbl = QLabel(str(self.detail.metadata.customer_name), card)
        cust_lbl.setObjectName("HeaderCustomer")
        cust_row.addWidget(cust_icon)
        cust_row.addWidget(cust_lbl)

        top_row.addWidget(badge)
        top_row.addLayout(title_col, 1)
        top_row.addLayout(cust_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        stats_row.addWidget(
            self._make_stat_tile(card, "Total Tagihan", format_rupiah(self.detail.amounts.total), "StatValueTotal"),
            1,
        )
        stats_row.addWidget(
            self._make_stat_tile(
                card, "Sudah Dibayar", format_rupiah(self.detail.payment.amount_paid), "StatValuePaid"
            ),
            1,
        )
        stats_row.addWidget(
            self._make_stat_tile(
                card,
                "Sisa Hutang",
                format_rupiah(self.detail.payment.remaining_amount),
                "StatValueRemain" if self.detail.payment.remaining_amount > 0 else "StatValuePaid",
            ),
            1,
        )

        total = max(0, int(self.detail.amounts.total))
        paid = max(0, int(self.detail.payment.amount_paid))
        ratio = 1.0 if total <= 0 else min(1.0, paid / total)
        if self.detail.payment.remaining_amount <= 0:
            ratio = 1.0

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        progress_row.addWidget(_ProgressBar(ratio, card), 1)
        progress_text = QLabel(f"{ratio * 100:.0f}% terbayar", card)
        progress_text.setObjectName("ProgressText")
        progress_row.addWidget(progress_text)

        outer.addLayout(top_row)
        outer.addLayout(stats_row)
        outer.addLayout(progress_row)
        return card

    def _wrap_history_card(self, table: QTableWidget) -> QFrame:
        """Membungkus tabel riwayat dalam kartu berjudul beserta tampilan kosong.

        Args:
            table: Tabel riwayat pembayaran.

        Returns:
            Frame kartu riwayat.
        """
        card = QFrame(self)
        card.setObjectName("HistoryCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        history_title = "Riwayat Pembayaran" if self._read_only else "Riwayat Pembayaran Sebelumnya"
        header = self._make_section_header(
            card, "clock", _C.BLUE, history_title, "Daftar cicilan yang sudah tercatat untuk faktur ini"
        )
        count = QLabel(f"{len(self.detail.payments)} pembayaran", card)
        count.setObjectName("CountChip")
        header.addWidget(count, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        if self.detail.payments:
            layout.addWidget(table, 1)
        else:
            table.hide()
            empty = QFrame(card)
            empty.setObjectName("EmptyState")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(10, 8, 10, 8)
            empty_layout.setSpacing(2)
            empty_layout.addStretch(1)
            icon = QLabel(empty)
            icon.setPixmap(_svg_pixmap("inbox", 22, _C.MUTED, 1.8))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("background: transparent;")
            title = QLabel("Belum ada pembayaran", empty)
            title.setObjectName("EmptyTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub = QLabel("Cicilan yang dicatat akan muncul di sini.", empty)
            sub.setObjectName("EmptySubtitle")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon)
            empty_layout.addWidget(title)
            empty_layout.addWidget(sub)
            empty_layout.addStretch(1)
            layout.addWidget(empty, 1)
        return card

    def _build_payments_table(self) -> QTableWidget:
        """Membangun tabel daftar detail pembayaran sebelumnya (read-only)."""
        table = QTableWidget(self)
        table.setObjectName("PreviousPaymentsTable")
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["NO", "TANGGAL", "KASIR", "METODE", "NOMINAL", "CATATAN"]
        )
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setMinimumHeight(92)

        # Read-only penuh: tanpa edit, tanpa seleksi, tanpa fokus/drag.
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
        table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 140)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 98)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 116)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        align_left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for col, align in (
            (0, Qt.AlignmentFlag.AlignCenter),
            (1, align_left),
            (2, Qt.AlignmentFlag.AlignCenter),
            (3, Qt.AlignmentFlag.AlignCenter),
            (4, align_right),
            (5, align_left),
        ):
            head_item = table.horizontalHeaderItem(col)
            if head_item is not None:
                head_item.setTextAlignment(align)

        read_only_flags = Qt.ItemFlag.ItemIsEnabled
        bold = QFont()
        bold.setBold(True)

        payments = self.detail.payments
        table.setRowCount(len(payments))

        for idx, pay in enumerate(payments, start=1):
            col_no = QTableWidgetItem(str(idx))
            col_no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            col_no.setForeground(QColor(_C.MUTED))

            col_date = QTableWidgetItem(pay.payment_date)
            col_date.setTextAlignment(align_left)
            col_date.setForeground(QColor(_C.SUBTEXT))

            col_cashier = QTableWidgetItem(pay.cashier_name.strip() or "KASIR")
            col_cashier.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_method = QTableWidgetItem(pay.payment_method)
            col_method.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_name, accent = _METHOD_ICONS.get(
                str(pay.payment_method).strip().lower(), ("coins", _C.PEACH)
            )
            col_method.setIcon(_svg_icon(icon_name, accent, 14))
            col_method.setForeground(QColor(accent))
            col_method.setFont(bold)

            col_amount = QTableWidgetItem(format_rupiah(pay.amount))
            col_amount.setTextAlignment(align_right)
            col_amount.setForeground(QColor(_C.GREEN))
            col_amount.setFont(bold)

            note_text = pay.notes.strip() or "-"
            col_notes = QTableWidgetItem(note_text)
            col_notes.setTextAlignment(align_left)
            col_notes.setToolTip(note_text)
            col_notes.setForeground(QColor(_C.TEXT if note_text != "-" else _C.MUTED))

            for col, cell in enumerate((col_no, col_date, col_cashier, col_method, col_amount, col_notes)):
                cell.setFlags(read_only_flags)
                table.setItem(idx - 1, col, cell)
            table.setRowHeight(idx - 1, 28)

        table.setIconSize(QSize(14, 14))
        return table

    def _build_input_card(self) -> QFrame:
        """Membangun panel input nominal pembayaran, metode bayar, dan catatan."""
        card = QFrame(self)
        card.setObjectName("DebtInputCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 10)
        card_layout.setSpacing(6)
        card_layout.addLayout(
            self._make_section_header(
                card, "coins", _C.GREEN, "Catat Pembayaran Baru", "Isi nominal, pilih metode, lalu simpan"
            )
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        nominal_col = QVBoxLayout()
        nominal_col.setSpacing(3)
        nominal_lbl = QLabel("Nominal Bayar (Rp)", card)
        nominal_lbl.setObjectName("FieldLabel")

        nominal_wrap = QFrame(card)
        nominal_wrap.setObjectName("NominalWrap")
        nominal_wrap.setFixedHeight(34)
        wrap_layout = QHBoxLayout(nominal_wrap)
        wrap_layout.setContentsMargins(8, 3, 3, 3)
        wrap_layout.setSpacing(4)

        prefix = QLabel("Rp", nominal_wrap)
        prefix.setObjectName("NominalPrefix")

        self.nominal_input = QLineEdit(nominal_wrap)
        self.nominal_input.setObjectName("DebtNominalInput")
        self.nominal_input.setValidator(QIntValidator(1, 1_000_000_000, self))
        self.nominal_input.setPlaceholderText(
            f"Masukkan nominal (sisa {self.detail.payment.remaining_amount})"
        )
        self.nominal_input.textChanged.connect(self._update_preview)
        self.nominal_input.returnPressed.connect(self._on_submit_clicked)

        fill_btn = _HoverIconButton("Pas", "zap", _C.BLUE, "#FFFFFF", nominal_wrap, icon_size=13)
        fill_btn.setObjectName("FillButton")
        fill_btn.setFixedHeight(26)
        fill_btn.setToolTip("Isi sesuai sisa hutang")
        fill_btn.clicked.connect(self._fill_remaining_amount)

        wrap_layout.addWidget(prefix)
        wrap_layout.addWidget(self.nominal_input, stretch=1)
        wrap_layout.addWidget(fill_btn)
        nominal_col.addWidget(nominal_lbl)
        nominal_col.addWidget(nominal_wrap)

        method_col = QVBoxLayout()
        method_col.setSpacing(3)
        method_lbl = QLabel("Metode Bayar", card)
        method_lbl.setObjectName("FieldLabel")

        self.method_combo = QComboBox(card)
        self.method_combo.setObjectName("DebtMethodCombo")
        self.method_combo.addItems(list(PAYMENT_METHOD_CHOICES))
        self.method_combo.hide()

        segment_row = QHBoxLayout()
        segment_row.setSpacing(6)
        self._method_group = QButtonGroup(self)
        self._method_group.setExclusive(True)
        for index, choice in enumerate(PAYMENT_METHOD_CHOICES):
            icon_name, accent = _METHOD_ICONS.get(choice.lower(), ("coins", _C.PEACH))
            seg = QPushButton(choice, card)
            seg.setObjectName("MethodSegment")
            seg.setCheckable(True)
            seg.setFixedHeight(34)
            seg.setCursor(Qt.CursorShape.PointingHandCursor)
            seg.setIcon(_svg_icon(icon_name, accent, 15))
            seg.setIconSize(QSize(15, 15))
            seg.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._method_group.addButton(seg, index)
            segment_row.addWidget(seg, 1)
        self._method_group.idClicked.connect(self.method_combo.setCurrentIndex)
        self.method_combo.currentIndexChanged.connect(self._sync_method_segments)
        self._sync_method_segments(self.method_combo.currentIndex())

        method_col.addWidget(method_lbl)
        method_col.addLayout(segment_row)

        top_row.addLayout(nominal_col, stretch=6)
        top_row.addLayout(method_col, stretch=6)
        card_layout.addLayout(top_row)

        notes_lbl = QLabel("Catatan Tambahan (Opsional)", card)
        notes_lbl.setObjectName("FieldLabel")

        self.notes_input = QTextEdit(card)
        self.notes_input.setObjectName("DebtNotesInput")
        self.notes_input.setFixedHeight(38)
        self.notes_input.setAcceptRichText(False)
        self.notes_input.setPlaceholderText(
            "Tambahkan catatan manual (catatan otomatis 'Pembayaran hutang')..."
        )

        card_layout.addWidget(notes_lbl)
        card_layout.addWidget(self.notes_input)
        return card

    # ------------------------------------------------------------------
    # Helper tampilan (murni visual)
    # ------------------------------------------------------------------
    def _sync_method_segments(self, index: int) -> None:
        """Menyelaraskan tombol segmen metode dengan pilihan combobox.

        Args:
            index: Indeks pilihan combobox saat ini.
        """
        button = self._method_group.button(index)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def _set_feedback(self, state: str, text: str) -> None:
        """Memperbarui teks, warna, dan ikon kotak umpan balik.

        Args:
            state: Salah satu dari "info", "paid", "partial", atau "error".
            text: Pesan umpan balik.
        """
        icons = {
            "info": ("info", _C.SUBTEXT),
            "paid": ("check_circle", _C.GREEN),
            "partial": ("clock", "#FBBF24"),
            "error": ("alert_circle", _C.RED),
        }
        icon_name, color = icons.get(state, icons["info"])
        self._feedback_icon.setPixmap(_svg_pixmap(icon_name, 16, color))
        for widget in (self._feedback_box, self.feedback_label):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.feedback_label.setText(text)

    # ------------------------------------------------------------------
    # Logika (tidak berubah)
    # ------------------------------------------------------------------
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
            self._set_feedback("info", f"Sisa tagihan saat ini: {format_rupiah(remaining)}")
            return

        if amount >= remaining:
            change = amount - remaining
            self._set_feedback(
                "paid", f"Status setelah bayar: LUNAS (Kembalian: {format_rupiah(change)})"
            )
        else:
            left = remaining - amount
            self._set_feedback(
                "partial", f"Status setelah bayar: CICILAN (Sisa hutang: {format_rupiah(left)})"
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
            self._set_feedback("error", "Masukkan nominal pembayaran lebih dari Rp 0.")
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