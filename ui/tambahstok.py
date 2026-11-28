"""Modul antarmuka pengguna (UI) Tambah Stok dan Kulakan berbasis PySide6.

Modul ini menyediakan halaman input pembelian stok dengan prioritas Mode Grid
Keyboard-First serta tab riwayat kulakan dan pelunasan hutang supplier. Seluruh
komponen dirancang terpisah dari logika basis data agar siap diintegrasikan
dengan modul backend melalui sinyal Qt dan metode publik terstruktur.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TypedDict

from PySide6.QtCore import (
    QDate,
    QDateTime,
    QLocale,
    QRect,
    QSize,
    QStringListModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFocusEvent,
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCalendarWidget,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.customwindowtitlebar import (
    ICON_PATHS,
    FramelessMainWindow,
    TitleBarIconConfig,
)
from util.customtooltip import TooltipPosition, attach_tooltip
from util.helper.formatrupiah import format_qty as format_quantity
from util.helper.formatrupiah import format_rupiah
from util.helper.svg_helper import build_svg_icon
from util.helper.toast_helper import show_toast


class SupplierOption(TypedDict):
    """Struktur data ringkas pilihan supplier untuk komponen dropdown.

    Attributes:
        id: ID unik supplier pada tabel suppliers.
        name: Nama supplier yang ditampilkan.
        phone: Nomor telepon supplier opsional.
    """

    id: int
    name: str
    phone: str


class ItemUnitOption(TypedDict):
    """Struktur data varian satuan beli untuk satu barang.

    Attributes:
        item_unit_id: ID unik pada tabel item_units.
        variant_name: Nama varian satuan, misalnya Rim atau Dus.
        unit_symbol: Simbol satuan singkat, misalnya rim atau pcs.
        conversion_qty: Faktor konversi ke satuan dasar barang.
        selling_price: Harga jual saat ini pada satuan tersebut.
        is_default: Penanda satuan bawaan untuk barang terkait.
        last_unit_cost: Harga beli terakhir per satuan varian ini.
    """

    item_unit_id: int
    variant_name: str
    unit_symbol: str
    conversion_qty: float
    selling_price: int
    is_default: bool
    last_unit_cost: float


class CatalogItemData(TypedDict):
    """Struktur data katalog barang untuk pencarian cepat dan keranjang.

    Attributes:
        item_id: ID unik barang pada tabel items.
        sku: Kode SKU atau barcode barang.
        name: Nama lengkap barang.
        base_unit_symbol: Simbol satuan dasar barang pada tabel units.
        current_stock: Total sisa stok saat ini dalam satuan dasar.
        units: Daftar varian satuan yang tersedia untuk barang ini.
    """

    item_id: int
    sku: str
    name: str
    base_unit_symbol: str
    current_stock: float
    units: list[ItemUnitOption]


class PurchaseLinePayload(TypedDict):
    """Struktur data satu baris item pembelian untuk tabel purchase_details.

    Attributes:
        item_id: ID barang yang dibeli.
        item_unit_id: ID varian satuan pembelian.
        quantity: Jumlah beli pada satuan terpilih.
        conversion_qty: Faktor konversi satuan ke satuan dasar.
        base_quantity: Jumlah stok masuk dalam satuan dasar.
        unit_cost: Harga beli per satuan pembelian.
        subtotal: Total biaya untuk baris item ini.
    """

    item_id: int
    item_unit_id: int
    quantity: float
    conversion_qty: float
    base_quantity: float
    unit_cost: float
    subtotal: float


class PurchasePayload(TypedDict):
    """Struktur data lengkap nota pembelian untuk dikirim ke backend.

    Attributes:
        invoice_number: Nomor faktur atau nota pembelian.
        supplier_id: ID supplier atau None untuk belanja umum.
        purchase_date: Tanggal dan waktu transaksi pembelian.
        subtotal: Jumlah subtotal seluruh item sebelum diskon.
        discount: Nilai potongan harga tingkat nota.
        total: Total akhir pembelian setelah diskon.
        payment_method: Metode pembayaran yang dipilih.
        amount_paid: Nominal uang yang dibayarkan saat transaksi.
        remaining_amount: Sisa hutang pembelian ke supplier.
        payment_status: Status pembayaran PAID, PARTIAL, atau UNPAID.
        due_date: Tanggal jatuh tempo pembayaran atau None jika lunas.
        status: Status dokumen COMPLETED atau DRAFT.
        notes: Catatan tambahan untuk nota pembelian.
        reference_number: Nomor referensi transfer non-tunai atau None.
        details: Daftar rincian item dalam keranjang pembelian.
    """

    invoice_number: str
    supplier_id: int | None
    purchase_date: str
    subtotal: int
    discount: int
    total: int
    payment_method: str
    amount_paid: int
    remaining_amount: int
    payment_status: str
    due_date: str | None
    status: str
    notes: str
    reference_number: str | None
    details: list[PurchaseLinePayload]


class PurchaseHistoryRow(TypedDict):
    """Struktur data satu baris ringkasan riwayat pembelian supplier.

    Attributes:
        id: ID unik transaksi pada tabel purchases.
        purchase_date: Tanggal dan waktu pembelian.
        invoice_number: Nomor faktur pembelian.
        supplier_name: Nama supplier atau label belanja umum.
        total: Nilai total nota pembelian.
        amount_paid: Total nominal yang telah dibayarkan.
        remaining_amount: Sisa tagihan yang belum lunas.
        payment_status: Status pembayaran PAID, PARTIAL, atau UNPAID.
        due_date: Tanggal jatuh tempo atau None.
        status: Status transaksi COMPLETED atau DRAFT.
    """

    id: int
    purchase_date: str
    invoice_number: str
    supplier_name: str
    total: int
    amount_paid: int
    remaining_amount: int
    payment_status: str
    due_date: str | None
    status: str


class HistoryFilterPayload(TypedDict):
    """Struktur data filter pencarian pada tab riwayat kulakan.

    Attributes:
        search: Kata kunci nomor faktur atau nama supplier.
        payment_status: Filter status pembayaran ALL, PAID, PARTIAL, atau UNPAID.
        date_from: Tanggal awal filter dalam format yyyy-MM-dd.
        date_to: Tanggal akhir filter dalam format yyyy-MM-dd.
    """

    search: str
    payment_status: str
    date_from: str
    date_to: str


SVG_SEARCH: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<circle cx='11' cy='11' r='7'/>"
    "<line x1='20' y1='20' x2='16.65' y2='16.65'/>"
    "</svg>"
)

SVG_PLUS: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.4' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<line x1='12' y1='5' x2='12' y2='19'/>"
    "<line x1='5' y1='12' x2='19' y2='12'/>"
    "</svg>"
)

SVG_LAYERS: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polygon points='12 2 2 7 12 12 22 7 12 2'/>"
    "<polyline points='2 17 12 22 22 17'/>"
    "<polyline points='2 12 12 17 22 12'/>"
    "</svg>"
)

SVG_REPEAT: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polyline points='17 1 21 5 17 9'/>"
    "<path d='M3 11V9a4 4 0 0 1 4-4h14'/>"
    "<polyline points='7 23 3 19 7 15'/>"
    "<path d='M21 13v2a4 4 0 0 1-4 4H3'/>"
    "</svg>"
)

SVG_UPLOAD: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/>"
    "<polyline points='17 8 12 3 7 8'/>"
    "<line x1='12' y1='3' x2='12' y2='15'/>"
    "</svg>"
)

SVG_TRASH: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polyline points='3 6 5 6 21 6'/>"
    "<path d='M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6'/>"
    "<path d='M10 11v6'/>"
    "<path d='M14 11v6'/>"
    "<path d='M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2'/>"
    "</svg>"
)

SVG_TAG: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z'/>"
    "<line x1='7' y1='7' x2='7.01' y2='7'/>"
    "</svg>"
)

SVG_CHECK: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.4' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polyline points='20 6 9 17 4 12'/>"
    "</svg>"
)

SVG_SAVE: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z'/>"
    "<polyline points='17 21 17 13 7 13 7 21'/>"
    "<polyline points='7 3 7 8 15 8'/>"
    "</svg>"
)

SVG_REFRESH: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polyline points='23 4 23 10 17 10'/>"
    "<path d='M20.49 15a9 9 0 1 1-2.12-9.36L23 10'/>"
    "</svg>"
)

SVG_SPARKLE: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M12 3l1.9 5.8L20 10.7l-6.1 1.9L12 18.4l-1.9-5.8L4 10.7l6.1-1.9L12 3z'/>"
    "</svg>"
)

SVG_EYE: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'/>"
    "<circle cx='12' cy='12' r='3'/>"
    "</svg>"
)

SVG_WALLET: str = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<rect x='2' y='5' width='20' height='14' rx='2'/>"
    "<path d='M16 12h4'/>"
    "</svg>"
)


def _draw_calendar_glyph(painter: QPainter, center_x: float, center_y: float, color: QColor) -> None:
    """Menggambar ikon kalender vektor minimalis dengan anti-aliasing pada sisi kanan widget.

    Args:
        painter: Instance QPainter aktif milik widget target.
        center_x: Koordinat horizontal titik tengah ikon.
        center_y: Koordinat vertikal titik tengah ikon.
        color: Warna garis vektor ikon kalender.
    """
    pen = QPen(
        color,
        1.5,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    left = center_x - 5.5
    top = center_y - 4.5
    width = 11.0
    height = 10.0

    painter.drawRoundedRect(
        int(round(left)),
        int(round(top)),
        int(round(width)),
        int(round(height)),
        2.0,
        2.0,
    )
    painter.drawLine(
        int(round(left + 1.0)),
        int(round(top + 3.5)),
        int(round(left + width - 1.0)),
        int(round(top + 3.5)),
    )
    painter.drawLine(
        int(round(left + 3.0)),
        int(round(top - 1.5)),
        int(round(left + 3.0)),
        int(round(top + 1.0)),
    )
    painter.drawLine(
        int(round(left + width - 3.0)),
        int(round(top - 1.5)),
        int(round(left + width - 3.0)),
        int(round(top + 1.0)),
    )


def _configure_popup_calendar(calendar: QCalendarWidget | None) -> None:
    """Mengonfigurasi tampilan popup kalender agar bersih tanpa header nomor minggu.

    Args:
        calendar: Instance QCalendarWidget milik QDateEdit atau QDateTimeEdit.
    """
    if calendar is None:
        return
    calendar.setGridVisible(False)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setNavigationBarVisible(True)


class StyledComboBox(QComboBox):
    """Dropdown kustom dengan indikator chevron vektor anti-aliased pengganti panah bawaan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi StyledComboBox dengan kursor interaktif.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar kotak combo beserta ikon chevron modern pada area kanan.

        Args:
            event: Objek QPaintEvent dari siklus render Qt.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self.isEnabled():
            arrow_color = QColor("#475569")
        elif self.hasFocus():
            arrow_color = QColor("#22D3EE")
        else:
            arrow_color = QColor("#94A3B8")

        pen = QPen(
            arrow_color,
            1.8,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)

        center_x = float(self.width() - 14)
        center_y = float(self.height()) / 2.0
        chevron = QPainterPath()
        chevron.moveTo(center_x - 4.0, center_y - 2.0)
        chevron.lineTo(center_x, center_y + 2.5)
        chevron.lineTo(center_x + 4.0, center_y - 2.0)
        painter.drawPath(chevron)
        painter.end()


