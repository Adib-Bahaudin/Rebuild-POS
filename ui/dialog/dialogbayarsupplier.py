"""Dialog pencatatan cicilan atau pelunasan hutang nota pembelian supplier."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QDateTime,
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog, DialogTitleBarConfig
from ui.tambahstok import CurrencySpinBox, TambahStokPage
from util.helper.formatrupiah import format_rupiah
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

if TYPE_CHECKING:
    from core.tambah_stok_backend import PurchaseDetailBundle


_SVG_WALLET = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 '
    '0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
    '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'
    "</svg>"
)

_SVG_STORE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#7DD3FC" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/>'
    '<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>'
    '<path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/>'
    '<path d="M2 7h20"/>'
    '<path d="M22 7v3a2 2 0 0 1-2 2 2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 '
    '2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 '
    '12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 '
    '1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7"/>'
    "</svg>"
)

_SVG_RECEIPT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#818CF8" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-'
    '1-2 1Z"/>'
    '<path d="M8 7h8"/>'
    '<path d="M8 11h8"/>'
    '<path d="M8 15h5"/>'
    "</svg>"
)

_SVG_DEBT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FBBF24" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M12 7v5l3 2"/>'
    "</svg>"
)

_SVG_SHIELD_CHECK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#34D399" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 '
    '13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 '
    '3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
    '<path d="m9 12 2 2 4-4"/>'
    "</svg>"
)

_SVG_FULL_PAY = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#ECFDF5" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M18 6 7 17l-5-5"/>'
    '<path d="m22 10-7.5 7.5L13 16"/>'
    "</svg>"
)

_SVG_CALENDAR = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#38BDF8" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<rect width="18" height="18" x="3" y="4" rx="2"/>'
    '<path d="M16 2v4"/>'
    '<path d="M8 2v4"/>'
    '<path d="M3 10h18"/>'
    "</svg>"
)

_SVG_HASH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#818CF8" stroke-width="2.1" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<line x1="4" x2="20" y1="9" y2="9"/>'
    '<line x1="4" x2="20" y1="15" y2="15"/>'
    '<line x1="10" x2="8" y1="3" y2="21"/>'
    '<line x1="16" x2="14" y1="3" y2="21"/>'
    "</svg>"
)

_SVG_NOTE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#38BDF8" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M12 20h9"/>'
    '<path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.'
    '506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/>'
    "</svg>"
)

_SVG_CANCEL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#CBD5E1" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M18 6 6 18"/>'
    '<path d="m6 6 12 12"/>'
    "</svg>"
)

_SVG_SUBMIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="m9 12 2 2 4-4"/>'
    "</svg>"
)

_SVG_STATUS_OK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#34D399" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="m9 12 2 2 4-4"/>'
    "</svg>"
)

_SVG_STATUS_PARTIAL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#38BDF8" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M12 8v4l2.5 2.5"/>'
    "</svg>"
)

_SVG_STATUS_WARN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FB7185" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M12 8v4"/>'
    '<path d="M12 16h.01"/>'
    "</svg>"
)

PAYMENT_DIALOG_STYLESHEET = """
QWidget#CustomDialogContent {
    background-color: #0B1120;
    color: #E2E8F0;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget#CustomDialogContent QLabel {
    background-color: transparent;
    border: none;
}

QFrame#headerBanner {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #064E3B,
        stop: 0.48 #0F293A,
        stop: 1 #1E1B4B
    );
    border: 1px solid #1E3A5F;
    border-radius: 14px;
}

QFrame#headerIconWrap {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #10B981,
        stop: 1 #06B6D4
    );
    border: 1px solid #34D399;
    border-radius: 12px;
}

QLabel#dialogTitle {
    color: #F8FAFC;
    font-size: 16px;
    font-weight: 700;
}

QFrame#invoiceBadge {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid #38BDF8;
    border-radius: 10px;
}

QLabel#invoiceBadgeText {
    color: #7DD3FC;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
}

QLabel#supplierLabel {
    color: #CBD5E1;
    font-size: 12px;
    font-weight: 500;
}

QFrame#metricCardTotal {
    background-color: #111827;
    border: 1px solid #312E81;
    border-radius: 11px;
}

