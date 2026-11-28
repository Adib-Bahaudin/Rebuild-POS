"""Dialog pemilihan banyak barang sekaligus untuk halaman Tambah Stok."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractItemModel,
    QEasingCurve,
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog, DialogTitleBarConfig
from ui.tambahstok import CatalogItemData
from util.helper.formatrupiah import format_qty as format_quantity
from util.helper.svg_helper import build_svg_icon, render_svg_pixmap

if TYPE_CHECKING:
    from core.tambah_stok_backend import BulkCatalogItemView


_SVG_HEADER_BOX = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#E0E7FF" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8'
    'a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>'
    '<path d="m3.3 7 8.7 5 8.7-5"/>'
    '<path d="M12 22V12"/>'
    "</svg>"
)

_SVG_SEARCH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#38BDF8" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="11" cy="11" r="7"/>'
    '<path d="m20 20-3.5-3.5"/>'
    "</svg>"
)

_SVG_CHECK_ALL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#A5B4FC" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M18 6 7 17l-5-5"/>'
    '<path d="m22 10-7.5 7.5L13 16"/>'
    "</svg>"
)

_SVG_CART_PLUS = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="8" cy="21" r="1.2"/>'
    '<circle cx="19" cy="21" r="1.2"/>'
    '<path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 '
    '1.95-1.57l1.65-7.43H5.12"/>'
    '<path d="M12 7v4"/>'
    '<path d="M10 9h4"/>'
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

_SVG_LAYERS = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#38BDF8" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91'
    'a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>'
    '<path d="m22 12.5-8.97 4.08a2 2 0 0 1-1.66 0L2 12.5"/>'
    '<path d="m22 17-8.97 4.08a2 2 0 0 1-1.66 0L2 17"/>'
    "</svg>"
)

_SVG_ALERT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#FBBF24" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16'
    'a2 2 0 0 0 1.73-3Z"/>'
    '<path d="M12 9v4"/>'
    '<path d="M12 17h.01"/>'
    "</svg>"
)

_SVG_CHECK_CIRCLE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#34D399" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="m9 12 2 2 4-4"/>'
    "</svg>"
)

_CATEGORY_PALETTE: tuple[tuple[str, str, str], ...] = (
    ("#1E1B4B", "#6366F1", "#C7D2FE"),
    ("#083344", "#06B6D4", "#A5F3FC"),
    ("#3B0764", "#A855F7", "#E9D5FF"),
    ("#064E3B", "#10B981", "#A7F3D0"),
    ("#4C0519", "#F43F5E", "#FECDD3"),
    ("#431407", "#F97316", "#FED7AA"),
)

BULK_PICKER_STYLESHEET = """
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
        stop: 0 #1E1B4B,
        stop: 0.52 #172554,
        stop: 1 #0F293A
    );
    border: 1px solid #312E81;
    border-radius: 14px;
}

QFrame#headerIconWrap {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #6366F1,
        stop: 1 #06B6D4
    );
    border: 1px solid #818CF8;
    border-radius: 12px;
}

QLabel#dialogTitle {
    color: #F8FAFC;
    font-size: 17px;
    font-weight: 700;
    background: transparent;
}

QLabel#dialogSubtitle {
    color: #94A3B8;
    font-size: 12px;
    background: transparent;
}

QFrame#statChip {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid #334155;
    border-radius: 10px;
}

QLabel#statValueVisible {
    color: #38BDF8;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QLabel#statValueLow {
    color: #FBBF24;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QLabel#statValueSelected {
    color: #34D399;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QLabel#statCaption {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 500;
    background: transparent;
}

QFrame#filterCard {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

QLineEdit#searchInput {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #4F46E5;
}

QLineEdit#searchInput:hover {
    border-color: #475569;
    background-color: #131E33;
}

QLineEdit#searchInput:focus {
    border-color: #38BDF8;
    background-color: #0F172A;
}

QComboBox#categoryCombo {
    background-color: #0F172A;
    color: #F1F5F9;
    border: 1.5px solid #334155;
    border-radius: 9px;
    padding: 8px 34px 8px 12px;
    min-width: 175px;
    font-size: 13px;
    font-weight: 500;
}

