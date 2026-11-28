"""Dialog pemilih nota kulakan lama atau draft untuk dimuat ulang ke keranjang."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.tambahstok import PurchaseHistoryRow
from util.customdialog import CustomDialog, DialogTitleBarConfig
from util.helper.formatrupiah import format_rupiah
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

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
_LAVENDER = "#B4BEFE"
_MAUVE = "#CBA6F7"
_PINK = "#F5C2E7"
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
}
_STATUS_FALLBACK = _OVERLAY1

_COL_DATE, _COL_INVOICE, _COL_SUPPLIER, _COL_TOTAL, _COL_STATUS = range(5)

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICON_HISTORY = (
    '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
    '<path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>'
)
_ICON_CALENDAR = (
    '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<path d="M16 2v4M8 2v4M3 10h18"/>'
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
_ICON_LIST = (
    '<path d="M8 6h13M8 12h13M8 18h13"/>'
    '<path d="M3 6h.01M3 12h.01M3 18h.01"/>'
)
_ICON_INBOX = (
    '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
    '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89'
    'A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
)
_ICON_INFO = (
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 16v-4"/><path d="M12 8h.01"/>'
)
_ICON_CART = (
    '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/>'
    '<path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57'
    'l1.65-7.43H5.12"/>'
)
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


class _StatusPillDelegate(QStyledItemDelegate):
    """Delegate yang menggambar teks status sebagai pill berwarna."""

    _PAD_X = 10
    _HEIGHT = 22
    _DOT = 6

    def _pill_font(self, base: QFont) -> QFont:
        """Membuat font tebal kecil untuk teks pill.

        Args:
            base: Font dasar dari opsi item.

        Returns:
            Font yang dipakai untuk menggambar pill.
        """
        font = QFont(base)
        font.setPixelSize(10)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        return font

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar latar sel (termasuk seleksi) lalu pill status di tengah.

        Args:
            painter: Painter aktif.
            option: Opsi gaya item.
            index: Indeks model sel.
        """
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        if not text:
            return

        color = QColor(_STATUS_COLORS.get(text.upper(), _STATUS_FALLBACK))
        font = self._pill_font(opt.font)
        metrics = QFontMetrics(font)
        width = (
            self._PAD_X * 2 + self._DOT + 6 + metrics.horizontalAdvance(text)
        )
        rect = QRectF(
            opt.rect.center().x() - width / 2 + 0.5,
            opt.rect.center().y() - self._HEIGHT / 2 + 0.5,
            width,
            self._HEIGHT,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(color)
        fill.setAlpha(38)
        border = QColor(color)
        border.setAlpha(100)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, self._HEIGHT / 2, self._HEIGHT / 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        dot_x = rect.left() + self._PAD_X
        dot_y = rect.center().y() - self._DOT / 2
        painter.drawEllipse(QRectF(dot_x, dot_y, self._DOT, self._DOT))

        painter.setPen(color)
        painter.setFont(font)
        text_rect = QRectF(
            dot_x + self._DOT + 6, rect.top(), metrics.horizontalAdvance(text) + 2, rect.height()
        )
        painter.drawText(
            text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text
        )
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Memberi ruang cukup untuk pill status.

        Args:
            option: Opsi gaya item.
            index: Indeks model sel.

        Returns:
            Ukuran yang disarankan untuk sel status.
        """
        base = super().sizeHint(option, index)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        metrics = QFontMetrics(self._pill_font(option.font))
        width = self._PAD_X * 2 + self._DOT + 6 + metrics.horizontalAdvance(text) + 20
        return QSize(max(base.width(), width), max(base.height(), self._HEIGHT + 12))


_DIALOG_QSS = f"""
QWidget#CustomDialogContent {{
    background-color: transparent;
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
}}

/* ---------- Header ---------- */
QFrame#headerCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2EFAB387, stop:0.55 #22F5C2E7, stop:1 #14CBA6F7);
    border: 1px solid #4DFAB387;
    border-radius: 14px;
}}
QLabel#headerBadge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_PEACH}, stop:1 {_PINK});
    border-radius: 14px;
}}
QLabel#headerTitle {{
    color: {_TEXT};
    font-size: 17px;
    font-weight: 700;
    background: transparent;
}}
QLabel#headerSubtitle {{
    color: {_SUBTEXT};
    font-size: 12px;
    background: transparent;
}}
QLabel#headerSubtitle b {{
    color: {_TEXT};
}}