QFrame#metricCardRemaining {
    background-color: #111827;
    border: 1px solid #78350F;
    border-radius: 11px;
}

QFrame#metricCardAfter {
    background-color: #111827;
    border: 1px solid #065F46;
    border-radius: 11px;
}

QFrame#metricCardAfter[afterState="invalid"] {
    border: 1px solid #9F1239;
}

QLabel#metricCaption {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#metricValueTotal {
    color: #A5B4FC;
    font-size: 14px;
    font-weight: 700;
}

QLabel#metricValueRemaining {
    color: #FBBF24;
    font-size: 14px;
    font-weight: 700;
}

QLabel#metricValueAfter {
    color: #34D399;
    font-size: 14px;
    font-weight: 700;
}

QLabel#metricValueAfter[afterState="partial"] {
    color: #38BDF8;
}

QLabel#metricValueAfter[afterState="invalid"] {
    color: #FB7185;
}

QFrame#dialogCard {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

QLabel#fieldLabel {
    color: #CBD5E1;
    font-size: 12px;
    font-weight: 600;
}

QLabel#requiredMark {
    color: #F43F5E;
    font-size: 12px;
    font-weight: 700;
}

QLabel#progressCaption {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#progressPercent {
    color: #34D399;
    font-size: 11px;
    font-weight: 700;
}

QLabel#progressPercent[afterState="partial"] {
    color: #38BDF8;
}

QLabel#progressPercent[afterState="invalid"] {
    color: #FB7185;
}

#amountSpin {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 4px 12px;
    font-size: 14px;
    font-weight: 700;
    selection-background-color: #4F46E5;
}

#amountSpin:hover {
    border-color: #10B981;
    background-color: #131E33;
}

#amountSpin:focus {
    border-color: #34D399;
    background-color: #0F172A;
}

#amountSpin::up-button,
#amountSpin::down-button {
    width: 22px;
    border: none;
    background-color: #1E293B;
}

#amountSpin::up-button {
    border-top-right-radius: 7px;
    border-bottom: 1px solid #334155;
}

#amountSpin::down-button {
    border-bottom-right-radius: 7px;
}

#amountSpin::up-button:hover,
#amountSpin::down-button:hover {
    background-color: #334155;
}

QPushButton#accentBtn {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #059669,
        stop: 1 #0891B2
    );
    color: #ECFDF5;
    border: 1px solid #34D399;
    border-radius: 9px;
    padding: 0px 14px;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#accentBtn:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #10B981,
        stop: 1 #06B6D4
    );
    color: #FFFFFF;
    border-color: #6EE7B7;
}

QPushButton#accentBtn:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #047857,
        stop: 1 #0E7490
    );
}

QComboBox#methodCombo {
    background-color: #0F172A;
    color: #F1F5F9;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 6px 34px 6px 12px;
    font-size: 13px;
    font-weight: 500;
}

QComboBox#methodCombo:hover {
    border-color: #6366F1;
    background-color: #131E33;
}

QComboBox#methodCombo:focus {
    border-color: #818CF8;
}

QComboBox#methodCombo::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    background: transparent;
}

QComboBox#methodCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QDateTimeEdit#dateEdit {
    background-color: #0F172A;
    color: #F1F5F9;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 6px 34px 6px 12px;
    font-size: 13px;
    font-weight: 500;
    selection-background-color: #4F46E5;
}

QDateTimeEdit#dateEdit:hover {
    border-color: #38BDF8;
    background-color: #131E33;
}

QDateTimeEdit#dateEdit:focus {
    border-color: #38BDF8;
    background-color: #0F172A;
}

QDateTimeEdit#dateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
    background: transparent;
}

QDateTimeEdit#dateEdit::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QLineEdit#formInput {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: #4F46E5;
}

QLineEdit#formInput:hover {
    border-color: #475569;
    background-color: #131E33;
}

QLineEdit#formInput:focus {
    border-color: #38BDF8;
    background-color: #0F172A;
}

QWidget#CustomDialogContent QLabel#errorLabel {
    background-color: #3B1120;
    color: #FDA4AF;
    border: 1px solid #F43F5E;
    border-radius: 9px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
}

QFrame#footerBar {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

