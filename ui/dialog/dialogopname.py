"""Modul dialog stok awal dan penyesuaian opname FIFO berbasis CustomDialog.

Modul ini menyediakan antarmuka modal modern dan interaktif untuk mencatat
penambahan stok awal (OPENING_STOCK), penyesuaian masuk (ADJUSTMENT_IN),
maupun penyesuaian keluar berbasis FIFO (ADJUSTMENT_OUT) tanpa memuat logika
query basis data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QByteArray, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPaintEvent, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import (
    StockAdjustmentPayload,
    format_qty,
)
from util.customdialog import CustomDialog
from util.helper.dialog_form_helper import (
    build_footer_actions,
    make_field_label,
    show_inline_error,
)

AdjustmentType = Literal["OPENING_STOCK", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"]


@dataclass(frozen=True, slots=True)
class _ModeTheme:
    """Menyimpan konfigurasi warna dan teks untuk setiap mode penyesuaian stok.

    Attributes:
        accent: Warna aksen utama dalam format heksadesimal.
        accent_hover: Warna aksen saat tombol disorot kursor.
        accent_pressed: Warna aksen saat tombol ditekan.
        soft_bg: Warna latar transparan lembut untuk badge dan header.
        soft_border: Warna garis tepi lembut untuk elemen beraksen.
        subtitle: Ringkasan singkat fungsi mode penyesuaian.
        hint: Teks panduan pengisian harga modal untuk mode terkait.
        save_label: Teks label dinamis untuk tombol simpan.
        icon_key: Kunci ikon SVG yang mewakili mode penyesuaian.
    """

    accent: str
    accent_hover: str
    accent_pressed: str
    soft_bg: str
    soft_border: str
    subtitle: str
    hint: str
    save_label: str
    icon_key: str


_MODE_THEMES: dict[AdjustmentType, _ModeTheme] = {
    "ADJUSTMENT_IN": _ModeTheme(
        accent="#10B981",
        accent_hover="#059669",
        accent_pressed="#047857",
        soft_bg="rgba(16, 185, 129, 0.14)",
        soft_border="rgba(16, 185, 129, 0.38)",
        subtitle="Menambah layer stok FIFO baru dari hasil opname atau koreksi masuk.",
        hint="Masukkan harga modal per satuan dasar untuk batch penyesuaian stok masuk.",
        save_label="Simpan Stok Masuk",
        icon_key="arrow_in",
    ),
    "ADJUSTMENT_OUT": _ModeTheme(
        accent="#F59E0B",
        accent_hover="#D97706",
        accent_pressed="#B45309",
        soft_bg="rgba(245, 158, 11, 0.14)",
        soft_border="rgba(245, 158, 11, 0.38)",
        subtitle="Mengurangi stok secara otomatis mulai dari layer FIFO paling lama.",
        hint="Harga modal untuk stok keluar dihitung otomatis dari layer FIFO terlama.",
        save_label="Simpan Stok Keluar",
        icon_key="arrow_out",
    ),
    "OPENING_STOCK": _ModeTheme(
        accent="#38BDF8",
        accent_hover="#0EA5E9",
        accent_pressed="#0284C7",
        soft_bg="rgba(56, 189, 248, 0.14)",
        soft_border="rgba(56, 189, 248, 0.38)",
        subtitle="Mencatat saldo awal persediaan beserta nilai modal dasar barang.",
        hint="Masukkan harga beli/modal per satuan dasar untuk membentuk layer stok awal.",
        save_label="Simpan Stok Awal",
        icon_key="sparkle_box",
    ),
}


def _svg_template(icon_key: str, color: str) -> str:
    """Menghasilkan markup SVG vektor berdasarkan kunci ikon dan warna.

    Args:
        icon_key: Nama kunci ikon yang diminta.
        color: Warna stroke SVG dalam format CSS/hex.

    Returns:
        String markup XML SVG yang siap dirender oleh QSvgRenderer.
    """
    icons: dict[str, str] = {
        "package": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M16.5 9.4 7.55 4.24"/>'
            f'<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
            f'<polyline points="3.29 7 12 12 20.71 7"/>'
            f'<line x1="12" y1="22" x2="12" y2="12"/>'
            f"</svg>"
        ),
        "arrow_in": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M12 8v8"/>'
            f'<path d="M8 12h8"/>'
            f"</svg>"
        ),
        "arrow_out": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M8 12h8"/>'
            f"</svg>"
        ),
        "sparkle_box": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.1" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/>'
            f'<path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z"/>'
            f"</svg>"
        ),
        "arrow_right": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M5 12h14"/>'
            f'<path d="m13 6 6 6-6 6"/>'
            f"</svg>"
        ),
        "chevron_down": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="6 9 12 15 18 9"/>'
            f"</svg>"
        ),
        "chevron_up": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="18 15 12 9 6 15"/>'
            f"</svg>"
        ),
        "info": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.1" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="12" cy="12" r="9"/>'
            f'<path d="M12 16v-4"/>'
            f'<path d="M12 8h.01"/>'
            f"</svg>"
        ),
        "check": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="20 6 9 17 4 12"/>'
            f"</svg>"
        ),
        "cancel": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M18 6 6 18"/>'
            f'<path d="m6 6 12 12"/>'
            f"</svg>"
        ),
    }
    return icons.get(icon_key, icons["package"])


def _render_svg_pixmap(icon_key: str, color: str, size: int) -> QPixmap:
    """Merender markup SVG menjadi objek QPixmap transparan beresolusi tajam.

    Args:
        icon_key: Kunci ikon SVG yang akan dirender.
        color: Warna stroke ikon dalam format CSS/hex.
        size: Ukuran sisi pixmap persegi dalam piksel.

    Returns:
        Objek QPixmap hasil rendering SVG.
    """
    svg_bytes = QByteArray(_svg_template(icon_key, color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _render_svg_icon(icon_key: str, color: str, size: int = 16) -> QIcon:
    """Membuat QIcon dari rendering SVG inline.

    Args:
        icon_key: Kunci ikon SVG yang akan dirender.
        color: Warna stroke ikon dalam format CSS/hex.
        size: Ukuran ikon dalam piksel.

    Returns:
        Objek QIcon yang siap dipasang pada tombol atau widget Qt.
    """
    return QIcon(_render_svg_pixmap(icon_key, color, size))


def _paint_centered_svg(
    painter: QPainter,
    rect: QRectF,
    icon_key: str,
    color: str,
    icon_size: float,
) -> None:
    """Menggambar ikon SVG tepat di tengah area persegi panjang yang ditentukan.

    Args:
        painter: Instance QPainter aktif.
        rect: Area target tempat ikon dipusatkan.
        icon_key: Kunci ikon SVG yang akan digambar.
        color: Warna stroke ikon dalam format CSS/hex.
        icon_size: Lebar dan tinggi ikon dalam piksel.
    """
    svg_bytes = QByteArray(_svg_template(icon_key, color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    x_pos = rect.x() + (rect.width() - icon_size) / 2.0
    y_pos = rect.y() + (rect.height() - icon_size) / 2.0
    renderer.render(painter, QRectF(x_pos, y_pos, icon_size, icon_size))


class _StyledComboBox(QComboBox):
    """QComboBox kustom dengan popup modern membulat dan ikon chevron SVG."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi _StyledComboBox beserta tampilan popup kustom.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        popup_view = QListView(self)
        popup_view.setObjectName("ComboPopupView")
        popup_view.setSpacing(2)
        popup_view.setUniformItemSizes(True)
        popup_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setView(popup_view)

    def showPopup(self) -> None:
        """Menampilkan daftar dropdown dengan sudut membulat dan jarak vertikal."""
        super().showPopup()
        view = self.view()
        if view is None:
            return
        popup_window = view.window()
        if popup_window is not None:
            popup_window.setWindowFlags(
                Qt.WindowType.Popup
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.NoDropShadowWindowHint
            )
            popup_window.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground,
                True,
            )
            target_pos = self.mapToGlobal(QPoint(0, self.height() + 4))
            popup_window.move(target_pos)
            popup_window.setMinimumWidth(self.width())
            popup_window.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar combobox beserta ikon chevron bawah SVG di area tombol.

        Args:
            event: Event penggambaran widget Qt.
        """
        super().paintEvent(event)
        style = self.style()
        if style is None:
            return
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow_rect = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if not arrow_rect.isValid():
            return
        color = "#9399B2" if self.isEnabled() else "#585B70"
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_centered_svg(
            painter,
            QRectF(arrow_rect),
            "chevron_down",
            color,
            13.0,
        )
        painter.end()


class _StyledDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox kustom dengan ikon chevron atas dan bawah SVG vektor."""

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar spinbox beserta ikon chevron atas dan bawah SVG.

        Args:
            event: Event penggambaran widget Qt.
        """
        super().paintEvent(event)
        style = self.style()
        if style is None:
            return
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        up_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxUp,
            self,
        )
        down_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxDown,
            self,
        )
        color = "#9399B2" if self.isEnabled() else "#585B70"
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if up_rect.isValid():
            _paint_centered_svg(
                painter,
                QRectF(up_rect),
                "chevron_up",
                color,
                10.5,
            )
        if down_rect.isValid():
            _paint_centered_svg(
                painter,
                QRectF(down_rect),
                "chevron_down",
                color,
                10.5,
            )
        painter.end()


@dataclass(frozen=True)
class StockItemOption:
    """Merepresentasikan satu pilihan barang beserta sisa stok aktifnya.

    Attributes:
        item_id: Primary key barang pada tabel items.
        sku: Kode SKU barang.
        name: Nama barang.
        base_unit_symbol: Simbol satuan dasar barang (misalnya 'Lbr', 'Pcs').
        current_stock: Total sisa stok saat ini dari seluruh layer FIFO aktif.
    """

    item_id: int
    sku: str
    name: str
    base_unit_symbol: str
    current_stock: float


class StockAdjustmentDialog(CustomDialog):
    """Dialog kustom untuk input stok awal dan penyesuaian stok opname FIFO.

    Menampilkan header dinamis, pemilih barang, ringkasan stok saat ini beserta
    estimasi hasil akhir, pemilih mode mutasi berikon SVG, kuantitas, harga
    modal satuan, serta catatan.
    """

    def __init__(
        self,
        item_options: list[StockItemOption],
        preselected_item_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi StockAdjustmentDialog dengan daftar barang aktif.

        Args:
            item_options: Daftar barang yang dapat dipilih untuk disesuaikan stoknya.
            preselected_item_id: ID barang yang otomatis dipilih jika dibuka dari
                panel detail barang, atau None untuk memilih secara bebas.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._item_options: list[StockItemOption] = item_options
        self._option_by_id: dict[int, StockItemOption] = {
            opt.item_id: opt for opt in item_options
        }
        self._preselected_item_id: int | None = preselected_item_id
        self._result_payload: StockAdjustmentPayload | None = None
        self._selected_adjustment_type: AdjustmentType = "ADJUSTMENT_IN"

        self.setWindowTitle("Stok Awal / Penyesuaian Opname")
        self.setMinimumWidth(560)
        self.resize(580, 485)

        self._header_banner = QFrame(self)
        self._header_icon_badge = QLabel(self)
        self._header_subtitle = QLabel("", self)

        self._item_combo = _StyledComboBox(self)
        self._mode_group = QButtonGroup(self)
        self._mode_buttons: dict[AdjustmentType, QPushButton] = {}

        self._qty_spin = _StyledDoubleSpinBox(self)
        self._cost_spin = _StyledDoubleSpinBox(self)
        self._hint_box = QFrame(self)
        self._hint_icon = QLabel(self)
        self._cost_hint_label = QLabel("", self)
        self._notes_input = QLineEdit(self)

        self._current_stock_val = QLabel("0", self)
        self._delta_badge = QLabel("+0", self)
        self._transition_arrow = QLabel(self)
        self._projected_stock_val = QLabel("0", self)

        self._error_label = QLabel("", self)
        self._cancel_btn = QPushButton("Batal", self)
        self._save_btn = QPushButton("Simpan Penyesuaian", self)

        self._setup_ui()
        self._apply_styles()
        self._populate_controls()
        self._connect_signals()
        self._sync_dynamic_ui()

    def _setup_ui(self) -> None:
        """Menyusun tata letak formulir penyesuaian stok yang modern dan rapi."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header_banner())
        root_layout.addWidget(self._build_item_and_preview_section())
        root_layout.addWidget(self._build_adjustment_form_section())

        self._error_label.setObjectName("FormErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root_layout.addWidget(self._error_label)

        root_layout.addStretch(1)
        root_layout.addLayout(self._build_footer_actions())
        self.setLayout(root_layout)

    def _build_header_banner(self) -> QFrame:
        """Membangun banner judul ringkas dengan ikon SVG dinamis.

        Returns:
            Frame banner header di bagian atas dialog.
        """
        self._header_banner.setObjectName("HeaderBanner")
        layout = QHBoxLayout(self._header_banner)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self._header_icon_badge.setObjectName("HeaderIconBadge")
        self._header_icon_badge.setFixedSize(38, 38)
        self._header_icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)

        title = QLabel("Penyesuaian Persediaan FIFO", self._header_banner)
        title.setObjectName("HeaderTitle")

        self._header_subtitle.setObjectName("HeaderSubtitle")
        self._header_subtitle.setWordWrap(True)

        text_box.addWidget(title)
        text_box.addWidget(self._header_subtitle)

        layout.addWidget(self._header_icon_badge)
        layout.addLayout(text_box, 1)
        return self._header_banner

    def _build_item_and_preview_section(self) -> QFrame:
        """Membangun kartu pemilih barang dan strip pratinjau perubahan stok.

        Returns:
            Frame berisi dropdown barang serta indikator stok sebelum dan sesudah.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self._item_combo.setObjectName("FormCombo")
        self._item_combo.setCursor(Qt.CursorShape.PointingHandCursor)

        preview_strip = QFrame(card)
        preview_strip.setObjectName("SummaryStrip")
        strip_layout = QHBoxLayout(preview_strip)
        strip_layout.setContentsMargins(12, 10, 12, 10)
        strip_layout.setSpacing(12)

        curr_box = QVBoxLayout()
        curr_box.setContentsMargins(0, 0, 0, 0)
        curr_box.setSpacing(2)
        curr_caption = QLabel("STOK SAAT INI", preview_strip)
        curr_caption.setObjectName("StripCaption")
        self._current_stock_val.setObjectName("StripValue")
        curr_box.addWidget(curr_caption)
        curr_box.addWidget(self._current_stock_val)

        center_box = QVBoxLayout()
        center_box.setContentsMargins(0, 0, 0, 0)
        center_box.setSpacing(3)
        center_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._delta_badge.setObjectName("DeltaBadge")
        self._delta_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._transition_arrow.setObjectName("TransitionArrow")
        self._transition_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._transition_arrow.setFixedSize(20, 16)
        self._transition_arrow.setPixmap(
            _render_svg_pixmap("arrow_right", "#6C7086", 16)
        )

        center_box.addWidget(self._delta_badge)
        center_box.addWidget(self._transition_arrow)

        proj_box = QVBoxLayout()
        proj_box.setContentsMargins(0, 0, 0, 0)
        proj_box.setSpacing(2)
        proj_caption = QLabel("ESTIMASI AKHIR", preview_strip)
        proj_caption.setObjectName("StripCaption")
        proj_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._projected_stock_val.setObjectName("StripValueProjected")
        self._projected_stock_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        proj_box.addWidget(proj_caption)
        proj_box.addWidget(self._projected_stock_val)

        strip_layout.addLayout(curr_box, 1)
        strip_layout.addLayout(center_box, 0)
        strip_layout.addLayout(proj_box, 1)

        layout.addWidget(self._make_field_label("Barang Target *"))
        layout.addWidget(self._item_combo)
        layout.addWidget(preview_strip)
        return card

    def _build_mode_selector(self, parent: QWidget) -> QHBoxLayout:
        """Membangun deretan tombol kartu berikon SVG untuk memilih jenis mutasi.

        Args:
            parent: Widget induk penampung tombol mode.

        Returns:
            QHBoxLayout berisi tiga tombol pilihan mode penyesuaian stok.
        """
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(8)

        self._mode_group.setExclusive(True)

        mode_specs: list[tuple[AdjustmentType, str]] = [
            ("ADJUSTMENT_IN", "Stok Masuk"),
            ("ADJUSTMENT_OUT", "Stok Keluar"),
            ("OPENING_STOCK", "Stok Awal"),
        ]

        for adj_type, label_text in mode_specs:
            theme = _MODE_THEMES[adj_type]
            btn = QPushButton(label_text, parent)
            btn.setObjectName("ModePillBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(_render_svg_icon(theme.icon_key, theme.accent, 16))
            btn.setIconSize(QSize(16, 16))
            btn.setProperty("modeType", adj_type)
            self._mode_group.addButton(btn)
            self._mode_buttons[adj_type] = btn
            mode_layout.addWidget(btn, 1)

        self._mode_buttons["ADJUSTMENT_IN"].setChecked(True)
        return mode_layout

    def _build_adjustment_form_section(self) -> QFrame:
        """Membangun kartu input jenis mutasi, kuantitas, harga modal, dan catatan.

        Returns:
            Frame berisi kontrol input penyesuaian stok.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self._qty_spin.setObjectName("FormSpin")
        self._qty_spin.setRange(0.001, 1_000_000.0)
        self._qty_spin.setDecimals(3)
        self._qty_spin.setSingleStep(1.0)
        self._qty_spin.setValue(1.0)

        self._cost_spin.setObjectName("FormSpin")
        self._cost_spin.setRange(0.0, 999_999_999.0)
        self._cost_spin.setDecimals(2)
        self._cost_spin.setSingleStep(100.0)
        self._cost_spin.setPrefix("Rp ")
        self._cost_spin.setValue(0.0)

        self._hint_box.setObjectName("HintBox")
        hint_layout = QHBoxLayout(self._hint_box)
        hint_layout.setContentsMargins(10, 7, 10, 7)
        hint_layout.setSpacing(8)

        self._hint_icon.setObjectName("HintIcon")
        self._hint_icon.setFixedSize(18, 18)
        self._hint_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._cost_hint_label.setObjectName("FieldHint")
        self._cost_hint_label.setWordWrap(True)

        hint_layout.addWidget(self._hint_icon)
        hint_layout.addWidget(self._cost_hint_label, 1)

        self._notes_input.setObjectName("FormInput")
        self._notes_input.setPlaceholderText(
            "Contoh: Stok opname akhir bulan / stok awal toko / barang rusak"
        )

        grid.addWidget(self._make_field_label("Jenis Penyesuaian *"), 0, 0, 1, 2)
        grid.addLayout(self._build_mode_selector(card), 1, 0, 1, 2)

        grid.addWidget(self._make_field_label("Kuantitas (Satuan Dasar) *"), 2, 0)
        grid.addWidget(self._make_field_label("Harga Modal / Satuan Dasar"), 2, 1)
        grid.addWidget(self._qty_spin, 3, 0)
        grid.addWidget(self._cost_spin, 3, 1)

        grid.addWidget(self._hint_box, 4, 0, 1, 2)
        grid.addWidget(self._make_field_label("Catatan / Keterangan"), 5, 0, 1, 2)
        grid.addWidget(self._notes_input, 6, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return card

    def _build_footer_actions(self) -> QHBoxLayout:
        """Membangun baris tombol aksi Batal dan Simpan pada bagian bawah dialog.

        Returns:
            QHBoxLayout berisi tombol aksi sejajar kanan.
        """
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setIcon(_render_svg_icon("cancel", "#BAC2DE", 14))
        self._cancel_btn.setIconSize(QSize(14, 14))

        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setIcon(_render_svg_icon("check", "#FFFFFF", 15))
        self._save_btn.setIconSize(QSize(15, 15))

        return build_footer_actions(self._cancel_btn, self._save_btn)

    def _make_field_label(self, text: str) -> QLabel:
        """Membuat label teks ringkas untuk judul kolom masukan.

        Args:
            text: Teks judul kolom masukan.

        Returns:
            Widget QLabel bergaya seragam.
        """
        return make_field_label(self, text)

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS modern serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #161622;
                color: #CDD6F4;
            }
            QFrame#HeaderBanner {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QLabel#HeaderTitle {
                color: #F5F7FF;
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#HeaderSubtitle {
                color: #A6ADC8;
                font-size: 11px;
                background: transparent;
            }
            QFrame#FormSectionCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QFrame#SummaryStrip {
                background-color: #14141F;
                border: 1px solid #2A2B3D;
                border-radius: 8px;
            }
            QLabel#StripCaption {
                color: #7F849C;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.6px;
                background: transparent;
            }
            QLabel#StripValue {
                color: #E2E8F0;
                font-size: 15px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#StripValueProjected {
                color: #34D399;
                font-size: 15px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#TransitionArrow {
                background: transparent;
                border: none;
            }
            QLabel#FieldLabel {
                color: #BAC2DE;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QFrame#HintBox {
                background-color: rgba(56, 189, 248, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.22);
                border-radius: 7px;
            }
            QLabel#HintIcon {
                background: transparent;
                border: none;
            }
            QLabel#FieldHint {
                color: #A6ADC8;
                font-size: 11px;
                background: transparent;
                border: none;
            }
            QLabel#FormErrorLabel {
                background-color: rgba(244, 63, 94, 0.14);
                color: #FDA4AF;
                border: 1px solid rgba(244, 63, 94, 0.42);
                border-radius: 7px;
                padding: 7px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#ModePillBtn {
                background-color: #161622;
                color: #A6ADC8;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#ModePillBtn:hover {
                background-color: #232436;
                color: #CDD6F4;
                border-color: #45475A;
            }
            QPushButton#ModePillBtn[modeType="ADJUSTMENT_IN"]:checked {
                background-color: rgba(16, 185, 129, 0.16);
                color: #6EE7B7;
                border: 1.5px solid #10B981;
            }
            QPushButton#ModePillBtn[modeType="ADJUSTMENT_OUT"]:checked {
                background-color: rgba(245, 158, 11, 0.16);
                color: #FCD34D;
                border: 1.5px solid #F59E0B;
            }
            QPushButton#ModePillBtn[modeType="OPENING_STOCK"]:checked {
                background-color: rgba(56, 189, 248, 0.16);
                color: #7DD3FC;
                border: 1.5px solid #38BDF8;
            }
            QLineEdit#FormInput,
            QComboBox#FormCombo {
                background-color: #14141F;
                color: #F1F5F9;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 12px;
                min-height: 24px;
            }
            QDoubleSpinBox#FormSpin {
                background-color: #14141F;
                color: #F1F5F9;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 6px 30px 6px 10px;
                font-size: 12px;
                min-height: 24px;
            }
            QLineEdit#FormInput:hover,
            QComboBox#FormCombo:hover,
            QDoubleSpinBox#FormSpin:hover {
                border-color: #45475A;
            }
            QLineEdit#FormInput:focus,
            QComboBox#FormCombo:focus,
            QComboBox#FormCombo:on,
            QDoubleSpinBox#FormSpin:focus {
                border: 1.5px solid #38BDF8;
                background-color: #181826;
            }
            QDoubleSpinBox#FormSpin:disabled {
                color: #585B70;
                background-color: #12121C;
                border-color: #252638;
            }
            QComboBox#FormCombo::drop-down {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 28px;
                margin: 2px 2px 2px 0px;
                border-left: 1px solid #2A2B3D;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background-color: #1B1B2A;
            }
            QComboBox#FormCombo::drop-down:hover {
                background-color: #26273B;
            }
            QComboBox#FormCombo::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }
            QListView#ComboPopupView {
                background-color: #1A1B2B;
                color: #CDD6F4;
                border: 1px solid #3E405B;
                border-radius: 9px;
                padding: 5px;
                outline: none;
                font-size: 12px;
            }
            QListView#ComboPopupView::item {
                padding: 8px 10px;
                border-radius: 6px;
                color: #CDD6F4;
                background-color: transparent;
            }
            QListView#ComboPopupView::item:hover {
                background-color: #26283E;
                color: #FFFFFF;
            }
            QListView#ComboPopupView::item:selected {
                background-color: rgba(56, 189, 248, 0.20);
                color: #7DD3FC;
                font-weight: 600;
            }
            QDoubleSpinBox#FormSpin::up-button,
            QDoubleSpinBox#FormSpin::down-button {
                subcontrol-origin: border;
                width: 24px;
                background-color: #1B1B2A;
                border-left: 1px solid #2A2B3D;
            }
            QDoubleSpinBox#FormSpin::up-button {
                subcontrol-position: top right;
                margin: 2px 2px 0px 0px;
                border-top-right-radius: 5px;
                border-bottom: 1px solid #2A2B3D;
            }
            QDoubleSpinBox#FormSpin::down-button {
                subcontrol-position: bottom right;
                margin: 0px 2px 2px 0px;
                border-bottom-right-radius: 5px;
            }
            QDoubleSpinBox#FormSpin::up-button:hover,
            QDoubleSpinBox#FormSpin::down-button:hover {
                background-color: #2A2C42;
            }
            QDoubleSpinBox#FormSpin::up-button:pressed,
            QDoubleSpinBox#FormSpin::down-button:pressed {
                background-color: #343752;
            }
            QDoubleSpinBox#FormSpin::up-arrow,
            QDoubleSpinBox#FormSpin::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }
            QPushButton#CancelBtn {
                background-color: #232436;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 7px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CancelBtn:hover {
                background-color: #313244;
                border-color: #585B70;
            }
            QPushButton#CancelBtn:pressed {
                background-color: #1E1E2E;
            }
            QPushButton#SaveBtn:disabled {
                background-color: #252638;
                color: #585B70;
                border: none;
                border-radius: 7px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

    def _apply_mode_accent(self, adj_type: AdjustmentType) -> None:
        """Menyesuaikan warna aksen dinamis pada header, hint, dan tombol simpan.

        Args:
            adj_type: Jenis penyesuaian stok yang sedang aktif.
        """
        theme = _MODE_THEMES[adj_type]
        self._header_subtitle.setText(theme.subtitle)
        self._header_icon_badge.setPixmap(
            _render_svg_pixmap(theme.icon_key, theme.accent, 20)
        )
        self._header_icon_badge.setStyleSheet(
            f"background-color: {theme.soft_bg}; "
            f"border: 1px solid {theme.soft_border}; "
            f"border-radius: 10px;"
        )
        self._hint_icon.setPixmap(_render_svg_pixmap("info", theme.accent, 15))
        self._hint_box.setStyleSheet(
            f"QFrame#HintBox {{"
            f"background-color: {theme.soft_bg}; "
            f"border: 1px solid {theme.soft_border}; "
            f"border-radius: 7px;"
            f"}}"
        )
        self._save_btn.setText(theme.save_label)
        self._save_btn.setStyleSheet(
            f"""
            QPushButton#SaveBtn {{
                background-color: {theme.accent};
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#SaveBtn:hover:enabled {{
                background-color: {theme.accent_hover};
            }}
            QPushButton#SaveBtn:pressed {{
                background-color: {theme.accent_pressed};
            }}
            QPushButton#SaveBtn:disabled {{
                background-color: #252638;
                color: #585B70;
            }}
            """
        )

    def _populate_controls(self) -> None:
        """Mengisi daftar pilihan barang dan status awal tombol aksi."""
        self._item_combo.clear()
        for opt in self._item_options:
            label = f"[{opt.sku}] {opt.name} ({opt.base_unit_symbol})"
            self._item_combo.addItem(label, opt.item_id)

        if self._preselected_item_id is not None:
            found_idx = self._item_combo.findData(self._preselected_item_id)
            if found_idx >= 0:
                self._item_combo.setCurrentIndex(found_idx)

        has_items = len(self._item_options) > 0
        self._save_btn.setEnabled(has_items)
        if not has_items:
            self._show_error(
                "Belum ada data barang fisik. Tambahkan barang terlebih dahulu."
            )

    def _connect_signals(self) -> None:
        """Menghubungkan perubahan kontrol input dan tombol aksi dialog."""
        self._item_combo.currentIndexChanged.connect(self._sync_dynamic_ui)
        self._mode_group.buttonClicked.connect(self._handle_mode_button_clicked)
        self._qty_spin.valueChanged.connect(self._update_stock_preview)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._handle_save_clicked)

    def _handle_mode_button_clicked(self, button: QPushButton) -> None:
        """Memperbarui jenis penyesuaian stok aktif saat tombol mode ditekan.

        Args:
            button: Tombol mode yang diklik pengguna.
        """
        raw_mode = button.property("modeType")
        if raw_mode == "OPENING_STOCK":
            self._selected_adjustment_type = "OPENING_STOCK"
        elif raw_mode == "ADJUSTMENT_OUT":
            self._selected_adjustment_type = "ADJUSTMENT_OUT"
        else:
            self._selected_adjustment_type = "ADJUSTMENT_IN"
        self._sync_dynamic_ui()

    def _get_selected_option(self) -> StockItemOption | None:
        """Mengambil objek StockItemOption yang sedang terpilih di combobox.

        Returns:
            Objek StockItemOption terpilih atau None jika daftar kosong.
        """
        raw_id = self._item_combo.currentData()
        if isinstance(raw_id, int):
            return self._option_by_id.get(raw_id)
        return None

    def _get_selected_adjustment_type(self) -> AdjustmentType:
        """Mengambil nilai Literal jenis penyesuaian stok yang sedang terpilih.

        Returns:
            Salah satu dari 'OPENING_STOCK', 'ADJUSTMENT_IN', atau 'ADJUSTMENT_OUT'.
        """
        return self._selected_adjustment_type

    def _sync_dynamic_ui(self) -> None:
        """Menyelaraskan simbol satuan, tema aksen, status harga modal, dan pratinjau."""
        selected = self._get_selected_option()
        if selected is not None:
            symbol = selected.base_unit_symbol.strip()
            self._qty_spin.setSuffix(f" {symbol}" if symbol else "")
        else:
            self._qty_spin.setSuffix("")

        adj_type = self._get_selected_adjustment_type()
        theme = _MODE_THEMES[adj_type]
        is_stock_out = adj_type == "ADJUSTMENT_OUT"

        self._cost_spin.setEnabled(not is_stock_out)
        self._cost_hint_label.setText(theme.hint)
        self._apply_mode_accent(adj_type)
        self._update_stock_preview()

    def _update_stock_preview(self) -> None:
        """Memperbarui indikator stok saat ini, badge delta, dan estimasi akhir."""
        selected = self._get_selected_option()
        if selected is None:
            self._current_stock_val.setText("-")
            self._delta_badge.setText("-")
            self._projected_stock_val.setText("-")
            return

        symbol = selected.base_unit_symbol
        curr_qty = selected.current_stock
        delta_qty = float(self._qty_spin.value())
        adj_type = self._get_selected_adjustment_type()
        is_out = adj_type == "ADJUSTMENT_OUT"

        projected_qty = curr_qty - delta_qty if is_out else curr_qty + delta_qty
        delta_prefix = "-" if is_out else "+"

        self._current_stock_val.setText(format_qty(curr_qty, symbol))
        self._delta_badge.setText(f"{delta_prefix}{format_qty(delta_qty, symbol)}")
        self._projected_stock_val.setText(format_qty(projected_qty, symbol))

        if projected_qty < -1e-9:
            proj_color = "#FB7185"
            badge_bg = "rgba(244, 63, 94, 0.16)"
            badge_border = "rgba(244, 63, 94, 0.42)"
        elif is_out:
            proj_color = "#FBBF24"
            badge_bg = "rgba(245, 158, 11, 0.16)"
            badge_border = "rgba(245, 158, 11, 0.40)"
        elif adj_type == "OPENING_STOCK":
            proj_color = "#38BDF8"
            badge_bg = "rgba(56, 189, 248, 0.16)"
            badge_border = "rgba(56, 189, 248, 0.40)"
        else:
            proj_color = "#34D399"
            badge_bg = "rgba(16, 185, 129, 0.16)"
            badge_border = "rgba(16, 185, 129, 0.40)"

        self._delta_badge.setStyleSheet(
            f"background-color: {badge_bg}; "
            f"color: {proj_color}; "
            f"border: 1px solid {badge_border}; "
            f"border-radius: 10px; "
            f"padding: 2px 8px; "
            f"font-size: 11px; "
            f"font-weight: 700;"
        )
        self._transition_arrow.setPixmap(
            _render_svg_pixmap("arrow_right", proj_color, 16)
        )
        self._projected_stock_val.setStyleSheet(
            f"color: {proj_color}; font-size: 15px; font-weight: 700; "
            f"background: transparent;"
        )

    def _show_error(self, message: str) -> None:
        """Menampilkan pesan kesalahan validasi secara inline di dalam dialog.

        Args:
            message: Teks pesan kesalahan yang harus diperbaiki pengguna.
        """
        show_inline_error(self._error_label, message)

    def _build_validated_payload(self) -> StockAdjustmentPayload | None:
        """Memvalidasi seluruh isian formulir dan menyusun StockAdjustmentPayload.

        Returns:
            Objek StockAdjustmentPayload valid, atau None jika terdapat kesalahan.
        """
        selected = self._get_selected_option()
        if selected is None:
            self._show_error("Pilih barang target terlebih dahulu.")
            return None

        adj_type = self._get_selected_adjustment_type()
        qty = float(self._qty_spin.value())
        if qty <= 0:
            self._show_error("Kuantitas penyesuaian harus lebih dari 0.")
            self._qty_spin.setFocus()
            return None

        if adj_type == "ADJUSTMENT_OUT" and qty > selected.current_stock + 1e-9:
            self._show_error(
                f"Pengurangan ({format_qty(qty, selected.base_unit_symbol)}) melebihi "
                f"sisa stok tersedia ({format_qty(selected.current_stock, selected.base_unit_symbol)})."
            )
            self._qty_spin.setFocus()
            return None

        unit_cost = (
            0.0 if adj_type == "ADJUSTMENT_OUT" else float(self._cost_spin.value())
        )
        self._error_label.hide()
        return StockAdjustmentPayload(
            item_id=selected.item_id,
            adjustment_type=adj_type,
            quantity=qty,
            unit_cost=unit_cost,
            notes=self._notes_input.text().strip(),
        )

    def _handle_save_clicked(self) -> None:
        """Memvalidasi formulir lalu menutup dialog dengan status diterima."""
        payload = self._build_validated_payload()
        if payload is None:
            return
        self._result_payload = payload
        self.accept()

    def get_payload(self) -> StockAdjustmentPayload | None:
        """Mengembalikan muatan data penyesuaian stok setelah dialog diterima.

        Returns:
            Objek StockAdjustmentPayload jika pengguna menekan Simpan, atau None.
        """
        return self._result_payload

    @classmethod
    def get_adjustment_payload(
        cls,
        parent: QWidget,
        item_options: list[StockItemOption],
        preselected_item_id: int | None = None,
    ) -> StockAdjustmentPayload | None:
        """Membuka dialog secara modal dan mengembalikan StockAdjustmentPayload.

        Args:
            parent: Widget induk dialog.
            item_options: Daftar barang beserta sisa stok FIFO saat ini.
            preselected_item_id: ID barang yang langsung dipilih jika ada.

        Returns:
            StockAdjustmentPayload apabila pengguna menekan Simpan, atau None jika batal.
        """
        dialog = cls(
            item_options=item_options,
            preselected_item_id=preselected_item_id,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_payload()
        return None