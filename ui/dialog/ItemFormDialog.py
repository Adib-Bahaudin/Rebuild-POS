"""Modul dialog formulir tambah dan edit barang fisik berbasis CustomDialog.

Modul ini menyediakan antarmuka modal ringkas untuk mengelola data dasar
barang, variasi multi-satuan jual (item_units), serta input stok awal opsional
untuk layer FIFO tanpa menyertakan logika query basis data secara langsung.

Tampilan dibangun ulang dengan ikon SVG inline, kontrol toggle/radio yang
digambar kustom, serta palet warna yang lebih hidup. Logika validasi dan
kontrak payload tidak berubah.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QEvent,
    QLocale,
    QPoint,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import (
    ItemEditData,
    ItemFormPayload,
    ItemUnitPayload,
    UnitRecord,
)
from ui.manajemenproduk import CategoryOption
from util.customdialog import CustomDialog
from util.helper.dialog_form_helper import show_inline_error


# ---------------------------------------------------------------------------
# Palet warna
# ---------------------------------------------------------------------------
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
    BLUE_STRONG = "#3B82F6"
    MAUVE = "#CBA6F7"
    GREEN = "#A6E3A1"
    PEACH = "#FAB387"
    PINK = "#F38BA8"
    TEAL = "#94E2D5"
    RED = "#EF4444"


def _rgba(hex_color: str, alpha: float) -> str:
    """Mengubah warna hex menjadi notasi rgba() QSS.

    Args:
        hex_color: Warna dalam format #RRGGBB.
        alpha: Opasitas 0.0 hingga 1.0.

    Returns:
        String warna rgba yang dapat dipakai di QSS.
    """
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.2f})"


def _mix(c1: QColor, c2: QColor, t: float) -> QColor:
    """Menginterpolasi dua warna secara linear.

    Args:
        c1: Warna awal.
        c2: Warna akhir.
        t: Faktor interpolasi 0.0 hingga 1.0.

    Returns:
        Warna hasil campuran.
    """
    t = max(0.0, min(1.0, t))
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue() + (c2.blue() - c1.blue()) * t),
        round(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


# ---------------------------------------------------------------------------
# Ikon SVG inline
# ---------------------------------------------------------------------------
_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS: dict[str, str] = {
    "package": (
        '<path d="M21 8 12 3 3 8l9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>'
        '<path d="M12 13v8"/><path d="m7.5 5.5 9 5"/>'
    ),
    "edit_box": (
        '<path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>'
    ),
    "tag": (
        '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/>'
        '<circle cx="7.5" cy="7.5" r="1.5"/>'
    ),
    "layers": (
        '<path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="m2 17 10 5 10-5"/>'
        '<path d="m2 12 10 5 10-5"/>'
    ),
    "archive": (
        '<rect x="3" y="4" width="18" height="4" rx="1"/>'
        '<path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/>'
    ),
    "barcode": (
        '<path d="M4 6v12"/><path d="M7.5 6v12"/><path d="M10.5 6v12"/>'
        '<path d="M14 6v12"/><path d="M17 6v12"/><path d="M20 6v12"/>'
    ),
    "type": '<path d="M4 7V5h16v2"/><path d="M12 5v14"/><path d="M9 19h6"/>',
    "note": (
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'
    ),
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "trash": (
        '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "chevron_down": '<path d="m6 9 6 6 6-6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "coins": (
        '<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1 1 10.3 18"/>'
        '<path d="M7 6h1v4"/>'
    ),
}


_ID_LOCALE = QLocale(QLocale.Language.Indonesian, QLocale.Country.Indonesia)


def _svg_markup(name: str, color: str, stroke: float = 2.0) -> str:
    """Menyusun markup SVG lengkap untuk ikon tertentu.

    Args:
        name: Kunci ikon pada kamus _ICONS.
        color: Warna goresan ikon.
        stroke: Ketebalan goresan.

    Returns:
        String markup SVG.
    """
    return _SVG_TEMPLATE.format(color=color, stroke=stroke, body=_ICONS[name])


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
    renderer = QSvgRenderer(QByteArray(_svg_markup(name, color, stroke).encode("utf-8")))
    dpr = 2.0
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def _svg_icon(
    name: str,
    color: str,
    size: int = 16,
    *,
    disabled_color: str | None = None,
) -> QIcon:
    """Membuat QIcon dari ikon SVG inline.

    Args:
        name: Kunci ikon pada kamus _ICONS.
        color: Warna normal ikon.
        size: Ukuran ikon.
        disabled_color: Warna ikon saat widget nonaktif (opsional).

    Returns:
        Objek QIcon siap pakai.
    """
    icon = QIcon()
    icon.addPixmap(_svg_pixmap(name, size, color), QIcon.Mode.Normal)
    if disabled_color is not None:
        icon.addPixmap(_svg_pixmap(name, size, disabled_color), QIcon.Mode.Disabled)
    return icon


def _svg_file(name: str, color: str) -> str | None:
    """Menulis ikon SVG ke direktori temp agar bisa dirujuk lewat url() di QSS.

    Args:
        name: Kunci ikon pada kamus _ICONS.
        color: Warna goresan ikon.

    Returns:
        Path POSIX file SVG, atau None jika gagal ditulis.
    """
    markup = _svg_markup(name, color, 2.4)
    try:
        directory = Path(tempfile.gettempdir()) / "itemformdialog_icons"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}_{color.lstrip('#')}.svg"
        if not path.exists() or path.read_text(encoding="utf-8") != markup:
            path.write_text(markup, encoding="utf-8")
        return path.as_posix()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Widget kustom
# ---------------------------------------------------------------------------
class _ToggleSwitch(QCheckBox):
    """Checkbox berbentuk sakelar toggle beranimasi (API tetap QCheckBox)."""

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        accent: str = _C.GREEN,
        track_width: int = 38,
        track_height: int = 20,
    ) -> None:
        """Menginisialisasi sakelar toggle.

        Args:
            text: Teks label di sisi kanan sakelar (boleh kosong).
            parent: Widget induk opsional.
            accent: Warna track saat aktif.
            track_width: Lebar track dalam piksel.
            track_height: Tinggi track dalam piksel.
        """
        super().__init__(text, parent)
        self._accent = QColor(accent)
        self._off_color = QColor(_C.BORDER_HI)
        self._track_w = track_width
        self._track_h = track_height
        self._progress = 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self.toggled.connect(self._on_toggled)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def _on_anim_value(self, value: object) -> None:
        """Memperbarui posisi knob dari nilai animasi."""
        if isinstance(value, (int, float)):
            self._progress = float(value)
            self.update()

    def _on_toggled(self, checked: bool) -> None:
        """Menjalankan animasi atau langsung memposisikan knob."""
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._anim.stop()
            self._progress = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(target)
        self._anim.start()

    def showEvent(self, event: QEvent) -> None:  # type: ignore[override]
        """Menyelaraskan posisi knob dengan status saat widget pertama tampil."""
        self._progress = 1.0 if self.isChecked() else 0.0
        super().showEvent(event)  # type: ignore[arg-type]

    def sizeHint(self) -> QSize:
        """Ukuran ideal sakelar beserta teksnya."""
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text()) + 10 if self.text() else 0
        return QSize(self._track_w + text_w + 2, max(self._track_h, fm.height()) + 4)

    def minimumSizeHint(self) -> QSize:
        """Ukuran minimum sama dengan ukuran ideal."""
        return self.sizeHint()

    def hitButton(self, pos: QPoint) -> bool:
        """Seluruh area widget dapat diklik."""
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar track, knob, dan teks sakelar."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        enabled = self.isEnabled()
        y = (self.height() - self._track_h) / 2
        track = QRectF(1, y, self._track_w, self._track_h)
        track_color = _mix(self._off_color, self._accent, self._progress)
        if not enabled:
            track_color.setAlpha(110)
        if self.underMouse() and enabled:
            track_color = track_color.lighter(112)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        radius = self._track_h / 2
        painter.drawRoundedRect(track, radius, radius)

        margin = 3
        knob_d = self._track_h - margin * 2
        knob_x = track.left() + margin + self._progress * (self._track_w - knob_d - margin * 2)
        painter.setBrush(QColor("#FFFFFF") if enabled else QColor("#9399B2"))
        painter.drawEllipse(QRectF(knob_x, y + margin, knob_d, knob_d))

        if self.text():
            painter.setPen(QColor(_C.TEXT if enabled else _C.MUTED))
            text_rect = self.rect().adjusted(self._track_w + 10, 0, 0, 0)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self.text(),
            )
        painter.end()


class _DotRadio(QRadioButton):
    """Radio button bulat bergradien (API tetap QRadioButton)."""

    _SIZE = 18

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi radio button kustom.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedSize(self._SIZE + 4, self._SIZE + 4)

    def hitButton(self, pos: QPoint) -> bool:
        """Seluruh area widget dapat diklik."""
        return self.rect().contains(pos)

    def enterEvent(self, event: QEvent) -> None:  # type: ignore[override]
        """Menggambar ulang saat kursor masuk."""
        self.update()
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: QEvent) -> None:
        """Menggambar ulang saat kursor keluar."""
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar lingkaran radio dengan gradien saat terpilih."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(2, 2, self._SIZE, self._SIZE)

        if self.isChecked():
            grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
            grad.setColorAt(0.0, QColor(_C.BLUE))
            grad.setColorAt(1.0, QColor(_C.MAUVE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(outer)
            painter.setBrush(QColor(_C.BASE))
            painter.drawEllipse(outer.adjusted(5, 5, -5, -5))
        else:
            pen_color = QColor(_C.BLUE if self.underMouse() else "#585B70")
            painter.setPen(QPen(pen_color, 1.6))
            painter.setBrush(QColor(_rgba(_C.BLUE, 0.08)) if self.underMouse() else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(outer.adjusted(0.8, 0.8, -0.8, -0.8))
        painter.end()


class _HoverIconButton(QPushButton):
    """Tombol ikon yang menukar warna ikon saat kursor berada di atasnya."""

    def __init__(
        self,
        icon_name: str,
        normal_color: str,
        hover_color: str,
        parent: QWidget | None = None,
        *,
        text: str = "",
        icon_size: int = 14,
    ) -> None:
        """Menginisialisasi tombol ikon dengan dua varian warna.

        Args:
            icon_name: Kunci ikon pada kamus _ICONS.
            normal_color: Warna ikon normal.
            hover_color: Warna ikon saat hover.
            parent: Widget induk opsional.
            text: Teks tombol opsional.
            icon_size: Ukuran ikon.
        """
        super().__init__(text, parent)
        self._icon_normal = _svg_icon(icon_name, normal_color, icon_size, disabled_color=_C.BORDER_HI)
        self._icon_hover = _svg_icon(icon_name, hover_color, icon_size, disabled_color=_C.BORDER_HI)
        self.setIcon(self._icon_normal)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event: QEvent) -> None:  # type: ignore[override]
        """Mengganti ikon ke varian hover."""
        if self.isEnabled():
            self.setIcon(self._icon_hover)
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: QEvent) -> None:
        """Mengembalikan ikon ke varian normal."""
        self.setIcon(self._icon_normal)
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Struktur baris tabel
# ---------------------------------------------------------------------------
@dataclass
class _UnitRowWidgets:
    """Menyimpan referensi widget kontrol untuk satu baris variasi satuan jual.

    Attributes:
        item_unit_id: Primary key item_units untuk mode edit atau None saat baru.
        variant_input: Input teks nama varian satuan.
        unit_combo: Pilihan satuan dari tabel master units.
        conversion_spin: Input nilai konversi terhadap satuan dasar.
        price_spin: Input harga jual dalam Rupiah bulat.
        default_radio: Tombol radio penanda satuan utama kasir.
        active_check: Kotak centang (sakelar) status aktif varian satuan.
        remove_btn: Tombol penghapus baris variasi satuan.
    """

    item_unit_id: int | None
    variant_input: QLineEdit
    unit_combo: QComboBox
    conversion_spin: QDoubleSpinBox
    price_spin: QSpinBox
    default_radio: QRadioButton
    active_check: QCheckBox
    remove_btn: QPushButton


class ItemFormDialog(CustomDialog):
    """Dialog kustom untuk menambah atau memperbarui data barang fisik.

    Menampilkan formulir identitas barang, tabel dinamis multi-satuan jual,
    serta bagian stok awal opsional khusus pada mode tambah barang baru.
    """

    def __init__(
        self,
        categories: list[CategoryOption],
        units: list[UnitRecord],
        edit_data: ItemEditData | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi ItemFormDialog dalam mode tambah atau edit.

        Args:
            categories: Daftar opsi kategori untuk dropdown pilihan kategori.
            units: Daftar master satuan untuk pilihan satuan dasar dan varian.
            edit_data: Data barang yang akan diedit, atau None untuk mode tambah.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._categories: list[CategoryOption] = categories
        self._units: list[UnitRecord] = units
        self._edit_data: ItemEditData | None = edit_data
        self._result_payload: ItemFormPayload | None = None
        self._unit_rows: list[_UnitRowWidgets] = []
        self._default_group = QButtonGroup(self)
        self._default_group.setExclusive(True)
        self._arrow_path: str | None = _svg_file("chevron_down", _C.SUBTEXT)

        is_edit = edit_data is not None
        self.setWindowTitle(
            f"Edit Barang - {edit_data.sku}" if edit_data is not None else "Tambah Barang Baru"
        )
        self.setMinimumWidth(740)
        self.resize(780, 640 if not is_edit else 560)

        self._sku_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._category_combo = QComboBox(self)
        self._base_unit_combo = QComboBox(self)
        self._desc_input = QLineEdit(self)
        self._active_checkbox: QCheckBox = _ToggleSwitch("Aktif di Katalog Kasir", self)

        self._units_table = QTableWidget(0, 7, self)
        self._add_unit_btn = QPushButton("Tambah Satuan", self)
        self._units_count_chip = QLabel("", self)

        self._opening_stock_frame = QFrame(self)
        self._opening_qty_spin = QDoubleSpinBox(self._opening_stock_frame)
        self._opening_cost_spin = QDoubleSpinBox(self._opening_stock_frame)
        self._opening_value_label = QLabel("", self._opening_stock_frame)

        self._error_label = QLabel("", self)
        self._cancel_btn = QPushButton("Batal", self)
        self._save_btn = QPushButton(
            "Simpan Perubahan" if is_edit else "Simpan Barang",
            self,
        )

        self._setup_ui()
        self._apply_styles()
        self._populate_master_combos()
        self._load_initial_data()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Penyusunan UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Menyusun tata letak formulir yang padat, rapi, dan proporsional."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_header_banner())
        root_layout.addWidget(self._build_basic_info_section())
        root_layout.addWidget(self._build_units_section(), 1)

        if self._edit_data is None:
            root_layout.addWidget(self._build_opening_stock_section())
        else:
            self._opening_stock_frame.hide()

        self._error_label.setObjectName("FormErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root_layout.addWidget(self._error_label)

        root_layout.addLayout(self._build_footer_actions())
        self.setLayout(root_layout)

    def _build_header_banner(self) -> QFrame:
        """Membangun banner bergradien berisi ikon, judul, dan chip mode.

        Returns:
            Frame banner bagian atas dialog.
        """
        is_edit = self._edit_data is not None
        banner = QFrame(self)
        banner.setObjectName("HeaderBanner")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        badge = QLabel(banner)
        badge.setObjectName("HeaderBadgeEdit" if is_edit else "HeaderBadge")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(_svg_pixmap("edit_box" if is_edit else "package", 22, "#FFFFFF", 2.1))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        title = QLabel("Edit Data Barang" if is_edit else "Tambah Barang Baru", banner)
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            "Perbarui identitas, variasi satuan jual, dan harga barang."
            if is_edit
            else "Lengkapi identitas barang, atur satuan jual, lalu isi stok awal bila ada.",
            banner,
        )
        subtitle.setObjectName("HeaderSubtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        chip_text = f"SKU · {self._edit_data.sku}" if self._edit_data is not None else "BARANG BARU"
        chip = QLabel(chip_text, banner)
        chip.setObjectName("ModeChipEdit" if is_edit else "ModeChipNew")

        layout.addWidget(badge)
        layout.addLayout(text_col, 1)
        layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
        return banner

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

    def _build_section_header(
        self,
        parent: QWidget,
        icon: str,
        accent: str,
        title: str,
        subtitle: str,
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
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        title_label = QLabel(title, parent)
        title_label.setObjectName("SectionTitle")
        sub_label = QLabel(subtitle, parent)
        sub_label.setObjectName("SectionSubtitle")
        text_col.addWidget(title_label)
        text_col.addWidget(sub_label)

        row.addWidget(self._make_icon_badge(parent, icon, accent))
        row.addLayout(text_col, 1)
        return row

    def _build_basic_info_section(self) -> QFrame:
        """Membangun kartu isian informasi dasar barang dalam grid dua kolom.

        Returns:
            Frame berisi input SKU, nama, kategori, satuan dasar, dan deskripsi.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)
        outer.addLayout(
            self._build_section_header(
                card, "tag", _C.BLUE, "Informasi Barang", "Identitas utama barang di katalog"
            )
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self._sku_input.setObjectName("FormInput")
        self._sku_input.setPlaceholderText("Contoh: KRT-A4-70")
        self._sku_input.addAction(
            _svg_icon("barcode", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self._name_input.setObjectName("FormInput")
        self._name_input.setPlaceholderText("Nama lengkap barang")
        self._name_input.addAction(
            _svg_icon("type", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self._category_combo.setObjectName("FormCombo")
        self._base_unit_combo.setObjectName("FormCombo")
        self._prepare_combo(self._category_combo)
        self._prepare_combo(self._base_unit_combo)

        self._desc_input.setObjectName("FormInput")
        self._desc_input.setPlaceholderText("Catatan atau spesifikasi singkat (opsional)")
        self._desc_input.addAction(
            _svg_icon("note", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self._active_checkbox.setObjectName("FormCheckbox")
        self._active_checkbox.setChecked(True)

        status_wrap = QFrame(card)
        status_wrap.setObjectName("ToggleWrap")
        status_layout = QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(10, 2, 10, 2)
        status_layout.addWidget(self._active_checkbox)
        status_layout.addStretch(1)

        grid.addWidget(self._make_field_label("Kode SKU *"), 0, 0)
        grid.addWidget(self._make_field_label("Nama Barang *"), 0, 1)
        grid.addWidget(self._sku_input, 1, 0)
        grid.addWidget(self._name_input, 1, 1)
        grid.setRowMinimumHeight(2, 6)

        grid.addWidget(self._make_field_label("Kategori *"), 3, 0)
        grid.addWidget(self._make_field_label("Satuan Dasar *"), 3, 1)
        grid.addWidget(self._category_combo, 4, 0)
        grid.addWidget(self._base_unit_combo, 4, 1)
        grid.setRowMinimumHeight(5, 6)

        grid.addWidget(self._make_field_label("Deskripsi"), 6, 1)
        grid.addWidget(self._make_field_label("Status"), 6, 0)
        grid.addWidget(self._desc_input, 7, 1)
        grid.addWidget(status_wrap, 7, 0)

        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 6)
        outer.addLayout(grid)
        return card

    def _build_units_section(self) -> QFrame:
        """Membangun bagian tabel dinamis variasi satuan jual (item_units).

        Returns:
            Frame berisi header tombol tambah satuan dan tabel variasi satuan.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header_row = self._build_section_header(
            card,
            "layers",
            _C.MAUVE,
            "Variasi Satuan Jual",
            "Atur satuan, konversi, dan harga — pilih satu sebagai satuan utama kasir",
        )

        self._units_count_chip.setObjectName("CountChip")
        self._add_unit_btn.setObjectName("AddUnitBtn")
        self._add_unit_btn.setIcon(_svg_icon("plus", _C.MAUVE, 14))
        self._add_unit_btn.setIconSize(QSize(14, 14))
        self._add_unit_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        header_row.addWidget(self._units_count_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._add_unit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._units_table.setObjectName("UnitEditTable")
        self._units_table.setHorizontalHeaderLabels(
            [
                "NAMA VARIAN",
                "SATUAN",
                "KONVERSI",
                "HARGA JUAL",
                "UTAMA",
                "AKTIF",
                "",
            ]
        )
        self._units_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._units_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._units_table.setShowGrid(False)
        self._units_table.setMinimumHeight(160)
        self._units_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._units_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        v_header = self._units_table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(40)

        h_header = self._units_table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(30)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col in range(1, 7):
                h_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self._units_table.setColumnWidth(1, 132)
            self._units_table.setColumnWidth(2, 86)
            self._units_table.setColumnWidth(3, 124)
            self._units_table.setColumnWidth(4, 56)
            self._units_table.setColumnWidth(5, 58)
            self._units_table.setColumnWidth(6, 42)

            header_item_center = Qt.AlignmentFlag.AlignCenter
            for col in (4, 5):
                item = self._units_table.horizontalHeaderItem(col)
                if item is not None:
                    item.setTextAlignment(header_item_center)

        layout.addLayout(header_row)
        layout.addWidget(self._units_table, 1)
        return card

    def _build_opening_stock_section(self) -> QFrame:
        """Membangun bagian input stok awal opsional khusus mode tambah barang.

        Returns:
            Frame berisi input kuantitas stok awal dan harga modal satuan.
        """
        self._opening_stock_frame.setObjectName("FormSectionCard")
        outer = QVBoxLayout(self._opening_stock_frame)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)
        outer.addLayout(
            self._build_section_header(
                self._opening_stock_frame,
                "archive",
                _C.GREEN,
                "Stok Awal FIFO",
                "Opsional — kosongkan jika barang belum memiliki stok",
            )
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self._opening_qty_spin.setLocale(_ID_LOCALE)
        self._opening_qty_spin.setObjectName("FormSpin")
        self._opening_qty_spin.setRange(0.0, 1_000_000.0)
        self._opening_qty_spin.setDecimals(2)
        self._opening_qty_spin.setValue(0.0)
        self._opening_qty_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._opening_qty_spin.setGroupSeparatorShown(True)

        self._opening_cost_spin.setLocale(_ID_LOCALE)
        self._opening_cost_spin.setObjectName("FormSpin")
        self._opening_cost_spin.setRange(0.0, 999_999_999.0)
        self._opening_cost_spin.setDecimals(2)
        self._opening_cost_spin.setPrefix("Rp ")
        self._opening_cost_spin.setSingleStep(100.0)
        self._opening_cost_spin.setValue(0.0)
        self._opening_cost_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._opening_cost_spin.setGroupSeparatorShown(True)

        estimate_card = QFrame(self._opening_stock_frame)
        estimate_card.setObjectName("EstimateCard")
        est_layout = QHBoxLayout(estimate_card)
        est_layout.setContentsMargins(10, 0, 12, 0)
        est_layout.setSpacing(8)
        est_icon = QLabel(estimate_card)
        est_icon.setPixmap(_svg_pixmap("coins", 16, _C.GREEN))
        est_icon.setStyleSheet("background: transparent; border: none;")
        self._opening_value_label.setObjectName("EstimateValue")
        self._opening_value_label.setParent(estimate_card)
        est_layout.addWidget(est_icon)
        est_layout.addWidget(self._opening_value_label, 1)

        grid.addWidget(self._make_field_label("Qty Awal (Satuan Dasar)"), 0, 0)
        grid.addWidget(self._make_field_label("Harga Modal / Satuan Dasar"), 0, 1)
        grid.addWidget(self._make_field_label("Estimasi Nilai Persediaan"), 0, 2)
        grid.addWidget(self._opening_qty_spin, 1, 0)
        grid.addWidget(self._opening_cost_spin, 1, 1)
        grid.addWidget(estimate_card, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        outer.addLayout(grid)

        self._update_opening_estimate()
        return self._opening_stock_frame

    def _build_footer_actions(self) -> QHBoxLayout:
        """Membangun baris tombol aksi Batal dan Simpan pada bagian bawah dialog.

        Returns:
            QHBoxLayout berisi petunjuk di kiri dan tombol aksi di kanan.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(8)

        hint_icon = QLabel(self)
        hint_icon.setPixmap(_svg_pixmap("info", 14, _C.MUTED))
        hint_icon.setStyleSheet("background: transparent;")
        hint = QLabel(
            f'Kolom bertanda <span style="color:{_C.PINK}; font-weight:700;">*</span> wajib diisi',
            self,
        )
        hint.setObjectName("FooterHint")
        hint.setTextFormat(Qt.TextFormat.RichText)

        self._cancel_btn.setObjectName("CancelBtn")
        self._cancel_btn.setIcon(_svg_icon("close", _C.SUBTEXT, 14))
        self._cancel_btn.setIconSize(QSize(14, 14))
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setMinimumWidth(96)

        self._save_btn.setObjectName("SaveBtn")
        self._save_btn.setIcon(_svg_icon("check", "#FFFFFF", 15))
        self._save_btn.setIconSize(QSize(15, 15))
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setMinimumWidth(150)
        self._save_btn.setDefault(True)

        row.addWidget(hint_icon)
        row.addWidget(hint)
        row.addStretch(1)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._save_btn)
        return row

    def _make_field_label(self, text: str) -> QLabel:
        """Membuat label teks ringkas untuk judul field formulir.

        Tanda bintang di akhir teks dirender berwarna sebagai penanda wajib.

        Args:
            text: Teks label kolom masukan.

        Returns:
            Widget QLabel bergaya seragam.
        """
        label = QLabel(self)
        label.setObjectName("FieldLabel")
        label.setTextFormat(Qt.TextFormat.RichText)
        stripped = text.rstrip()
        if stripped.endswith("*"):
            base = escape(stripped[:-1].rstrip())
            label.setText(f'{base} <span style="color:{_C.PINK};">*</span>')
        else:
            label.setText(escape(text))
        return label

    def _prepare_combo(self, combo: QComboBox) -> None:
        """Memasang view list agar item popup dapat ditata via QSS.

        Args:
            combo: Combobox yang akan disiapkan.
        """
        view = QListView(combo)
        view.setObjectName("ComboPopup")
        combo.setView(view)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap berwarna serasi dengan CustomDialog."""
        arrow_rule = ""
        if self._arrow_path:
            arrow_rule = (
                "QComboBox#FormCombo::down-arrow, QComboBox#CellCombo::down-arrow {"
                f' image: url("{self._arrow_path}"); width: 11px; height: 11px; }}'
            )

        qss = """
            QWidget#CustomDialogContent {
                background-color: @BASE@;
                color: @TEXT@;
            }

            /* ---------- Header ---------- */
            QFrame#HeaderBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 @BLUE_A@, stop:0.55 @MAUVE_A@, stop:1 @PINK_A@);
                border: 1px solid @BLUE_B@;
                border-radius: 10px;
            }
            QLabel#HeaderBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B82F6, stop:1 #A855F7);
                border-radius: 12px;
            }
            QLabel#HeaderBadgeEdit {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F59E0B, stop:1 #EC4899);
                border-radius: 12px;
            }
            QLabel#HeaderTitle {
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#HeaderSubtitle {
                color: @SUBTEXT@;
                font-size: 11px;
                background: transparent;
            }
            QLabel#ModeChipNew, QLabel#ModeChipEdit {
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#ModeChipNew {
                background-color: @GREEN_A@;
                color: @GREEN@;
                border: 1px solid @GREEN_B@;
            }
            QLabel#ModeChipEdit {
                background-color: @PEACH_A@;
                color: @PEACH@;
                border: 1px solid @PEACH_B@;
            }

            /* ---------- Kartu seksi ---------- */
            QFrame#FormSectionCard {
                background-color: @SURFACE@;
                border: 1px solid @BORDER@;
                border-radius: 10px;
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
            QLabel#FieldLabel {
                color: @SUBTEXT@;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
                padding-left: 1px;
            }
            QLabel#CountChip {
                background-color: @MAUVE_A@;
                color: @MAUVE@;
                border: 1px solid @MAUVE_B@;
                border-radius: 9px;
                padding: 2px 9px;
                font-size: 10px;
                font-weight: 700;
            }
            QFrame#ToggleWrap {
                background-color: @BASE@;
                border: 1px solid @BORDER@;
                border-radius: 7px;
                min-height: 30px;
            }
            QCheckBox#FormCheckbox {
                font-size: 12px;
                background: transparent;
            }

            /* ---------- Error ---------- */
            QLabel#FormErrorLabel {
                background-color: rgba(239, 68, 68, 0.12);
                color: #FCA5A5;
                border: 1px solid rgba(239, 68, 68, 0.30);
                border-left: 3px solid #EF4444;
                border-radius: 7px;
                padding: 7px 10px;
                font-size: 11px;
                font-weight: 600;
            }

            /* ---------- Input ---------- */
            QLineEdit#FormInput,
            QComboBox#FormCombo,
            QDoubleSpinBox#FormSpin {
                background-color: @BASE@;
                color: @TEXT@;
                border: 1px solid @BORDER@;
                border-radius: 7px;
                padding: 5px 9px;
                font-size: 12px;
                min-height: 20px;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QLineEdit#FormInput:hover,
            QComboBox#FormCombo:hover,
            QDoubleSpinBox#FormSpin:hover {
                border: 1px solid @BORDER_HI@;
                background-color: #1B1B2A;
            }
            QLineEdit#FormInput:focus,
            QComboBox#FormCombo:focus,
            QComboBox#FormCombo:on,
            QDoubleSpinBox#FormSpin:focus {
                border: 1px solid @BLUE@;
                background-color: #1A1C2E;
            }
            QComboBox#FormCombo:disabled {
                color: #6C7086;
                background-color: #161622;
                border: 1px dashed @BORDER@;
            }

            /* ---------- Input sel tabel ---------- */
            QSpinBox#CellSpin,
            QDoubleSpinBox#CellDoubleSpin,
            QLineEdit#CellInput,
            QComboBox#CellCombo {
                background-color: @SURFACE@;
                color: @TEXT@;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 3px 8px;
                margin: 4px 3px;
                font-size: 12px;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QSpinBox#CellSpin:hover,
            QDoubleSpinBox#CellDoubleSpin:hover,
            QLineEdit#CellInput:hover,
            QComboBox#CellCombo:hover {
                border: 1px solid @BORDER_HI@;
            }
            QSpinBox#CellSpin:focus,
            QDoubleSpinBox#CellDoubleSpin:focus,
            QLineEdit#CellInput:focus,
            QComboBox#CellCombo:focus,
            QComboBox#CellCombo:on {
                border: 1px solid @BLUE@;
                background-color: #1A1C2E;
            }
            QSpinBox#CellSpin::up-button, QSpinBox#CellSpin::down-button,
            QDoubleSpinBox#CellDoubleSpin::up-button, QDoubleSpinBox#CellDoubleSpin::down-button,
            QDoubleSpinBox#FormSpin::up-button, QDoubleSpinBox#FormSpin::down-button {
                width: 0px;
                border: none;
                background: transparent;
            }
            QSpinBox#CellSpin::up-arrow, QSpinBox#CellSpin::down-arrow,
            QDoubleSpinBox#CellDoubleSpin::up-arrow, QDoubleSpinBox#CellDoubleSpin::down-arrow,
            QDoubleSpinBox#FormSpin::up-arrow, QDoubleSpinBox#FormSpin::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QSpinBox#CellSpin {
                color: @GREEN@;
                font-weight: 600;
            }

            /* ---------- Combobox ---------- */
            QComboBox#FormCombo, QComboBox#CellCombo {
                padding-right: 26px;
            }
            QComboBox#FormCombo::drop-down, QComboBox#CellCombo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border: none;
                background: transparent;
            }
            @ARROW_RULE@
            QListView#ComboPopup {
                background-color: @SURFACE@;
                color: @TEXT@;
                border: 1px solid @BORDER_HI@;
                border-radius: 6px;
                padding: 4px;
                outline: 0;
            }
            QListView#ComboPopup::item {
                min-height: 26px;
                padding: 0 8px;
                border-radius: 5px;
            }
            QListView#ComboPopup::item:hover {
                background-color: @BLUE_A@;
                color: #FFFFFF;
            }
            QListView#ComboPopup::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }

            /* ---------- Tabel ---------- */
            QTableWidget#UnitEditTable {
                background-color: @BASE@;
                color: @TEXT@;
                border: 1px solid @BORDER@;
                border-radius: 8px;
                font-size: 11px;
                gridline-color: transparent;
                outline: 0;
            }
            QTableWidget#UnitEditTable::item {
                border-bottom: 1px solid #232334;
            }
            QTableWidget#UnitEditTable QHeaderView {
                background-color: transparent;
            }
            QTableWidget#UnitEditTable QHeaderView::section {
                background-color: @SURFACE_HI@;
                color: @MUTED@;
                border: none;
                border-bottom: 1px solid @BORDER@;
                padding: 0 9px;
                font-size: 10px;
                font-weight: 700;
            }
            QTableWidget#UnitEditTable QTableCornerButton::section {
                background-color: @SURFACE_HI@;
                border: none;
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
            QScrollBar::handle:vertical:hover {
                background: @MAUVE@;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0;
                background: transparent;
            }

            /* ---------- Tombol ---------- */
            QPushButton#AddUnitBtn {
                background-color: @MAUVE_A@;
                color: @MAUVE@;
                border: 1px solid @MAUVE_B@;
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#AddUnitBtn:hover {
                background-color: @MAUVE_H@;
                border-color: @MAUVE@;
            }
            QPushButton#AddUnitBtn:pressed {
                background-color: @MAUVE_B@;
            }
            QPushButton#RemoveRowBtn {
                background-color: rgba(243, 139, 168, 0.10);
                border: 1px solid rgba(243, 139, 168, 0.25);
                border-radius: 6px;
            }
            QPushButton#RemoveRowBtn:hover:enabled {
                background-color: #EF4444;
                border-color: #EF4444;
            }
            QPushButton#RemoveRowBtn:disabled {
                background-color: transparent;
                border-color: @BORDER@;
            }
            QPushButton#CancelBtn {
                background-color: @SURFACE_HI@;
                color: @TEXT@;
                border: 1px solid #3B3D54;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CancelBtn:hover {
                background-color: @BORDER@;
                border-color: @BORDER_HI@;
            }
            QPushButton#SaveBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #8B5CF6);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#SaveBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #7C3AED);
            }
            QPushButton#SaveBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #6D28D9);
            }

            /* ---------- Stok awal ---------- */
            QFrame#EstimateCard {
                background-color: @GREEN_A@;
                border: 1px solid @GREEN_B@;
                border-radius: 7px;
                min-height: 30px;
            }
            QLabel#EstimateValue {
                color: @GREEN@;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
            QLabel#FooterHint {
                color: @MUTED@;
                font-size: 11px;
                background: transparent;
            }
            QToolTip {
                background-color: @SURFACE_HI@;
                color: @TEXT@;
                border: 1px solid @BORDER_HI@;
                padding: 5px 8px;
                border-radius: 4px;
            }
        """
        tokens = {
            "@ARROW_RULE@": arrow_rule,
            "@BASE@": _C.BASE,
            "@SURFACE@": _C.SURFACE,
            "@SURFACE_HI@": _C.SURFACE_HI,
            "@BORDER_HI@": _C.BORDER_HI,
            "@BORDER@": _C.BORDER,
            "@SUBTEXT@": _C.SUBTEXT,
            "@MUTED@": _C.MUTED,
            "@TEXT@": _C.TEXT,
            "@BLUE_A@": _rgba(_C.BLUE, 0.18),
            "@BLUE_B@": _rgba(_C.BLUE, 0.30),
            "@BLUE@": _C.BLUE,
            "@MAUVE_A@": _rgba(_C.MAUVE, 0.14),
            "@MAUVE_B@": _rgba(_C.MAUVE, 0.35),
            "@MAUVE_H@": _rgba(_C.MAUVE, 0.24),
            "@MAUVE@": _C.MAUVE,
            "@PINK_A@": _rgba(_C.PINK, 0.12),
            "@GREEN_A@": _rgba(_C.GREEN, 0.10),
            "@GREEN_B@": _rgba(_C.GREEN, 0.32),
            "@GREEN@": _C.GREEN,
            "@PEACH_A@": _rgba(_C.PEACH, 0.14),
            "@PEACH_B@": _rgba(_C.PEACH, 0.38),
            "@PEACH@": _C.PEACH,
        }
        for key, value in tokens.items():
            qss = qss.replace(key, value)
        self.content_widget.setStyleSheet(qss)

    # ------------------------------------------------------------------
    # Data awal
    # ------------------------------------------------------------------
    def _populate_master_combos(self) -> None:
        """Mengisi daftar pilihan kategori dan satuan dasar ke dalam combobox."""
        self._category_combo.clear()
        for cat in self._categories:
            self._category_combo.addItem(cat.label, cat.category_id)

        self._base_unit_combo.clear()
        for unit in self._units:
            self._base_unit_combo.addItem(
                f"{unit.name} ({unit.symbol})",
                unit.unit_id,
            )

    def _load_initial_data(self) -> None:
        """Mengisi formulir dengan data edit atau baris satuan awal untuk barang baru."""
        if self._edit_data is None:
            default_unit_id = self._units[0].unit_id if self._units else 0
            self._add_unit_row(
                ItemUnitPayload(
                    unit_id=default_unit_id,
                    variant_name="Satuan",
                    conversion_qty=1.0,
                    selling_price=0,
                    is_default=True,
                    is_active=True,
                )
            )
            return

        data = self._edit_data
        self._sku_input.setText(data.sku)
        self._name_input.setText(data.name)
        self._desc_input.setText(data.description)
        self._active_checkbox.setChecked(data.is_active)

        cat_idx = self._category_combo.findData(data.category_id)
        if cat_idx >= 0:
            self._category_combo.setCurrentIndex(cat_idx)

        unit_idx = self._base_unit_combo.findData(data.base_unit_id)
        if unit_idx >= 0:
            self._base_unit_combo.setCurrentIndex(unit_idx)

        if data.is_base_unit_locked:
            self._base_unit_combo.setEnabled(False)
            self._base_unit_combo.setToolTip(
                "Satuan dasar dikunci karena barang sudah memiliki riwayat stok/transaksi."
            )

        if data.units:
            for unit_item in data.units:
                self._add_unit_row(unit_item)
        else:
            self._add_unit_row(
                ItemUnitPayload(
                    unit_id=data.base_unit_id,
                    variant_name="Satuan",
                    conversion_qty=1.0,
                    selling_price=0,
                    is_default=True,
                    is_active=True,
                )
            )

    def _connect_signals(self) -> None:
        """Menghubungkan aksi tombol tambah satuan, batal, simpan, dan estimasi stok."""
        self._add_unit_btn.clicked.connect(self._handle_add_empty_unit_row)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._handle_save_clicked)
        self._opening_qty_spin.valueChanged.connect(self._update_opening_estimate)
        self._opening_cost_spin.valueChanged.connect(self._update_opening_estimate)

    # ------------------------------------------------------------------
    # Baris satuan
    # ------------------------------------------------------------------
    def _handle_add_empty_unit_row(self) -> None:
        """Menambahkan satu baris variasi satuan baru ke tabel multi-satuan."""
        raw_base_unit = self._base_unit_combo.currentData()
        default_unit_id = (
            raw_base_unit
            if isinstance(raw_base_unit, int)
            else (self._units[0].unit_id if self._units else 0)
        )
        self._add_unit_row(
            ItemUnitPayload(
                unit_id=default_unit_id,
                variant_name="",
                conversion_qty=1.0,
                selling_price=0,
                is_default=len(self._unit_rows) == 0,
                is_active=True,
            )
        )

    def _add_unit_row(self, unit_data: ItemUnitPayload) -> None:
        """Menyisipkan satu baris kontrol variasi satuan ke QTableWidget.

        Args:
            unit_data: Nilai awal kolom baris variasi satuan.
        """
        row_idx = self._units_table.rowCount()
        self._units_table.insertRow(row_idx)

        variant_input = QLineEdit(unit_data.variant_name, self._units_table)
        variant_input.setObjectName("CellInput")
        variant_input.setPlaceholderText("Contoh: Eceran / 1 Rim")

        unit_combo = QComboBox(self._units_table)
        unit_combo.setObjectName("CellCombo")
        self._prepare_combo(unit_combo)
        for unit in self._units:
            unit_combo.addItem(f"{unit.symbol} ({unit.name})", unit.unit_id)
        found_idx = unit_combo.findData(unit_data.unit_id)
        if found_idx >= 0:
            unit_combo.setCurrentIndex(found_idx)

        conv_spin = QDoubleSpinBox(self._units_table)
        conv_spin.setLocale(_ID_LOCALE)
        conv_spin.setObjectName("CellDoubleSpin")
        conv_spin.setRange(0.001, 1_000_000.0)
        conv_spin.setDecimals(3)
        conv_spin.setValue(max(0.001, float(unit_data.conversion_qty)))
        conv_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        conv_spin.setGroupSeparatorShown(True)

        price_spin = QSpinBox(self._units_table)
        price_spin.setLocale(_ID_LOCALE)
        price_spin.setObjectName("CellSpin")
        price_spin.setRange(0, 999_999_999)
        price_spin.setSingleStep(500)
        price_spin.setPrefix("Rp ")
        price_spin.setValue(max(0, int(unit_data.selling_price)))
        price_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_spin.setGroupSeparatorShown(True)

        radio_wrap = QWidget(self._units_table)
        radio_wrap.setStyleSheet("background: transparent;")
        radio_layout = QHBoxLayout(radio_wrap)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_radio = _DotRadio(radio_wrap)
        default_radio.setToolTip("Jadikan satuan utama di kasir")
        default_radio.setChecked(unit_data.is_default)
        self._default_group.addButton(default_radio)
        radio_layout.addWidget(default_radio)

        check_wrap = QWidget(self._units_table)
        check_wrap.setStyleSheet("background: transparent;")
        check_layout = QHBoxLayout(check_wrap)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        active_check = _ToggleSwitch(
            "", check_wrap, accent=_C.GREEN, track_width=32, track_height=18
        )
        active_check.setToolTip("Aktif / nonaktifkan varian ini")
        active_check.setChecked(unit_data.is_active)
        check_layout.addWidget(active_check)

        remove_wrap = QWidget(self._units_table)
        remove_wrap.setStyleSheet("background: transparent;")
        remove_layout = QHBoxLayout(remove_wrap)
        remove_layout.setContentsMargins(2, 2, 2, 2)
        remove_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remove_btn = _HoverIconButton("trash", _C.PINK, "#FFFFFF", remove_wrap, icon_size=14)
        remove_btn.setObjectName("RemoveRowBtn")
        remove_btn.setFixedSize(28, 26)
        remove_btn.setToolTip("Hapus varian satuan")
        remove_layout.addWidget(remove_btn)

        row_widgets = _UnitRowWidgets(
            item_unit_id=unit_data.item_unit_id,
            variant_input=variant_input,
            unit_combo=unit_combo,
            conversion_spin=conv_spin,
            price_spin=price_spin,
            default_radio=default_radio,
            active_check=active_check,
            remove_btn=remove_btn,
        )
        remove_btn.clicked.connect(
            lambda _checked=False, target=row_widgets: self._remove_unit_row(target)
        )

        self._unit_rows.append(row_widgets)
        self._units_table.setCellWidget(row_idx, 0, variant_input)
        self._units_table.setCellWidget(row_idx, 1, unit_combo)
        self._units_table.setCellWidget(row_idx, 2, conv_spin)
        self._units_table.setCellWidget(row_idx, 3, price_spin)
        self._units_table.setCellWidget(row_idx, 4, radio_wrap)
        self._units_table.setCellWidget(row_idx, 5, check_wrap)
        self._units_table.setCellWidget(row_idx, 6, remove_wrap)
        self._sync_remove_buttons_state()

    def _remove_unit_row(self, target: _UnitRowWidgets) -> None:
        """Menghapus baris variasi satuan tertentu bila masih ada baris tersisa.

        Args:
            target: Referensi kumpulan widget baris yang akan dihapus.
        """
        if len(self._unit_rows) <= 1 or target not in self._unit_rows:
            return

        row_idx = self._unit_rows.index(target)
        was_default = target.default_radio.isChecked()
        self._default_group.removeButton(target.default_radio)
        self._unit_rows.pop(row_idx)
        self._units_table.removeRow(row_idx)

        if was_default and self._unit_rows:
            self._unit_rows[0].default_radio.setChecked(True)
        self._sync_remove_buttons_state()

    def _sync_remove_buttons_state(self) -> None:
        """Menonaktifkan tombol hapus jika hanya tersisa satu variasi satuan."""
        can_remove = len(self._unit_rows) > 1
        for row in self._unit_rows:
            row.remove_btn.setEnabled(can_remove)
        self._units_count_chip.setText(f"{len(self._unit_rows)} varian")

    # ------------------------------------------------------------------
    # Tampilan tambahan (murni visual)
    # ------------------------------------------------------------------
    def _update_opening_estimate(self) -> None:
        """Memperbarui label estimasi nilai stok awal (qty x harga modal)."""
        total = float(self._opening_qty_spin.value()) * float(self._opening_cost_spin.value())
        formatted = f"{total:,.0f}".replace(",", ".")
        self._opening_value_label.setText(f"Rp {formatted}")

    # ------------------------------------------------------------------
    # Validasi & hasil
    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        """Menampilkan pesan kesalahan validasi secara inline di dalam dialog.

        Args:
            message: Teks pesan kesalahan yang harus diperbaiki pengguna.
        """
        show_inline_error(self._error_label, message)

    def _build_validated_payload(self) -> ItemFormPayload | None:
        """Memvalidasi seluruh isian formulir dan membentuk ItemFormPayload.

        Returns:
            Objek ItemFormPayload valid, atau None jika terdapat kesalahan input.
        """
        sku = self._sku_input.text().strip()
        name = self._name_input.text().strip()
        if not sku:
            self._show_error("Kode SKU barang wajib diisi.")
            self._sku_input.setFocus()
            return None
        if not name:
            self._show_error("Nama barang wajib diisi.")
            self._name_input.setFocus()
            return None

        raw_cat = self._category_combo.currentData()
        if not isinstance(raw_cat, int):
            self._show_error("Pilih kategori terlebih dahulu (tambahkan kategori jika kosong).")
            return None

        raw_base_unit = self._base_unit_combo.currentData()
        if not isinstance(raw_base_unit, int):
            self._show_error("Pilih satuan dasar terlebih dahulu (tambahkan satuan jika kosong).")
            return None

        unit_payloads: list[ItemUnitPayload] = []
        seen_variants: set[str] = set()
        active_default_count = 0

        for idx, row in enumerate(self._unit_rows, start=1):
            variant_name = row.variant_input.text().strip()
            if not variant_name:
                self._show_error(f"Nama varian pada baris satuan ke-{idx} wajib diisi.")
                row.variant_input.setFocus()
                return None

            variant_key = variant_name.lower()
            if variant_key in seen_variants:
                self._show_error(f"Nama varian '{variant_name}' tidak boleh duplikat.")
                row.variant_input.setFocus()
                return None
            seen_variants.add(variant_key)

            raw_unit_id = row.unit_combo.currentData()
            if not isinstance(raw_unit_id, int):
                self._show_error(f"Satuan pada baris ke-{idx} tidak valid.")
                return None

            is_default = row.default_radio.isChecked()
            is_active = row.active_check.isChecked()
            if is_default and is_active:
                active_default_count += 1

            unit_payloads.append(
                ItemUnitPayload(
                    item_unit_id=row.item_unit_id,
                    unit_id=raw_unit_id,
                    variant_name=variant_name,
                    conversion_qty=float(row.conversion_spin.value()),
                    selling_price=int(row.price_spin.value()),
                    is_default=is_default,
                    is_active=is_active,
                )
            )

        if active_default_count != 1:
            self._show_error(
                "Pilih tepat satu variasi satuan yang berstatus Aktif sebagai satuan Utama."
            )
            return None

        opening_qty = (
            float(self._opening_qty_spin.value()) if self._edit_data is None else 0.0
        )
        opening_cost = (
            float(self._opening_cost_spin.value()) if self._edit_data is None else 0.0
        )

        self._error_label.hide()
        return ItemFormPayload(
            sku=sku,
            name=name,
            category_id=raw_cat,
            base_unit_id=raw_base_unit,
            description=self._desc_input.text().strip(),
            is_active=self._active_checkbox.isChecked(),
            units=unit_payloads,
            opening_stock_qty=opening_qty,
            opening_stock_cost=opening_cost,
        )

    def _handle_save_clicked(self) -> None:
        """Memvalidasi isian formulir lalu menutup dialog dengan status diterima."""
        payload = self._build_validated_payload()
        if payload is None:
            return
        self._result_payload = payload
        self.accept()

    def get_payload(self) -> ItemFormPayload | None:
        """Mengembalikan muatan data formulir setelah dialog diterima.

        Returns:
            Objek ItemFormPayload jika pengguna menekan Simpan, atau None.
        """
        return self._result_payload

    @classmethod
    def get_item_payload(
        cls,
        parent: QWidget,
        edit_data: ItemEditData | None,
        categories: list[CategoryOption],
        units: list[UnitRecord],
    ) -> ItemFormPayload | None:
        """Membuka dialog secara modal dan mengembalikan ItemFormPayload hasil input.

        Metode ini sesuai dengan kontrak ItemDialogHandler pada ManajemenProdukHelper.

        Args:
            parent: Widget induk dialog.
            edit_data: Data barang untuk mode edit atau None untuk tambah barang baru.
            categories: Daftar pilihan kategori aktif/tersedia.
            units: Daftar master satuan tersedia.

        Returns:
            ItemFormPayload apabila pengguna menekan Simpan, atau None jika batal.
        """
        dialog = cls(
            categories=categories,
            units=units,
            edit_data=edit_data,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_payload()
        return None