QFrame#statusPill {
    background-color: #064E3B;
    border: 1px solid #10B981;
    border-radius: 17px;
}

QFrame#statusPill[afterState="partial"] {
    background-color: #0C2A45;
    border: 1px solid #0EA5E9;
}

QFrame#statusPill[afterState="invalid"] {
    background-color: #3B1120;
    border: 1px solid #F43F5E;
}

QLabel#statusPillLabel {
    color: #A7F3D0;
    font-size: 12px;
    font-weight: 600;
}

QLabel#statusPillLabel[afterState="partial"] {
    color: #BAE6FD;
}

QLabel#statusPillLabel[afterState="invalid"] {
    color: #FDA4AF;
}

QPushButton#secondaryBtn {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#secondaryBtn:hover {
    background-color: #293548;
    border-color: #64748B;
    color: #FFFFFF;
}

QPushButton#secondaryBtn:pressed {
    background-color: #172033;
}

QPushButton#primaryBtn {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #059669,
        stop: 0.5 #0284C7,
        stop: 1 #4F46E5
    );
    color: #FFFFFF;
    border: 1px solid #38BDF8;
    border-radius: 9px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #10B981,
        stop: 0.5 #0EA5E9,
        stop: 1 #6366F1
    );
    border-color: #7DD3FC;
}

QPushButton#primaryBtn:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #047857,
        stop: 1 #4338CA
    );
}
"""

_CALENDAR_STYLESHEET = """
QCalendarWidget#paymentCalendar {
    background-color: #0F172A;
    border: 1px solid #38BDF8;
    border-radius: 8px;
}

QCalendarWidget#paymentCalendar QWidget#qt_calendar_navigationbar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #1E1B4B,
        stop: 1 #0F293A
    );
    min-height: 34px;
    padding: 2px 6px;
}

QCalendarWidget#paymentCalendar QToolButton {
    color: #F8FAFC;
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
}

QCalendarWidget#paymentCalendar QToolButton:hover {
    background-color: rgba(56, 189, 248, 0.22);
}

QCalendarWidget#paymentCalendar QMenu {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #4F46E5;
}

QCalendarWidget#paymentCalendar QSpinBox {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 2px 6px;
}

QCalendarWidget#paymentCalendar QAbstractItemView:enabled {
    background-color: #0F172A;
    color: #E2E8F0;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
    outline: none;
}

QCalendarWidget#paymentCalendar QAbstractItemView:disabled {
    color: #475569;
}
"""


class _ComboPopupDelegate(QStyledItemDelegate):
    """Delegate kustom untuk merender warna item aktif dan hover pada dropdown."""

    def __init__(
        self,
        combo: QComboBox,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi delegate popup combobox.

        Args:
            combo: Instance QComboBox pemilik daftar popup.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._combo = combo

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Menentukan tinggi baris ideal untuk setiap opsi pada popup dropdown.

        Args:
            option: Informasi gaya item.
            index: Indeks model item.

        Returns:
            Objek QSize dengan tinggi minimum 34 piksel.
        """
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(34, base.height()))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar item dropdown dengan pembedaan warna aktif dan hover.

        Args:
            painter: Objek QPainter aktif.
            option: Informasi gaya, state, dan geometri baris item.
            index: Indeks model baris item dropdown.
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        is_active = index.row() == self._combo.currentIndex()
        is_hovered = bool(
            option.state
            & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
        )
        item_rect = QRectF(option.rect).adjusted(2.0, 2.0, -2.0, -2.0)

        if is_active and is_hovered:
            painter.setBrush(QColor("#3730A3"))
            painter.setPen(QPen(QColor("#818CF8"), 1.2))
            painter.drawRoundedRect(item_rect, 7.0, 7.0)
            text_color = QColor("#FFFFFF")
            font_weight = QFont.Weight.Bold
        elif is_hovered:
            painter.setBrush(QColor("#1E3A5F"))
            painter.setPen(QPen(QColor("#38BDF8"), 1.1))
            painter.drawRoundedRect(item_rect, 7.0, 7.0)
            text_color = QColor("#F8FAFC")
            font_weight = QFont.Weight.DemiBold
        elif is_active:
            painter.setBrush(QColor("#1E1B4B"))
            painter.setPen(QPen(QColor("#6366F1"), 1.1))
            painter.drawRoundedRect(item_rect, 7.0, 7.0)
            text_color = QColor("#C7D2FE")
            font_weight = QFont.Weight.DemiBold
        else:
            text_color = QColor("#CBD5E1")
            font_weight = QFont.Weight.Normal

        if is_active:
            dot_center = QPointF(item_rect.right() - 12.0, item_rect.center().y())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#38BDF8"))
            painter.drawEllipse(dot_center, 3.5, 3.5)

        item_font = QFont(option.font)
        item_font.setWeight(font_weight)
        painter.setFont(item_font)
        painter.setPen(text_color)

        right_pad = -24.0 if is_active else -10.0
        text_rect = item_rect.adjusted(10.0, 0.0, right_pad, 0.0)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            int(text_rect.width()),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )
        painter.restore()


