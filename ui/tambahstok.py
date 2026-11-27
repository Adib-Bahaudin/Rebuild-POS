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
    QByteArray,
    QDate,
    QDateTime,
    QEasingCurve,
    QLocale,
    QPropertyAnimation,
    QSize,
    QStringListModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFrame,
    QGraphicsOpacityEffect,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.customwindowtitlebar import (
    ICON_PATHS,
    FramelessMainWindow,
    TitleBarIconConfig,
)


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
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' "
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
    "<svg viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' "
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


def format_rupiah(amount: int | float) -> str:
    """Memformat angka nominal menjadi string mata uang Rupiah Indonesia.

    Args:
        amount: Nilai nominal angka bulat atau desimal.

    Returns:
        String terformat dalam gaya Rupiah, misalnya 'Rp 125.000'.
    """
    rounded = int(round(amount))
    sign = "-" if rounded < 0 else ""
    formatted = f"{abs(rounded):,}".replace(",", ".")
    return f"{sign}Rp {formatted}"


def format_quantity(value: float) -> str:
    """Memformat angka kuantitas agar ringkas tanpa nol desimal berlebih.

    Args:
        value: Nilai kuantitas dalam tipe float.

    Returns:
        String kuantitas terformat dengan pemisah ribuan titik.
    """
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}".replace(",", ".")
    formatted = f"{value:,.2f}".rstrip("0").rstrip(".")
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def build_svg_icon(svg_markup: str, color: str, size: int = 16) -> QIcon:
    """Merender markup SVG inline menjadi objek QIcon tajam berkualitas vektor.

    Args:
        svg_markup: Template string SVG yang mengandung placeholder '{color}'.
        color: Kode warna heksadesimal untuk stroke atau fill ikon.
        size: Dimensi persegi piksel untuk rendering ikon.

    Returns:
        Objek QIcon siap digunakan pada tombol atau tab.
    """
    rendered_svg = svg_markup.replace("{color}", color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(rendered_svg))
    pixmap = QPixmap(QSize(size * 2, size * 2))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return QIcon(pixmap)


class StatusBannerWidget(QFrame):
    """Banner notifikasi inline dengan animasi fade-in dan tombol tutup.

    Attributes:
        dismissed: Sinyal yang dipancarkan saat banner ditutup pengguna.
    """

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi StatusBannerWidget dalam keadaan tersembunyi.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("statusBanner")
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide_banner)

        self._message_label = QLabel("", self)
        self._message_label.setWordWrap(True)
        self._close_button = QPushButton("Tutup", self)
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close_button.clicked.connect(self.hide_banner)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(self._message_label, 1)
        layout.addWidget(self._close_button, 0)

        self.setVisible(False)

    def show_message(
        self,
        message: str,
        level: str = "info",
        duration_ms: int = 4500,
    ) -> None:
        """Menampilkan pesan notifikasi dengan warna sesuai tingkat kepentingan.

        Args:
            message: Teks pesan yang akan ditampilkan.
            level: Tingkat status berupa 'info', 'success', 'warning', atau 'error'.
            duration_ms: Lama tampil otomatis dalam milidetik; 0 agar tidak hilang otomatis.
        """
        palettes: dict[str, tuple[str, str, str]] = {
            "info": ("#1E2A3A", "#89B4FA", "#DBEAFE"),
            "success": ("#17322A", "#10B981", "#D1FAE5"),
            "warning": ("#362B18", "#F59E0B", "#FEF3C7"),
            "error": ("#3A1D28", "#F38BA8", "#FFE4E6"),
        }
        bg_color, border_color, text_color = palettes.get(level, palettes["info"])
        self.setStyleSheet(
            f"""
            QFrame#statusBanner {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#statusBanner QLabel {{
                color: {text_color};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QFrame#statusBanner QPushButton {{
                background: transparent;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QFrame#statusBanner QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
            }}
            """
        )
        self._message_label.setText(message)
        self.setVisible(True)
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

        self._auto_hide_timer.stop()
        if duration_ms > 0:
            self._auto_hide_timer.start(duration_ms)

    def hide_banner(self) -> None:
        """Menyembunyikan banner notifikasi dan memancarkan sinyal dismissed."""
        self._auto_hide_timer.stop()
        self.setVisible(False)
        self.dismissed.emit()


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