QComboBox#categoryCombo:hover {
    border-color: #6366F1;
    background-color: #131E33;
}

QComboBox#categoryCombo:focus {
    border-color: #818CF8;
}

QComboBox#categoryCombo::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    background: transparent;
}

QComboBox#categoryCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QComboBox#categoryCombo QAbstractItemView {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #4F46E5;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: #312E81;
    selection-color: #FFFFFF;
}

QComboBox#categoryCombo QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
}

QFrame#tableContainer {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

QTableWidget#bulkTable {
    background-color: #0F172A;
    alternate-background-color: #131D31;
    color: #F1F5F9;
    border: none;
    border-radius: 10px;
    gridline-color: transparent;
    outline: none;
}

QTableWidget#bulkTable::item {
    border: none;
    padding: 0px;
}

QTableWidget#bulkTable::item:focus {
    outline: none;
}

QTableWidget#bulkTable QHeaderView::section {
    background-color: #172033;
    color: #94A3B8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    border: none;
    border-bottom: 1.5px solid #26354F;
    padding: 10px 10px;
}

QTableWidget#bulkTable QHeaderView::section:first {
    border-top-left-radius: 10px;
}

QTableWidget#bulkTable QHeaderView::section:last {
    border-top-right-radius: 10px;
}

QTableWidget#bulkTable QScrollBar:vertical {
    background-color: #0F172A;
    width: 10px;
    margin: 4px 2px 4px 2px;
    border-radius: 5px;
}

QTableWidget#bulkTable QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 28px;
    border-radius: 5px;
}

QTableWidget#bulkTable QScrollBar::handle:vertical:hover {
    background-color: #6366F1;
}

QTableWidget#bulkTable QScrollBar::add-line:vertical,
QTableWidget#bulkTable QScrollBar::sub-line:vertical,
QTableWidget#bulkTable QScrollBar::add-page:vertical,
QTableWidget#bulkTable QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0px;
}

QTableWidget#bulkTable QScrollBar:horizontal {
    background-color: #0F172A;
    height: 10px;
    margin: 2px 4px 2px 4px;
    border-radius: 5px;
}

QTableWidget#bulkTable QScrollBar::handle:horizontal {
    background-color: #334155;
    min-width: 28px;
    border-radius: 5px;
}

QTableWidget#bulkTable QScrollBar::handle:horizontal:hover {
    background-color: #6366F1;
}

QTableWidget#bulkTable QScrollBar::add-line:horizontal,
QTableWidget#bulkTable QScrollBar::sub-line:horizontal,
QTableWidget#bulkTable QScrollBar::add-page:horizontal,
QTableWidget#bulkTable QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0px;
}

QFrame#footerBar {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

QFrame#selectionPill {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 18px;
}

QFrame#selectionPill[selectedState="active"] {
    background-color: #064E3B;
    border: 1px solid #10B981;
}

QLabel#countLabel {
    color: #CBD5E1;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QLabel#countLabel[selectedState="active"] {
    color: #A7F3D0;
}

QPushButton#selectAllBtn {
    background-color: #1E1B4B;
    color: #C7D2FE;
    border: 1.5px solid #4338CA;
    border-radius: 9px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#selectAllBtn:hover {
    background-color: #312E81;
    color: #FFFFFF;
    border-color: #818CF8;
}

QPushButton#selectAllBtn:pressed {
    background-color: #3730A3;
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
        stop: 0 #4F46E5,
        stop: 0.55 #2563EB,
        stop: 1 #06B6D4
    );
    color: #FFFFFF;
    border: 1px solid #60A5FA;
    border-radius: 9px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #6366F1,
        stop: 0.55 #3B82F6,
        stop: 1 #22D3EE
    );
    border-color: #93C5FD;
}