/* ---------- Chip ringkasan ---------- */
QFrame#statChip {{
    background-color: {_MANTLE};
    border: 1px solid {_SURFACE0};
    border-radius: 10px;
}}
QLabel#statValue {{
    color: {_TEXT};
    font-size: 16px;
    font-weight: 800;
    background: transparent;
}}
QLabel#statLabel {{
    color: {_OVERLAY1};
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}}

/* ---------- Kartu tabel ---------- */
QFrame#tableCard {{
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
QLabel#selectionChip {{
    color: {_OVERLAY1};
    background-color: #1F7F849C;
    border: 1px solid #407F849C;
    border-radius: 8px;
    padding: 1px 10px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#selectionChip[active="true"] {{
    color: {_PEACH};
    background-color: #1FFAB387;
    border: 1px solid #59FAB387;
}}

QTableWidget#historyTable {{
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
QTableWidget#historyTable::item {{
    padding: 0px 10px;
    border: none;
    border-bottom: 1px solid #1C1C2A;
}}
QTableWidget#historyTable::item:hover {{
    background-color: #1AB4BEFE;
}}
QTableWidget#historyTable::item:selected {{
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
    min-height: 34px;
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

/* ---------- Empty state ---------- */
QFrame#emptyState {{
    background-color: {_CRUST};
    border: 1px dashed {_SURFACE1};
    border-radius: 10px;
}}
QLabel#emptyTitle {{
    color: {_TEXT};
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}}
QLabel#emptyText {{
    color: {_OVERLAY1};
    font-size: 12px;
    background: transparent;
}}

/* ---------- Footer ---------- */
QLabel#footerHint {{
    color: {_OVERLAY1};
    font-size: 11px;
    background: transparent;
}}
QLabel#footerHintIcon {{
    background: transparent;
}}

/* ---------- Tombol ---------- */
QPushButton#secondaryBtn {{
    background-color: transparent;
    color: {_TEXT};
    border: 1px solid {_SURFACE1};
    border-radius: 10px;
    padding: 0px 18px;
    min-height: 38px;
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
        stop:0 {_PEACH}, stop:1 {_PINK});
    color: {_CRUST};
    border: none;
    border-radius: 10px;
    padding: 0px 20px;
    min-height: 38px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FFC7A3, stop:1 #FAD4EF);
}}
QPushButton#primaryBtn:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #E09A70, stop:1 #DDA8CE);
}}
QPushButton#primaryBtn:disabled {{
    background: {_SURFACE0};
    color: {_OVERLAY1};
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