class _ModernComboBox(QComboBox):
    """QComboBox kustom dengan panah chevron vektor dan popup item berwarna."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi combobox dengan QListView dan delegate kustom.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        popup_view = QListView(self)
        popup_view.setObjectName("methodPopupView")
        popup_view.setMouseTracking(True)
        popup_view.setCursor(Qt.CursorShape.PointingHandCursor)
        popup_view.setFrameShape(QFrame.Shape.NoFrame)
        popup_view.setStyleSheet(
            """
            QListView#methodPopupView {
                background-color: #0F172A;
                border: 1px solid #4F46E5;
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            """
        )
        self.setView(popup_view)
        self.setItemDelegate(_ComboPopupDelegate(self, self))

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar combobox standar diikuti panah chevron modern di kanan.

        Args:
            event: Event pengecatan ulang widget.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#94A3B8"), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = float(self.width() - 18)
        center_y = float(self.height()) / 2.0
        chevron = QPainterPath()
        chevron.moveTo(center_x - 4.0, center_y - 2.0)
        chevron.lineTo(center_x, center_y + 2.5)
        chevron.lineTo(center_x + 4.0, center_y - 2.0)
        painter.drawPath(chevron)
        painter.end()


class _ModernDateTimeEdit(QDateTimeEdit):
    """QDateTimeEdit kustom dengan ikon kalender SVG dan popup kalender gelap."""

    def __init__(
        self,
        dt: QDateTime,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi pemilih tanggal dan waktu bergaya modern.

        Args:
            dt: Nilai QDateTime awal yang ditampilkan.
            parent: Widget induk opsional.
        """
        super().__init__(dt, parent)
        self._calendar_pixmap = render_svg_pixmap(_SVG_CALENDAR, 16)
        self.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.setCalendarPopup(True)
        self._style_calendar_popup()

    def _style_calendar_popup(self) -> None:
        """Menerapkan tema gelap berwarna pada widget kalender popup."""
        calendar = self.calendarWidget()
        if isinstance(calendar, QCalendarWidget):
            calendar.setObjectName("paymentCalendar")
            calendar.setGridVisible(False)
            calendar.setVerticalHeaderFormat(
                QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
            )
            calendar.setStyleSheet(_CALENDAR_STYLESHEET)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar input tanggal beserta ikon kalender vektor di sisi kanan.

        Args:
            event: Event pengecatan ulang widget.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        icon_x = self.width() - 26
        icon_y = (self.height() - self._calendar_pixmap.height()) // 2
        painter.drawPixmap(icon_x, icon_y, self._calendar_pixmap)
        painter.end()