QPushButton#primaryBtn:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #4338CA,
        stop: 1 #0891B2
    );
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
        popup_view.setObjectName("categoryPopupView")
        popup_view.setMouseTracking(True)
        popup_view.setCursor(Qt.CursorShape.PointingHandCursor)
        popup_view.setFrameShape(QFrame.Shape.NoFrame)
        popup_view.setStyleSheet(
            """
            QListView#categoryPopupView {
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


class _ToggleSwitchCheckBox(QCheckBox):
    """QCheckBox bergaya toggle switch modern dengan animasi geser halus."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Menginisialisasi toggle switch checkbox.

        Args:
            text: Teks label yang ditampilkan di samping sakelar.
            parent: Widget induk opsional.
        """
        super().__init__(text, parent)
        self._thumb_progress: float = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value_changed)
        self.toggled.connect(self._start_toggle_animation)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_anim_value_changed(self, value: object) -> None:
        """Memperbarui progres posisi tombol bulat selama animasi berlangsung.

        Args:
            value: Nilai interpolasi animasi antara 0.0 hingga 1.0.
        """
        if isinstance(value, (int, float)):
            self._thumb_progress = float(value)
            self.update()

    def _start_toggle_animation(self, checked: bool) -> None:
        """Memulai animasi perpindahan sakelar saat status centang berubah.

        Args:
            checked: Status aktif terbaru dari checkbox.
        """
        self._anim.stop()
        self._anim.setStartValue(self._thumb_progress)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        """Menghitung ukuran ideal widget mencakup sakelar dan label teks.

        Returns:
            Objek QSize ukuran minimum ideal untuk widget.
        """
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(46 + text_width + 22, 34)

    def hitButton(self, pos: QPoint) -> bool:
        """Memastikan seluruh area bingkai sakelar dan label dapat diklik.

        Args:
            pos: Koordinat klik relatif terhadap widget.

        Returns:
            True jika titik klik berada di dalam batas widget.
        """
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar wadah pill, sakelar geser animasi, dan teks label.

        Args:
            event: Event pengecatan ulang widget.
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pill_rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        is_checked = self.isChecked()
        pill_bg = QColor("#2D2111") if is_checked else QColor("#0F172A")
        pill_border = QColor("#F59E0B") if is_checked else QColor("#334155")
        painter.setBrush(pill_bg)
        painter.setPen(QPen(pill_border, 1.4))
        painter.drawRoundedRect(pill_rect, 9.0, 9.0)

        track_w = 34.0
        track_h = 18.0
        track_x = 10.0
        track_y = (float(self.height()) - track_h) / 2.0
        track_rect = QRectF(track_x, track_y, track_w, track_h)
        track_color = QColor("#F59E0B") if is_checked else QColor("#334155")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, track_h / 2.0, track_h / 2.0)

        thumb_d = 14.0
        travel = track_w - thumb_d - 4.0
        thumb_x = track_x + 2.0 + (travel * self._thumb_progress)
        thumb_y = track_y + 2.0
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_d, thumb_d))

        text_rect = QRectF(
            track_x + track_w + 9.0,
            0.0,
            float(self.width()) - (track_x + track_w + 15.0),
            float(self.height()),
        )
        text_color = QColor("#FDE68A") if is_checked else QColor("#CBD5E1")
        label_font = QFont(self.font())
        label_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(label_font)
        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )
        painter.end()


class _BulkItemDelegate(QStyledItemDelegate):
    """Delegate kustom untuk merender checkbox, badge kategori, dan status stok."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar tiap sel tabel dengan gaya visual modern dan berwarna.

        Args:
            painter: Objek QPainter aktif untuk menggambar sel.
            option: Informasi gaya, state, dan geometri sel.
            index: Indeks model baris dan kolom sel yang dirender.
        """
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        self._paint_row_background(painter, opt, index)

        col = index.column()
        if col == 0:
            self._paint_checkbox_cell(painter, opt, index)
        elif col == 1:
            self._paint_sku_cell(painter, opt, index)
        elif col == 2:
            self._paint_name_cell(painter, opt, index)
        elif col == 3:
            self._paint_category_cell(painter, opt, index)
        elif col == 4:
            self._paint_stock_cell(painter, opt, index)
        else:
            super().paint(painter, option, index)

        painter.restore()

    def _paint_row_background(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar latar baris termasuk highlight hover, seleksi, dan garis bawah.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks baris yang sedang dirender.
        """
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            bg_color = QColor("#1E2F4D")
        elif is_hovered:
            bg_color = QColor("#1A263C")
        elif index.row() % 2 == 1:
            bg_color = QColor("#131D31")
        else:
            bg_color = QColor("#0F172A")

        painter.fillRect(option.rect, bg_color)
        painter.setPen(QPen(QColor("#1E293B"), 1.0))
        painter.drawLine(
            option.rect.bottomLeft(),
            option.rect.bottomRight(),
        )

    def _paint_checkbox_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar kotak centang modern tepat di tengah sel kolom Pilih.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks sel kolom checkbox.
        """
        center = option.rect.center()
        box_size = 18.0
        box_rect = QRectF(
            float(center.x()) - (box_size / 2.0),
            float(center.y()) - (box_size / 2.0),
            box_size,
            box_size,
        )

        raw_state = index.data(Qt.ItemDataRole.CheckStateRole)
        is_checked = raw_state in (
            Qt.CheckState.Checked,
            Qt.CheckState.Checked.value,
        )
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_checked:
            painter.setBrush(QColor("#10B981"))
            painter.setPen(QPen(QColor("#34D399"), 1.5))
            painter.drawRoundedRect(box_rect, 5.0, 5.0)

            check_pen = QPen(QColor("#FFFFFF"), 2.2)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)

            tick = QPainterPath()
            tick.moveTo(box_rect.left() + 4.2, box_rect.top() + 9.2)
            tick.lineTo(box_rect.left() + 7.6, box_rect.top() + 12.6)
            tick.lineTo(box_rect.left() + 13.8, box_rect.top() + 5.6)
            painter.drawPath(tick)
        else:
            border_color = QColor("#38BDF8") if is_hovered else QColor("#475569")
            painter.setBrush(QColor("#0B1120"))
            painter.setPen(QPen(border_color, 1.5))
            painter.drawRoundedRect(box_rect, 5.0, 5.0)

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Menangani klik mouse dan tombol spasi pada kotak centang di tengah sel.

        Args:
            event: Event masukan dari pengguna.
            model: Model data milik tabel.
            option: Informasi geometri dan gaya sel.
            index: Indeks baris dan kolom sel yang menerima event.

        Returns:
            True jika event telah ditangani oleh delegate.
        """
        if index.column() != 0:
            return super().editorEvent(event, model, option, index)

        flags = model.flags(index)
        is_checkable = bool(flags & Qt.ItemFlag.ItemIsUserCheckable)
        is_enabled = bool(flags & Qt.ItemFlag.ItemIsEnabled)
        if not (is_checkable and is_enabled):
            return False

        event_type = event.type()
        if event_type in (
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            if not isinstance(event, QMouseEvent):
                return False
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            center = option.rect.center()
            hit_rect = QRect(center.x() - 14, center.y() - 14, 28, 28)
            if not hit_rect.contains(event.position().toPoint()):
                return False
            if event_type == QEvent.Type.MouseButtonDblClick:
                return True
            return self._toggle_check_state(model, index)

        if event_type == QEvent.Type.KeyPress:
            if not isinstance(event, QKeyEvent):
                return False
            if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Select):
                return self._toggle_check_state(model, index)

        return False

    def _toggle_check_state(
        self,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Membalik status centang item pada indeks tabel yang diberikan.

        Args:
            model: Model data tabel tempat status centang disimpan.
            index: Indeks sel yang status centangnya akan diubah.

        Returns:
            True jika pembaruan data pada model berhasil.
        """
        raw_state = index.data(Qt.ItemDataRole.CheckStateRole)
        is_checked = raw_state in (
            Qt.CheckState.Checked,
            Qt.CheckState.Checked.value,
        )
        next_state = (
            Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
        )
        return model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole)

    def _paint_sku_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar teks SKU berwarna cyan dengan gaya rapi.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks sel kolom SKU.
        """
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        sku_font = QFont(option.font)
        sku_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(sku_font)
        painter.setPen(QColor("#7DD3FC"))
        text_rect = option.rect.adjusted(10, 0, -8, 0)
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )

    def _paint_name_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar nama barang sebagai fokus utama dengan kontras tinggi.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks sel kolom nama barang.
        """
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        name_font = QFont(option.font)
        name_font.setWeight(QFont.Weight.Medium)
        painter.setFont(name_font)
        painter.setPen(QColor("#F8FAFC"))
        text_rect = option.rect.adjusted(10, 0, -10, 0)
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )

    def _paint_category_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar kategori barang sebagai chip berwarna dinamis.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks sel kolom kategori.
        """
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        palette_idx = sum(ord(ch) for ch in text) % len(_CATEGORY_PALETTE)
        bg_hex, border_hex, text_hex = _CATEGORY_PALETTE[palette_idx]

        badge_font = QFont(option.font)
        badge_font.setPointSize(max(8, badge_font.pointSize() - 1))
        badge_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(badge_font)

        max_w = max(40, option.rect.width() - 18)
        raw_text_w = painter.fontMetrics().horizontalAdvance(text)
        pill_w = min(max_w, raw_text_w + 20)
        pill_h = 24
        pill_x = option.rect.left() + 9
        pill_y = option.rect.top() + ((option.rect.height() - pill_h) // 2)
        pill_rect = QRectF(float(pill_x), float(pill_y), float(pill_w), float(pill_h))

        painter.setBrush(QColor(bg_hex))
        painter.setPen(QPen(QColor(border_hex), 1.1))
        painter.drawRoundedRect(pill_rect, 12.0, 12.0)

        painter.setPen(QColor(text_hex))
        inner_rect = pill_rect.adjusted(8.0, 0.0, -8.0, 0.0)
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            int(inner_rect.width()),
        )
        painter.drawText(
            inner_rect,
            int(Qt.AlignmentFlag.AlignCenter),
            elided,
        )

    def _paint_stock_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Menggambar sisa stok dalam badge semantik sesuai tingkat ketersediaan.

        Args:
            painter: Objek QPainter aktif.
            option: Opsi gaya sel.
            index: Indeks sel kolom sisa stok.
        """
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        raw_stock = index.data(Qt.ItemDataRole.UserRole)
        stock_val = float(raw_stock) if isinstance(raw_stock, (int, float)) else 0.0

        if stock_val <= 0.0:
            bg_hex, border_hex, text_hex, dot_hex = (
                "#3B1120",
                "#E11D48",
                "#FDA4AF",
                "#FB7185",
            )
        elif stock_val <= 10.0:
            bg_hex, border_hex, text_hex, dot_hex = (
                "#33230C",
                "#D97706",
                "#FDE68A",
                "#FBBF24",
            )
        else:
            bg_hex, border_hex, text_hex, dot_hex = (
                "#0B2E26",
                "#059669",
                "#A7F3D0",
                "#34D399",
            )

        stock_font = QFont(option.font)
        stock_font.setPointSize(max(8, stock_font.pointSize() - 1))
        stock_font.setWeight(QFont.Weight.Bold)
        painter.setFont(stock_font)

        max_w = max(56, option.rect.width() - 18)
        raw_text_w = painter.fontMetrics().horizontalAdvance(text)
        pill_w = min(max_w, raw_text_w + 28)
        pill_h = 24
        pill_x = option.rect.right() - pill_w - 10
        pill_y = option.rect.top() + ((option.rect.height() - pill_h) // 2)
        pill_rect = QRectF(float(pill_x), float(pill_y), float(pill_w), float(pill_h))

        painter.setBrush(QColor(bg_hex))
        painter.setPen(QPen(QColor(border_hex), 1.1))
        painter.drawRoundedRect(pill_rect, 12.0, 12.0)

        dot_center = QPointF(pill_rect.left() + 10.0, pill_rect.center().y())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(dot_hex))
        painter.drawEllipse(dot_center, 3.0, 3.0)

        painter.setPen(QColor(text_hex))
        inner_rect = pill_rect.adjusted(18.0, 0.0, -8.0, 0.0)
        elided = painter.fontMetrics().elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            int(inner_rect.width()),
        )
        painter.drawText(
            inner_rect,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )


class BulkItemPickerDialog(CustomDialog):
    """Dialog pemilihan banyak barang sekaligus dengan filter kategori dan stok menipis."""

    def __init__(
        self,
        items: list[BulkCatalogItemView],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi BulkItemPickerDialog.

        Args:
            items: Daftar barang katalog lengkap beserta nama kategorinya.
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

        self._all_items = items
        self._filtered_items: list[BulkCatalogItemView] = list(items)
        self._selected_ids: set[int] = set()

        self.setWindowTitle("Pilih Banyak Barang Sekaligus")
        self.setMinimumSize(880, 580)
        self.content_widget.setStyleSheet(BULK_PICKER_STYLESHEET)

        self._visible_stat_label = QLabel("0", self.content_widget)
        self._low_stat_label = QLabel("0", self.content_widget)
        self._selected_stat_label = QLabel("0", self.content_widget)
        self._count_pill = QFrame(self.content_widget)

        self.search_input = QLineEdit(self.content_widget)
        self.category_combo: QComboBox = _ModernComboBox(self.content_widget)
        self.low_stock_check: QCheckBox = _ToggleSwitchCheckBox(
            "Hanya Stok <= 10",
            self.content_widget,
        )
        self.table = QTableWidget(0, 5, self.content_widget)
        self.count_label = QLabel("0 barang dipilih", self.content_widget)
        self._select_visible_btn = QPushButton(
            "Centang Semua Tampil",
            self.content_widget,
        )

        self._setup_ui()
        self._render_table()

    def _setup_ui(self) -> None:
        """Menyusun seluruh bagian antarmuka dialog ke dalam area konten."""
        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header_banner())
        layout.addWidget(self._build_filter_bar())
        layout.addWidget(self._build_table_container(), 1)
        layout.addWidget(self._build_footer_bar())

    def _build_header_banner(self) -> QFrame:
        """Membangun banner judul berwarna dengan ikon SVG dan statistik ringkas.

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
        icon_label.setPixmap(render_svg_pixmap(_SVG_HEADER_BOX, 24))
        icon_layout.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        title = QLabel("Pilih Banyak Barang (Bulk Picker)", banner)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Saring katalog berdasarkan SKU, kategori, atau stok menipis "
            "lalu centang barang sekaligus.",
            banner,
        )
        subtitle.setObjectName("dialogSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        stats_row.addWidget(
            self._create_stat_chip(
                _SVG_LAYERS,
                self._visible_stat_label,
                "statValueVisible",
                "Tampil",
            )
        )
        stats_row.addWidget(
            self._create_stat_chip(
                _SVG_ALERT,
                self._low_stat_label,
                "statValueLow",
                "Stok <= 10",
            )
        )
        stats_row.addWidget(
            self._create_stat_chip(
                _SVG_CHECK_CIRCLE,
                self._selected_stat_label,
                "statValueSelected",
                "Dipilih",
            )
        )

        row.addWidget(icon_wrap)
        row.addLayout(title_col, 1)
        row.addLayout(stats_row)
        return banner

    def _create_stat_chip(
        self,
        svg_markup: str,
        value_label: QLabel,
        value_object_name: str,
        caption_text: str,
    ) -> QFrame:
        """Membuat kartu chip statistik mini untuk area header dialog.

        Args:
            svg_markup: Markup SVG ikon untuk chip statistik.
            value_label: QLabel penampil angka statistik yang akan diperbarui dinamis.
            value_object_name: Nama objek QSS untuk pewarnaan nilai statistik.
            caption_text: Keterangan singkat di bawah angka statistik.

        Returns:
            Widget QFrame chip statistik siap dipasang ke layout.
        """
        chip = QFrame(self.content_widget)
        chip.setObjectName("statChip")

        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(10, 6, 12, 6)
        chip_layout.setSpacing(8)

        icon_label = QLabel(chip)
        icon_label.setPixmap(render_svg_pixmap(svg_markup, 18))
        icon_label.setFixedSize(18, 18)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        value_label.setParent(chip)
        value_label.setObjectName(value_object_name)

        caption = QLabel(caption_text, chip)
        caption.setObjectName("statCaption")

        text_col.addWidget(value_label)
        text_col.addWidget(caption)

        chip_layout.addWidget(icon_label)
        chip_layout.addLayout(text_col)
        return chip

    def _build_filter_bar(self) -> QFrame:
        """Membangun kartu filter berisi pencarian, kategori, sakelar stok, dan aksi.

        Returns:
            Widget QFrame kartu filter dialog.
        """
        filter_card = QFrame(self.content_widget)
        filter_card.setObjectName("filterCard")

        filter_row = QHBoxLayout(filter_card)
        filter_row.setContentsMargins(12, 10, 12, 10)
        filter_row.setSpacing(10)

        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Cari SKU atau nama barang...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.addAction(
            build_svg_icon(_SVG_SEARCH, size=16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_input.textChanged.connect(self._apply_filter)

        self.category_combo.setObjectName("categoryCombo")
        self.category_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_combo.addItem("Semua Kategori", "")
        categories = sorted({entry["category_name"] for entry in self._all_items})
        for cat in categories:
            self.category_combo.addItem(cat, cat)
        combo_view = self.category_combo.view()
        if combo_view is not None:
            combo_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_combo.currentIndexChanged.connect(self._apply_filter)

        self.low_stock_check.toggled.connect(self._apply_filter)

        self._select_visible_btn.setParent(filter_card)
        self._select_visible_btn.setObjectName("selectAllBtn")
        self._select_visible_btn.setIcon(build_svg_icon(_SVG_CHECK_ALL, size=15))
        self._select_visible_btn.setIconSize(QSize(15, 15))
        self._select_visible_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_visible_btn.clicked.connect(self._select_all_visible)

        filter_row.addWidget(self.search_input, 1)
        filter_row.addWidget(self.category_combo)
        filter_row.addWidget(self.low_stock_check)
        filter_row.addWidget(self._select_visible_btn)
        return filter_card

    def _build_table_container(self) -> QFrame:
        """Membangun wadah tabel dan mengonfigurasi kolom serta delegate kustom.

        Returns:
            Widget QFrame pembungkus QTableWidget.
        """
        container = QFrame(self.content_widget)
        container.setObjectName("tableContainer")

        box = QVBoxLayout(container)
        box.setContentsMargins(6, 6, 6, 6)
        box.setSpacing(0)

        self.table.setObjectName("bulkTable")
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setHorizontalHeaderLabels(
            ["Pilih", "SKU", "Nama Barang", "Kategori", "Sisa Stok"]
        )
        
        pilih_header = self.table.horizontalHeaderItem(0)
        if pilih_header is not None:
            pilih_header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setItemDelegate(_BulkItemDelegate(self.table))

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
            h_head.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            h_head.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            h_head.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            h_head.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 62)
        self.table.setColumnWidth(1, 138)
        self.table.setColumnWidth(3, 168)
        self.table.setColumnWidth(4, 148)
        self.table.itemChanged.connect(self._handle_item_checked)

        box.addWidget(self.table)
        return container

    def _build_footer_bar(self) -> QFrame:
        """Membangun footer dialog berisi pill jumlah pilihan dan tombol aksi.

        Returns:
            Widget QFrame footer dialog.
        """
        footer = QFrame(self.content_widget)
        footer.setObjectName("footerBar")

        btn_row = QHBoxLayout(footer)
        btn_row.setContentsMargins(14, 10, 14, 10)
        btn_row.setSpacing(10)

        self._count_pill.setParent(footer)
        self._count_pill.setObjectName("selectionPill")
        pill_layout = QHBoxLayout(self._count_pill)
        pill_layout.setContentsMargins(12, 6, 14, 6)
        pill_layout.setSpacing(8)

        pill_icon = QLabel(self._count_pill)
        pill_icon.setPixmap(render_svg_pixmap(_SVG_CHECK_CIRCLE, 16))
        pill_icon.setFixedSize(16, 16)

        self.count_label.setParent(self._count_pill)
        self.count_label.setObjectName("countLabel")

        pill_layout.addWidget(pill_icon)
        pill_layout.addWidget(self.count_label)

        cancel_btn = QPushButton("Batal", footer)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setIcon(build_svg_icon(_SVG_CANCEL, size=15))
        cancel_btn.setIconSize(QSize(15, 15))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Tambahkan ke Keranjang", footer)
        add_btn.setObjectName("primaryBtn")
        add_btn.setIcon(build_svg_icon(_SVG_CART_PLUS, size=16))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.accept)

        btn_row.addWidget(self._count_pill)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        return footer

    def _apply_filter(self) -> None:
        """Menyaring daftar barang sesuai teks pencarian, kategori, dan batas stok."""
        query = self.search_input.text().strip().lower()
        selected_category = str(self.category_combo.currentData() or "")
        only_low = self.low_stock_check.isChecked()

        filtered: list[BulkCatalogItemView] = []
        for entry in self._all_items:
            item = entry["catalog_item"]
            if selected_category and entry["category_name"] != selected_category:
                continue
            if only_low and item["current_stock"] > 10.0:
                continue
            if query and (
                query not in item["sku"].lower() and query not in item["name"].lower()
            ):
                continue
            filtered.append(entry)

        self._filtered_items = filtered
        self._render_table()

    def _render_table(self) -> None:
        """Merender ulang isi tabel dialog tanpa memicu sinyal itemChanged palsu."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._filtered_items))
        low_stock_visible = 0
        for row_idx, entry in enumerate(self._filtered_items):
            item = entry["catalog_item"]
            if item["current_stock"] <= 10.0:
                low_stock_visible += 1

            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setData(Qt.ItemDataRole.UserRole, item["item_id"])
            is_checked = item["item_id"] in self._selected_ids
            check_item.setCheckState(
                Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
            )
            self.table.setItem(row_idx, 0, check_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(item["sku"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item["name"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(entry["category_name"]))

            stock_item = QTableWidgetItem(
                f"{format_quantity(item['current_stock'])} {item['base_unit_symbol']}"
            )
            stock_item.setData(Qt.ItemDataRole.UserRole, float(item["current_stock"]))
            stock_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row_idx, 4, stock_item)
        self.table.blockSignals(False)

        self._visible_stat_label.setText(str(len(self._filtered_items)))
        self._low_stat_label.setText(str(low_stock_visible))
        self._update_selected_count()

    def _handle_item_checked(self, item: QTableWidgetItem) -> None:
        """Memperbarui himpunan ID barang terpilih saat checkbox berubah.

        Args:
            item: Objek sel tabel yang status centangnya berubah.
        """
        if item.column() != 0:
            return
        raw_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(raw_id, int):
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(raw_id)
        else:
            self._selected_ids.discard(raw_id)
        self._update_selected_count()

    def _select_all_visible(self) -> None:
        """Mencentang seluruh item tampil jika kosong, atau menghapus semua centang."""
        if self._selected_ids:
            self._selected_ids.clear()
        else:
            for entry in self._filtered_items:
                self._selected_ids.add(entry["catalog_item"]["item_id"])
        self._render_table()

    def _update_selected_count(self) -> None:
        """Memperbarui teks jumlah barang terpilih, tombol pilih semua, dan footer."""
        count = len(self._selected_ids)
        self.count_label.setText(f"{count} barang dipilih")
        self._selected_stat_label.setText(str(count))

        if count > 0:
            self._select_visible_btn.setText("Hapus Semua Centang")
            self._select_visible_btn.setIcon(build_svg_icon(_SVG_CANCEL, size=15))
        else:
            self._select_visible_btn.setText("Centang Semua Tampil")
            self._select_visible_btn.setIcon(build_svg_icon(_SVG_CHECK_ALL, size=15))

        state = "active" if count > 0 else "empty"
        self._count_pill.setProperty("selectedState", state)
        self.count_label.setProperty("selectedState", state)

        for widget in (self._count_pill, self.count_label):
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)

    def get_selected_items(self) -> list[CatalogItemData]:
        """Mengembalikan daftar CatalogItemData yang dicentang pengguna.

        Returns:
            Daftar CatalogItemData siap ditambahkan ke keranjang belanja.
        """
        return [
            entry["catalog_item"]
            for entry in self._all_items
            if entry["catalog_item"]["item_id"] in self._selected_ids
        ]