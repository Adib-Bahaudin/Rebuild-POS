"""Modul dialog formulir tambah dan edit layanan jasa berbasis CustomDialog.

Modul ini menyediakan antarmuka modal ringkas untuk mengelola informasi dasar
layanan jasa serta daftar komposisi bahan baku (service_materials) yang akan
memotong stok FIFO saat transaksi berlangsung.

Tampilan dibangun ulang dengan ikon SVG inline, sakelar toggle kustom, kartu
berwarna, dan tampilan kosong untuk tabel bahan. Logika validasi dan kontrak
payload tidak berubah.
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
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QSpinBox,
    QStackedLayout,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import (
    ServiceEditData,
    ServiceFormPayload,
    ServiceMaterialPayload,
)
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
    MAUVE = "#CBA6F7"
    GREEN = "#A6E3A1"
    PEACH = "#FAB387"
    PINK = "#F38BA8"
    TEAL = "#94E2D5"
    SKY = "#89DCEB"


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


_ID_LOCALE = QLocale(QLocale.Language.Indonesian, QLocale.Country.Indonesia)


# ---------------------------------------------------------------------------
# Ikon SVG inline
# ---------------------------------------------------------------------------
_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS: dict[str, str] = {
    "tool": (
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77'
        'a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91'
        'a6 6 0 0 1 7.94-7.94z"/>'
    ),
    "edit_box": (
        '<path d="M12 20h9"/>'
        '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>'
    ),
    "info_card": (
        '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10"/>'
        '<path d="M7 13h6"/><path d="M7 17h4"/>'
    ),
    "flask": (
        '<path d="M9 3h6"/><path d="M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3"/>'
        '<path d="M7 15h10"/>'
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
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "box_open": (
        '<path d="M21 8 12 3 3 8l9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>'
        '<path d="M12 13v8"/>'
    ),
}


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
        directory = Path(tempfile.gettempdir()) / "serviceformdialog_icons"
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
        self._anim.stop()
        if not self.isVisible():
            self._progress = target
            self.update()
            return
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
# Data
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MaterialItemOption:
    """Merepresentasikan satu pilihan barang bahan baku untuk layanan jasa.

    Attributes:
        item_id: Primary key barang pada tabel items.
        sku: Kode SKU barang.
        name: Nama barang bahan baku.
        base_unit_symbol: Simbol satuan dasar barang (misalnya 'Lbr', 'Pcs').
    """

    item_id: int
    sku: str
    name: str
    base_unit_symbol: str


@dataclass
class _MaterialRowWidgets:
    """Menyimpan referensi widget kontrol untuk satu baris komposisi bahan baku.

    Attributes:
        item_combo: Combobox pemilih barang bahan baku.
        qty_spin: Input takaran pemakaian bahan per satu kali transaksi jasa.
        remove_btn: Tombol penghapus baris bahan baku.
    """

    item_combo: QComboBox
    qty_spin: QDoubleSpinBox
    remove_btn: QPushButton


class ServiceFormDialog(CustomDialog):
    """Dialog kustom untuk menambah atau memperbarui data layanan jasa.

    Menampilkan formulir identitas layanan, harga jual, status aktif, serta
    tabel dinamis komposisi bahan baku pemotong stok FIFO.
    """

    def __init__(
        self,
        material_options: list[MaterialItemOption],
        edit_data: ServiceEditData | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi ServiceFormDialog dalam mode tambah atau edit.

        Args:
            material_options: Daftar barang yang dapat dipilih sebagai bahan baku.
            edit_data: Data layanan jasa untuk mode edit, atau None saat tambah baru.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._material_options: list[MaterialItemOption] = material_options
        self._symbol_by_item_id: dict[int, str] = {
            opt.item_id: opt.base_unit_symbol for opt in material_options
        }
        self._edit_data: ServiceEditData | None = edit_data
        self._result_payload: ServiceFormPayload | None = None
        self._material_rows: list[_MaterialRowWidgets] = []
        self._arrow_path: str | None = _svg_file("chevron_down", _C.SUBTEXT)

        is_edit = edit_data is not None
        self.setWindowTitle(
            f"Edit Jasa - {edit_data.sku}"
            if edit_data is not None
            else "Tambah Layanan / Jasa Baru"
        )
        self.setMinimumWidth(680)
        self.resize(720, 600)

        self._sku_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._price_spin = QSpinBox(self)
        self._active_checkbox: QCheckBox = _ToggleSwitch("Aktif di Katalog Kasir", self)
        self._desc_input = QLineEdit(self)

        self._materials_table = QTableWidget(0, 3, self)
        self._add_material_btn = QPushButton("Tambah Bahan", self)
        self._materials_count_chip = QLabel("", self)
        self._materials_stack: QStackedLayout | None = None
        self._materials_empty: QFrame | None = None

        self._error_label = QLabel("", self)
        self._cancel_btn = QPushButton("Batal", self)
        self._save_btn = QPushButton(
            "Simpan Perubahan" if is_edit else "Simpan Jasa",
            self,
        )

        self._setup_ui()
        self._apply_styles()
        self._load_initial_data()
        self._connect_signals()
        self._refresh_materials_view()

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
        root_layout.addWidget(self._build_materials_section(), 1)

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
        badge.setPixmap(_svg_pixmap("edit_box" if is_edit else "tool", 22, "#FFFFFF", 2.1))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        title = QLabel("Edit Layanan / Jasa" if is_edit else "Tambah Layanan / Jasa Baru", banner)
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            "Perbarui identitas, harga, dan komposisi bahan baku layanan."
            if is_edit
            else "Isi identitas dan harga layanan, lalu tentukan bahan baku bila ada.",
            banner,
        )
        subtitle.setObjectName("HeaderSubtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        chip_text = f"SKU · {self._edit_data.sku}" if self._edit_data is not None else "JASA BARU"
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
        sub_label.setObjectName("SectionHint")
        sub_label.setWordWrap(True)
        text_col.addWidget(title_label)
        text_col.addWidget(sub_label)

        row.addWidget(self._make_icon_badge(parent, icon, accent))
        row.addLayout(text_col, 1)
        return row

    def _build_basic_info_section(self) -> QFrame:
        """Membangun kartu isian informasi dasar layanan jasa.

        Returns:
            Frame berisi input SKU, nama jasa, harga jual, status, dan deskripsi.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)
        outer.addLayout(
            self._build_section_header(
                card, "info_card", _C.BLUE, "Informasi Layanan", "Identitas dan harga jual layanan di kasir"
            )
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self._sku_input.setObjectName("FormInput")
        self._sku_input.setPlaceholderText("Contoh: JS-FC-A4")
        self._sku_input.addAction(
            _svg_icon("barcode", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self._name_input.setObjectName("FormInput")
        self._name_input.setPlaceholderText("Nama layanan jasa")
        self._name_input.addAction(
            _svg_icon("type", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        self._price_spin.setObjectName("PriceSpin")
        self._price_spin.setLocale(_ID_LOCALE)
        self._price_spin.setRange(0, 999_999_999)
        self._price_spin.setSingleStep(500)
        self._price_spin.setPrefix("Rp ")
        self._price_spin.setValue(0)
        self._price_spin.setGroupSeparatorShown(True)
        self._price_spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._active_checkbox.setObjectName("FormCheckbox")
        self._active_checkbox.setChecked(True)

        status_wrap = QFrame(card)
        status_wrap.setObjectName("ToggleWrap")
        status_layout = QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(10, 2, 10, 2)
        status_layout.addWidget(self._active_checkbox)
        status_layout.addStretch(1)

        self._desc_input.setObjectName("FormInput")
        self._desc_input.setPlaceholderText(
            "Keterangan atau syarat layanan (opsional)"
        )
        self._desc_input.addAction(
            _svg_icon("note", _C.MUTED), QLineEdit.ActionPosition.LeadingPosition
        )

        grid.addWidget(self._make_field_label("Kode SKU *"), 0, 0)
        grid.addWidget(self._make_field_label("Nama Layanan / Jasa *"), 0, 1)
        grid.addWidget(self._sku_input, 1, 0)
        grid.addWidget(self._name_input, 1, 1)
        grid.setRowMinimumHeight(2, 6)

        grid.addWidget(self._make_field_label("Harga Jual *"), 3, 0)
        grid.addWidget(self._make_field_label("Status"), 3, 1)
        grid.addWidget(self._price_spin, 4, 0)
        grid.addWidget(status_wrap, 4, 1)
        grid.setRowMinimumHeight(5, 6)

        grid.addWidget(self._make_field_label("Deskripsi"), 6, 0, 1, 2)
        grid.addWidget(self._desc_input, 7, 0, 1, 2)

        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 6)
        outer.addLayout(grid)
        return card

    def _build_materials_section(self) -> QFrame:
        """Membangun bagian tabel dinamis komposisi bahan baku layanan.

        Returns:
            Frame berisi tombol tambah bahan dan tabel komposisi bahan baku.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header_row = self._build_section_header(
            card,
            "flask",
            _C.PEACH,
            "Komposisi Bahan Baku (Opsional)",
            "Bahan yang ditambahkan akan otomatis memotong stok FIFO per 1x transaksi jasa.",
        )

        self._materials_count_chip.setObjectName("CountChip")
        self._add_material_btn.setObjectName("AddMaterialBtn")
        self._add_material_btn.setIcon(
            _svg_icon("plus", _C.PEACH, 14, disabled_color=_C.BORDER_HI)
        )
        self._add_material_btn.setIconSize(QSize(14, 14))
        self._add_material_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_material_btn.setEnabled(len(self._material_options) > 0)
        if not self._material_options:
            self._add_material_btn.setToolTip(
                "Belum ada data barang fisik yang dapat dijadikan bahan baku."
            )

        header_row.addWidget(self._materials_count_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._add_material_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._materials_table.setObjectName("MaterialEditTable")
        self._materials_table.setHorizontalHeaderLabels(
            ["BARANG BAHAN BAKU", "TAKARAN / 1x JASA", ""]
        )
        self._materials_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._materials_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._materials_table.setShowGrid(False)
        self._materials_table.setMinimumHeight(150)
        self._materials_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._materials_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        v_header = self._materials_table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(40)

        h_header = self._materials_table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(30)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            self._materials_table.setColumnWidth(1, 160)
            self._materials_table.setColumnWidth(2, 44)

        self._materials_empty = self._build_materials_empty_state(card)

        stack_host = QWidget(card)
        stack_host.setObjectName("MaterialsStackHost")
        self._materials_stack = QStackedLayout(stack_host)
        self._materials_stack.setContentsMargins(0, 0, 0, 0)
        self._materials_stack.addWidget(self._materials_table)
        self._materials_stack.addWidget(self._materials_empty)

        layout.addLayout(header_row)
        layout.addWidget(stack_host, 1)
        return card

    def _build_materials_empty_state(self, parent: QWidget) -> QFrame:
        """Membangun tampilan kosong saat belum ada bahan baku.

        Args:
            parent: Widget induk.

        Returns:
            Frame tampilan kosong.
        """
        empty = QFrame(parent)
        empty.setObjectName("EmptyState")
        empty.setMinimumHeight(150)
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addStretch(1)

        icon = QLabel(empty)
        icon.setPixmap(_svg_pixmap("box_open", 30, _C.MUTED, 1.8))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: transparent;")

        has_options = bool(self._material_options)
        title = QLabel(
            "Belum ada bahan baku" if has_options else "Belum ada barang fisik",
            empty,
        )
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel(
            "Layanan ini tidak memotong stok. Klik “Tambah Bahan” bila perlu."
            if has_options
            else "Tambahkan barang fisik terlebih dahulu agar dapat dipakai sebagai bahan baku.",
            empty,
        )
        sub.setObjectName("EmptySubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addStretch(1)
        return empty

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
        """Membuat label teks ringkas untuk judul kolom masukan.

        Tanda bintang di akhir teks dirender berwarna sebagai penanda wajib.

        Args:
            text: Teks judul kolom masukan.

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
                "QComboBox#CellCombo::down-arrow {"
                f' image: url("{self._arrow_path}"); width: 11px; height: 11px; }}'
            )

        qss = """
            QWidget#CustomDialogContent {
                background-color: @BASE@;
                color: @TEXT@;
            }
            QWidget#MaterialsStackHost { background: transparent; }

            /* ---------- Header ---------- */
            QFrame#HeaderBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 @PEACH_A@, stop:0.55 @PINK_A@, stop:1 @MAUVE_A@);
                border: 1px solid @PEACH_B@;
                border-radius: 10px;
            }
            QLabel#HeaderBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F97316, stop:1 #EC4899);
                border-radius: 12px;
            }
            QLabel#HeaderBadgeEdit {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F59E0B, stop:1 #A855F7);
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
            QLabel#SectionHint {
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
                background-color: @PEACH_A@;
                color: @PEACH@;
                border: 1px solid @PEACH_B@;
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
            QSpinBox#PriceSpin {
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
            QSpinBox#PriceSpin {
                color: @GREEN@;
                font-size: 13px;
                font-weight: 700;
            }
            QLineEdit#FormInput:hover,
            QSpinBox#PriceSpin:hover {
                border: 1px solid @BORDER_HI@;
                background-color: #1B1B2A;
            }
            QLineEdit#FormInput:focus,
            QSpinBox#PriceSpin:focus {
                border: 1px solid @BLUE@;
                background-color: #1A1C2E;
            }

            /* ---------- Input sel tabel ---------- */
            QComboBox#CellCombo,
            QDoubleSpinBox#CellDoubleSpin {
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
            QDoubleSpinBox#CellDoubleSpin {
                color: @PEACH@;
                font-weight: 700;
            }
            QComboBox#CellCombo:hover,
            QDoubleSpinBox#CellDoubleSpin:hover {
                border: 1px solid @BORDER_HI@;
            }
            QComboBox#CellCombo:focus,
            QComboBox#CellCombo:on,
            QDoubleSpinBox#CellDoubleSpin:focus {
                border: 1px solid @BLUE@;
                background-color: #1A1C2E;
            }

            /* Spinbox tanpa tombol naik-turun bawaan */
            QSpinBox#PriceSpin::up-button, QSpinBox#PriceSpin::down-button,
            QDoubleSpinBox#CellDoubleSpin::up-button, QDoubleSpinBox#CellDoubleSpin::down-button {
                width: 0px;
                border: none;
                background: transparent;
            }
            QSpinBox#PriceSpin::up-arrow, QSpinBox#PriceSpin::down-arrow,
            QDoubleSpinBox#CellDoubleSpin::up-arrow, QDoubleSpinBox#CellDoubleSpin::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }

            /* ---------- Combobox ---------- */
            QComboBox#CellCombo {
                padding-right: 26px;
            }
            QComboBox#CellCombo::drop-down {
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
            QTableWidget#MaterialEditTable {
                background-color: @BASE@;
                color: @TEXT@;
                border: 1px solid @BORDER@;
                border-radius: 8px;
                font-size: 11px;
                gridline-color: transparent;
                outline: 0;
            }
            QTableWidget#MaterialEditTable QHeaderView {
                background-color: transparent;
            }
            QTableWidget#MaterialEditTable QHeaderView::section {
                background-color: @SURFACE_HI@;
                color: @MUTED@;
                border: none;
                border-bottom: 1px solid @BORDER@;
                padding: 0 9px;
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
                background: @PEACH@;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0;
                background: transparent;
            }

            /* ---------- Tombol ---------- */
            QPushButton#AddMaterialBtn {
                background-color: @PEACH_A@;
                color: @PEACH@;
                border: 1px solid @PEACH_B@;
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#AddMaterialBtn:hover:enabled {
                background-color: @PEACH_H@;
                border-color: @PEACH@;
            }
            QPushButton#AddMaterialBtn:pressed {
                background-color: @PEACH_B@;
            }
            QPushButton#AddMaterialBtn:disabled {
                background-color: transparent;
                color: #585B70;
                border-color: @BORDER@;
            }
            QPushButton#RemoveRowBtn {
                background-color: rgba(243, 139, 168, 0.10);
                border: 1px solid rgba(243, 139, 168, 0.25);
                border-radius: 6px;
            }
            QPushButton#RemoveRowBtn:hover {
                background-color: #EF4444;
                border-color: #EF4444;
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
            "@SURFACE_HI@": _C.SURFACE_HI,
            "@SURFACE@": _C.SURFACE,
            "@BORDER_HI@": _C.BORDER_HI,
            "@BORDER@": _C.BORDER,
            "@SUBTEXT@": _C.SUBTEXT,
            "@MUTED@": _C.MUTED,
            "@TEXT@": _C.TEXT,
            "@BLUE_A@": _rgba(_C.BLUE, 0.18),
            "@BLUE@": _C.BLUE,
            "@MAUVE_A@": _rgba(_C.MAUVE, 0.10),
            "@PINK_A@": _rgba(_C.PINK, 0.10),
            "@PEACH_A@": _rgba(_C.PEACH, 0.14),
            "@PEACH_B@": _rgba(_C.PEACH, 0.36),
            "@PEACH_H@": _rgba(_C.PEACH, 0.24),
            "@PEACH@": _C.PEACH,
            "@GREEN_A@": _rgba(_C.GREEN, 0.10),
            "@GREEN_B@": _rgba(_C.GREEN, 0.32),
            "@GREEN@": _C.GREEN,
        }
        for key, value in tokens.items():
            qss = qss.replace(key, value)
        self.content_widget.setStyleSheet(qss)

    # ------------------------------------------------------------------
    # Data awal & sinyal
    # ------------------------------------------------------------------
    def _load_initial_data(self) -> None:
        """Mengisi formulir dengan data edit layanan jasa apabila tersedia."""
        if self._edit_data is None:
            return

        data = self._edit_data
        self._sku_input.setText(data.sku)
        self._name_input.setText(data.name)
        self._price_spin.setValue(max(0, int(data.selling_price)))
        self._active_checkbox.setChecked(data.is_active)
        self._desc_input.setText(data.description)

        for mat in data.materials:
            self._add_material_row(item_id=mat.item_id, quantity=mat.quantity)

    def _connect_signals(self) -> None:
        """Menghubungkan aksi tombol tambah bahan, batal, dan simpan."""
        self._add_material_btn.clicked.connect(self._handle_add_material_clicked)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._handle_save_clicked)

    # ------------------------------------------------------------------
    # Baris bahan baku
    # ------------------------------------------------------------------
    def _pick_default_material_id(self) -> int | None:
        """Memilih ID barang pertama yang belum digunakan pada baris bahan baku.

        Returns:
            ID barang yang belum terpakai, atau ID barang pertama jika semua terpakai.
        """
        if not self._material_options:
            return None

        used_ids: set[int] = set()
        for row in self._material_rows:
            raw_id = row.item_combo.currentData()
            if isinstance(raw_id, int):
                used_ids.add(raw_id)

        for opt in self._material_options:
            if opt.item_id not in used_ids:
                return opt.item_id
        return self._material_options[0].item_id

    def _handle_add_material_clicked(self) -> None:
        """Menambahkan satu baris bahan baku baru ke tabel komposisi."""
        default_item_id = self._pick_default_material_id()
        if default_item_id is None:
            return
        self._add_material_row(item_id=default_item_id, quantity=1.0)

    def _sync_qty_suffix(
        self,
        item_combo: QComboBox,
        qty_spin: QDoubleSpinBox,
    ) -> None:
        """Menyelaraskan akhiran simbol satuan pada spinbox sesuai barang terpilih.

        Args:
            item_combo: Combobox barang bahan baku pada baris terkait.
            qty_spin: Spinbox takaran kuantitas pada baris terkait.
        """
        raw_id = item_combo.currentData()
        if isinstance(raw_id, int):
            symbol = self._symbol_by_item_id.get(raw_id, "").strip()
            qty_spin.setSuffix(f" {symbol}" if symbol else "")
        else:
            qty_spin.setSuffix("")

    def _add_material_row(self, item_id: int, quantity: float) -> None:
        """Menyisipkan satu baris kontrol bahan baku ke QTableWidget.

        Args:
            item_id: ID barang bahan baku awal yang dipilih.
            quantity: Takaran kuantitas pemakaian per satu kali layanan.
        """
        row_idx = self._materials_table.rowCount()
        self._materials_table.insertRow(row_idx)

        item_combo = QComboBox(self._materials_table)
        item_combo.setObjectName("CellCombo")
        self._prepare_combo(item_combo)
        for opt in self._material_options:
            label = f"[{opt.sku}] {opt.name} ({opt.base_unit_symbol})"
            item_combo.addItem(label, opt.item_id)

        found_idx = item_combo.findData(item_id)
        if found_idx >= 0:
            item_combo.setCurrentIndex(found_idx)

        qty_spin = QDoubleSpinBox(self._materials_table)
        qty_spin.setObjectName("CellDoubleSpin")
        qty_spin.setLocale(_ID_LOCALE)
        qty_spin.setRange(0.001, 100_000.0)
        qty_spin.setDecimals(3)
        qty_spin.setSingleStep(1.0)
        qty_spin.setValue(max(0.001, float(quantity)))
        qty_spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._sync_qty_suffix(item_combo, qty_spin)

        item_combo.currentIndexChanged.connect(
            lambda _idx=0, combo=item_combo, spin=qty_spin: self._sync_qty_suffix(
                combo,
                spin,
            )
        )

        remove_wrap = QWidget(self._materials_table)
        remove_wrap.setStyleSheet("background: transparent;")
        remove_layout = QHBoxLayout(remove_wrap)
        remove_layout.setContentsMargins(2, 2, 2, 2)
        remove_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remove_btn = _HoverIconButton("trash", _C.PINK, "#FFFFFF", remove_wrap, icon_size=14)
        remove_btn.setObjectName("RemoveRowBtn")
        remove_btn.setFixedSize(28, 26)
        remove_btn.setToolTip("Hapus bahan baku")
        remove_layout.addWidget(remove_btn)

        row_widgets = _MaterialRowWidgets(
            item_combo=item_combo,
            qty_spin=qty_spin,
            remove_btn=remove_btn,
        )
        remove_btn.clicked.connect(
            lambda _checked=False, target=row_widgets: self._remove_material_row(
                target
            )
        )

        self._material_rows.append(row_widgets)
        self._materials_table.setCellWidget(row_idx, 0, item_combo)
        self._materials_table.setCellWidget(row_idx, 1, qty_spin)
        self._materials_table.setCellWidget(row_idx, 2, remove_wrap)
        self._refresh_materials_view()

    def _remove_material_row(self, target: _MaterialRowWidgets) -> None:
        """Menghapus satu baris bahan baku dari tabel komposisi.

        Args:
            target: Referensi kumpulan widget baris yang akan dihapus.
        """
        if target not in self._material_rows:
            return
        row_idx = self._material_rows.index(target)
        self._material_rows.pop(row_idx)
        self._materials_table.removeRow(row_idx)
        self._refresh_materials_view()

    def _refresh_materials_view(self) -> None:
        """Menampilkan tabel atau tampilan kosong serta memperbarui chip jumlah.

        Murni visual; tidak memengaruhi data baris bahan baku.
        """
        count = len(self._material_rows)
        self._materials_count_chip.setText(f"{count} bahan")
        if self._materials_stack is not None and self._materials_empty is not None:
            self._materials_stack.setCurrentWidget(
                self._materials_table if count > 0 else self._materials_empty
            )

    # ------------------------------------------------------------------
    # Validasi & hasil
    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        """Menampilkan pesan kesalahan validasi secara inline di dalam dialog.

        Args:
            message: Teks pesan kesalahan yang harus diperbaiki pengguna.
        """
        show_inline_error(self._error_label, message)

    def _build_validated_payload(self) -> ServiceFormPayload | None:
        """Memvalidasi seluruh isian formulir dan menyusun ServiceFormPayload.

        Returns:
            Objek ServiceFormPayload valid, atau None jika terdapat kesalahan input.
        """
        sku = self._sku_input.text().strip()
        name = self._name_input.text().strip()
        if not sku:
            self._show_error("Kode SKU layanan jasa wajib diisi.")
            self._sku_input.setFocus()
            return None
        if not name:
            self._show_error("Nama layanan jasa wajib diisi.")
            self._name_input.setFocus()
            return None

        materials: list[ServiceMaterialPayload] = []
        seen_item_ids: set[int] = set()
        for idx, row in enumerate(self._material_rows, start=1):
            raw_item_id = row.item_combo.currentData()
            if not isinstance(raw_item_id, int):
                self._show_error(f"Pilihan bahan baku pada baris ke-{idx} tidak valid.")
                return None
            if raw_item_id in seen_item_ids:
                self._show_error(
                    f"Bahan baku '{row.item_combo.currentText()}' dimasukkan lebih dari sekali."
                )
                return None
            seen_item_ids.add(raw_item_id)

            qty_val = float(row.qty_spin.value())
            if qty_val <= 0:
                self._show_error(
                    f"Takaran bahan baku pada baris ke-{idx} harus lebih dari 0."
                )
                row.qty_spin.setFocus()
                return None

            materials.append(
                ServiceMaterialPayload(item_id=raw_item_id, quantity=qty_val)
            )

        self._error_label.hide()
        return ServiceFormPayload(
            sku=sku,
            name=name,
            description=self._desc_input.text().strip(),
            selling_price=int(self._price_spin.value()),
            is_active=self._active_checkbox.isChecked(),
            materials=materials,
        )

    def _handle_save_clicked(self) -> None:
        """Memvalidasi isian formulir lalu menutup dialog dengan status diterima."""
        payload = self._build_validated_payload()
        if payload is None:
            return
        self._result_payload = payload
        self.accept()

    def get_payload(self) -> ServiceFormPayload | None:
        """Mengembalikan muatan data formulir setelah dialog diterima.

        Returns:
            Objek ServiceFormPayload jika pengguna menekan Simpan, atau None.
        """
        return self._result_payload

    @classmethod
    def get_service_payload(
        cls,
        parent: QWidget,
        edit_data: ServiceEditData | None,
        material_options: list[MaterialItemOption],
    ) -> ServiceFormPayload | None:
        """Membuka dialog secara modal dan mengembalikan ServiceFormPayload hasil input.

        Args:
            parent: Widget induk dialog.
            edit_data: Data layanan jasa untuk mode edit atau None untuk tambah baru.
            material_options: Daftar barang fisik yang tersedia sebagai bahan baku.

        Returns:
            ServiceFormPayload apabila pengguna menekan Simpan, atau None jika batal.
        """
        dialog = cls(
            material_options=material_options,
            edit_data=edit_data,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_payload()
        return None