class StyledDateEdit(QDateEdit):
    """Input tanggal kustom dengan ikon kalender vektor dan popup kalender tema gelap."""

    def __init__(self, date: QDate, parent: QWidget | None = None) -> None:
        """Menginisialisasi StyledDateEdit dengan popup kalender terkonfigurasi.

        Args:
            date: Tanggal awal yang ditampilkan.
            parent: Widget induk opsional.
        """
        super().__init__(date, parent)
        self.setCalendarPopup(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _configure_popup_calendar(self.calendarWidget())

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar input tanggal beserta ikon kalender vektor di sisi kanan.

        Args:
            event: Objek QPaintEvent dari siklus render Qt.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self.isEnabled():
            icon_color = QColor("#475569")
        elif self.hasFocus():
            icon_color = QColor("#22D3EE")
        else:
            icon_color = QColor("#60A5FA")

        _draw_calendar_glyph(
            painter,
            float(self.width() - 15),
            float(self.height()) / 2.0,
            icon_color,
        )
        painter.end()


class StyledDateTimeEdit(QDateTimeEdit):
    """Input tanggal-waktu kustom dengan ikon kalender vektor dan popup kalender tema gelap."""

    def __init__(self, date_time: QDateTime, parent: QWidget | None = None) -> None:
        """Menginisialisasi StyledDateTimeEdit dengan popup kalender terkonfigurasi.

        Args:
            date_time: Tanggal dan waktu awal yang ditampilkan.
            parent: Widget induk opsional.
        """
        super().__init__(date_time, parent)
        self.setCalendarPopup(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _configure_popup_calendar(self.calendarWidget())

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar input tanggal-waktu beserta ikon kalender vektor di sisi kanan.

        Args:
            event: Objek QPaintEvent dari siklus render Qt.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self.isEnabled():
            icon_color = QColor("#475569")
        elif self.hasFocus():
            icon_color = QColor("#22D3EE")
        else:
            icon_color = QColor("#60A5FA")

        _draw_calendar_glyph(
            painter,
            float(self.width() - 15),
            float(self.height()) / 2.0,
            icon_color,
        )
        painter.end()


class ColoredHeaderView(QHeaderView):
    """Header tabel horizontal kustom dengan pewarnaan teks dan aksen per kolom."""

    def __init__(
        self,
        column_colors: dict[int, str],
        column_alignments: dict[int, Qt.AlignmentFlag] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi ColoredHeaderView dengan peta warna setiap kolom.

        Args:
            column_colors: Peta indeks kolom ke kode warna heksadesimal.
            column_alignments: Peta opsional perataan teks tiap indeks kolom.
            parent: Widget induk opsional.
        """
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._column_colors = column_colors
        self._column_alignments = column_alignments if column_alignments is not None else {}
        self.setHighlightSections(False)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(38)

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int) -> None:
        """Menggambar tiap segmen header dengan gradasi gelap dan aksen warna kolom.

        Args:
            painter: Instance QPainter yang disediakan oleh QHeaderView.
            rect: Area persegi segmen header yang akan digambar.
            logicalIndex: Indeks logis kolom tabel.
        """
        painter.save()

        bg_gradient = QLinearGradient(
            float(rect.left()),
            float(rect.top()),
            float(rect.left()),
            float(rect.bottom()),
        )
        bg_gradient.setColorAt(0.0, QColor("#1B223C"))
        bg_gradient.setColorAt(1.0, QColor("#13182B"))
        painter.fillRect(rect, bg_gradient)

        painter.setPen(QPen(QColor("#263052"), 1.0))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        accent_hex = self._column_colors.get(logicalIndex, "#CBD5E1")
        bar_width = max(0, rect.width() - 18)
        if bar_width > 0:
            accent_bar = QColor(accent_hex)
            accent_bar.setAlpha(110)
            painter.fillRect(
                QRect(rect.left() + 9, rect.bottom() - 2, bar_width, 2),
                accent_bar,
            )

        header_text = ""
        model = self.model()
        if model is not None:
            raw_title = model.headerData(
                logicalIndex,
                self.orientation(),
                Qt.ItemDataRole.DisplayRole,
            )
            if raw_title is not None:
                header_text = str(raw_title)

        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(accent_hex))

        alignment = self._column_alignments.get(logicalIndex, Qt.AlignmentFlag.AlignCenter)
        text_rect = rect.adjusted(8, 0, -8, -2)
        painter.drawText(
            text_rect,
            int(alignment | Qt.AlignmentFlag.AlignVCenter),
            header_text,
        )
        painter.restore()


class QuickSearchLineEdit(QLineEdit):
    """Input pencarian barang cepat yang dioptimalkan untuk alur keyboard.

    Attributes:
        item_submitted: Sinyal saat tombol Enter ditekan pada kotak pencarian.
        focus_grid_requested: Sinyal saat tombol Panah Bawah ditekan tanpa popup aktif.
    """

    item_submitted = Signal(str)
    focus_grid_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi QuickSearchLineEdit dengan pengaturan dasar.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setClearButtonEnabled(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Menangani pintasan Enter dan Panah Bawah untuk navigasi cepat.

        Args:
            event: Objek QKeyEvent dari sistem input Qt.
        """
        completer = self.completer()
        popup_visible = False
        if completer is not None:
            popup = completer.popup()
            if popup is not None:
                popup_visible = popup.isVisible()

        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not popup_visible:
            self.item_submitted.emit(self.text().strip())
            event.accept()
            return

        if key == Qt.Key.Key_Down and not popup_visible:
            self.focus_grid_requested.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class KeyboardDoubleSpinBox(QDoubleSpinBox):
    """SpinBox angka desimal khusus grid keyboard tanpa tombol panah tumpang tindih.

    Attributes:
        enter_pressed: Sinyal saat pengguna menekan Enter untuk berpindah fokus.
        navigate_vertical: Sinyal perpindahan baris (-1 naik, +1 turun) dengan Ctrl+Panah.
        row_delete_requested: Sinyal penghapusan baris aktif dengan Ctrl+Delete.
    """

    enter_pressed = Signal()
    navigate_vertical = Signal(int)
    row_delete_requested = Signal()

    def __init__(
        self,
        decimals: int = 2,
        minimum: float = 0.0,
        maximum: float = 999999999.0,
        prefix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi KeyboardDoubleSpinBox dengan format lokal Indonesia.

        Args:
            decimals: Jumlah angka di belakang koma.
            minimum: Nilai batas minimum.
            maximum: Nilai batas maksimum.
            prefix: Awalan teks opsional seperti 'Rp '.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setDecimals(decimals)
        self.setRange(minimum, maximum)
        self.setGroupSeparatorShown(True)
        self.setLocale(QLocale(QLocale.Language.Indonesian, QLocale.Country.Indonesia))
        if prefix:
            self.setPrefix(prefix)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Menyorot seluruh teks angka secara otomatis saat widget menerima fokus.

        Args:
            event: Objek QFocusEvent dari sistem fokus Qt.
        """
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Mencegah perubahan angka tidak sengaja akibat gulir mouse di tabel.

        Args:
            event: Objek QWheelEvent dari roda gulir mouse.
        """
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Menangani tombol Enter, navigasi baris vertikal, dan hapus baris cepat.

        Args:
            event: Objek QKeyEvent dari papan ketik.
        """
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.interpretText()
            self.enter_pressed.emit()
            event.accept()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Up:
            self.navigate_vertical.emit(-1)
            event.accept()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Down:
            self.navigate_vertical.emit(1)
            event.accept()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Delete:
            self.row_delete_requested.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class KeyboardUnitComboBox(StyledComboBox):
    """Dropdown pilihan satuan beli di dalam sel tabel yang ramah keyboard.

    Attributes:
        enter_pressed: Sinyal saat tombol Enter ditekan untuk pindah ke kolom Qty.
    """

    enter_pressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi KeyboardUnitComboBox.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Mengabaikan gulir mouse bila dropdown tidak sedang difokuskan.

        Args:
            event: Objek QWheelEvent dari roda mouse.
        """
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Memancarkan enter_pressed ketika pengguna menekan Enter pada combo box.

        Args:
            event: Objek QKeyEvent dari sistem input.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class CurrencySpinBox(QSpinBox):
    """Input angka bulat Rupiah tanpa tombol panah dengan seleksi otomatis saat fokus.

    Attributes:
        enter_pressed: Sinyal yang dipancarkan saat tombol Enter ditekan.
    """

    enter_pressed = Signal()

    def __init__(
        self,
        maximum: int = 2_000_000_000,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi CurrencySpinBox untuk input nominal Rupiah.

        Args:
            maximum: Batas nilai nominal maksimum.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setRange(0, maximum)
        self.setPrefix("Rp ")
        self.setGroupSeparatorShown(True)
        self.setLocale(QLocale(QLocale.Language.Indonesian, QLocale.Country.Indonesia))
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Memilih seluruh nilai teks secara otomatis ketika input mendapat fokus.

        Args:
            event: Objek QFocusEvent dari sistem fokus Qt.
        """
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Mencegah perubahan nominal tidak sengaja saat menggulir layar.

        Args:
            event: Objek QWheelEvent dari roda mouse.
        """
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Memancarkan sinyal enter_pressed saat pengguna menekan Enter.

        Args:
            event: Objek QKeyEvent dari papan ketik.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.interpretText()
            self.enter_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ItemInfoCellWidget(QWidget):
    """Widget tampilan sel barang yang menampilkan nama, SKU, dan stok saat ini."""

    def __init__(
        self,
        name: str,
        sku: str,
        current_stock: float,
        base_unit_symbol: str,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi ItemInfoCellWidget untuk kolom barang di keranjang.

        Args:
            name: Nama barang.
            sku: Kode SKU barang.
            current_stock: Jumlah stok tersedia saat ini.
            base_unit_symbol: Simbol satuan dasar barang.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(1)

        name_label = QLabel(name, self)
        name_label.setObjectName("cellItemName")

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        sku_label = QLabel(sku, self)
        sku_label.setObjectName("cellSkuTag")

        stock_label = QLabel(
            f"Stok: {format_quantity(current_stock)} {base_unit_symbol}",
            self,
        )
        stock_label.setObjectName("cellStockTag")

        meta_row.addWidget(sku_label)
        meta_row.addWidget(stock_label)
        meta_row.addStretch(1)

        layout.addWidget(name_label)
        layout.addLayout(meta_row)


class SubtotalCellWidget(QWidget):
    """Widget sel subtotal dua arah yang disertai pratinjau HPP satuan dasar.

    Attributes:
        subtotal_spin: Input angka subtotal yang dapat diedit langsung.
        hpp_label: Label pratinjau HPP per satuan dasar untuk layer FIFO.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi SubtotalCellWidget dengan spinbox dan label HPP.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        self.subtotal_spin = KeyboardDoubleSpinBox(
            decimals=0,
            minimum=0.0,
            maximum=2_000_000_000.0,
            prefix="Rp ",
            parent=self,
        )
        self.subtotal_spin.setObjectName("gridSpinBox")
        self.subtotal_spin.setFixedHeight(24)

        self.hpp_label = QLabel("HPP: Rp 0 / unit", self)
        self.hpp_label.setObjectName("cellHppPreview")
        self.hpp_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self.subtotal_spin)
        layout.addWidget(self.hpp_label)

    def update_hpp_preview(self, hpp_per_base: float, base_symbol: str) -> None:
        """Memperbarui teks pratinjau HPP per satuan dasar pada sel subtotal.

        Args:
            hpp_per_base: Nilai biaya modal per satu satuan dasar barang.
            base_symbol: Simbol satuan dasar barang.
        """
        self.hpp_label.setText(f"HPP: {format_rupiah(hpp_per_base)} / {base_symbol}")


class RowActionCellWidget(QWidget):
    """Widget sel aksi transparan berisi tombol edit harga jual dan hapus baris.

    Attributes:
        edit_price_clicked: Sinyal saat tombol ubah harga jual ditekan.
        delete_clicked: Sinyal saat tombol hapus baris ditekan.
    """

    edit_price_clicked = Signal()
    delete_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi RowActionCellWidget tanpa kotak latar gelap.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        price_button = QPushButton(self)
        price_button.setObjectName("iconActionNeutral")
        price_button.setIcon(build_svg_icon(SVG_TAG, "#38BDF8", 14))
        price_button.setIconSize(QSize(14, 14))
        price_button.setFixedSize(26, 26)
        attach_tooltip(
            price_button,
            "Cek / Ubah Harga Jual Barang",
            position=TooltipPosition.TOP,
        )
        price_button.setCursor(Qt.CursorShape.PointingHandCursor)
        price_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        price_button.clicked.connect(self.edit_price_clicked.emit)

        delete_button = QPushButton(self)
        delete_button.setObjectName("iconActionDanger")
        delete_button.setIcon(build_svg_icon(SVG_TRASH, "#FB7185", 14))
        delete_button.setIconSize(QSize(14, 14))
        delete_button.setFixedSize(26, 26)
        attach_tooltip(
            delete_button,
            "Hapus Baris (Ctrl+Del)",
            position=TooltipPosition.TOP,
        )
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        delete_button.clicked.connect(self.delete_clicked.emit)

        layout.addWidget(price_button)
        layout.addWidget(delete_button)


class HistoryActionCellWidget(QWidget):
    """Widget sel aksi transparan pada tabel riwayat pembelian.

    Attributes:
        detail_clicked: Sinyal saat tombol lihat detail nota ditekan.
        payment_clicked: Sinyal saat tombol bayar cicilan atau pelunasan ditekan.
        duplicate_clicked: Sinyal saat tombol belanja lagi ditekan.
    """

    detail_clicked = Signal()
    payment_clicked = Signal()
    duplicate_clicked = Signal()

    def __init__(
        self,
        can_pay: bool,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi HistoryActionCellWidget.

        Args:
            can_pay: Menentukan apakah tombol bayar pelunasan diaktifkan.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detail_btn = QPushButton("Detail", self)
        detail_btn.setObjectName("tablePillNeutral")
        detail_btn.setIcon(build_svg_icon(SVG_EYE, "#38BDF8", 13))
        detail_btn.setIconSize(QSize(13, 13))
        detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        detail_btn.clicked.connect(self.detail_clicked.emit)

        pay_btn = QPushButton("Bayar", self)
        pay_btn.setObjectName("tablePillSuccess")
        pay_btn.setIcon(
            build_svg_icon(SVG_WALLET, "#34D399" if can_pay else "#475569", 13)
        )
        pay_btn.setIconSize(QSize(13, 13))
        pay_btn.setEnabled(can_pay)
        pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pay_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pay_btn.clicked.connect(self.payment_clicked.emit)

        repeat_btn = QPushButton("Ulang", self)
        repeat_btn.setObjectName("tablePillAccent")
        repeat_btn.setIcon(build_svg_icon(SVG_REPEAT, "#C084FC", 13))
        repeat_btn.setIconSize(QSize(13, 13))
        attach_tooltip(
            repeat_btn,
            "Salin daftar barang nota ini ke keranjang",
            position=TooltipPosition.TOP,
        )
        repeat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        repeat_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        repeat_btn.clicked.connect(self.duplicate_clicked.emit)

        layout.addWidget(detail_btn)
        layout.addWidget(pay_btn)
        layout.addWidget(repeat_btn)


class TambahStokPage(QWidget):
    """Halaman utama UI Tambah Stok dengan prioritas Mode Grid Keyboard-First.

    Attributes:
        submit_purchase_requested: Sinyal pengiriman nota pembelian final (COMPLETED).
        save_draft_requested: Sinyal penyimpanan nota sebagai rencana belanja (DRAFT).
        add_supplier_requested: Sinyal permintaan membuka dialog tambah supplier baru.
        generate_invoice_requested: Sinyal permintaan nomor faktur otomatis dari backend.
        bulk_picker_requested: Sinyal permintaan membuka dialog pilih banyak barang.
        repeat_order_requested: Sinyal permintaan memuat ulang barang dari nota lama.
        import_csv_requested: Sinyal permintaan impor daftar kulakan dari CSV atau Excel.
        edit_selling_price_requested: Sinyal permintaan membuka edit harga jual item_id.
        search_text_changed: Sinyal perubahan teks pada kotak pencarian cepat.
        history_filter_changed: Sinyal perubahan filter pencarian pada tab riwayat.
        history_refresh_requested: Sinyal permintaan memuat ulang daftar riwayat kulakan.
        history_detail_requested: Sinyal permintaan melihat rincian nota pembelian.
        history_payment_requested: Sinyal permintaan membuka pelunasan hutang nota.
        history_duplicate_requested: Sinyal permintaan menyalin nota lama ke keranjang.
    """

    submit_purchase_requested = Signal(dict)
    save_draft_requested = Signal(dict)
    add_supplier_requested = Signal()
    generate_invoice_requested = Signal()
    bulk_picker_requested = Signal()
    repeat_order_requested = Signal()
    import_csv_requested = Signal()
    edit_selling_price_requested = Signal(int)
    search_text_changed = Signal(str)
    history_filter_changed = Signal(dict)
    history_refresh_requested = Signal()
    history_detail_requested = Signal(int)
    history_payment_requested = Signal(int)
    history_duplicate_requested = Signal(int)

    COL_NO: int = 0
    COL_ITEM: int = 1
    COL_UNIT: int = 2
    COL_QTY: int = 3
    COL_BASE_QTY: int = 4
    COL_UNIT_COST: int = 5
    COL_SUBTOTAL: int = 6
    COL_ACTION: int = 7

    PAYMENT_METHODS: tuple[str, ...] = (
        "Tunai",
        "Transfer Bank",
        "QRIS",
        "E-Wallet",
        "Giro / Cek",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi TambahStokPage beserta seluruh komponen dan pintasan.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("TambahStokPage")
        self._catalog_by_id: dict[int, CatalogItemData] = {}
        self._catalog_by_sku: dict[str, CatalogItemData] = {}
        self._catalog_by_label: dict[str, CatalogItemData] = {}
        self._row_item_data: list[CatalogItemData] = []
        self._updating_row: bool = False
        self._auto_full_payment: bool = True
        self._shortcuts: list[QShortcut] = []

        self._search_model = QStringListModel(self)
        self._search_completer = QCompleter(self._search_model, self)
        self._search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._search_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_payment_controls_state()
        self._recalculate_totals()

    def _setup_ui(self) -> None:
        """Menyusun tata letak utama halaman berupa dua panel berlapis (stacked)."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 0, 14, 12)
        root_layout.setSpacing(10)

        self._stack = QStackedWidget(self)

        self._purchase_tab = QWidget(self._stack)
        self._purchase_tab.setObjectName("tabContentContainer")
        self._history_tab = QWidget(self._stack)
        self._history_tab.setObjectName("tabContentContainer")

        self._build_purchase_tab()
        self._build_history_tab()

        self._stack.addWidget(self._purchase_tab)
        self._stack.addWidget(self._history_tab)
        self._stack.setCurrentIndex(0)

        root_layout.addWidget(self._stack, 1)

        completer_popup = self._search_completer.popup()
        if completer_popup is not None:
            completer_popup.setObjectName("searchCompleterPopup")
            completer_popup.setStyleSheet(
                """
                QListView#searchCompleterPopup {
                    background-color: #13192D;
                    color: #E2E8F0;
                    border: 1.5px solid #06B6D4;
                    border-radius: 8px;
                    padding: 4px;
                    outline: none;
                    font-size: 12px;
                }
                QListView#searchCompleterPopup::item {
                    padding: 7px 10px;
                    border-radius: 6px;
                }
                QListView#searchCompleterPopup::item:selected {
                    background-color: rgba(14, 165, 233, 0.25);
                    color: #67E8F9;
                }
                QListView#searchCompleterPopup::item:hover {
                    background-color: rgba(56, 189, 248, 0.14);
                }
                """
            )

    def _update_tab_icons(self, active_index: int) -> None:
        """Tidak diperlukan lagi — ikon pada QStackedWidget tidak ada. Dipertahankan untuk kompatibilitas sinyal."""

    @staticmethod
    def _apply_glow_effect(
        widget: QWidget,
        color_hex: str,
        alpha: int = 85,
        blur_radius: float = 18.0,
        offset_y: float = 3.0,
    ) -> None:
        """Menambahkan efek pendar lembut pada elemen fokus utama.

        Args:
            widget: Widget target yang akan diberi efek bayangan berpendar.
            color_hex: Kode warna heksadesimal pendar.
            alpha: Tingkat transparansi warna pendar (0-255).
            blur_radius: Radius keburaman bayangan.
            offset_y: Pergeseran vertikal bayangan.
        """
        shadow = QGraphicsDropShadowEffect(widget)
        glow_color = QColor(color_hex)
        glow_color.setAlpha(alpha)
        shadow.setColor(glow_color)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(0.0, offset_y)
        widget.setGraphicsEffect(shadow)

    def _build_purchase_tab(self) -> None:
        """Menyusun komponen Tab 1: Header Nota, Bar Input Cepat, Grid, dan Footer."""
        layout = QVBoxLayout(self._purchase_tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._create_header_card())
        layout.addWidget(self._create_quick_add_bar())
        layout.addWidget(self._create_cart_table(), 1)
        layout.addWidget(self._create_footer_panel())

    def _create_header_card(self) -> QFrame:
        """Membuat kartu header nota untuk data supplier, faktur, tanggal, dan catatan.

        Returns:
            Widget QFrame berisi kontrol metadata nota pembelian.
        """
        card = QFrame(self._purchase_tab)
        card.setObjectName("sectionCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        supplier_label = QLabel("Supplier", card)
        supplier_label.setObjectName("fieldLabel")
        invoice_label = QLabel("No. Faktur / Nota", card)
        invoice_label.setObjectName("fieldLabel")
        date_label = QLabel("Tanggal Belanja", card)
        date_label.setObjectName("fieldLabel")
        notes_label = QLabel("Catatan Nota", card)
        notes_label.setObjectName("fieldLabel")

        supplier_row = QHBoxLayout()
        supplier_row.setContentsMargins(0, 0, 0, 0)
        supplier_row.setSpacing(8)

        self.supplier_combo = StyledComboBox(card)
        self.supplier_combo.setObjectName("headerCombo")
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.supplier_combo.setFixedHeight(34)
        self.supplier_combo.addItem("-- Tanpa Supplier (Belanja Umum) --", None)
        supplier_line = self.supplier_combo.lineEdit()
        if supplier_line is not None:
            supplier_line.setPlaceholderText("Cari atau pilih supplier...")
        supplier_completer = self.supplier_combo.completer()
        if supplier_completer is not None:
            supplier_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            supplier_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.add_supplier_btn = QPushButton(card)
        self.add_supplier_btn.setObjectName("addSupplierButton")
        self.add_supplier_btn.setIcon(build_svg_icon(SVG_PLUS, "#FFFFFF", 15))
        self.add_supplier_btn.setIconSize(QSize(15, 15))
        self.add_supplier_btn.setFixedSize(34, 34)
        attach_tooltip(
            self.add_supplier_btn,
            "Tambah Supplier Baru",
            position=TooltipPosition.TOP,
        )
        self.add_supplier_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        supplier_row.addWidget(self.supplier_combo, 1)
        supplier_row.addWidget(self.add_supplier_btn)

        invoice_row = QHBoxLayout()
        invoice_row.setContentsMargins(0, 0, 0, 0)
        invoice_row.setSpacing(8)

        self.invoice_input = QLineEdit(card)
        self.invoice_input.setObjectName("headerInput")
        self.invoice_input.setFixedHeight(34)
        self.invoice_input.setPlaceholderText("Contoh: INV-20261127-001")
        self.invoice_input.setText(self._build_default_invoice_number())

        self.auto_invoice_btn = QPushButton("Auto", card)
        self.auto_invoice_btn.setObjectName("autoInvoiceButton")
        self.auto_invoice_btn.setIcon(build_svg_icon(SVG_SPARKLE, "#FFFFFF", 14))
        self.auto_invoice_btn.setIconSize(QSize(14, 14))
        self.auto_invoice_btn.setFixedHeight(34)
        attach_tooltip(
            self.auto_invoice_btn,
            "Buat Nomor Nota Otomatis",
            position=TooltipPosition.TOP,
        )
        self.auto_invoice_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        invoice_row.addWidget(self.invoice_input, 1)
        invoice_row.addWidget(self.auto_invoice_btn)

        self.purchase_date_edit = StyledDateTimeEdit(QDateTime.currentDateTime(), card)
        self.purchase_date_edit.setObjectName("headerDate")
        self.purchase_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.purchase_date_edit.setFixedHeight(34)

        self.notes_input = QLineEdit(card)
        self.notes_input.setObjectName("headerInput")
        self.notes_input.setFixedHeight(34)
        self.notes_input.setPlaceholderText("Catatan kulakan, kurir, atau promo (opsional)...")

        grid.addWidget(supplier_label, 0, 0)
        grid.addWidget(invoice_label, 0, 1)
        grid.addWidget(date_label, 0, 2)
        grid.addWidget(notes_label, 0, 3)

        grid.addLayout(supplier_row, 1, 0)
        grid.addLayout(invoice_row, 1, 1)
        grid.addWidget(self.purchase_date_edit, 1, 2)
        grid.addWidget(self.notes_input, 1, 3)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 3)
        return card

    def _create_quick_add_bar(self) -> QFrame:
        """Membuat bilah input cepat keyboard-first dan tombol aksi massal.

        Returns:
            Widget QFrame berisi kotak scan/pencarian cepat dan petunjuk pintasan.
        """
        bar = QFrame(self._purchase_tab)
        bar.setObjectName("quickAddCard")
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(14, 10, 14, 9)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        search_icon_box = QLabel(bar)
        search_icon_box.setObjectName("searchIconBadge")
        search_icon_box.setPixmap(build_svg_icon(SVG_SEARCH, "#38BDF8", 17).pixmap(17, 17))
        search_icon_box.setFixedSize(34, 36)
        search_icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.quick_search_input = QuickSearchLineEdit(bar)
        self.quick_search_input.setObjectName("quickSearchInput")
        self.quick_search_input.setPlaceholderText(
            "Scan barcode atau ketik SKU / nama barang, lalu tekan Enter untuk masuk ke grid..."
        )
        self.quick_search_input.setFixedHeight(36)
        self.quick_search_input.setCompleter(self._search_completer)

        self.quick_add_btn = QPushButton("Tambah", bar)
        self.quick_add_btn.setObjectName("btnQuickAdd")
        self.quick_add_btn.setIcon(build_svg_icon(SVG_PLUS, "#FFFFFF", 14))
        self.quick_add_btn.setIconSize(QSize(14, 14))
        self.quick_add_btn.setFixedHeight(36)
        self.quick_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.bulk_picker_btn = QPushButton("Pilih Banyak (F4)", bar)
        self.bulk_picker_btn.setObjectName("btnBulkPicker")
        self.bulk_picker_btn.setIcon(build_svg_icon(SVG_LAYERS, "#FFFFFF", 14))
        self.bulk_picker_btn.setIconSize(QSize(14, 14))
        self.bulk_picker_btn.setFixedHeight(36)
        self.bulk_picker_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.repeat_order_btn = QPushButton("Ulang Nota", bar)
        self.repeat_order_btn.setObjectName("btnRepeatOrder")
        self.repeat_order_btn.setIcon(build_svg_icon(SVG_REPEAT, "#FFFFFF", 14))
        self.repeat_order_btn.setIconSize(QSize(14, 14))
        self.repeat_order_btn.setFixedHeight(36)
        self.repeat_order_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.import_csv_btn = QPushButton("Import CSV", bar)
        self.import_csv_btn.setObjectName("btnImportCsv")
        self.import_csv_btn.setIcon(build_svg_icon(SVG_UPLOAD, "#FFFFFF", 14))
        self.import_csv_btn.setIconSize(QSize(14, 14))
        self.import_csv_btn.setFixedHeight(36)
        self.import_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.clear_cart_btn = QPushButton("Kosongkan", bar)
        self.clear_cart_btn.setObjectName("btnClearCart")
        self.clear_cart_btn.setIcon(build_svg_icon(SVG_TRASH, "#FFFFFF", 14))
        self.clear_cart_btn.setIconSize(QSize(14, 14))
        self.clear_cart_btn.setFixedHeight(36)
        self.clear_cart_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        top_row.addWidget(search_icon_box)
        top_row.addWidget(self.quick_search_input, 1)
        top_row.addWidget(self.quick_add_btn)
        top_row.addWidget(self.bulk_picker_btn)
        top_row.addWidget(self.repeat_order_btn)
        top_row.addWidget(self.import_csv_btn)
        top_row.addWidget(self.clear_cart_btn)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        hint_row.setSpacing(8)

        hints = [
            "F1: Cari Barang",
            "Enter: Qty -> Harga Beli -> Cari Lagi",
            "Ctrl+Panah: Pindah Baris",
            "Ctrl+Del: Hapus Baris",
            "F8: Lunas",
            "F9: Draft",
            "F10 / Ctrl+Enter: Simpan Stok",
        ]
        for hint_text in hints:
            hint_label = QLabel(hint_text, bar)
            hint_label.setObjectName("shortcutHint")
            hint_row.addWidget(hint_label)
        hint_row.addStretch(1)

        outer.addLayout(top_row)
        outer.addLayout(hint_row)
        return bar

    def _create_cart_table(self) -> QTableWidget:
        """Membuat tabel keranjang kulakan yang dapat diedit langsung di sel.

        Returns:
            Objek QTableWidget terkonfigurasi untuk input cepat multi-item.
        """
        self.cart_table = QTableWidget(0, 8, self._purchase_tab)
        self.cart_table.setObjectName("cartTable")

        cart_header = ColoredHeaderView(
            column_colors={
                self.COL_NO: "#94A3B8",
                self.COL_ITEM: "#FBBF24",
                self.COL_UNIT: "#FDE047",
                self.COL_QTY: "#34D399",
                self.COL_BASE_QTY: "#38BDF8",
                self.COL_UNIT_COST: "#60A5FA",
                self.COL_SUBTOTAL: "#C084FC",
                self.COL_ACTION: "#FB7185",
            },
            column_alignments={
                self.COL_NO: Qt.AlignmentFlag.AlignCenter,
                self.COL_ITEM: Qt.AlignmentFlag.AlignLeft,
                self.COL_UNIT: Qt.AlignmentFlag.AlignCenter,
                self.COL_QTY: Qt.AlignmentFlag.AlignCenter,
                self.COL_BASE_QTY: Qt.AlignmentFlag.AlignRight,
                self.COL_UNIT_COST: Qt.AlignmentFlag.AlignRight,
                self.COL_SUBTOTAL: Qt.AlignmentFlag.AlignRight,
                self.COL_ACTION: Qt.AlignmentFlag.AlignCenter,
            },
            parent=self.cart_table,
        )
        self.cart_table.setHorizontalHeader(cart_header)

        self.cart_table.setHorizontalHeaderLabels(
            [
                "#",
                "Barang / SKU",
                "Satuan Beli",
                "Qty Beli",
                "Stok Masuk",
                "Harga Beli (Satuan)",
                "Subtotal & HPP/Dasar",
                "Aksi",
            ]
        )
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.setShowGrid(False)
        self.cart_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        v_header = self.cart_table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(44)

        cart_header.setSectionResizeMode(self.COL_NO, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_ITEM, QHeaderView.ResizeMode.Stretch)
        cart_header.setSectionResizeMode(self.COL_UNIT, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_QTY, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_BASE_QTY, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_UNIT_COST, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_SUBTOTAL, QHeaderView.ResizeMode.Fixed)
        cart_header.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.Fixed)

        self.cart_table.setColumnWidth(self.COL_NO, 40)
        self.cart_table.setColumnWidth(self.COL_UNIT, 154)
        self.cart_table.setColumnWidth(self.COL_QTY, 104)
        self.cart_table.setColumnWidth(self.COL_BASE_QTY, 132)
        self.cart_table.setColumnWidth(self.COL_UNIT_COST, 156)
        self.cart_table.setColumnWidth(self.COL_SUBTOTAL, 180)
        self.cart_table.setColumnWidth(self.COL_ACTION, 84)
        return self.cart_table

    def _create_footer_panel(self) -> QFrame:
        """Membuat panel footer ringkasan nominal, pembayaran, hutang, dan tombol simpan.

        Returns:
            Widget QFrame berisi ringkasan transaksi dan kontrol eksekusi.
        """
        footer = QFrame(self._purchase_tab)
        footer.setObjectName("sectionCard")
        outer = QVBoxLayout(footer)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(8)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(12)

        summary_card = QFrame(footer)
        summary_card.setObjectName("grandTotalCard")
        summary_grid = QGridLayout(summary_card)
        summary_grid.setContentsMargins(12, 8, 12, 8)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(4)

        self.item_count_label = QLabel("0 Jenis Barang  •  0 Total Qty Beli", summary_card)
        self.item_count_label.setObjectName("summaryMetaLabel")

        subtotal_title = QLabel("Subtotal Belanja", summary_card)
        subtotal_title.setObjectName("summaryFieldLabel")
        self.subtotal_value_label = QLabel("Rp 0", summary_card)
        self.subtotal_value_label.setObjectName("summaryValueLabel")
        self.subtotal_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        discount_title = QLabel("Diskon Nota", summary_card)
        discount_title.setObjectName("summaryFieldLabel")
        self.discount_spin = CurrencySpinBox(parent=summary_card)
        self.discount_spin.setObjectName("summarySpinBox")
        self.discount_spin.setFixedHeight(27)

        grand_title = QLabel("GRAND TOTAL", summary_card)
        grand_title.setObjectName("grandTotalTitle")
        self.grand_total_label = QLabel("Rp 0", summary_card)
        self.grand_total_label.setObjectName("grandTotalValue")
        self.grand_total_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        summary_grid.addWidget(self.item_count_label, 0, 0, 1, 2)
        summary_grid.addWidget(subtotal_title, 1, 0)
        summary_grid.addWidget(self.subtotal_value_label, 1, 1)
        summary_grid.addWidget(discount_title, 2, 0)
        summary_grid.addWidget(self.discount_spin, 2, 1)
        summary_grid.addWidget(grand_title, 3, 0)
        summary_grid.addWidget(self.grand_total_label, 3, 1)
        summary_grid.setColumnStretch(0, 1)
        summary_grid.setColumnStretch(1, 1)
        self._apply_glow_effect(summary_card, "#14B8A6", alpha=60, blur_radius=18.0, offset_y=2.0)

        payment_card = QFrame(footer)
        payment_card.setObjectName("paymentCard")
        pay_grid = QGridLayout(payment_card)
        pay_grid.setContentsMargins(12, 8, 12, 8)
        pay_grid.setHorizontalSpacing(12)
        pay_grid.setVerticalSpacing(4)

        method_label = QLabel("Metode Pembayaran", payment_card)
        method_label.setObjectName("fieldLabel")
        self.payment_method_combo = StyledComboBox(payment_card)
        self.payment_method_combo.setObjectName("headerCombo")
        self.payment_method_combo.addItems(list(self.PAYMENT_METHODS))
        self.payment_method_combo.setFixedHeight(27)

        quick_pay_row = QHBoxLayout()
        quick_pay_row.setContentsMargins(0, 0, 0, 0)
        quick_pay_row.setSpacing(6)

        self.btn_pay_full = QPushButton("Lunas (F8)", payment_card)
        self.btn_pay_full.setObjectName("quickPaySuccess")
        self.btn_pay_full.setFixedHeight(24)
        self.btn_pay_full.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_pay_partial = QPushButton("DP / Cicil", payment_card)
        self.btn_pay_partial.setObjectName("quickPayWarning")
        self.btn_pay_partial.setFixedHeight(24)
        self.btn_pay_partial.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_pay_unpaid = QPushButton("Tempo", payment_card)
        self.btn_pay_unpaid.setObjectName("quickPayDanger")
        self.btn_pay_unpaid.setFixedHeight(24)
        self.btn_pay_unpaid.setCursor(Qt.CursorShape.PointingHandCursor)

        quick_pay_row.addWidget(self.btn_pay_full)
        quick_pay_row.addWidget(self.btn_pay_partial)
        quick_pay_row.addWidget(self.btn_pay_unpaid)

        paid_label = QLabel("Nominal Dibayar", payment_card)
        paid_label.setObjectName("fieldLabel")
        self.amount_paid_spin = CurrencySpinBox(parent=payment_card)
        self.amount_paid_spin.setObjectName("footerSpinBox")
        self.amount_paid_spin.setFixedHeight(27)

        remaining_label = QLabel("Sisa Hutang / Status", payment_card)
        remaining_label.setObjectName("fieldLabel")

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        self.remaining_value_label = QLabel("Rp 0", payment_card)
        self.remaining_value_label.setObjectName("remainingValueLabel")
        self.payment_status_badge = QLabel("LUNAS", payment_card)
        self.payment_status_badge.setObjectName("statusBadgePaid")
        self.payment_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.remaining_value_label, 1)
        status_row.addWidget(self.payment_status_badge, 0)

        due_label = QLabel("Jatuh Tempo", payment_card)
        due_label.setObjectName("fieldLabel")
        self.due_date_edit = StyledDateEdit(QDate.currentDate().addDays(14), payment_card)
        self.due_date_edit.setObjectName("headerDate")
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setFixedHeight(27)

        ref_label = QLabel("No. Referensi", payment_card)
        ref_label.setObjectName("fieldLabel")
        self.reference_input = QLineEdit(payment_card)
        self.reference_input.setObjectName("headerInput")
        self.reference_input.setFixedHeight(27)
        self.reference_input.setPlaceholderText("No. bukti transfer / QRIS...")

        pay_grid.addWidget(method_label, 0, 0)
        pay_grid.addWidget(paid_label, 0, 1)
        pay_grid.addWidget(due_label, 0, 2)

        pay_grid.addWidget(self.payment_method_combo, 1, 0)
        pay_grid.addWidget(self.amount_paid_spin, 1, 1)
        pay_grid.addWidget(self.due_date_edit, 1, 2)

        pay_grid.addLayout(quick_pay_row, 2, 0)
        pay_grid.addWidget(remaining_label, 2, 1)
        pay_grid.addWidget(ref_label, 2, 2)

        pay_grid.addLayout(status_row, 3, 1)
        pay_grid.addWidget(self.reference_input, 3, 2)

        pay_grid.setColumnStretch(0, 2)
        pay_grid.setColumnStretch(1, 2)
        pay_grid.setColumnStretch(2, 2)

        content_row.addWidget(summary_card, 4)
        content_row.addWidget(payment_card, 6)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)

        self.reset_form_btn = QPushButton(footer)
        self.reset_form_btn.setObjectName("resetFormButton")
        self.reset_form_btn.setIcon(build_svg_icon(SVG_REFRESH, "#FB7185", 15))
        self.reset_form_btn.setIconSize(QSize(15, 15))
        self.reset_form_btn.setFixedHeight(34)
        self.reset_form_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_tooltip(
            self.reset_form_btn, 
            "Reset Form (Ctrl+R", 
            position=TooltipPosition.TOP 
            )

        self.save_draft_btn = QPushButton("Simpan Draft (F9)", footer)
        self.save_draft_btn.setObjectName("secondaryActionButton")
        self.save_draft_btn.setIcon(build_svg_icon(SVG_SAVE, "#E0E7FF", 15))
        self.save_draft_btn.setIconSize(QSize(15, 15))
        self.save_draft_btn.setFixedHeight(34)
        self.save_draft_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.submit_btn = QPushButton("Simpan & Tambah Stok (F10)", footer)
        self.submit_btn.setObjectName("primaryActionButton")
        self.submit_btn.setIcon(build_svg_icon(SVG_CHECK, "#022C22", 17))
        self.submit_btn.setIconSize(QSize(17, 17))
        self.submit_btn.setFixedHeight(34)
        self.submit_btn.setMinimumWidth(245)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_glow_effect(self.submit_btn, "#10B981", alpha=95, blur_radius=18.0, offset_y=2.0)

        self.btn_goto_history = QPushButton("Riwayat && Hutang Supplier", footer)
        self.btn_goto_history.setObjectName("secondaryActionButton")
        self.btn_goto_history.setIcon(build_svg_icon(SVG_WALLET, "#34D399", 15))
        self.btn_goto_history.setIconSize(QSize(15, 15))
        self.btn_goto_history.setFixedHeight(34)
        self.btn_goto_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_goto_history.clicked.connect(lambda: self._stack.setCurrentIndex(1))

        action_row.addWidget(self.reset_form_btn)
        action_row.addWidget(self.btn_goto_history)
        action_row.addStretch(1)
        action_row.addWidget(self.save_draft_btn)
        action_row.addWidget(self.submit_btn)

        outer.addLayout(content_row)
        outer.addLayout(action_row)
        return footer

    def _build_history_tab(self) -> None:
        """Menyusun komponen Tab 2: Ringkasan KPI, Filter Riwayat, dan Tabel Nota."""
        layout = QVBoxLayout(self._history_tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        kpi_row = QHBoxLayout()
        kpi_row.setContentsMargins(0, 0, 0, 0)
        kpi_row.setSpacing(12)

        self.kpi_total_notes_label = self._create_kpi_card(
            parent_layout=kpi_row,
            title="Total Nota Kulakan",
            initial_value="0 Nota",
            accent_color="#38BDF8",
            bg_start="#0F2547",
            bg_end="#11172B",
            svg_template=SVG_LAYERS,
        )
        self.kpi_total_spend_label = self._create_kpi_card(
            parent_layout=kpi_row,
            title="Total Nilai Pembelian",
            initial_value="Rp 0",
            accent_color="#34D399",
            bg_start="#063B32",
            bg_end="#11172B",
            svg_template=SVG_CHECK,
        )
        self.kpi_total_debt_label = self._create_kpi_card(
            parent_layout=kpi_row,
            title="Total Sisa Hutang Supplier",
            initial_value="Rp 0",
            accent_color="#FB7185",
            bg_start="#401228",
            bg_end="#11172B",
            svg_template=SVG_WALLET,
        )
        layout.addLayout(kpi_row)

        filter_card = QFrame(self._history_tab)
        filter_card.setObjectName("sectionCard")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(10)

        self.history_search_input = QLineEdit(filter_card)
        self.history_search_input.setObjectName("headerInput")
        self.history_search_input.setPlaceholderText("Cari nomor faktur atau nama supplier...")
        self.history_search_input.setFixedHeight(34)

        self.history_status_combo = StyledComboBox(filter_card)
        self.history_status_combo.setObjectName("headerCombo")
        self.history_status_combo.setFixedHeight(34)
        self.history_status_combo.setMinimumWidth(170)
        self.history_status_combo.addItem("Semua Status", "ALL")
        self.history_status_combo.addItem("Belum Lunas (UNPAID)", "UNPAID")
        self.history_status_combo.addItem("Cicilan (PARTIAL)", "PARTIAL")
        self.history_status_combo.addItem("Lunas (PAID)", "PAID")

        self.history_date_from = StyledDateEdit(QDate.currentDate().addMonths(-1), filter_card)
        self.history_date_from.setObjectName("headerDate")
        self.history_date_from.setDisplayFormat("yyyy-MM-dd")
        self.history_date_from.setFixedHeight(34)

        date_sep_label = QLabel("s/d", filter_card)
        date_sep_label.setObjectName("fieldLabel")

        self.history_date_to = StyledDateEdit(QDate.currentDate(), filter_card)
        self.history_date_to.setObjectName("headerDate")
        self.history_date_to.setDisplayFormat("yyyy-MM-dd")
        self.history_date_to.setFixedHeight(34)

        self.history_refresh_btn = QPushButton("Muat Ulang", filter_card)
        self.history_refresh_btn.setObjectName("btnQuickAdd")
        self.history_refresh_btn.setIcon(build_svg_icon(SVG_REFRESH, "#FFFFFF", 14))
        self.history_refresh_btn.setIconSize(QSize(14, 14))
        self.history_refresh_btn.setFixedHeight(34)
        self.history_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        filter_layout.addWidget(self.history_search_input, 1)
        filter_layout.addWidget(self.history_status_combo)
        filter_layout.addWidget(self.history_date_from)
        filter_layout.addWidget(date_sep_label)
        filter_layout.addWidget(self.history_date_to)
        filter_layout.addWidget(self.history_refresh_btn)

        layout.addWidget(filter_card)

        self.history_table = QTableWidget(0, 9, self._history_tab)
        self.history_table.setObjectName("cartTable")

        history_header = ColoredHeaderView(
            column_colors={
                0: "#94A3B8",
                1: "#38BDF8",
                2: "#FBBF24",
                3: "#E2E8F0",
                4: "#34D399",
                5: "#FB7185",
                6: "#C084FC",
                7: "#FDE047",
                8: "#60A5FA",
            },
            column_alignments={
                0: Qt.AlignmentFlag.AlignLeft,
                1: Qt.AlignmentFlag.AlignLeft,
                2: Qt.AlignmentFlag.AlignLeft,
                3: Qt.AlignmentFlag.AlignRight,
                4: Qt.AlignmentFlag.AlignRight,
                5: Qt.AlignmentFlag.AlignRight,
                6: Qt.AlignmentFlag.AlignCenter,
                7: Qt.AlignmentFlag.AlignCenter,
                8: Qt.AlignmentFlag.AlignCenter,
            },
            parent=self.history_table,
        )
        self.history_table.setHorizontalHeader(history_header)

        self.history_table.setHorizontalHeaderLabels(
            [
                "Tanggal",
                "No. Faktur",
                "Supplier",
                "Total",
                "Dibayar",
                "Sisa Hutang",
                "Status",
                "Jatuh Tempo",
                "Aksi",
            ]
        )
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setShowGrid(False)

        hv_header = self.history_table.verticalHeader()
        if hv_header is not None:
            hv_header.setVisible(False)
            hv_header.setDefaultSectionSize(46)

        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        history_header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)

        self.history_table.setColumnWidth(0, 134)
        self.history_table.setColumnWidth(1, 154)
        self.history_table.setColumnWidth(3, 124)
        self.history_table.setColumnWidth(4, 124)
        self.history_table.setColumnWidth(5, 124)
        self.history_table.setColumnWidth(6, 114)
        self.history_table.setColumnWidth(7, 108)
        self.history_table.setColumnWidth(8, 224)

        layout.addWidget(self.history_table, 1)

        back_footer = QFrame(self._history_tab)
        back_footer.setObjectName("sectionCard")
        back_footer_layout = QHBoxLayout(back_footer)
        back_footer_layout.setContentsMargins(14, 8, 14, 8)
        back_footer_layout.setSpacing(8)

        self.btn_back_to_purchase = QPushButton("Kembali ke Belanja", back_footer)
        self.btn_back_to_purchase.setObjectName("secondaryActionButton")
        self.btn_back_to_purchase.setIcon(build_svg_icon(SVG_LAYERS, "#38BDF8", 15))
        self.btn_back_to_purchase.setIconSize(QSize(15, 15))
        self.btn_back_to_purchase.setFixedHeight(38)
        self.btn_back_to_purchase.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_to_purchase.clicked.connect(lambda: self._stack.setCurrentIndex(0))

        back_footer_layout.addWidget(self.btn_back_to_purchase)
        back_footer_layout.addStretch(1)
        layout.addWidget(back_footer)

    def _create_kpi_card(
        self,
        parent_layout: QHBoxLayout,
        title: str,
        initial_value: str,
        accent_color: str,
        bg_start: str,
        bg_end: str,
        svg_template: str,
    ) -> QLabel:
        """Membuat kartu KPI bergradasi modern untuk bagian atas tab riwayat kulakan.

        Args:
            parent_layout: Layout horizontal tempat kartu akan ditempatkan.
            title: Label judul metrik KPI.
            initial_value: Nilai tampilan awal KPI.
            accent_color: Warna garis aksen, ikon, dan nilai KPI.
            bg_start: Warna awal gradasi latar kartu.
            bg_end: Warna akhir gradasi latar kartu.
            svg_template: Template string SVG untuk ikon metrik.

        Returns:
            Widget QLabel nilai KPI yang dapat diperbarui secara dinamis.
        """
        card = QFrame(self._history_tab)
        card.setObjectName("kpiCard")
        card.setStyleSheet(
            f"""
            QFrame#kpiCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg_start}, stop:1 {bg_end}
                );
                border: 1px solid {accent_color};
                border-left: 4px solid {accent_color};
                border-radius: 10px;
            }}
            """
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        icon_holder = QLabel(card)
        icon_holder.setFixedSize(38, 38)
        icon_holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_holder.setPixmap(build_svg_icon(svg_template, accent_color, 20).pixmap(20, 20))
        icon_holder.setStyleSheet(
            f"""
            background-color: rgba(15, 23, 42, 0.55);
            border: 1px solid {accent_color};
            border-radius: 9px;
            """
        )

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_lbl = QLabel(title, card)
        title_lbl.setStyleSheet(
            "color: #CBD5E1; font-size: 11px; font-weight: 600; background: transparent;"
        )

        value_lbl = QLabel(initial_value, card)
        value_lbl.setStyleSheet(
            f"color: {accent_color}; font-size: 18px; font-weight: 800; background: transparent;"
        )

        text_col.addWidget(title_lbl)
        text_col.addWidget(value_lbl)

        row.addWidget(icon_holder)
        row.addLayout(text_col, 1)
        parent_layout.addWidget(card, 1)
        return value_lbl

    def _apply_styles(self) -> None:
        """Menerapkan stylesheet QSS tema Deep Midnight Indigo yang berwarna ke halaman."""
        self.setStyleSheet(
            """
            QWidget#TambahStokPage {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #111424, stop:1 #0B0C16
                );
                color: #E2E8F0;
                font-family: "Segoe UI", "Inter", sans-serif;
            }
            QWidget#tabContentContainer {
                background: transparent;
            }
            QFrame#sectionCard {
                background-color: #14192D;
                border: 1px solid #263052;
                border-radius: 12px;
            }
            QFrame#quickAddCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #151C34, stop:0.5 #141A30, stop:1 #181C35
                );
                border: 1.5px solid #2B4C7E;
                border-radius: 12px;
            }
            QFrame#grandTotalCard {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #064E3B, stop:0.55 #0D353A, stop:1 #0F172A
                );
                border: 1.5px solid #14B8A6;
                border-radius: 10px;
            }
            QFrame#paymentCard {
                background-color: #101528;
                border: 1px solid #263052;
                border-radius: 10px;
            }
            QLabel#fieldLabel {
                color: #CBD5E1;
                font-size: 11px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#summaryFieldLabel {
                color: #CCFBF1;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#searchIconBadge {
                background-color: #0D1326;
                border: 1px solid #2B4C7E;
                border-radius: 8px;
            }
            QLabel#shortcutHint {
                color: #93C5FD;
                background-color: rgba(30, 41, 74, 0.72);
                border: 1px solid #26345C;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#summaryMetaLabel {
                color: #5EEAD4;
                font-size: 11px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#summaryValueLabel {
                color: #F8FAFC;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#grandTotalTitle {
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.5px;
                background: transparent;
            }
            QLabel#grandTotalValue {
                color: #34D399;
                font-size: 19px;
                font-weight: 800;
                background: transparent;
            }
            QLabel#remainingValueLabel {
                color: #FBBF24;
                font-size: 14px;
                font-weight: 800;
                background: transparent;
            }
            QLabel#statusBadgePaid {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ADE80, stop:1 #22C55E
                );
                color: #052E16;
                border: 1px solid #86EFAC;
                border-radius: 9px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#statusBadgePartial {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FBBF24, stop:1 #F59E0B
                );
                color: #451A03;
                border: 1px solid #FDE68A;
                border-radius: 9px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#statusBadgeUnpaid {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FB7185, stop:1 #F43F5E
                );
                color: #FFFFFF;
                border: 1px solid #FDA4AF;
                border-radius: 9px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#cellItemName {
                color: #F8FAFC;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#cellSkuTag {
                color: #38BDF8;
                background-color: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#cellStockTag {
                color: #34D399;
                background-color: rgba(52, 211, 153, 0.12);
                border: 1px solid rgba(52, 211, 153, 0.3);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#cellHppPreview {
                color: #34D399;
                font-size: 10px;
                font-weight: 700;
                background: transparent;
            }
            QLineEdit#headerInput,
            QLineEdit#quickSearchInput,
            QComboBox#headerCombo,
            QDateEdit#headerDate,
            QDateTimeEdit#headerDate,
            QSpinBox#footerSpinBox,
            QSpinBox#summarySpinBox {
                background-color: #0D1224;
                color: #F1F5F9;
                border: 1.5px solid #263254;
                border-radius: 7px;
                padding: 2px 10px;
                font-size: 12px;
                font-weight: 500;
                selection-background-color: #0EA5E9;
                selection-color: #FFFFFF;
            }
            QComboBox#headerCombo,
            QDateEdit#headerDate,
            QDateTimeEdit#headerDate {
                padding-right: 28px;
            }
            QSpinBox#summarySpinBox {
                background-color: rgba(11, 18, 33, 0.85);
                border: 1.5px solid #115E59;
                color: #F8FAFC;
                font-weight: 700;
            }
            QLineEdit#quickSearchInput {
                background-color: #0B1020;
                border: 1.5px solid #2D4A7C;
                font-size: 13px;
                font-weight: 500;
                padding: 4px 12px;
            }
            QLineEdit#headerInput:hover,
            QLineEdit#quickSearchInput:hover,
            QComboBox#headerCombo:hover,
            QDateEdit#headerDate:hover,
            QDateTimeEdit#headerDate:hover,
            QSpinBox#footerSpinBox:hover {
                border-color: #3B82F6;
            }
            QLineEdit#headerInput:focus,
            QLineEdit#quickSearchInput:focus,
            QComboBox#headerCombo:focus,
            QDateEdit#headerDate:focus,
            QDateTimeEdit#headerDate:focus,
            QSpinBox#footerSpinBox:focus,
            QSpinBox#summarySpinBox:focus {
                border: 2px solid #06B6D4;
                background-color: #0F172E;
            }
            QLineEdit#headerInput:disabled,
            QDateEdit#headerDate:disabled {
                background-color: #0C101E;
                color: #475569;
                border-color: #1D253E;
            }
            QComboBox#headerCombo::drop-down,
            QComboBox#gridCombo::drop-down,
            QDateEdit#headerDate::drop-down,
            QDateTimeEdit#headerDate::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                border: none;
                width: 28px;
                background: transparent;
            }
            QComboBox#headerCombo::down-arrow,
            QComboBox#gridCombo::down-arrow,
            QDateEdit#headerDate::down-arrow,
            QDateTimeEdit#headerDate::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #13192D;
                color: #E2E8F0;
                border: 1.5px solid #06B6D4;
                border-radius: 8px;
                selection-background-color: rgba(14, 165, 233, 0.25);
                selection-color: #67E8F9;
                padding: 4px;
                outline: none;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #141A30;
                background-color: #0F1426;
                color: #E2E8F0;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0E7490, stop:1 #1D4ED8
                );
                padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #FFFFFF;
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 700;
            }
            QCalendarWidget QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.16);
            }
            QCalendarWidget QMenu {
                background-color: #14192D;
                color: #E2E8F0;
                border: 1px solid #38BDF8;
            }
            QCalendarWidget QSpinBox {
                background-color: #0F172A;
                color: #FFFFFF;
                border: 1px solid #38BDF8;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #0F1426;
                color: #E2E8F0;
                selection-background-color: #06B6D4;
                selection-color: #022C22;
                outline: none;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #475569;
            }
            QDoubleSpinBox#gridSpinBox,
            QComboBox#gridCombo {
                background-color: #0D1326;
                color: #F8FAFC;
                border: 1.5px solid #263254;
                border-radius: 6px;
                padding: 1px 8px;
                font-size: 12px;
                font-weight: 700;
                selection-background-color: #0EA5E9;
            }
            QComboBox#gridCombo {
                padding-right: 26px;
            }
            QDoubleSpinBox#gridSpinBox:focus,
            QComboBox#gridCombo:focus {
                border: 1.5px solid #22D3EE;
                background-color: #131C36;
            }
            QTableWidget#cartTable {
                background-color: #0F1324;
                alternate-background-color: #13182E;
                color: #E2E8F0;
                border: 1px solid #263052;
                border-radius: 12px;
                outline: none;
                selection-background-color: rgba(14, 165, 233, 0.16);
                selection-color: #F8FAFC;
            }
            QTableWidget#cartTable::item {
                border-bottom: 1px solid #1E2746;
                padding: 4px 6px;
            }
            QPushButton#addSupplierButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #38BDF8, stop:1 #0284C7
                );
                border: 1px solid #7DD3FC;
                border-radius: 8px;
            }
            QPushButton#addSupplierButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7DD3FC, stop:1 #0EA5E9
                );
            }
            QPushButton#addSupplierButton:pressed {
                background-color: #0369A1;
            }
            QPushButton#autoInvoiceButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #A855F7, stop:1 #6D28D9
                );
                color: #FFFFFF;
                border: 1px solid #C084FC;
                border-radius: 8px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#autoInvoiceButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #C084FC, stop:1 #7C3AED
                );
            }
            QPushButton#autoInvoiceButton:pressed {
                background-color: #5B21B6;
            }
            QPushButton#btnQuickAdd {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3B82F6, stop:1 #1D4ED8
                );
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnQuickAdd:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #60A5FA, stop:1 #2563EB
                );
            }
            QPushButton#btnQuickAdd:pressed {
                background-color: #1E40AF;
            }
            QPushButton#btnBulkPicker {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14B8A6, stop:1 #0F766E
                );
                color: #FFFFFF;
                border: 1px solid #5EEAD4;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnBulkPicker:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2DD4BF, stop:1 #0D9488
                );
            }
            QPushButton#btnBulkPicker:pressed {
                background-color: #115E59;
            }
            QPushButton#btnRepeatOrder {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FB923C, stop:1 #EA580C
                );
                color: #FFFFFF;
                border: 1px solid #FDBA74;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnRepeatOrder:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDBA74, stop:1 #F97316
                );
            }
            QPushButton#btnRepeatOrder:pressed {
                background-color: #C2410C;
            }
            QPushButton#btnImportCsv {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EAB308, stop:1 #B45309
                );
                color: #FFFFFF;
                border: 1px solid #FDE047;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnImportCsv:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FACC15, stop:1 #CA8A04
                );
            }
            QPushButton#btnImportCsv:pressed {
                background-color: #A16207;
            }
            QPushButton#btnClearCart {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FB7185, stop:1 #E11D48
                );
                color: #FFFFFF;
                border: 1px solid #FDA4AF;
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnClearCart:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDA4AF, stop:1 #F43F5E
                );
            }
            QPushButton#btnClearCart:pressed {
                background-color: #BE123C;
            }
            QPushButton#quickPaySuccess {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10B981, stop:1 #059669
                );
                color: #FFFFFF;
                border: 1px solid #34D399;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton#quickPaySuccess:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34D399, stop:1 #10B981
                );
            }
            QPushButton#quickPayWarning {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FBBF24, stop:1 #D97706
                );
                color: #1E1B4B;
                border: 1px solid #FDE68A;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton#quickPayWarning:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDE047, stop:1 #F59E0B
                );
            }
            QPushButton#quickPayDanger {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F43F5E, stop:1 #BE123C
                );
                color: #FFFFFF;
                border: 1px solid #FB7185;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton#quickPayDanger:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FB7185, stop:1 #E11D48
                );
            }
            QPushButton#resetFormButton {
                background-color: #151B31;
                color: #E2E8F0;
                border: 1.5px solid #334168;
                border-radius: 9px;
                padding: 0px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#resetFormButton:hover {
                background-color: rgba(244, 63, 94, 0.14);
                border-color: #FB7185;
                color: #FFFFFF;
            }
            QPushButton#secondaryActionButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3730A3, stop:1 #1E1B4B
                );
                color: #E0E7FF;
                border: 1.5px solid #6366F1;
                border-radius: 9px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#secondaryActionButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4F46E5, stop:1 #312E81
                );
                border-color: #818CF8;
                color: #FFFFFF;
            }
            QPushButton#primaryActionButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4ADE80, stop:1 #10B981
                );
                color: #022C22;
                border: 1.5px solid #86EFAC;
                border-radius: 9px;
                padding: 0px 22px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#primaryActionButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #86EFAC, stop:1 #34D399
                );
            }
            QPushButton#primaryActionButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10B981, stop:1 #059669
                );
            }
            QPushButton#iconActionNeutral {
                background-color: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 7px;
            }
            QPushButton#iconActionNeutral:hover {
                background-color: rgba(56, 189, 248, 0.28);
                border-color: #38BDF8;
            }
            QPushButton#iconActionDanger {
                background-color: rgba(251, 113, 133, 0.12);
                border: 1px solid rgba(251, 113, 133, 0.35);
                border-radius: 7px;
            }
            QPushButton#iconActionDanger:hover {
                background-color: rgba(251, 113, 133, 0.28);
                border-color: #FB7185;
            }
            QPushButton#tablePillNeutral,
            QPushButton#tablePillSuccess,
            QPushButton#tablePillAccent {
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#tablePillNeutral {
                background-color: rgba(56, 189, 248, 0.12);
                color: #7DD3FC;
                border: 1px solid rgba(56, 189, 248, 0.4);
            }
            QPushButton#tablePillNeutral:hover {
                background-color: rgba(56, 189, 248, 0.26);
                color: #FFFFFF;
            }
            QPushButton#tablePillSuccess {
                background-color: rgba(52, 211, 153, 0.14);
                color: #6EE7B7;
                border: 1px solid rgba(52, 211, 153, 0.45);
            }
            QPushButton#tablePillSuccess:hover {
                background-color: rgba(52, 211, 153, 0.28);
                color: #FFFFFF;
            }
            QPushButton#tablePillSuccess:disabled {
                background-color: rgba(30, 41, 59, 0.4);
                color: #475569;
                border-color: #1E293B;
            }
            QPushButton#tablePillAccent {
                background-color: rgba(192, 132, 252, 0.14);
                color: #D8B4FE;
                border: 1px solid rgba(192, 132, 252, 0.45);
            }
            QPushButton#tablePillAccent:hover {
                background-color: rgba(192, 132, 252, 0.28);
                color: #FFFFFF;
            }
            QScrollBar:vertical {
                background: #0D1224;
                width: 9px;
                border-radius: 4px;
                margin: 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: #2C3B63;
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38BDF8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #0D1224;
                height: 9px;
                border-radius: 4px;
                margin: 0px 2px;
            }
            QScrollBar::handle:horizontal {
                background: #2C3B63;
                min-width: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38BDF8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh sinyal interaksi UI ke handler internal dan sinyal keluar."""

        self.add_supplier_btn.clicked.connect(self.add_supplier_requested.emit)
        self.auto_invoice_btn.clicked.connect(self._handle_auto_invoice_click)

        self.quick_search_input.textChanged.connect(self.search_text_changed.emit)
        self.quick_search_input.item_submitted.connect(self._handle_quick_search_submit)
        self.quick_search_input.focus_grid_requested.connect(self.focus_cart_grid)
        self._search_completer.activated.connect(self._handle_completer_activated)

        self.quick_add_btn.clicked.connect(self._handle_quick_add_click)
        self.bulk_picker_btn.clicked.connect(self.bulk_picker_requested.emit)
        self.repeat_order_btn.clicked.connect(self.repeat_order_requested.emit)
        self.import_csv_btn.clicked.connect(self.import_csv_requested.emit)
        self.clear_cart_btn.clicked.connect(self.clear_cart)

        self.discount_spin.valueChanged.connect(self._recalculate_totals)
        self.amount_paid_spin.valueChanged.connect(self._handle_amount_paid_changed)
        self.payment_method_combo.currentTextChanged.connect(
            self._update_payment_controls_state
        )

        self.btn_pay_full.clicked.connect(self.set_payment_full)
        self.btn_pay_partial.clicked.connect(self.set_payment_partial)
        self.btn_pay_unpaid.clicked.connect(self.set_payment_unpaid)

        self.reset_form_btn.clicked.connect(self._handle_reset_form_click)
        self.save_draft_btn.clicked.connect(self._handle_save_draft)
        self.submit_btn.clicked.connect(self._handle_submit_purchase)

        self.history_search_input.textChanged.connect(self._emit_history_filter)
        self.history_status_combo.currentIndexChanged.connect(self._emit_history_filter)
        self.history_date_from.dateChanged.connect(self._emit_history_filter)
        self.history_date_to.dateChanged.connect(self._emit_history_filter)
        self.history_refresh_btn.clicked.connect(self.history_refresh_requested.emit)

    def _setup_shortcuts(self) -> None:
        """Mendaftarkan pintasan papan ketik global pada halaman Tambah Stok."""
        shortcut_bindings: list[tuple[str, Callable[[], None]]] = [
            ("F1", self.focus_quick_search),
            ("F2", self.focus_cart_grid),
            ("F4", self.bulk_picker_requested.emit),
            ("F8", self.set_payment_full),
            ("F9", self._handle_save_draft),
            ("F10", self._handle_submit_purchase),
            ("Ctrl+Return", self._handle_submit_purchase),
            ("Ctrl+Enter", self._handle_submit_purchase),
            ("Ctrl+R", self._handle_reset_form_click),
        ]
        self._shortcuts.clear()
        for sequence_text, callback in shortcut_bindings:
            shortcut = QShortcut(QKeySequence(sequence_text), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    @staticmethod
    def _build_default_invoice_number() -> str:
        """Membuat format nomor nota bawaan berbasis tanggal dan jam saat ini.

        Returns:
            String nomor nota awal dengan awalan PO.
        """
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd-HHmm")
        return f"PO-{timestamp}"

    def _handle_auto_invoice_click(self) -> None:
        """Mengisi nomor faktur sementara dan memancarkan sinyal generate_invoice_requested."""
        self.invoice_input.setText(self._build_default_invoice_number())
        self.generate_invoice_requested.emit()

    def _handle_quick_add_click(self) -> None:
        """Memproses klik tombol Tambah menggunakan teks pada kotak pencarian cepat."""
        self._handle_quick_search_submit(self.quick_search_input.text().strip())

    def _handle_reset_form_click(self) -> None:
        """Menangani klik tombol atau pintasan Reset Form."""
        self.reset_form(keep_supplier=False)

    def focus_quick_search(self) -> None:
        """Memindahkan fokus kursor ke kotak pencarian cepat pada panel belanja."""
        self._stack.setCurrentIndex(0)
        self.quick_search_input.setFocus()
        self.quick_search_input.selectAll()

    def focus_cart_grid(self) -> None:
        """Memindahkan fokus ke kolom Qty baris pertama pada tabel keranjang."""
        if self.cart_table.rowCount() == 0:
            self.focus_quick_search()
            return
        self._focus_row_widget(0, self.COL_QTY)

    def set_suppliers(
        self,
        suppliers: list[SupplierOption],
        selected_id: int | None = None,
    ) -> None:
        """Mengisi ulang daftar pilihan supplier pada dropdown header nota.

        Args:
            suppliers: Daftar objek SupplierOption dari backend.
            selected_id: ID supplier yang ingin langsung dipilih opsional.
        """
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("-- Tanpa Supplier (Belanja Umum) --", None)

        target_index = 0
        for idx, supplier in enumerate(suppliers, start=1):
            label = supplier["name"]
            if supplier["phone"]:
                label = f"{supplier['name']} ({supplier['phone']})"
            self.supplier_combo.addItem(label, supplier["id"])
            if selected_id is not None and supplier["id"] == selected_id:
                target_index = idx

        self.supplier_combo.setCurrentIndex(target_index)
        self.supplier_combo.blockSignals(False)

    def set_catalog_items(self, items: list[CatalogItemData]) -> None:
        """Memuat katalog barang untuk autocomplete pencarian instan keyboard-first.

        Args:
            items: Daftar CatalogItemData lengkap beserta varian satuannya.
        """
        self._catalog_by_id.clear()
        self._catalog_by_sku.clear()
        self._catalog_by_label.clear()

        labels: list[str] = []
        for item in items:
            self._catalog_by_id[item["item_id"]] = item
            self._catalog_by_sku[item["sku"].strip().lower()] = item
            display_label = (
                f"{item['sku']} | {item['name']} "
                f"(Stok: {format_quantity(item['current_stock'])} {item['base_unit_symbol']})"
            )
            self._catalog_by_label[display_label.lower()] = item
            labels.append(display_label)

        self._search_model.setStringList(labels)

    def set_invoice_number(self, invoice_number: str) -> None:
        """Mengatur teks nomor faktur pada input header nota.

        Args:
            invoice_number: Nomor faktur hasil generasi backend.
        """
        self.invoice_input.setText(invoice_number)

    def show_status_banner(
        self,
        message: str,
        level: str = "info",
        duration_ms: int = 4500,
    ) -> None:
        """Menampilkan notifikasi Toast tanpa menghalangi alur ketik pengguna.

        Args:
            message: Pesan informasi, keberhasilan, peringatan, atau galat.
            level: Tingkat pesan berupa 'info', 'success', 'warning', atau 'error'.
            duration_ms: Durasi tampil otomatis dalam milidetik.
        """
        title_map: dict[str, tuple[str, bool]] = {
            "success": ("Berhasil", True),
            "info": ("Informasi", True),
            "warning": ("Peringatan", False),
            "error": ("Kesalahan", False),
        }
        title, is_success = title_map.get(level, ("Informasi", True))
        resolved_duration = duration_ms if duration_ms > 0 else 4500
        show_toast(
            parent=self,
            title=title,
            message=message,
            is_success=is_success,
            duration_ms=resolved_duration,
        )

    def _resolve_catalog_item(self, query: str) -> CatalogItemData | None:
        """Mencari kecocokan barang dari teks SKU, label autocomplete, atau potongan nama.

        Args:
            query: Kata kunci yang diketik atau dipindai pengguna.

        Returns:
            Objek CatalogItemData jika ditemukan, atau None bila tidak cocok.
        """
        normalized = query.strip().lower()
        if not normalized:
            return None

        if normalized in self._catalog_by_label:
            return self._catalog_by_label[normalized]

        if normalized in self._catalog_by_sku:
            return self._catalog_by_sku[normalized]

        if "|" in normalized:
            sku_candidate = normalized.split("|", 1)[0].strip()
            if sku_candidate in self._catalog_by_sku:
                return self._catalog_by_sku[sku_candidate]

        matches: list[CatalogItemData] = [
            item
            for item in self._catalog_by_id.values()
            if normalized in item["sku"].lower() or normalized in item["name"].lower()
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _handle_completer_activated(self, text: str) -> None:
        """Menangani pemilihan item dari popup autocomplete pencarian cepat.

        Args:
            text: Teks item yang dipilih pengguna pada popup completer.
        """
        QTimer.singleShot(0, partial(self._handle_quick_search_submit, text))

    def _handle_quick_search_submit(self, query: str) -> None:
        """Menambahkan barang hasil pencarian cepat ke keranjang dan memfokuskan Qty.

        Args:
            query: Teks pencarian atau hasil pemindaian barcode.
        """
        if not query:
            if self.cart_table.rowCount() > 0:
                self.focus_cart_grid()
            return

        item = self._resolve_catalog_item(query)
        if item is None:
            self.show_status_banner(
                f"Barang '{query}' tidak ditemukan pada katalog aktif.",
                level="warning",
                duration_ms=3000,
            )
            self.quick_search_input.selectAll()
            return

        self.quick_search_input.clear()
        self.add_item_to_cart(item, quantity=1.0, focus_qty=True)

    def _get_selected_unit_option(self, row: int) -> ItemUnitOption | None:
        """Mengambil data ItemUnitOption yang sedang aktif pada baris keranjang.

        Args:
            row: Indeks baris pada tabel keranjang.

        Returns:
            Objek ItemUnitOption yang cocok atau None jika tidak tersedia.
        """
        if row < 0 or row >= len(self._row_item_data):
            return None
        unit_combo = self._get_unit_combo(row)
        if unit_combo is None:
            return None
        raw_unit_id = unit_combo.currentData()
        if not isinstance(raw_unit_id, int):
            return None
        for unit in self._row_item_data[row]["units"]:
            if unit["item_unit_id"] == raw_unit_id:
                return unit
        return None

    def _find_matching_row(self, item_id: int, item_unit_id: int) -> int:
        """Mencari indeks baris yang sudah memuat kombinasi item dan satuan identik.

        Args:
            item_id: ID barang yang dicari.
            item_unit_id: ID varian satuan yang dicari.

        Returns:
            Indeks baris (0-based) jika ditemukan, atau -1 bila belum ada.
        """
        for row in range(self.cart_table.rowCount()):
            if row >= len(self._row_item_data):
                continue
            if self._row_item_data[row]["item_id"] != item_id:
                continue
            unit_option = self._get_selected_unit_option(row)
            if unit_option is not None and unit_option["item_unit_id"] == item_unit_id:
                return row
        return -1

    def add_item_to_cart(
        self,
        item: CatalogItemData,
        quantity: float = 1.0,
        item_unit_id: int | None = None,
        unit_cost: float | None = None,
        focus_qty: bool = True,
    ) -> int:
        """Menambahkan satu barang ke keranjang atau menambah qty jika baris identik ada.

        Args:
            item: Data katalog barang lengkap dengan daftar varian satuannya.
            quantity: Jumlah awal pembelian pada satuan terpilih.
            item_unit_id: ID varian satuan khusus; jika None memilih satuan default.
            unit_cost: Harga beli per satuan; jika None menggunakan last_unit_cost.
            focus_qty: Jika True, langsung memfokuskan kursor ke kolom Qty baris tersebut.

        Returns:
            Indeks baris pada tabel keranjang tempat barang berada, atau -1 jika unit kosong.
        """
        units = item["units"]
        if not units:
            self.show_status_banner(
                f"Barang '{item['name']}' belum memiliki satuan beli pada item_units.",
                level="error",
            )
            return -1

        selected_unit = units[0]
        if item_unit_id is not None:
            for unit in units:
                if unit["item_unit_id"] == item_unit_id:
                    selected_unit = unit
                    break
        else:
            for unit in units:
                if unit["is_default"]:
                    selected_unit = unit
                    break

        existing_row = self._find_matching_row(item["item_id"], selected_unit["item_unit_id"])
        if existing_row >= 0 and unit_cost is None:
            qty_spin = self._get_qty_spin(existing_row)
            if qty_spin is not None:
                qty_spin.setValue(qty_spin.value() + quantity)
            if focus_qty:
                self._focus_row_widget(existing_row, self.COL_QTY)
            return existing_row

        row = self.cart_table.rowCount()
        self.cart_table.insertRow(row)
        self._row_item_data.append(item)

        no_item = QTableWidgetItem(str(row + 1))
        no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        no_item.setForeground(QBrush(QColor("#94A3B8")))
        self.cart_table.setItem(row, self.COL_NO, no_item)

        info_widget = ItemInfoCellWidget(
            name=item["name"],
            sku=item["sku"],
            current_stock=item["current_stock"],
            base_unit_symbol=item["base_unit_symbol"],
            parent=self.cart_table,
        )
        self.cart_table.setCellWidget(row, self.COL_ITEM, info_widget)

        unit_combo = KeyboardUnitComboBox(self.cart_table)
        unit_combo.setObjectName("gridCombo")
        unit_combo.setFixedHeight(28)
        selected_unit_index = 0
        for idx, unit in enumerate(units):
            conv_text = format_quantity(unit["conversion_qty"])
            label = f"{unit['variant_name']} (x{conv_text})"
            unit_combo.addItem(label, unit["item_unit_id"])
            if unit["item_unit_id"] == selected_unit["item_unit_id"]:
                selected_unit_index = idx
        unit_combo.setCurrentIndex(selected_unit_index)
        self.cart_table.setCellWidget(row, self.COL_UNIT, unit_combo)

        qty_spin = KeyboardDoubleSpinBox(
            decimals=2,
            minimum=0.01,
            maximum=999999.0,
            parent=self.cart_table,
        )
        qty_spin.setObjectName("gridSpinBox")
        qty_spin.setFixedHeight(28)
        qty_spin.setValue(max(0.01, quantity))
        self.cart_table.setCellWidget(row, self.COL_QTY, qty_spin)

        base_qty_item = QTableWidgetItem("")
        base_qty_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        base_qty_item.setForeground(QBrush(QColor("#38BDF8")))
        base_font = base_qty_item.font()
        base_font.setBold(True)
        base_qty_item.setFont(base_font)
        self.cart_table.setItem(row, self.COL_BASE_QTY, base_qty_item)

        initial_cost = (
            float(unit_cost)
            if unit_cost is not None
            else float(selected_unit["last_unit_cost"])
        )
        cost_spin = KeyboardDoubleSpinBox(
            decimals=0,
            minimum=0.0,
            maximum=2_000_000_000.0,
            prefix="Rp ",
            parent=self.cart_table,
        )
        cost_spin.setObjectName("gridSpinBox")
        cost_spin.setFixedHeight(28)
        cost_spin.setValue(max(0.0, initial_cost))
        self.cart_table.setCellWidget(row, self.COL_UNIT_COST, cost_spin)

        subtotal_widget = SubtotalCellWidget(self.cart_table)
        self.cart_table.setCellWidget(row, self.COL_SUBTOTAL, subtotal_widget)

        action_widget = RowActionCellWidget(self.cart_table)
        self.cart_table.setCellWidget(row, self.COL_ACTION, action_widget)

        self._bind_row_signals(
            unit_combo=unit_combo,
            qty_spin=qty_spin,
            cost_spin=cost_spin,
            subtotal_widget=subtotal_widget,
            action_widget=action_widget,
        )

        self._recalculate_row(row, source="cost")
        self._recalculate_totals()

        if focus_qty:
            self._focus_row_widget(row, self.COL_QTY)
        return row

    def _bind_row_signals(
        self,
        unit_combo: KeyboardUnitComboBox,
        qty_spin: KeyboardDoubleSpinBox,
        cost_spin: KeyboardDoubleSpinBox,
        subtotal_widget: SubtotalCellWidget,
        action_widget: RowActionCellWidget,
    ) -> None:
        """Menghubungkan seluruh sinyal keyboard dan sinkronisasi nilai pada satu baris grid.

        Args:
            unit_combo: Widget dropdown satuan baris.
            qty_spin: Widget input jumlah beli baris.
            cost_spin: Widget input harga beli satuan baris.
            subtotal_widget: Widget sel subtotal dan pratinjau HPP baris.
            action_widget: Widget tombol aksi edit harga jual dan hapus baris.
        """
        unit_combo.currentIndexChanged.connect(
            partial(self._handle_unit_changed, unit_combo)
        )
        unit_combo.enter_pressed.connect(
            partial(self._focus_widget_column, unit_combo, self.COL_QTY)
        )

        qty_spin.valueChanged.connect(
            partial(self._sync_row_from_qty_or_cost, qty_spin)
        )
        qty_spin.enter_pressed.connect(
            partial(self._focus_widget_column, qty_spin, self.COL_UNIT_COST)
        )
        qty_spin.navigate_vertical.connect(
            partial(self._navigate_vertical, qty_spin, self.COL_QTY)
        )
        qty_spin.row_delete_requested.connect(
            partial(self._remove_row_by_widget, qty_spin)
        )

        cost_spin.valueChanged.connect(
            partial(self._sync_row_from_qty_or_cost, cost_spin)
        )
        cost_spin.enter_pressed.connect(self.focus_quick_search)
        cost_spin.navigate_vertical.connect(
            partial(self._navigate_vertical, cost_spin, self.COL_UNIT_COST)
        )
        cost_spin.row_delete_requested.connect(
            partial(self._remove_row_by_widget, cost_spin)
        )

        subtotal_widget.subtotal_spin.valueChanged.connect(
            partial(self._sync_row_from_subtotal, subtotal_widget)
        )
        subtotal_widget.subtotal_spin.enter_pressed.connect(self.focus_quick_search)
        subtotal_widget.subtotal_spin.navigate_vertical.connect(
            partial(self._navigate_vertical, subtotal_widget, self.COL_SUBTOTAL)
        )
        subtotal_widget.subtotal_spin.row_delete_requested.connect(
            partial(self._remove_row_by_widget, subtotal_widget)
        )

        action_widget.edit_price_clicked.connect(
            partial(self._emit_edit_selling_price, action_widget)
        )
        action_widget.delete_clicked.connect(
            partial(self._remove_row_by_widget, action_widget)
        )

    def add_items_bulk(self, items: list[CatalogItemData]) -> None:
        """Menambahkan banyak barang sekaligus ke keranjang dari Bulk Picker atau CSV.

        Args:
            items: Daftar barang katalog yang akan dimasukkan secara berurutan.
        """
        if not items:
            return
        first_added_row = -1
        for item in items:
            row_idx = self.add_item_to_cart(item, quantity=1.0, focus_qty=False)
            if first_added_row < 0 and row_idx >= 0:
                first_added_row = row_idx

        if first_added_row >= 0:
            self._focus_row_widget(first_added_row, self.COL_QTY)
            self.show_status_banner(
                f"{len(items)} barang ditambahkan ke keranjang. Sesuaikan qty lalu tekan Enter.",
                level="success",
                duration_ms=3500,
            )

    def load_purchase_into_form(
        self,
        payload: PurchasePayload,
        catalog_map: dict[int, CatalogItemData] | None = None,
    ) -> None:
        """Memuat ulang data nota pembelian lama atau draft ke dalam form keranjang.

        Args:
            payload: Struktur PurchasePayload yang akan dimuat ke antarmuka.
            catalog_map: Peta opsional item_id ke CatalogItemData jika katalog belum terisi.
        """
        source_catalog = catalog_map if catalog_map is not None else self._catalog_by_id
        self.clear_cart()

        self._stack.setCurrentIndex(0)
        if payload["invoice_number"]:
            self.invoice_input.setText(payload["invoice_number"])

        supplier_id = payload["supplier_id"]
        found_supplier = False
        for idx in range(self.supplier_combo.count()):
            if self.supplier_combo.itemData(idx) == supplier_id:
                self.supplier_combo.setCurrentIndex(idx)
                found_supplier = True
                break
        if not found_supplier:
            self.supplier_combo.setCurrentIndex(0)

        self.notes_input.setText(payload["notes"])
        self.discount_spin.setValue(max(0, payload["discount"]))

        method_idx = self.payment_method_combo.findText(payload["payment_method"])
        if method_idx >= 0:
            self.payment_method_combo.setCurrentIndex(method_idx)

        missing_count = 0
        for line in payload["details"]:
            catalog_item = source_catalog.get(line["item_id"])
            if catalog_item is None:
                missing_count += 1
                continue
            self.add_item_to_cart(
                item=catalog_item,
                quantity=line["quantity"],
                item_unit_id=line["item_unit_id"],
                unit_cost=line["unit_cost"],
                focus_qty=False,
            )

        self._auto_full_payment = False
        self.amount_paid_spin.setValue(max(0, payload["amount_paid"]))
        if payload["due_date"]:
            parsed_due = QDate.fromString(payload["due_date"], "yyyy-MM-dd")
            if parsed_due.isValid():
                self.due_date_edit.setDate(parsed_due)
        if payload["reference_number"]:
            self.reference_input.setText(payload["reference_number"])

        self._recalculate_totals()
        if missing_count > 0:
            self.show_status_banner(
                f"Nota dimuat dengan {missing_count} barang tidak ditemukan di katalog aktif.",
                level="warning",
            )
        else:
            self.show_status_banner("Daftar barang berhasil dimuat ke keranjang.", level="info")
        self.focus_cart_grid()

    def _find_row_for_widget(self, target: QWidget) -> int:
        """Menemukan indeks baris aktual dari widget sel secara aman setelah penghapusan.

        Args:
            target: Widget yang berada di salah satu sel tabel keranjang.

        Returns:
            Indeks baris (0-based) jika ditemukan, atau -1 bila tidak ditemukan.
        """
        for row in range(self.cart_table.rowCount()):
            for col in (
                self.COL_UNIT,
                self.COL_QTY,
                self.COL_UNIT_COST,
                self.COL_SUBTOTAL,
                self.COL_ACTION,
            ):
                if self.cart_table.cellWidget(row, col) is target:
                    return row
        return -1

    def _get_unit_combo(self, row: int) -> KeyboardUnitComboBox | None:
        """Mengambil widget dropdown satuan pada baris tertentu secara aman.

        Args:
            row: Indeks baris tabel keranjang.

        Returns:
            Instance KeyboardUnitComboBox atau None jika tidak valid.
        """
        widget = self.cart_table.cellWidget(row, self.COL_UNIT)
        return widget if isinstance(widget, KeyboardUnitComboBox) else None

    def _get_qty_spin(self, row: int) -> KeyboardDoubleSpinBox | None:
        """Mengambil widget input Qty Beli pada baris tertentu secara aman.

        Args:
            row: Indeks baris tabel keranjang.

        Returns:
            Instance KeyboardDoubleSpinBox atau None jika tidak valid.
        """
        widget = self.cart_table.cellWidget(row, self.COL_QTY)
        return widget if isinstance(widget, KeyboardDoubleSpinBox) else None

    def _get_cost_spin(self, row: int) -> KeyboardDoubleSpinBox | None:
        """Mengambil widget input Harga Beli pada baris tertentu secara aman.

        Args:
            row: Indeks baris tabel keranjang.

        Returns:
            Instance KeyboardDoubleSpinBox atau None jika tidak valid.
        """
        widget = self.cart_table.cellWidget(row, self.COL_UNIT_COST)
        return widget if isinstance(widget, KeyboardDoubleSpinBox) else None

    def _get_subtotal_widget(self, row: int) -> SubtotalCellWidget | None:
        """Mengambil widget sel subtotal pada baris tertentu secara aman.

        Args:
            row: Indeks baris tabel keranjang.

        Returns:
            Instance SubtotalCellWidget atau None jika tidak valid.
        """
        widget = self.cart_table.cellWidget(row, self.COL_SUBTOTAL)
        return widget if isinstance(widget, SubtotalCellWidget) else None

    def _focus_row_widget(self, row: int, column: int) -> None:
        """Memfokuskan widget input pada baris dan kolom tertentu di keranjang.

        Args:
            row: Indeks baris tujuan.
            column: Indeks kolom tujuan.
        """
        if row < 0 or row >= self.cart_table.rowCount():
            return
        self.cart_table.selectRow(row)
        widget = self.cart_table.cellWidget(row, column)
        if isinstance(widget, SubtotalCellWidget):
            widget.subtotal_spin.setFocus()
            widget.subtotal_spin.selectAll()
            return
        if widget is not None:
            widget.setFocus()

    def _focus_widget_column(self, source_widget: QWidget, target_column: int) -> None:
        """Memindahkan fokus dari widget sumber ke kolom lain pada baris yang sama.

        Args:
            source_widget: Widget pengirim sinyal perpindahan.
            target_column: Indeks kolom tujuan pada baris yang sama.
        """
        row = self._find_row_for_widget(source_widget)
        if row >= 0:
            self._focus_row_widget(row, target_column)

    def _navigate_vertical(
        self,
        source_widget: QWidget,
        column: int,
        delta: int,
    ) -> None:
        """Memindahkan fokus ke baris di atas atau di bawah pada kolom yang sama.

        Args:
            source_widget: Widget pengirim sinyal navigasi.
            column: Indeks kolom yang dipertahankan.
            delta: Arah pergeseran baris (-1 untuk atas, +1 untuk bawah).
        """
        current_row = self._find_row_for_widget(source_widget)
        if current_row < 0:
            return
        next_row = current_row + delta
        if 0 <= next_row < self.cart_table.rowCount():
            self._focus_row_widget(next_row, column)

    def _handle_unit_changed(self, combo: QWidget, _index: int = 0) -> None:
        """Memperbarui harga beli bawaan dan konversi ketika satuan baris diganti.

        Args:
            combo: Widget KeyboardUnitComboBox yang nilainya berubah.
            _index: Indeks item baru dari sinyal currentIndexChanged.
        """
        row = self._find_row_for_widget(combo)
        if row < 0:
            return
        cost_spin = self._get_cost_spin(row)
        unit_option = self._get_selected_unit_option(row)
        if cost_spin is not None and unit_option is not None:
            self._updating_row = True
            cost_spin.setValue(max(0.0, float(unit_option["last_unit_cost"])))
            self._updating_row = False

        self._recalculate_row(row, source="cost")
        self._recalculate_totals()

    def _sync_row_from_qty_or_cost(self, widget: QWidget, _value: float = 0.0) -> None:
        """Menghitung ulang subtotal baris saat Qty atau Harga Beli diubah.

        Args:
            widget: Widget sel yang nilainya berubah.
            _value: Nilai desimal terbaru dari sinyal valueChanged.
        """
        if self._updating_row:
            return
        row = self._find_row_for_widget(widget)
        if row < 0:
            return
        self._recalculate_row(row, source="cost")
        self._recalculate_totals()

    def _sync_row_from_subtotal(self, widget: QWidget, _value: float = 0.0) -> None:
        """Menghitung balik Harga Beli per satuan saat pengguna mengetik subtotal baris.

        Args:
            widget: Widget SubtotalCellWidget yang nilainya diubah.
            _value: Nilai subtotal terbaru dari sinyal valueChanged.
        """
        if self._updating_row:
            return
        row = self._find_row_for_widget(widget)
        if row < 0:
            return
        self._recalculate_row(row, source="subtotal")
        self._recalculate_totals()

    def _recalculate_row(self, row: int, source: str) -> None:
        """Menyinkronkan stok masuk dasar, harga beli, subtotal, dan pratinjau HPP baris.

        Args:
            row: Indeks baris yang akan dihitung ulang.
            source: Sumber perubahan berupa 'cost' atau 'subtotal'.
        """
        if row < 0 or row >= len(self._row_item_data):
            return

        qty_spin = self._get_qty_spin(row)
        cost_spin = self._get_cost_spin(row)
        subtotal_widget = self._get_subtotal_widget(row)
        if qty_spin is None or cost_spin is None or subtotal_widget is None:
            return

        unit_option = self._get_selected_unit_option(row)
        conversion_qty = (
            unit_option["conversion_qty"]
            if unit_option is not None and unit_option["conversion_qty"] > 0
            else 1.0
        )

        qty = max(0.01, qty_spin.value())
        base_qty = qty * conversion_qty
        base_symbol = self._row_item_data[row]["base_unit_symbol"]

        base_item = self.cart_table.item(row, self.COL_BASE_QTY)
        if base_item is not None:
            base_item.setText(f"= {format_quantity(base_qty)} {base_symbol}")

        self._updating_row = True
        if source == "subtotal":
            line_subtotal = max(0.0, subtotal_widget.subtotal_spin.value())
            unit_cost = line_subtotal / qty if qty > 0 else 0.0
            cost_spin.setValue(unit_cost)
        else:
            unit_cost = max(0.0, cost_spin.value())
            line_subtotal = qty * unit_cost
            subtotal_widget.subtotal_spin.setValue(line_subtotal)
        self._updating_row = False

        hpp_per_base = line_subtotal / base_qty if base_qty > 0 else 0.0
        subtotal_widget.update_hpp_preview(hpp_per_base, base_symbol)

    def _remove_row_by_widget(self, widget: QWidget) -> None:
        """Menghapus baris keranjang berdasarkan referensi widget sel dan menata nomor urut.

        Args:
            widget: Widget sel pada baris yang akan dihapus.
        """
        row = self._find_row_for_widget(widget)
        if row < 0 or row >= len(self._row_item_data):
            return
        self.cart_table.removeRow(row)
        self._row_item_data.pop(row)
        self._renumber_cart_rows()
        self._recalculate_totals()

        if self.cart_table.rowCount() > 0:
            next_row = min(row, self.cart_table.rowCount() - 1)
            self._focus_row_widget(next_row, self.COL_QTY)
        else:
            self.focus_quick_search()

    def _emit_edit_selling_price(self, widget: QWidget) -> None:
        """Memancarkan sinyal edit harga jual untuk item pada baris terkait.

        Args:
            widget: Widget aksi pada baris yang ditekan.
        """
        row = self._find_row_for_widget(widget)
        if 0 <= row < len(self._row_item_data):
            self.edit_selling_price_requested.emit(self._row_item_data[row]["item_id"])

    def _renumber_cart_rows(self) -> None:
        """Memperbarui nomor urut pada kolom pertama seluruh baris keranjang."""
        for row in range(self.cart_table.rowCount()):
            cell_item = self.cart_table.item(row, self.COL_NO)
            if cell_item is not None:
                cell_item.setText(str(row + 1))

    def clear_cart(self) -> None:
        """Mengosongkan seluruh baris pada keranjang belanja dan mengatur ulang total."""
        self.cart_table.setRowCount(0)
        self._row_item_data.clear()
        self._auto_full_payment = True
        self._recalculate_totals()
        self.focus_quick_search()

    def _recalculate_totals(self) -> None:
        """Menghitung ulang subtotal, grand total, sisa hutang, dan badge status."""
        total_subtotal = 0.0
        total_qty = 0.0
        row_count = self.cart_table.rowCount()

        for row in range(row_count):
            qty_spin = self._get_qty_spin(row)
            subtotal_widget = self._get_subtotal_widget(row)
            if qty_spin is not None:
                total_qty += qty_spin.value()
            if subtotal_widget is not None:
                total_subtotal += subtotal_widget.subtotal_spin.value()

        subtotal_int = int(round(total_subtotal))
        discount_int = min(self.discount_spin.value(), subtotal_int)
        if self.discount_spin.value() > subtotal_int and subtotal_int >= 0:
            self.discount_spin.blockSignals(True)
            self.discount_spin.setValue(discount_int)
            self.discount_spin.blockSignals(False)

        grand_total = max(0, subtotal_int - discount_int)

        if self._auto_full_payment:
            self.amount_paid_spin.blockSignals(True)
            self.amount_paid_spin.setValue(grand_total)
            self.amount_paid_spin.blockSignals(False)

        amount_paid = self.amount_paid_spin.value()
        remaining = max(0, grand_total - amount_paid)

        self.item_count_label.setText(
            f"{row_count} Jenis Barang  •  {format_quantity(total_qty)} Total Qty Beli"
        )
        self.subtotal_value_label.setText(format_rupiah(subtotal_int))
        self.grand_total_label.setText(format_rupiah(grand_total))
        self.remaining_value_label.setText(format_rupiah(remaining))

        self._update_payment_status_badge(grand_total, amount_paid)
        self._update_payment_controls_state()

    def _handle_amount_paid_changed(self) -> None:
        """Menandai mode pembayaran manual dan memperbarui status sisa hutang."""
        self._auto_full_payment = False
        self._recalculate_totals()

    def _compute_payment_status(self, total: int, amount_paid: int) -> str:
        """Menentukan kode status pembayaran sesuai skema tabel purchases.

        Args:
            total: Nilai grand total nota pembelian.
            amount_paid: Nominal yang dibayarkan saat ini.

        Returns:
            String status 'PAID', 'PARTIAL', atau 'UNPAID'.
        """
        if total == 0 or amount_paid >= total:
            return "PAID"
        if amount_paid > 0:
            return "PARTIAL"
        return "UNPAID"

    def _update_payment_status_badge(self, total: int, amount_paid: int) -> None:
        """Memperbarui warna dan teks badge status pembayaran secara langsung.

        Args:
            total: Grand total pembelian.
            amount_paid: Nominal yang dibayarkan.
        """
        status = self._compute_payment_status(total, amount_paid)
        if status == "PAID":
            self.payment_status_badge.setText("LUNAS")
            self.payment_status_badge.setObjectName("statusBadgePaid")
        elif status == "PARTIAL":
            self.payment_status_badge.setText("CICILAN")
            self.payment_status_badge.setObjectName("statusBadgePartial")
        else:
            self.payment_status_badge.setText("BELUM LUNAS")
            self.payment_status_badge.setObjectName("statusBadgeUnpaid")

        badge_style = self.payment_status_badge.style()
        if badge_style is not None:
            badge_style.unpolish(self.payment_status_badge)
            badge_style.polish(self.payment_status_badge)

    def _update_payment_controls_state(self) -> None:
        """Mengaktifkan atau menonaktifkan jatuh tempo dan nomor referensi sesuai kondisi."""
        payload_total = self._current_grand_total()
        amount_paid = self.amount_paid_spin.value()
        has_debt = payload_total > 0 and amount_paid < payload_total
        self.due_date_edit.setEnabled(has_debt)

        is_non_cash = self.payment_method_combo.currentText() != "Tunai"
        self.reference_input.setEnabled(is_non_cash and amount_paid > 0)

    def _current_grand_total(self) -> int:
        """Menghitung nilai grand total terkini dari keranjang dan diskon nota.

        Returns:
            Nilai integer grand total pembelian.
        """
        total_subtotal = 0.0
        for row in range(self.cart_table.rowCount()):
            subtotal_widget = self._get_subtotal_widget(row)
            if subtotal_widget is not None:
                total_subtotal += subtotal_widget.subtotal_spin.value()
        return max(0, int(round(total_subtotal)) - self.discount_spin.value())

    def set_payment_full(self) -> None:
        """Mengatur nominal dibayar penuh (Lunas) sesuai grand total nota."""
        self._auto_full_payment = True
        self._recalculate_totals()

    def set_payment_partial(self) -> None:
        """Mengatur mode cicilan (DP) dan memfokuskan input nominal dibayar."""
        self._auto_full_payment = False
        grand_total = self._current_grand_total()
        suggested_dp = grand_total // 2 if grand_total > 0 else 0
        self.amount_paid_spin.setValue(suggested_dp)
        self.amount_paid_spin.setFocus()
        self.amount_paid_spin.selectAll()

    def set_payment_unpaid(self) -> None:
        """Mengatur nominal dibayar menjadi 0 (Tempo) dan memfokuskan tanggal jatuh tempo."""
        self._auto_full_payment = False
        self.amount_paid_spin.setValue(0)
        self.due_date_edit.setFocus()

    def get_purchase_payload(self, status: str = "COMPLETED") -> PurchasePayload:
        """Mengumpulkan seluruh data form dan keranjang menjadi PurchasePayload terstruktur.

        Args:
            status: Status dokumen yang diinginkan, biasanya 'COMPLETED' atau 'DRAFT'.

        Returns:
            Dictionary PurchasePayload yang selaras dengan tabel purchases dan purchase_details.
        """
        details: list[PurchaseLinePayload] = []
        raw_subtotal = 0.0

        for row in range(self.cart_table.rowCount()):
            if row >= len(self._row_item_data):
                continue
            qty_spin = self._get_qty_spin(row)
            cost_spin = self._get_cost_spin(row)
            subtotal_widget = self._get_subtotal_widget(row)
            if qty_spin is None or cost_spin is None or subtotal_widget is None:
                continue

            unit_option = self._get_selected_unit_option(row)
            item_unit_id = unit_option["item_unit_id"] if unit_option is not None else 0
            conversion_qty = (
                unit_option["conversion_qty"]
                if unit_option is not None and unit_option["conversion_qty"] > 0
                else 1.0
            )

            qty = qty_spin.value()
            unit_cost = cost_spin.value()
            line_subtotal = subtotal_widget.subtotal_spin.value()
            raw_subtotal += line_subtotal

            details.append(
                {
                    "item_id": self._row_item_data[row]["item_id"],
                    "item_unit_id": item_unit_id,
                    "quantity": qty,
                    "conversion_qty": conversion_qty,
                    "base_quantity": qty * conversion_qty,
                    "unit_cost": unit_cost,
                    "subtotal": line_subtotal,
                }
            )

        subtotal_int = int(round(raw_subtotal))
        discount_int = min(self.discount_spin.value(), subtotal_int)
        total_int = max(0, subtotal_int - discount_int)
        amount_paid = self.amount_paid_spin.value()
        remaining = max(0, total_int - amount_paid)
        payment_status = self._compute_payment_status(total_int, amount_paid)

        raw_supplier_id = self.supplier_combo.currentData()
        supplier_id = raw_supplier_id if isinstance(raw_supplier_id, int) else None

        due_date: str | None = None
        if remaining > 0:
            due_date = self.due_date_edit.date().toString("yyyy-MM-dd")

        ref_text = self.reference_input.text().strip()
        reference_number = ref_text if (self.reference_input.isEnabled() and ref_text) else None

        return {
            "invoice_number": self.invoice_input.text().strip(),
            "supplier_id": supplier_id,
            "purchase_date": self.purchase_date_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "subtotal": subtotal_int,
            "discount": discount_int,
            "total": total_int,
            "payment_method": self.payment_method_combo.currentText(),
            "amount_paid": amount_paid,
            "remaining_amount": remaining,
            "payment_status": payment_status,
            "due_date": due_date,
            "status": status,
            "notes": self.notes_input.text().strip(),
            "reference_number": reference_number,
            "details": details,
        }

    def validate_form(self) -> tuple[bool, str]:
        """Memvalidasi kelengkapan input form sebelum dikirim ke backend.

        Returns:
            Tuple (is_valid, error_message) hasil validasi antarmuka.
        """
        if not self.invoice_input.text().strip():
            self.invoice_input.setFocus()
            return False, "Nomor faktur / nota pembelian wajib diisi."

        if self.cart_table.rowCount() == 0:
            self.focus_quick_search()
            return False, "Keranjang kulakan masih kosong. Tambahkan minimal 1 barang."

        payload = self.get_purchase_payload()
        for idx, line in enumerate(payload["details"], start=1):
            if line["item_unit_id"] <= 0:
                return False, f"Satuan beli pada baris ke-{idx} belum valid."
            if line["quantity"] <= 0:
                self._focus_row_widget(idx - 1, self.COL_QTY)
                return False, f"Qty beli pada baris ke-{idx} harus lebih dari 0."

        if payload["remaining_amount"] > 0 and payload["supplier_id"] is None:
            self.supplier_combo.setFocus()
            return (
                False,
                "Transaksi cicilan atau tempo wajib memilih Supplier agar hutang tercatat.",
            )

        return True, ""

    def _handle_submit_purchase(self) -> None:
        """Memvalidasi form dan memancarkan sinyal submit_purchase_requested."""
        is_valid, error_message = self.validate_form()
        if not is_valid:
            self.show_status_banner(error_message, level="error", duration_ms=5000)
            return
        payload = self.get_purchase_payload(status="COMPLETED")
        self.submit_purchase_requested.emit(dict(payload))

    def _handle_save_draft(self) -> None:
        """Memvalidasi minimal nota/item lalu memancarkan sinyal save_draft_requested."""
        if self.cart_table.rowCount() == 0:
            self.show_status_banner(
                "Tambahkan minimal 1 barang sebelum menyimpan draft.",
                level="warning",
            )
            return
        if not self.invoice_input.text().strip():
            self.invoice_input.setText(self._build_default_invoice_number())
        payload = self.get_purchase_payload(status="DRAFT")
        self.save_draft_requested.emit(dict(payload))

    def reset_form(self, keep_supplier: bool = False) -> None:
        """Mengembalikan seluruh field form dan keranjang ke kondisi awal siap pakai.

        Args:
            keep_supplier: Jika True, mempertahankan supplier yang sedang dipilih.
        """
        if not keep_supplier:
            self.supplier_combo.setCurrentIndex(0)
        self.invoice_input.setText(self._build_default_invoice_number())
        self.purchase_date_edit.setDateTime(QDateTime.currentDateTime())
        self.notes_input.clear()
        self.discount_spin.setValue(0)
        self.payment_method_combo.setCurrentIndex(0)
        self.reference_input.clear()
        self.due_date_edit.setDate(QDate.currentDate().addDays(14))
        self.clear_cart()

    def _emit_history_filter(self) -> None:
        """Mengumpulkan nilai filter tab riwayat dan memancarkan history_filter_changed."""
        raw_status = self.history_status_combo.currentData()
        status_code = raw_status if isinstance(raw_status, str) else "ALL"
        filter_payload: HistoryFilterPayload = {
            "search": self.history_search_input.text().strip(),
            "payment_status": status_code,
            "date_from": self.history_date_from.date().toString("yyyy-MM-dd"),
            "date_to": self.history_date_to.date().toString("yyyy-MM-dd"),
        }
        self.history_filter_changed.emit(dict(filter_payload))

    def set_purchase_history(self, rows: list[PurchaseHistoryRow]) -> None:
        """Mengisi tabel riwayat pembelian dan memperbarui kartu KPI ringkasan.

        Args:
            rows: Daftar PurchaseHistoryRow yang diambil backend dari tabel purchases.
        """
        self.history_table.setRowCount(0)
        total_spend = 0
        total_debt = 0

        for row_idx, entry in enumerate(rows):
            self.history_table.insertRow(row_idx)
            total_spend += entry["total"]
            total_debt += entry["remaining_amount"]

            date_item = QTableWidgetItem(entry["purchase_date"])
            date_item.setForeground(QBrush(QColor("#94A3B8")))

            inv_item = QTableWidgetItem(entry["invoice_number"])
            inv_item.setForeground(QBrush(QColor("#38BDF8")))
            inv_font = inv_item.font()
            inv_font.setBold(True)
            inv_item.setFont(inv_font)

            sup_item = QTableWidgetItem(entry["supplier_name"])
            sup_item.setForeground(QBrush(QColor("#F8FAFC")))

            total_item = QTableWidgetItem(format_rupiah(entry["total"]))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            total_item.setForeground(QBrush(QColor("#F8FAFC")))
            total_font = total_item.font()
            total_font.setBold(True)
            total_item.setFont(total_font)

            paid_item = QTableWidgetItem(format_rupiah(entry["amount_paid"]))
            paid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            paid_item.setForeground(QBrush(QColor("#34D399")))

            rem_item = QTableWidgetItem(format_rupiah(entry["remaining_amount"]))
            rem_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            rem_color = "#FB7185" if entry["remaining_amount"] > 0 else "#64748B"
            rem_item.setForeground(QBrush(QColor(rem_color)))
            if entry["remaining_amount"] > 0:
                rem_font = rem_item.font()
                rem_font.setBold(True)
                rem_item.setFont(rem_font)

            due_text = entry["due_date"] if entry["due_date"] else "-"
            due_item = QTableWidgetItem(due_text)
            due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            due_item.setForeground(
                QBrush(QColor("#FBBF24" if entry["due_date"] else "#64748B"))
            )

            self.history_table.setItem(row_idx, 0, date_item)
            self.history_table.setItem(row_idx, 1, inv_item)
            self.history_table.setItem(row_idx, 2, sup_item)
            self.history_table.setItem(row_idx, 3, total_item)
            self.history_table.setItem(row_idx, 4, paid_item)
            self.history_table.setItem(row_idx, 5, rem_item)
            self.history_table.setCellWidget(
                row_idx,
                6,
                self._build_history_status_badge(entry["payment_status"]),
            )
            self.history_table.setItem(row_idx, 7, due_item)

            purchase_id = entry["id"]
            can_pay = entry["payment_status"] != "PAID" and entry["remaining_amount"] > 0
            action_cell = HistoryActionCellWidget(can_pay=can_pay, parent=self.history_table)
            action_cell.detail_clicked.connect(
                partial(self.history_detail_requested.emit, purchase_id)
            )
            action_cell.payment_clicked.connect(
                partial(self.history_payment_requested.emit, purchase_id)
            )
            action_cell.duplicate_clicked.connect(
                partial(self.history_duplicate_requested.emit, purchase_id)
            )
            self.history_table.setCellWidget(row_idx, 8, action_cell)

        self.kpi_total_notes_label.setText(f"{len(rows)} Nota")
        self.kpi_total_spend_label.setText(format_rupiah(total_spend))
        self.kpi_total_debt_label.setText(format_rupiah(total_debt))

    def _build_history_status_badge(self, payment_status: str) -> QWidget:
        """Membuat widget badge status pembayaran transparan untuk sel tabel riwayat.

        Args:
            payment_status: Nilai status berupa 'PAID', 'PARTIAL', atau 'UNPAID'.

        Returns:
            Widget kontainer transparan yang berisi QLabel badge status terpusat.
        """
        container = QWidget(self.history_table)
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel(container)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if payment_status == "PAID":
            badge.setText("LUNAS")
            badge.setObjectName("statusBadgePaid")
        elif payment_status == "PARTIAL":
            badge.setText("CICILAN")
            badge.setObjectName("statusBadgePartial")
        else:
            badge.setText("HUTANG")
            badge.setObjectName("statusBadgeUnpaid")

        layout.addWidget(badge)
        return container


class TambahStokWindow(FramelessMainWindow):
    """Jendela utama frameless untuk halaman Tambah Stok dan Kulakan.

    Attributes:
        page: Instance TambahStokPage yang ditempatkan di dalam area konten jendela.
    """

    def __init__(
        self,
        icon_config: TitleBarIconConfig | None = None,
        page_title: str = "Tambah Stok & Kulakan",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi TambahStokWindow menggunakan CustomTitleBar.

        Args:
            icon_config: Konfigurasi path ikon title bar; default menggunakan ICON_PATHS.
            page_title: Judul halaman yang tampil pada CustomTitleBar.
            parent: Widget induk opsional.
        """
        resolved_config = (
            icon_config
            if icon_config is not None
            else TitleBarIconConfig.from_dict(ICON_PATHS)
        )
        super().__init__(
            icon_config=resolved_config,
            page_title=page_title,
            parent=parent,
        )
        self.page = TambahStokPage(self)
        self.set_content_widget(self.page)
        self.page.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        QTimer.singleShot(50, self.page.focus_quick_search)