class KeyboardUnitComboBox(QComboBox):
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        name_label = QLabel(name, self)
        name_label.setObjectName("cellItemName")

        meta_text = f"{sku}  •  Stok: {format_quantity(current_stock)} {base_unit_symbol}"
        meta_label = QLabel(meta_text, self)
        meta_label.setObjectName("cellItemMeta")

        layout.addWidget(name_label)
        layout.addWidget(meta_label)


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
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)

        self.subtotal_spin = KeyboardDoubleSpinBox(
            decimals=0,
            minimum=0.0,
            maximum=2_000_000_000.0,
            prefix="Rp ",
            parent=self,
        )
        self.subtotal_spin.setObjectName("gridSpinBox")
        self.subtotal_spin.setFixedHeight(26)

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
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        price_button = QPushButton(self)
        price_button.setObjectName("iconActionNeutral")
        price_button.setIcon(build_svg_icon(SVG_TAG, "#89B4FA", 15))
        price_button.setIconSize(QSize(15, 15))
        price_button.setFixedSize(28, 28)
        price_button.setToolTip("Cek / Ubah Harga Jual Barang")
        price_button.setCursor(Qt.CursorShape.PointingHandCursor)
        price_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        price_button.clicked.connect(self.edit_price_clicked.emit)

        delete_button = QPushButton(self)
        delete_button.setObjectName("iconActionDanger")
        delete_button.setIcon(build_svg_icon(SVG_TRASH, "#F38BA8", 15))
        delete_button.setIconSize(QSize(15, 15))
        delete_button.setFixedSize(28, 28)
        delete_button.setToolTip("Hapus Baris (Ctrl+Del)")
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
        detail_btn.setIcon(build_svg_icon(SVG_EYE, "#CDD6F4", 13))
        detail_btn.setIconSize(QSize(13, 13))
        detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        detail_btn.clicked.connect(self.detail_clicked.emit)

        pay_btn = QPushButton("Bayar", self)
        pay_btn.setObjectName("tablePillSuccess")
        pay_btn.setIcon(build_svg_icon(SVG_WALLET, "#A6E3A1", 13))
        pay_btn.setIconSize(QSize(13, 13))
        pay_btn.setEnabled(can_pay)
        pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pay_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pay_btn.clicked.connect(self.payment_clicked.emit)

        repeat_btn = QPushButton("Ulang", self)
        repeat_btn.setObjectName("tablePillAccent")
        repeat_btn.setIcon(build_svg_icon(SVG_REPEAT, "#89B4FA", 13))
        repeat_btn.setIconSize(QSize(13, 13))
        repeat_btn.setToolTip("Salin daftar barang nota ini ke keranjang")
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
        """Menyusun tata letak utama halaman berupa banner status dan tab kerja."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(8)

        self.status_banner = StatusBannerWidget(self)
        root_layout.addWidget(self.status_banner)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mainTabs")
        self.tab_widget.setDocumentMode(False)

        tab_bar = self.tab_widget.tabBar()
        if tab_bar is not None:
            tab_bar.setDrawBase(False)

        self._purchase_tab = QWidget(self.tab_widget)
        self._history_tab = QWidget(self.tab_widget)

        self._build_purchase_tab()
        self._build_history_tab()

        self.tab_widget.addTab(
            self._purchase_tab,
            build_svg_icon(SVG_LAYERS, "#89B4FA", 15),
            "Belanja / Kulakan (Grid Cepat)",
        )
        self.tab_widget.addTab(
            self._history_tab,
            build_svg_icon(SVG_WALLET, "#A6E3A1", 15),
            "Riwayat && Hutang Supplier",
        )

        root_layout.addWidget(self.tab_widget, 1)

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
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(12)
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
        supplier_row.setSpacing(6)

        self.supplier_combo = QComboBox(card)
        self.supplier_combo.setObjectName("headerCombo")
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.supplier_combo.addItem("-- Tanpa Supplier (Belanja Umum) --", None)
        supplier_line = self.supplier_combo.lineEdit()
        if supplier_line is not None:
            supplier_line.setPlaceholderText("Cari atau pilih supplier...")
        supplier_completer = self.supplier_combo.completer()
        if supplier_completer is not None:
            supplier_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            supplier_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.add_supplier_btn = QPushButton(card)
        self.add_supplier_btn.setObjectName("compactAccentButton")
        self.add_supplier_btn.setIcon(build_svg_icon(SVG_PLUS, "#89B4FA", 14))
        self.add_supplier_btn.setIconSize(QSize(14, 14))
        self.add_supplier_btn.setFixedSize(32, 32)
        self.add_supplier_btn.setToolTip("Tambah Supplier Baru")
        self.add_supplier_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        supplier_row.addWidget(self.supplier_combo, 1)
        supplier_row.addWidget(self.add_supplier_btn)

        invoice_row = QHBoxLayout()
        invoice_row.setContentsMargins(0, 0, 0, 0)
        invoice_row.setSpacing(6)

        self.invoice_input = QLineEdit(card)
        self.invoice_input.setObjectName("headerInput")
        self.invoice_input.setPlaceholderText("Contoh: INV-20261127-001")
        self.invoice_input.setText(self._build_default_invoice_number())

        self.auto_invoice_btn = QPushButton("Auto", card)
        self.auto_invoice_btn.setObjectName("compactSecondaryButton")
        self.auto_invoice_btn.setIcon(build_svg_icon(SVG_SPARKLE, "#94E2D5", 13))
        self.auto_invoice_btn.setIconSize(QSize(13, 13))
        self.auto_invoice_btn.setFixedHeight(32)
        self.auto_invoice_btn.setToolTip("Buat Nomor Nota Otomatis")
        self.auto_invoice_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        invoice_row.addWidget(self.invoice_input, 1)
        invoice_row.addWidget(self.auto_invoice_btn)

        self.purchase_date_edit = QDateTimeEdit(QDateTime.currentDateTime(), card)
        self.purchase_date_edit.setObjectName("headerDate")
        self.purchase_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.purchase_date_edit.setCalendarPopup(True)
        self.purchase_date_edit.setFixedHeight(32)

        self.notes_input = QLineEdit(card)
        self.notes_input.setObjectName("headerInput")
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
        outer.setContentsMargins(12, 9, 12, 8)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        search_icon_label = QLabel(bar)
        search_icon_label.setPixmap(build_svg_icon(SVG_SEARCH, "#89B4FA", 18).pixmap(18, 18))
        search_icon_label.setFixedSize(22, 22)
        search_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.quick_search_input = QuickSearchLineEdit(bar)
        self.quick_search_input.setObjectName("quickSearchInput")
        self.quick_search_input.setPlaceholderText(
            "Scan barcode atau ketik SKU / nama barang, lalu tekan Enter untuk masuk ke grid..."
        )
        self.quick_search_input.setFixedHeight(36)
        self.quick_search_input.setCompleter(self._search_completer)

        self.quick_add_btn = QPushButton("Tambah", bar)
        self.quick_add_btn.setObjectName("primarySmallButton")
        self.quick_add_btn.setIcon(build_svg_icon(SVG_PLUS, "#11111B", 14))
        self.quick_add_btn.setIconSize(QSize(14, 14))
        self.quick_add_btn.setFixedHeight(36)
        self.quick_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.bulk_picker_btn = QPushButton("Pilih Banyak (F4)", bar)
        self.bulk_picker_btn.setObjectName("toolbarButton")
        self.bulk_picker_btn.setIcon(build_svg_icon(SVG_LAYERS, "#94E2D5", 14))
        self.bulk_picker_btn.setIconSize(QSize(14, 14))
        self.bulk_picker_btn.setFixedHeight(36)
        self.bulk_picker_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.repeat_order_btn = QPushButton("Ulang Nota", bar)
        self.repeat_order_btn.setObjectName("toolbarButton")
        self.repeat_order_btn.setIcon(build_svg_icon(SVG_REPEAT, "#CBA6F7", 14))
        self.repeat_order_btn.setIconSize(QSize(14, 14))
        self.repeat_order_btn.setFixedHeight(36)
        self.repeat_order_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.import_csv_btn = QPushButton("Import CSV", bar)
        self.import_csv_btn.setObjectName("toolbarButton")
        self.import_csv_btn.setIcon(build_svg_icon(SVG_UPLOAD, "#F9E2AF", 14))
        self.import_csv_btn.setIconSize(QSize(14, 14))
        self.import_csv_btn.setFixedHeight(36)
        self.import_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.clear_cart_btn = QPushButton("Kosongkan", bar)
        self.clear_cart_btn.setObjectName("dangerGhostButton")
        self.clear_cart_btn.setIcon(build_svg_icon(SVG_TRASH, "#F38BA8", 14))
        self.clear_cart_btn.setIconSize(QSize(14, 14))
        self.clear_cart_btn.setFixedHeight(36)
        self.clear_cart_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        top_row.addWidget(search_icon_label)
        top_row.addWidget(self.quick_search_input, 1)
        top_row.addWidget(self.quick_add_btn)
        top_row.addWidget(self.bulk_picker_btn)
        top_row.addWidget(self.repeat_order_btn)
        top_row.addWidget(self.import_csv_btn)
        top_row.addWidget(self.clear_cart_btn)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(2, 0, 2, 0)
        hint_row.setSpacing(14)

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
            v_header.setDefaultSectionSize(52)

        h_header = self.cart_table.horizontalHeader()
        if h_header is not None:
            h_header.setHighlightSections(False)
            h_header.setSectionResizeMode(self.COL_NO, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_ITEM, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(self.COL_UNIT, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_QTY, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_BASE_QTY, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_UNIT_COST, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_SUBTOTAL, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.Fixed)

        self.cart_table.setColumnWidth(self.COL_NO, 38)
        self.cart_table.setColumnWidth(self.COL_UNIT, 148)
        self.cart_table.setColumnWidth(self.COL_QTY, 102)
        self.cart_table.setColumnWidth(self.COL_BASE_QTY, 128)
        self.cart_table.setColumnWidth(self.COL_UNIT_COST, 152)
        self.cart_table.setColumnWidth(self.COL_SUBTOTAL, 174)
        self.cart_table.setColumnWidth(self.COL_ACTION, 82)
        return self.cart_table

    def _create_footer_panel(self) -> QFrame:
        """Membuat panel footer ringkasan nominal, pembayaran, hutang, dan tombol simpan.

        Returns:
            Widget QFrame berisi ringkasan transaksi dan kontrol eksekusi.
        """
        footer = QFrame(self._purchase_tab)
        footer.setObjectName("sectionCard")
        outer = QVBoxLayout(footer)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(16)

        summary_card = QFrame(footer)
        summary_card.setObjectName("subCard")
        summary_grid = QGridLayout(summary_card)
        summary_grid.setContentsMargins(12, 10, 12, 10)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(6)

        self.item_count_label = QLabel("0 Jenis Barang  •  0 Total Qty Masuk", summary_card)
        self.item_count_label.setObjectName("summaryMetaLabel")

        subtotal_title = QLabel("Subtotal Belanja", summary_card)
        subtotal_title.setObjectName("fieldLabel")
        self.subtotal_value_label = QLabel("Rp 0", summary_card)
        self.subtotal_value_label.setObjectName("summaryValueLabel")
        self.subtotal_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        discount_title = QLabel("Diskon Nota", summary_card)
        discount_title.setObjectName("fieldLabel")
        self.discount_spin = CurrencySpinBox(parent=summary_card)
        self.discount_spin.setObjectName("footerSpinBox")
        self.discount_spin.setFixedHeight(30)

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

        payment_card = QFrame(footer)
        payment_card.setObjectName("subCard")
        pay_grid = QGridLayout(payment_card)
        pay_grid.setContentsMargins(12, 10, 12, 10)
        pay_grid.setHorizontalSpacing(12)
        pay_grid.setVerticalSpacing(6)

        method_label = QLabel("Metode Pembayaran", payment_card)
        method_label.setObjectName("fieldLabel")
        self.payment_method_combo = QComboBox(payment_card)
        self.payment_method_combo.setObjectName("headerCombo")
        self.payment_method_combo.addItems(list(self.PAYMENT_METHODS))
        self.payment_method_combo.setFixedHeight(30)

        quick_pay_row = QHBoxLayout()
        quick_pay_row.setContentsMargins(0, 0, 0, 0)
        quick_pay_row.setSpacing(6)

        self.btn_pay_full = QPushButton("Lunas (F8)", payment_card)
        self.btn_pay_full.setObjectName("quickPaySuccess")
        self.btn_pay_full.setFixedHeight(28)
        self.btn_pay_full.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_pay_partial = QPushButton("DP / Cicil", payment_card)
        self.btn_pay_partial.setObjectName("quickPayWarning")
        self.btn_pay_partial.setFixedHeight(28)
        self.btn_pay_partial.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_pay_unpaid = QPushButton("Tempo", payment_card)
        self.btn_pay_unpaid.setObjectName("quickPayDanger")
        self.btn_pay_unpaid.setFixedHeight(28)
        self.btn_pay_unpaid.setCursor(Qt.CursorShape.PointingHandCursor)

        quick_pay_row.addWidget(self.btn_pay_full)
        quick_pay_row.addWidget(self.btn_pay_partial)
        quick_pay_row.addWidget(self.btn_pay_unpaid)

        paid_label = QLabel("Nominal Dibayar", payment_card)
        paid_label.setObjectName("fieldLabel")
        self.amount_paid_spin = CurrencySpinBox(parent=payment_card)
        self.amount_paid_spin.setObjectName("footerSpinBox")
        self.amount_paid_spin.setFixedHeight(30)

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
        self.due_date_edit = QDateEdit(QDate.currentDate().addDays(14), payment_card)
        self.due_date_edit.setObjectName("headerDate")
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setFixedHeight(30)

        ref_label = QLabel("No. Referensi", payment_card)
        ref_label.setObjectName("fieldLabel")
        self.reference_input = QLineEdit(payment_card)
        self.reference_input.setObjectName("headerInput")
        self.reference_input.setFixedHeight(30)
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

        self.reset_form_btn = QPushButton("Reset Form (Ctrl+R)", footer)
        self.reset_form_btn.setObjectName("toolbarButton")
        self.reset_form_btn.setIcon(build_svg_icon(SVG_REFRESH, "#A6ADC8", 14))
        self.reset_form_btn.setIconSize(QSize(14, 14))
        self.reset_form_btn.setFixedHeight(38)
        self.reset_form_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.save_draft_btn = QPushButton("Simpan Draft (F9)", footer)
        self.save_draft_btn.setObjectName("secondaryActionButton")
        self.save_draft_btn.setIcon(build_svg_icon(SVG_SAVE, "#CDD6F4", 15))
        self.save_draft_btn.setIconSize(QSize(15, 15))
        self.save_draft_btn.setFixedHeight(38)
        self.save_draft_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.submit_btn = QPushButton("Simpan & Tambah Stok (F10)", footer)
        self.submit_btn.setObjectName("primaryActionButton")
        self.submit_btn.setIcon(build_svg_icon(SVG_CHECK, "#11111B", 16))
        self.submit_btn.setIconSize(QSize(16, 16))
        self.submit_btn.setFixedHeight(38)
        self.submit_btn.setMinimumWidth(230)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        action_row.addWidget(self.reset_form_btn)
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
        kpi_row.setSpacing(10)

        self.kpi_total_notes_label = self._create_kpi_card(
            kpi_row,
            "Total Nota Kulakan",
            "0 Nota",
            "#89B4FA",
        )
        self.kpi_total_spend_label = self._create_kpi_card(
            kpi_row,
            "Total Nilai Pembelian",
            "Rp 0",
            "#A6E3A1",
        )
        self.kpi_total_debt_label = self._create_kpi_card(
            kpi_row,
            "Total Sisa Hutang Supplier",
            "Rp 0",
            "#F38BA8",
        )
        layout.addLayout(kpi_row)

        filter_card = QFrame(self._history_tab)
        filter_card.setObjectName("sectionCard")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(12, 8, 12, 8)
        filter_layout.setSpacing(8)

        self.history_search_input = QLineEdit(filter_card)
        self.history_search_input.setObjectName("headerInput")
        self.history_search_input.setPlaceholderText("Cari nomor faktur atau nama supplier...")
        self.history_search_input.setFixedHeight(32)

        self.history_status_combo = QComboBox(filter_card)
        self.history_status_combo.setObjectName("headerCombo")
        self.history_status_combo.setFixedHeight(32)
        self.history_status_combo.setMinimumWidth(155)
        self.history_status_combo.addItem("Semua Status", "ALL")
        self.history_status_combo.addItem("Belum Lunas (UNPAID)", "UNPAID")
        self.history_status_combo.addItem("Cicilan (PARTIAL)", "PARTIAL")
        self.history_status_combo.addItem("Lunas (PAID)", "PAID")

        self.history_date_from = QDateEdit(QDate.currentDate().addMonths(-1), filter_card)
        self.history_date_from.setObjectName("headerDate")
        self.history_date_from.setDisplayFormat("yyyy-MM-dd")
        self.history_date_from.setCalendarPopup(True)
        self.history_date_from.setFixedHeight(32)

        date_sep_label = QLabel("s/d", filter_card)
        date_sep_label.setObjectName("fieldLabel")

        self.history_date_to = QDateEdit(QDate.currentDate(), filter_card)
        self.history_date_to.setObjectName("headerDate")
        self.history_date_to.setDisplayFormat("yyyy-MM-dd")
        self.history_date_to.setCalendarPopup(True)
        self.history_date_to.setFixedHeight(32)

        self.history_refresh_btn = QPushButton("Muat Ulang", filter_card)
        self.history_refresh_btn.setObjectName("toolbarButton")
        self.history_refresh_btn.setIcon(build_svg_icon(SVG_REFRESH, "#89B4FA", 14))
        self.history_refresh_btn.setIconSize(QSize(14, 14))
        self.history_refresh_btn.setFixedHeight(32)
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
            hv_header.setDefaultSectionSize(44)

        hh_header = self.history_table.horizontalHeader()
        if hh_header is not None:
            hh_header.setHighlightSections(False)
            hh_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            hh_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
            hh_header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)

        self.history_table.setColumnWidth(0, 132)
        self.history_table.setColumnWidth(1, 152)
        self.history_table.setColumnWidth(3, 122)
        self.history_table.setColumnWidth(4, 122)
        self.history_table.setColumnWidth(5, 122)
        self.history_table.setColumnWidth(6, 108)
        self.history_table.setColumnWidth(7, 105)
        self.history_table.setColumnWidth(8, 215)

        layout.addWidget(self.history_table, 1)

    def _create_kpi_card(
        self,
        parent_layout: QHBoxLayout,
        title: str,
        initial_value: str,
        accent_color: str,
    ) -> QLabel:
        """Membuat kartu KPI ringkas untuk bagian atas tab riwayat kulakan.

        Args:
            parent_layout: Layout horizontal tempat kartu akan ditempatkan.
            title: Label judul metrik KPI.
            initial_value: Nilai tampilan awal KPI.
            accent_color: Warna garis aksen kiri dan nilai KPI.

        Returns:
            Widget QLabel nilai KPI yang dapat diperbarui secara dinamis.
        """
        card = QFrame(self._history_tab)
        card.setObjectName("kpiCard")
        card.setStyleSheet(
            f"""
            QFrame#kpiCard {{
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-left: 3px solid {accent_color};
                border-radius: 8px;
            }}
            """
        )
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(12, 8, 12, 8)
        vbox.setSpacing(2)

        title_lbl = QLabel(title, card)
        title_lbl.setObjectName("fieldLabel")

        value_lbl = QLabel(initial_value, card)
        value_lbl.setStyleSheet(
            f"color: {accent_color}; font-size: 16px; font-weight: 700; background: transparent;"
        )

        vbox.addWidget(title_lbl)
        vbox.addWidget(value_lbl)
        parent_layout.addWidget(card, 1)
        return value_lbl

    def _apply_styles(self) -> None:
        """Menerapkan stylesheet QSS tema gelap modern ke seluruh komponen halaman."""
        self.setStyleSheet(
            """
            QWidget#TambahStokPage {
                background-color: #11111B;
                color: #CDD6F4;
                font-family: "Segoe UI", "Inter", sans-serif;
            }
            QTabWidget#mainTabs::pane {
                border: none;
                background: transparent;
                top: 0px;
            }
            QTabWidget#mainTabs::tab-bar {
                alignment: left;
                border: none;
            }
            QTabWidget#mainTabs QTabBar {
                background: transparent;
                border: none;
            }
            QTabWidget#mainTabs QTabBar::tab {
                background-color: #181825;
                color: #A6ADC8;
                border: 1px solid #313244;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 18px;
                margin-right: 4px;
                font-size: 13px;
                font-weight: 600;
            }
            QTabWidget#mainTabs QTabBar::tab:selected {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border-color: #45475A;
                border-bottom: 2px solid #89B4FA;
            }
            QTabWidget#mainTabs QTabBar::tab:hover:!selected {
                background-color: #232336;
                color: #CDD6F4;
            }
            QFrame#sectionCard, QFrame#quickAddCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QFrame#quickAddCard {
                border-color: #3B4261;
            }
            QFrame#subCard {
                background-color: #161622;
                border: 1px solid #2A2A40;
                border-radius: 8px;
            }
            QLabel#fieldLabel {
                color: #A6ADC8;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#shortcutHint {
                color: #7F849C;
                font-size: 11px;
                font-weight: 500;
                background: transparent;
            }
            QLabel#summaryMetaLabel {
                color: #94E2D5;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#summaryValueLabel {
                color: #CDD6F4;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#grandTotalTitle {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#grandTotalValue {
                color: #A6E3A1;
                font-size: 20px;
                font-weight: 800;
                background: transparent;
            }
            QLabel#remainingValueLabel {
                color: #F9E2AF;
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#statusBadgePaid {
                background-color: rgba(166, 227, 161, 0.16);
                color: #A6E3A1;
                border: 1px solid rgba(166, 227, 161, 0.45);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#statusBadgePartial {
                background-color: rgba(249, 226, 175, 0.16);
                color: #F9E2AF;
                border: 1px solid rgba(249, 226, 175, 0.45);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#statusBadgeUnpaid {
                background-color: rgba(243, 139, 168, 0.16);
                color: #F38BA8;
                border: 1px solid rgba(243, 139, 168, 0.45);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#cellItemName {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#cellItemMeta {
                color: #7F849C;
                font-size: 11px;
                background: transparent;
            }
            QLabel#cellHppPreview {
                color: #94E2D5;
                font-size: 10px;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit#headerInput,
            QLineEdit#quickSearchInput,
            QComboBox#headerCombo,
            QDateEdit#headerDate,
            QDateTimeEdit#headerDate,
            QSpinBox#footerSpinBox {
                background-color: #161622;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 12px;
                selection-background-color: #3B82F6;
            }
            QLineEdit#quickSearchInput {
                background-color: #11111B;
                border: 1px solid #45475A;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit#headerInput:focus,
            QLineEdit#quickSearchInput:focus,
            QComboBox#headerCombo:focus,
            QDateEdit#headerDate:focus,
            QDateTimeEdit#headerDate:focus,
            QSpinBox#footerSpinBox:focus {
                border: 1px solid #89B4FA;
                background-color: #141421;
            }
            QLineEdit#headerInput:disabled,
            QDateEdit#headerDate:disabled {
                background-color: #13131E;
                color: #585B70;
                border-color: #252538;
            }
            QComboBox#headerCombo::drop-down,
            QComboBox#gridCombo::drop-down,
            QDateEdit#headerDate::drop-down,
            QDateTimeEdit#headerDate::drop-down {
                border: none;
                width: 22px;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 6px;
                selection-background-color: #313244;
                selection-color: #89B4FA;
                padding: 4px;
                outline: none;
            }
            QDoubleSpinBox#gridSpinBox,
            QComboBox#gridCombo {
                background-color: #141421;
                color: #CDD6F4;
                border: 1px solid #2F3147;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
                font-weight: 600;
                selection-background-color: #3B82F6;
            }
            QDoubleSpinBox#gridSpinBox:focus,
            QComboBox#gridCombo:focus {
                border: 1px solid #89B4FA;
                background-color: #181A2C;
            }
            QTableWidget#cartTable {
                background-color: #161622;
                alternate-background-color: #1A1A29;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 10px;
                outline: none;
                selection-background-color: #25283D;
                selection-color: #CDD6F4;
            }
            QTableWidget#cartTable::item {
                border-bottom: 1px solid #242538;
                padding: 4px;
            }
            QTableWidget#cartTable QHeaderView::section {
                background-color: #1E1E2E;
                color: #A6ADC8;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 8px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#primaryActionButton {
                background-color: #A6E3A1;
                color: #11111B;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#primaryActionButton:hover {
                background-color: #B8EBB3;
            }
            QPushButton#primaryActionButton:pressed {
                background-color: #8DD587;
            }
            QPushButton#primarySmallButton {
                background-color: #89B4FA;
                color: #11111B;
                border: none;
                border-radius: 7px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#primarySmallButton:hover {
                background-color: #A0C4FF;
            }
            QPushButton#secondaryActionButton {
                background-color: #2A2A40;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#secondaryActionButton:hover {
                background-color: #34344E;
                border-color: #585B70;
            }
            QPushButton#toolbarButton,
            QPushButton#compactSecondaryButton,
            QPushButton#compactAccentButton {
                background-color: #161622;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#toolbarButton:hover,
            QPushButton#compactSecondaryButton:hover,
            QPushButton#compactAccentButton:hover {
                background-color: #24263B;
                border-color: #89B4FA;
            }
            QPushButton#dangerGhostButton {
                background-color: transparent;
                color: #F38BA8;
                border: 1px solid rgba(243, 139, 168, 0.35);
                border-radius: 7px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#dangerGhostButton:hover {
                background-color: rgba(243, 139, 168, 0.12);
                border-color: #F38BA8;
            }
            QPushButton#quickPaySuccess {
                background-color: rgba(166, 227, 161, 0.14);
                color: #A6E3A1;
                border: 1px solid rgba(166, 227, 161, 0.35);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#quickPaySuccess:hover {
                background-color: rgba(166, 227, 161, 0.26);
            }
            QPushButton#quickPayWarning {
                background-color: rgba(249, 226, 175, 0.14);
                color: #F9E2AF;
                border: 1px solid rgba(249, 226, 175, 0.35);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#quickPayWarning:hover {
                background-color: rgba(249, 226, 175, 0.26);
            }
            QPushButton#quickPayDanger {
                background-color: rgba(243, 139, 168, 0.14);
                color: #F38BA8;
                border: 1px solid rgba(243, 139, 168, 0.35);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#quickPayDanger:hover {
                background-color: rgba(243, 139, 168, 0.26);
            }
            QPushButton#iconActionNeutral,
            QPushButton#iconActionDanger {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            QPushButton#iconActionNeutral:hover {
                background-color: rgba(137, 180, 250, 0.15);
                border-color: rgba(137, 180, 250, 0.4);
            }
            QPushButton#iconActionDanger:hover {
                background-color: rgba(243, 139, 168, 0.15);
                border-color: rgba(243, 139, 168, 0.4);
            }
            QPushButton#tablePillNeutral,
            QPushButton#tablePillSuccess,
            QPushButton#tablePillAccent {
                background-color: transparent;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#tablePillNeutral {
                color: #CDD6F4;
                border: 1px solid #45475A;
            }
            QPushButton#tablePillNeutral:hover {
                background-color: rgba(205, 214, 244, 0.1);
            }
            QPushButton#tablePillSuccess {
                color: #A6E3A1;
                border: 1px solid rgba(166, 227, 161, 0.45);
            }
            QPushButton#tablePillSuccess:hover {
                background-color: rgba(166, 227, 161, 0.14);
            }
            QPushButton#tablePillSuccess:disabled {
                color: #585B70;
                border-color: #2A2A40;
            }
            QPushButton#tablePillAccent {
                color: #89B4FA;
                border: 1px solid rgba(137, 180, 250, 0.45);
            }
            QPushButton#tablePillAccent:hover {
                background-color: rgba(137, 180, 250, 0.14);
            }
            QScrollBar:vertical {
                background: #141421;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #313244;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #45475A;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
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
        """Memindahkan fokus kursor ke kotak pencarian cepat pada Tab 1."""
        self.tab_widget.setCurrentIndex(0)
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
        """Menampilkan notifikasi banner inline tanpa menghalangi alur ketik pengguna.

        Args:
            message: Pesan informasi, keberhasilan, peringatan, atau galat.
            level: Tingkat pesan berupa 'info', 'success', 'warning', atau 'error'.
            duration_ms: Durasi tampil otomatis dalam milidetik.
        """
        self.status_banner.show_message(message, level=level, duration_ms=duration_ms)

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
        unit_combo.setFixedHeight(32)
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
        qty_spin.setFixedHeight(32)
        qty_spin.setValue(max(0.01, quantity))
        self.cart_table.setCellWidget(row, self.COL_QTY, qty_spin)

        base_qty_item = QTableWidgetItem("")
        base_qty_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
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
        cost_spin.setFixedHeight(32)
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

        self.tab_widget.setCurrentIndex(0)
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
            inv_item = QTableWidgetItem(entry["invoice_number"])
            sup_item = QTableWidgetItem(entry["supplier_name"])

            total_item = QTableWidgetItem(format_rupiah(entry["total"]))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            paid_item = QTableWidgetItem(format_rupiah(entry["amount_paid"]))
            paid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            rem_item = QTableWidgetItem(format_rupiah(entry["remaining_amount"]))
            rem_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            due_text = entry["due_date"] if entry["due_date"] else "-"
            due_item = QTableWidgetItem(due_text)
            due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

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