class RepeatOrderDialog(CustomDialog):
    """Dialog pemilih nota kulakan lama atau draft untuk dimuat ulang ke keranjang."""

    def __init__(
        self,
        history_rows: list[PurchaseHistoryRow],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RepeatOrderDialog.

        Args:
            history_rows: Daftar nota pembelian yang tersedia untuk disalin.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self._rows = history_rows
        self._selected_purchase_id: int | None = None

        self.setWindowTitle("Muat Ulang Nota Lama / Draft")
        self.setMinimumSize(780, 520)

        content = self.content_widget
        content.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        self.setLayout(layout)

        layout.addWidget(self._build_header(content, history_rows))

        card = QFrame(content)
        card.setObjectName("tableCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(10)

        section_row = QHBoxLayout()
        section_row.setSpacing(8)
        section_icon = QLabel(card)
        section_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=2.0, body=_ICON_LIST),
                size=14,
                dpr=3.0,
            )
        )
        section_icon.setStyleSheet("background: transparent;")
        section_title = QLabel("RIWAYAT NOTA KULAKAN", card)
        section_title.setObjectName("sectionTitle")
        self._selection_chip = QLabel("Belum ada nota dipilih", card)
        self._selection_chip.setObjectName("selectionChip")
        section_row.addWidget(section_icon)
        section_row.addWidget(section_title)
        section_row.addStretch(1)
        section_row.addWidget(self._selection_chip)
        card_layout.addLayout(section_row)

        self.table = QTableWidget(len(history_rows), 5, card)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(
            ["Tanggal", "No. Faktur", "Supplier", "Total", "Status"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setIconSize(QSize(14, 14))
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setItemDelegateForColumn(_COL_STATUS, _StatusPillDelegate(self.table))
        v_head = self.table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
            v_head.setDefaultSectionSize(44)
        h_head = self.table.horizontalHeader()
        if h_head is not None:
            h_head.setHighlightSections(False)
            h_head.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_head.setSectionResizeMode(_COL_DATE, QHeaderView.ResizeMode.ResizeToContents)
            h_head.setSectionResizeMode(
                _COL_INVOICE, QHeaderView.ResizeMode.ResizeToContents
            )
            h_head.setSectionResizeMode(_COL_SUPPLIER, QHeaderView.ResizeMode.Stretch)
            h_head.setSectionResizeMode(_COL_TOTAL, QHeaderView.ResizeMode.ResizeToContents)
            h_head.setSectionResizeMode(
                _COL_STATUS, QHeaderView.ResizeMode.ResizeToContents
            )
            h_head.setMinimumSectionSize(90)

        date_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_BLUE, stroke=2.0, body=_ICON_CALENDAR),
            size=14,
            dpr=3.0,
        )
        invoice_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_MAUVE, stroke=2.0, body=_ICON_RECEIPT),
            size=14,
            dpr=3.0,
        )
        supplier_icon = build_svg_icon(
            _SVG_TEMPLATE.format(color=_TEAL, stroke=2.0, body=_ICON_TRUCK),
            size=14,
            dpr=3.0,
        )
        invoice_font = QFont()
        invoice_font.setBold(True)
        total_font = QFont()
        total_font.setBold(True)

        for idx, row in enumerate(history_rows):
            date_item = QTableWidgetItem(row["purchase_date"])
            date_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            date_item.setIcon(date_icon)
            date_item.setForeground(QColor(_SUBTEXT))
            self.table.setItem(idx, _COL_DATE, date_item)

            invoice_item = QTableWidgetItem(row["invoice_number"])
            invoice_item.setIcon(invoice_icon)
            invoice_item.setFont(invoice_font)
            invoice_item.setForeground(QColor(_LAVENDER))
            self.table.setItem(idx, _COL_INVOICE, invoice_item)

            supplier_item = QTableWidgetItem(row["supplier_name"])
            supplier_item.setIcon(supplier_icon)
            supplier_item.setToolTip(row["supplier_name"])
            self.table.setItem(idx, _COL_SUPPLIER, supplier_item)

            total_item = QTableWidgetItem(format_rupiah(row["total"]))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            total_item.setFont(total_font)
            total_item.setForeground(QColor(_GREEN))
            self.table.setItem(idx, _COL_TOTAL, total_item)

            status_item = QTableWidgetItem(row["status"])
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, _COL_STATUS, status_item)

        total_header = self.table.horizontalHeaderItem(_COL_TOTAL)
        if total_header is not None:
            total_header.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        status_header = self.table.horizontalHeaderItem(_COL_STATUS)
        if status_header is not None:
            status_header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.itemDoubleClicked.connect(self._confirm_selection)

        if history_rows:
            card_layout.addWidget(self.table, 1)
        else:
            self.table.setVisible(False)
            card_layout.addWidget(self._build_empty_state(card), 1)

        layout.addWidget(card, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        hint_icon = QLabel(content)
        hint_icon.setObjectName("footerHintIcon")
        hint_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=2.0, body=_ICON_INFO),
                size=13,
                dpr=3.0,
            )
        )
        hint_label = QLabel("Klik dua kali pada baris untuk langsung memuat nota", content)
        hint_label.setObjectName("footerHint")
        btn_row.addWidget(hint_icon)
        btn_row.addWidget(hint_label)
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Batal", content)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color=_TEXT, stroke=2.0, body=_ICON_CLOSE),
                size=14,
                dpr=3.0,
            )
        )
        cancel_btn.setIconSize(QSize(14, 14))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)

        self._load_btn = QPushButton("Muat ke Keranjang", content)
        self._load_btn.setObjectName("primaryBtn")
        self._load_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.2, body=_ICON_CART),
                size=16,
                dpr=3.0,
            )
        )
        self._load_btn.setIconSize(QSize(16, 16))
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.setAutoDefault(False)
        self._load_btn.clicked.connect(self._confirm_selection)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._load_btn)
        layout.addLayout(btn_row)

        self.table.itemSelectionChanged.connect(self._refresh_selection_ui)
        self._refresh_selection_ui()
        if history_rows:
            self.table.setFocus()

    def _build_header(
        self, parent: QWidget, history_rows: list[PurchaseHistoryRow]
    ) -> QFrame:
        """Membangun kartu header bergradasi beserta chip ringkasan status.

        Args:
            parent: Widget induk header.
            history_rows: Data nota untuk menghitung ringkasan.

        Returns:
            QFrame header yang siap ditambahkan ke layout.
        """
        header = QFrame(parent)
        header.setObjectName("headerCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(14)

        badge = QLabel(header)
        badge.setObjectName("headerBadge")
        badge.setFixedSize(52, 52)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.1, body=_ICON_HISTORY),
                size=26,
                dpr=3.0,
            )
        )
        glow = QGraphicsDropShadowEffect(badge)
        glow.setBlurRadius(26)
        glow.setOffset(0, 4)
        glow.setColor(QColor(250, 179, 135, 110))
        badge.setGraphicsEffect(glow)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        title = QLabel("Pilih Nota untuk Dimuat ke Keranjang", header)
        title.setObjectName("headerTitle")
        subtitle = QLabel(
            f"Nota <b style='color:{_GREEN}'>COMPLETED</b> akan disalin dengan nomor "
            f"faktur baru; nota <b style='color:{_YELLOW}'>DRAFT</b> dibuka untuk "
            "dilanjutkan.",
            header,
        )
        subtitle.setObjectName("headerSubtitle")
        subtitle.setTextFormat(Qt.TextFormat.RichText)
        subtitle.setWordWrap(True)
        text_box.addStretch(1)
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        text_box.addStretch(1)

        completed = sum(1 for r in history_rows if r["status"].upper() == "COMPLETED")
        drafts = sum(1 for r in history_rows if r["status"].upper() == "DRAFT")

        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(self._build_stat_chip(header, str(len(history_rows)), "NOTA", _PEACH))
        stats.addWidget(self._build_stat_chip(header, str(completed), "COMPLETED", _GREEN))
        stats.addWidget(self._build_stat_chip(header, str(drafts), "DRAFT", _YELLOW))

        header_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(text_box, 1)
        header_layout.addLayout(stats)
        return header

    @staticmethod
    def _build_stat_chip(parent: QWidget, value: str, label: str, accent: str) -> QFrame:
        """Membangun chip angka ringkasan dengan garis aksen di atas.

        Args:
            parent: Widget induk chip.
            value: Angka yang ditampilkan.
            label: Keterangan di bawah angka.
            accent: Warna aksen chip.

        Returns:
            QFrame chip ringkasan.
        """
        chip = QFrame(parent)
        chip.setObjectName("statChip")
        chip.setMinimumWidth(78)
        chip.setStyleSheet(
            f"QFrame#statChip {{ border-top: 2px solid {accent}; }}"
        )
        box = QVBoxLayout(chip)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(0)
        value_label = QLabel(value, chip)
        value_label.setObjectName("statValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(label, chip)
        text_label.setObjectName("statLabel")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(value_label)
        box.addWidget(text_label)
        return chip

    @staticmethod
    def _build_empty_state(parent: QWidget) -> QFrame:
        """Membangun tampilan kosong ketika belum ada riwayat nota.

        Args:
            parent: Widget induk.

        Returns:
            QFrame empty state.
        """
        empty = QFrame(parent)
        empty.setObjectName("emptyState")
        box = QVBoxLayout(empty)
        box.setContentsMargins(24, 32, 24, 32)
        box.setSpacing(8)
        icon = QLabel(empty)
        icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=1.6, body=_ICON_INBOX),
                size=40,
                dpr=3.0,
            )
        )
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: transparent;")
        title = QLabel("Belum ada nota kulakan", empty)
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel("Nota yang selesai atau tersimpan sebagai draft akan muncul di sini.", empty)
        text.setObjectName("emptyText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        box.addStretch(1)
        box.addWidget(icon)
        box.addWidget(title)
        box.addWidget(text)
        box.addStretch(1)
        return empty

    def _refresh_selection_ui(self) -> None:
        """Memperbarui chip pilihan dan status tombol muat sesuai baris terpilih."""
        current_row = self.table.currentRow()
        has_selection = current_row >= 0 and bool(self.table.selectedItems())
        if has_selection:
            invoice_item = self.table.item(current_row, _COL_INVOICE)
            invoice = invoice_item.text() if invoice_item is not None else ""
            self._selection_chip.setText(f"Dipilih: {invoice}" if invoice else "1 nota dipilih")
        else:
            self._selection_chip.setText("Belum ada nota dipilih")
        self._selection_chip.setProperty("active", has_selection)
        self._selection_chip.style().unpolish(self._selection_chip)
        self._selection_chip.style().polish(self._selection_chip)
        self._load_btn.setEnabled(has_selection)

    def _confirm_selection(self) -> None:
        """Menyimpan ID nota yang dipilih baris aktif lalu menutup dialog."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
        first_item = self.table.item(current_row, 0)
        if first_item is None:
            return
        raw_id = first_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(raw_id, int):
            self._selected_purchase_id = raw_id
            self.accept()

    def get_selected_purchase_id(self) -> int | None:
        """Mengembalikan ID nota yang dipilih pengguna.

        Returns:
            ID pembelian atau None jika tidak ada yang dipilih.
        """
        return self._selected_purchase_id