class _PaymentProgressBar(QWidget):
    """Bilah progres tipis bergaya gradien untuk memvisualisasikan porsi bayar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi bilah progres pembayaran.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._ratio: float = 1.0
        self._state: str = "full"
        self.setFixedHeight(8)

    def set_progress(self, ratio: float, state: str) -> None:
        """Memperbarui rasio pengisian dan tema warna bilah progres.

        Args:
            ratio: Nilai progres antara 0.0 hingga 1.0.
            state: Status visual berupa 'full', 'partial', atau 'invalid'.
        """
        self._ratio = max(0.0, min(1.0, ratio))
        self._state = state
        self.update()

    def sizeHint(self) -> QSize:
        """Mengembalikan ukuran ideal bilah progres.

        Returns:
            Objek QSize dengan tinggi 8 piksel.
        """
        return QSize(160, 8)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar trek latar belakang dan isian gradien membulat.

        Args:
            event: Event pengecatan ulang widget.
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track_rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        radius = track_rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1E293B"))
        painter.drawRoundedRect(track_rect, radius, radius)

        fill_w = track_rect.width() * self._ratio
        if fill_w > 1.0:
            fill_rect = QRectF(0.0, 0.0, max(fill_w, track_rect.height()), track_rect.height())
            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            if self._state == "invalid":
                gradient.setColorAt(0.0, QColor("#E11D48"))
                gradient.setColorAt(1.0, QColor("#FB7185"))
            elif self._state == "partial":
                gradient.setColorAt(0.0, QColor("#4F46E5"))
                gradient.setColorAt(1.0, QColor("#38BDF8"))
            else:
                gradient.setColorAt(0.0, QColor("#10B981"))
                gradient.setColorAt(1.0, QColor("#06B6D4"))
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill_rect, radius, radius)

        painter.end()


class PurchasePaymentDialog(CustomDialog):
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
        titlebar_config = DialogTitleBarConfig(
            titlebar_color="#0F172A",
            title_text_color="#F8FAFC",
            close_btn_color="transparent",
            close_btn_text_color="#CBD5E1",
            close_btn_hover_color="#EF4444",
            close_btn_pressed_color="#DC2626",
            border_color="#1E293B",
            background_color="#0B1120",
            height=38,
        )
        super().__init__(parent, titlebar_config=titlebar_config)

        self._bundle = bundle
        self._remaining = bundle["remaining_amount"]
        self.setWindowTitle(f"Pelunasan Hutang - {bundle['invoice_number']}")
        self.setMinimumWidth(590)
        self.content_widget.setStyleSheet(PAYMENT_DIALOG_STYLESHEET)

        self._after_card = QFrame(self.content_widget)
        self._after_value_label = QLabel("Lunas (Rp 0)", self.content_widget)
        self._progress_percent_label = QLabel("100%", self.content_widget)
        self._progress_bar = _PaymentProgressBar(self.content_widget)
        self._status_pill = QFrame(self.content_widget)
        self._status_icon_label = QLabel(self.content_widget)
        self._status_text_label = QLabel("Pelunasan Penuh", self.content_widget)

        self.amount_spin = CurrencySpinBox(
            maximum=max(1, self._remaining),
            parent=self.content_widget,
        )
        self.method_combo: QComboBox = _ModernComboBox(self.content_widget)
        self.date_edit: QDateTimeEdit = _ModernDateTimeEdit(
            QDateTime.currentDateTime(),
            self.content_widget,
        )
        self.reference_input = QLineEdit(self.content_widget)
        self.notes_input = QLineEdit(self.content_widget)
        self.error_label = QLabel("", self.content_widget)

        self._setup_ui()
        self._sync_payment_preview(self.amount_spin.value())

    def _setup_ui(self) -> None:
        """Menyusun seluruh bagian antarmuka dialog ke dalam area konten."""
        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header_banner())
        layout.addLayout(self._build_summary_cards())
        layout.addWidget(self._build_form_card())

        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addWidget(self._build_footer_bar())

    def _build_header_banner(self) -> QFrame:
        """Membangun banner judul berwarna dengan ikon dompet dan info supplier.

        Returns:
            Widget QFrame header dialog.
        """
        banner = QFrame(self.content_widget)
        banner.setObjectName("headerBanner")

        row = QHBoxLayout(banner)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)

        icon_wrap = QFrame(banner)
        icon_wrap.setObjectName("headerIconWrap")
        icon_wrap.setFixedSize(44, 44)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon_wrap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(render_svg_pixmap(_SVG_WALLET, 24))
        icon_layout.addWidget(icon_label)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(4)

        top_line = QHBoxLayout()
        top_line.setContentsMargins(0, 0, 0, 0)
        top_line.setSpacing(8)

        title = QLabel("Bayar Cicilan / Pelunasan", banner)
        title.setObjectName("dialogTitle")

        invoice_badge = QFrame(banner)
        invoice_badge.setObjectName("invoiceBadge")
        badge_layout = QHBoxLayout(invoice_badge)
        badge_layout.setContentsMargins(9, 2, 9, 2)
        badge_text = QLabel(self._bundle["invoice_number"], invoice_badge)
        badge_text.setObjectName("invoiceBadgeText")
        badge_layout.addWidget(badge_text)

        top_line.addWidget(title)
        top_line.addWidget(invoice_badge)
        top_line.addStretch(1)

        supplier_line = QHBoxLayout()
        supplier_line.setContentsMargins(0, 0, 0, 0)
        supplier_line.setSpacing(6)

        store_icon = QLabel(banner)
        store_icon.setPixmap(render_svg_pixmap(_SVG_STORE, 14))
        store_icon.setFixedSize(14, 14)

        supplier_text = QLabel(f"Supplier: {self._bundle['supplier_name']}", banner)
        supplier_text.setObjectName("supplierLabel")
        supplier_text.setWordWrap(True)

        supplier_line.addWidget(store_icon)
        supplier_line.addWidget(supplier_text, 1)

        info_col.addLayout(top_line)
        info_col.addLayout(supplier_line)

        row.addWidget(icon_wrap)
        row.addLayout(info_col, 1)
        return banner

    def _build_summary_cards(self) -> QHBoxLayout:
        """Membangun baris tiga kartu ringkasan nominal tagihan dan estimasi sisa.

        Returns:
            QHBoxLayout berisi kartu Total Nota, Sisa Hutang, dan Sisa Setelah Bayar.
        """
        row = QHBoxLayout()
        row.setSpacing(10)

        total_card = self._create_metric_card(
            card_object_name="metricCardTotal",
            svg_markup=_SVG_RECEIPT,
            caption="Total Nota",
            value_label=QLabel(format_rupiah(self._bundle["total"]), self.content_widget),
            value_object_name="metricValueTotal",
        )
        remaining_card = self._create_metric_card(
            card_object_name="metricCardRemaining",
            svg_markup=_SVG_DEBT,
            caption="Sisa Hutang",
            value_label=QLabel(format_rupiah(self._remaining), self.content_widget),
            value_object_name="metricValueRemaining",
        )
        after_card = self._create_metric_card(
            card_object_name="metricCardAfter",
            svg_markup=_SVG_SHIELD_CHECK,
            caption="Estimasi Sisa",
            value_label=self._after_value_label,
            value_object_name="metricValueAfter",
            target_frame=self._after_card,
        )

        row.addWidget(total_card, 1)
        row.addWidget(remaining_card, 1)
        row.addWidget(after_card, 1)
        return row

    def _create_metric_card(
        self,
        card_object_name: str,
        svg_markup: str,
        caption: str,
        value_label: QLabel,
        value_object_name: str,
        target_frame: QFrame | None = None,
    ) -> QFrame:
        """Membuat kartu metrik ringkas dengan ikon SVG, judul, dan nilai nominal.

        Args:
            card_object_name: Nama objek QSS untuk kartu.
            svg_markup: Markup SVG ikon metrik.
            caption: Label deskripsi singkat metrik.
            value_label: Widget QLabel penampil nominal.
            value_object_name: Nama objek QSS untuk teks nominal.
            target_frame: Frame opsional yang sudah diinstansiasi sebelumnya.

        Returns:
            Widget QFrame kartu metrik siap pakai.
        """
        card = target_frame if target_frame is not None else QFrame(self.content_widget)
        card.setObjectName(card_object_name)

        box = QHBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(10)

        icon_label = QLabel(card)
        icon_label.setPixmap(render_svg_pixmap(svg_markup, 20))
        icon_label.setFixedSize(20, 20)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        caption_label = QLabel(caption, card)
        caption_label.setObjectName("metricCaption")

        value_label.setParent(card)
        value_label.setObjectName(value_object_name)

        text_col.addWidget(caption_label)
        text_col.addWidget(value_label)

        box.addWidget(icon_label)
        box.addLayout(text_col, 1)
        return card

    def _build_field_label(
        self,
        text: str,
        parent: QWidget,
        required: bool = False,
    ) -> QHBoxLayout:
        """Membangun baris label field form dengan tanda wajib opsional.

        Args:
            text: Teks judul field.
            parent: Widget induk label.
            required: True jika field wajib diisi.

        Returns:
            QHBoxLayout berisi label field.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        lbl = QLabel(text, parent)
        lbl.setObjectName("fieldLabel")
        row.addWidget(lbl)

        if required:
            mark = QLabel("*", parent)
            mark.setObjectName("requiredMark")
            row.addWidget(mark)

        row.addStretch(1)
        return row

    def _build_form_card(self) -> QFrame:
        """Membangun kartu formulir input nominal, metode, tanggal, resi, dan catatan.

        Returns:
            Widget QFrame pembungkus form pembayaran.
        """
        card = QFrame(self.content_widget)
        card.setObjectName("dialogCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(12)

        amount_section = QVBoxLayout()
        amount_section.setSpacing(6)
        amount_section.addLayout(self._build_field_label("Nominal Bayar", card, required=True))

        amount_row = QHBoxLayout()
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.setSpacing(8)

        self.amount_spin.setParent(card)
        self.amount_spin.setObjectName("amountSpin")
        self.amount_spin.setValue(self._remaining)
        self.amount_spin.setFixedHeight(38)
        self.amount_spin.valueChanged.connect(self._on_amount_changed)

        full_btn = QPushButton("Lunasi Semua", card)
        full_btn.setObjectName("accentBtn")
        full_btn.setIcon(build_svg_icon(_SVG_FULL_PAY, size=15))
        full_btn.setIconSize(QSize(15, 15))
        full_btn.setFixedHeight(38)
        full_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        full_btn.clicked.connect(self._set_full_remaining)

        amount_row.addWidget(self.amount_spin, 1)
        amount_row.addWidget(full_btn)
        amount_section.addLayout(amount_row)

        progress_header = QHBoxLayout()
        progress_header.setContentsMargins(2, 2, 2, 0)
        progress_caption = QLabel("Porsi pelunasan dari sisa hutang", card)
        progress_caption.setObjectName("progressCaption")
        self._progress_percent_label.setParent(card)
        self._progress_percent_label.setObjectName("progressPercent")
        progress_header.addWidget(progress_caption)
        progress_header.addStretch(1)
        progress_header.addWidget(self._progress_percent_label)

        self._progress_bar.setParent(card)
        amount_section.addLayout(progress_header)
        amount_section.addWidget(self._progress_bar)
        card_layout.addLayout(amount_section)

        split_row = QHBoxLayout()
        split_row.setSpacing(12)

        method_col = QVBoxLayout()
        method_col.setSpacing(6)
        method_col.addLayout(self._build_field_label("Metode Bayar", card))
        self.method_combo.setParent(card)
        self.method_combo.setObjectName("methodCombo")
        self.method_combo.addItems(list(TambahStokPage.PAYMENT_METHODS))
        self.method_combo.setFixedHeight(36)
        self.method_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        method_col.addWidget(self.method_combo)

        date_col = QVBoxLayout()
        date_col.setSpacing(6)
        date_col.addLayout(self._build_field_label("Tanggal Bayar", card))
        self.date_edit.setParent(card)
        self.date_edit.setObjectName("dateEdit")
        self.date_edit.setFixedHeight(36)
        date_col.addWidget(self.date_edit)

        split_row.addLayout(method_col, 1)
        split_row.addLayout(date_col, 1)
        card_layout.addLayout(split_row)

        ref_col = QVBoxLayout()
        ref_col.setSpacing(6)
        ref_col.addLayout(self._build_field_label("No. Referensi", card))
        self.reference_input.setParent(card)
        self.reference_input.setObjectName("formInput")
        self.reference_input.setPlaceholderText("No. resi / bukti transfer (opsional)")
        self.reference_input.setClearButtonEnabled(True)
        self.reference_input.setFixedHeight(36)
        self.reference_input.addAction(
            build_svg_icon(_SVG_HASH, size=15),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        ref_col.addWidget(self.reference_input)
        card_layout.addLayout(ref_col)

        notes_col = QVBoxLayout()
        notes_col.setSpacing(6)
        notes_col.addLayout(self._build_field_label("Catatan", card))
        self.notes_input.setParent(card)
        self.notes_input.setObjectName("formInput")
        self.notes_input.setPlaceholderText("Catatan pembayaran cicilan (opsional)")
        self.notes_input.setClearButtonEnabled(True)
        self.notes_input.setFixedHeight(36)
        self.notes_input.addAction(
            build_svg_icon(_SVG_NOTE, size=15),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        notes_col.addWidget(self.notes_input)
        card_layout.addLayout(notes_col)

        return card

    def _build_footer_bar(self) -> QFrame:
        """Membangun footer dialog berisi pill status pembayaran dan tombol aksi.

        Returns:
            Widget QFrame footer dialog.
        """
        footer = QFrame(self.content_widget)
        footer.setObjectName("footerBar")

        btn_row = QHBoxLayout(footer)
        btn_row.setContentsMargins(14, 10, 14, 10)
        btn_row.setSpacing(10)

        self._status_pill.setParent(footer)
        self._status_pill.setObjectName("statusPill")
        pill_layout = QHBoxLayout(self._status_pill)
        pill_layout.setContentsMargins(12, 6, 14, 6)
        pill_layout.setSpacing(7)

        self._status_icon_label.setParent(self._status_pill)
        self._status_icon_label.setFixedSize(16, 16)

        self._status_text_label.setParent(self._status_pill)
        self._status_text_label.setObjectName("statusPillLabel")

        pill_layout.addWidget(self._status_icon_label)
        pill_layout.addWidget(self._status_text_label)

        cancel_btn = QPushButton("Batal", footer)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setIcon(build_svg_icon(_SVG_CANCEL, size=15))
        cancel_btn.setIconSize(QSize(15, 15))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        submit_btn = QPushButton("Simpan Pembayaran", footer)
        submit_btn.setObjectName("primaryBtn")
        submit_btn.setIcon(build_svg_icon(_SVG_SUBMIT, size=16))
        submit_btn.setIconSize(QSize(16, 16))
        submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        submit_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(self._status_pill)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(submit_btn)
        return footer

    def _on_amount_changed(self, value: int) -> None:
        """Memperbarui pratinjau pelunasan dan menyembunyikan pesan galat lama.

        Args:
            value: Nominal pembayaran terbaru yang dimasukkan pengguna.
        """
        if self.error_label.isVisible():
            self.error_label.setVisible(False)
        self._sync_payment_preview(value)

    def _sync_payment_preview(self, amount: int) -> None:
        """Menyelaraskan kartu estimasi sisa, progres bar, dan pill status footer.

        Args:
            amount: Nominal pembayaran aktif dalam satuan rupiah.
        """
        remaining_base = max(1, self._remaining)
        ratio = float(amount) / float(remaining_base)
        percent = int(round(max(0.0, min(100.0, ratio * 100.0))))

        if amount <= 0 or amount > self._remaining:
            state = "invalid"
            self._after_value_label.setText(
                "Melebihi Hutang" if amount > self._remaining else format_rupiah(self._remaining)
            )
            self._progress_percent_label.setText(f"{percent}%")
            self._status_icon_label.setPixmap(render_svg_pixmap(_SVG_STATUS_WARN, 16))
            self._status_text_label.setText("Nominal Belum Valid")
        elif amount == self._remaining:
            state = "full"
            self._after_value_label.setText("LUNAS (Rp 0)")
            self._progress_percent_label.setText("100% Lunas")
            self._status_icon_label.setPixmap(render_svg_pixmap(_SVG_STATUS_OK, 16))
            self._status_text_label.setText("Pelunasan Penuh")
        else:
            state = "partial"
            after_amount = self._remaining - amount
            self._after_value_label.setText(format_rupiah(after_amount))
            self._progress_percent_label.setText(f"{percent}% dari sisa")
            self._status_icon_label.setPixmap(render_svg_pixmap(_SVG_STATUS_PARTIAL, 16))
            self._status_text_label.setText("Pembayaran Cicilan")

        self._progress_bar.set_progress(ratio, state)

        for widget in (
            self._after_card,
            self._after_value_label,
            self._progress_percent_label,
            self._status_pill,
            self._status_text_label,
        ):
            widget.setProperty("afterState", state)
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)

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