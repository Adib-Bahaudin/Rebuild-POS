"""Modul dialog manajemen master kategori dan satuan berbasis CustomDialog.

Modul ini menyediakan antarmuka modal dua tab bergaya Catppuccin Mocha dengan
ikon SVG inline, kartu formulir berwarna, badge status, dan tabel data yang
rapi. Logika backend, sinyal, dan nilai kembalian tidak berubah.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.manajemen_produk_backend import (
    CategoryRecord,
    ManajemenProdukBackend,
    UnitRecord,
)
from util.customdialog import CustomDialog
from util.helper.svg_helper import render_svg_pixmap


# ---------------------------------------------------------------------------
# Palet warna (Catppuccin Mocha vivid)
# ---------------------------------------------------------------------------
class _C:
    """Konstanta palet warna dialog (Catppuccin Mocha, lebih vivid)."""

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
    BLUE_DARK = "#3B82F6"
    MAUVE = "#CBA6F7"
    GREEN = "#A6E3A1"
    PEACH = "#FAB387"
    YELLOW = "#F9E2AF"
    PINK = "#F38BA8"
    RED = "#F87171"
    TEAL = "#94E2D5"
    SAPPHIRE = "#74C7EC"


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
# Template & kamus SVG inline
# ---------------------------------------------------------------------------
_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS: dict[str, str] = {
    "tag": (
        '<path d="M12 2H7a2 2 0 0 0-2 2v5l9 9a2 2 0 0 0 2.83 0l4.17-4.17'
        'a2 2 0 0 0 0-2.83z"/><circle cx="8.5" cy="8.5" r="1.5"/>'
    ),
    "layers": (
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>'
    ),
    "package": (
        '<polyline points="21 8 21 21 3 21 3 8"/>'
        '<rect x="1" y="3" width="22" height="5"/>'
        '<line x1="10" y1="12" x2="14" y2="12"/>'
    ),
    "ruler": (
        '<path d="M3 21L21 3"/>'
        '<path d="M6.5 17.5l1.5-1.5"/><path d="M10.5 13.5l1.5-1.5"/>'
        '<path d="M14.5 9.5l1.5-1.5"/><path d="M17.5 6.5l1.5-1.5"/>'
        '<path d="M3 17l4 4"/><path d="M17 3l4 4"/>'
    ),
    "edit": (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4z"/>'
    ),
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "save": (
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 3 7 8 15 8"/>'
    ),
    "check": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="m8 12.5 2.8 2.8L16 10"/>'
    ),
    "close": (
        '<circle cx="12" cy="12" r="9"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
    ),
}


def _svg_pixmap(
    icon_key: str,
    size: int = 20,
    color: str = _C.TEXT,
    stroke: str = "2",
) -> QPixmap:
    """Merender ikon SVG inline menjadi QPixmap dengan resolusi 2×.

    Args:
        icon_key: Kunci nama ikon pada kamus _ICONS.
        size: Ukuran piksel persegi output.
        color: Warna stroke ikon dalam format hex.
        stroke: Lebar stroke SVG.

    Returns:
        QPixmap hasil render ikon.
    """
    body = _ICONS.get(icon_key, "")
    svg_str = _SVG_TEMPLATE.format(color=color, stroke=stroke, body=body)
    return render_svg_pixmap(svg_str, size=size)


def _make_icon_badge(
    icon_key: str,
    color: str,
    bg_alpha: float = 0.18,
    icon_size: int = 16,
    badge_size: int = 30,
) -> QLabel:
    """Membuat label lencana ikon berbentuk persegi panjang dengan latar berwarna.

    Args:
        icon_key: Kunci ikon SVG.
        color: Warna stroke ikon dan border badge.
        bg_alpha: Opasitas latar belakang badge.
        icon_size: Ukuran ikon piksel.
        badge_size: Ukuran sisi label badge piksel.

    Returns:
        QLabel bergaya lencana ikon.
    """
    badge = QLabel()
    badge.setFixedSize(badge_size, badge_size)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setPixmap(_svg_pixmap(icon_key, icon_size, color))
    badge.setStyleSheet(
        f"background-color: {_rgba(color, bg_alpha)};"
        f"border: 1px solid {_rgba(color, 0.35)};"
        "border-radius: 7px;"
    )
    return badge


# ---------------------------------------------------------------------------
# Widget header banner bergradien
# ---------------------------------------------------------------------------
class _GradientBanner(QFrame):
    """Frame dengan latar gradien diagonal khas header dialog."""

    def __init__(
        self,
        color_a: str,
        color_b: str,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi banner gradien dengan dua warna.

        Args:
            color_a: Warna awal gradien (#RRGGBB).
            color_b: Warna akhir gradien (#RRGGBB).
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._qa = QColor(color_a)
        self._qb = QColor(color_b)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Menggambar latar gradien pada setiap siklus lukis.

        Args:
            event: Objek event lukis Qt.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, self._qa)
        grad.setColorAt(1.0, self._qb)
        painter.fillRect(self.rect(), grad)
        painter.end()


# ---------------------------------------------------------------------------
# Dialog utama
# ---------------------------------------------------------------------------
class MasterCategoryUnitDialog(CustomDialog):
    """Dialog kustom dua tab bergaya Catppuccin Mocha untuk mengelola master kategori dan satuan.

    Menyediakan formulir tambah/edit inline yang terhubung ke tabel daftar
    kategori serta tabel daftar satuan agar pengelolaan master data cepat
    dan padat informasi. Seluruh sinyal, properti, dan perilaku fungsional
    tidak berubah dari versi sebelumnya.
    """

    def __init__(
        self,
        backend: ManajemenProdukBackend,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi MasterCategoryUnitDialog dengan referensi backend.

        Args:
            backend: Instance ManajemenProdukBackend untuk pembacaan dan
                penyimpanan data kategori maupun satuan.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self._backend: ManajemenProdukBackend = backend
        self._categories: list[CategoryRecord] = []
        self._units: list[UnitRecord] = []
        self._editing_category_id: int | None = None
        self._editing_unit_id: int | None = None

        self.setWindowTitle("Manajemen Kategori & Satuan")
        self.setMinimumSize(680, 500)
        self.resize(760, 580)

        self._tab_cat_btn = QPushButton("Kategori Produk", self)
        self._tab_unit_btn = QPushButton("Satuan (Units)", self)
        self._stack = QStackedWidget(self)

        self._cat_form_title = QLabel("Tambah Kategori Baru", self)
        self._cat_cancel_edit_btn = QPushButton("Batal Edit", self)
        self._cat_name_input = QLineEdit(self)
        self._cat_parent_combo = QComboBox(self)
        self._cat_active_check = QCheckBox("Aktif", self)
        self._cat_save_btn = QPushButton("  Simpan", self)
        self._cat_error_label = QLabel("", self)
        self._cat_table = QTableWidget(0, 4, self)

        self._unit_form_title = QLabel("Tambah Satuan Baru", self)
        self._unit_cancel_edit_btn = QPushButton("Batal Edit", self)
        self._unit_name_input = QLineEdit(self)
        self._unit_symbol_input = QLineEdit(self)
        self._unit_save_btn = QPushButton("  Simpan", self)
        self._unit_error_label = QLabel("", self)
        self._unit_table = QTableWidget(0, 3, self)

        self._footer_info_label = QLabel("0 kategori · 0 satuan", self)
        self._close_btn = QPushButton("  Tutup", self)

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._reload_all_data()

    def _setup_ui(self) -> None:
        """Menyusun tata letak utama dialog dengan pengalih tab dan stack konten."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header_banner())
        root_layout.addWidget(self._build_tab_bar())

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(14, 10, 14, 10)
        inner_layout.setSpacing(8)

        self._stack.addWidget(self._build_categories_tab())
        self._stack.addWidget(self._build_units_tab())
        self._stack.setCurrentIndex(0)

        inner_layout.addWidget(self._stack, 1)
        inner_layout.addLayout(self._build_footer_bar())

        root_layout.addWidget(inner, 1)
        self.setLayout(root_layout)

    def _build_header_banner(self) -> _GradientBanner:
        """Membangun banner header gradien dengan judul dan deskripsi dialog.

        Returns:
            Frame banner bergradien berisi ikon, judul, dan teks petunjuk.
        """
        qa = QColor(_C.BASE)
        qa.setAlpha(200)
        qb = QColor("#1a1535")
        qb.setAlpha(230)
        banner = _GradientBanner(
            color_a="#1E1535",
            color_b="#151030",
            parent=self,
        )
        banner.setFixedHeight(72)
        banner.setObjectName("HeaderBanner")

        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(14)

        icon_badge = _make_icon_badge("layers", _C.MAUVE, icon_size=22, badge_size=44)
        banner_layout.addWidget(icon_badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        title_lbl = QLabel("Manajemen Kategori & Satuan")
        title_lbl.setObjectName("BannerTitle")
        sub_lbl = QLabel("Tambah, ubah, atau hapus master kategori dan satuan produk.")
        sub_lbl.setObjectName("BannerSub")

        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)
        banner_layout.addLayout(text_col, 1)

        pkg_badge = _make_icon_badge("package", _C.TEAL, bg_alpha=0.12, icon_size=18, badge_size=36)
        banner_layout.addWidget(pkg_badge)

        return banner

    def _build_tab_bar(self) -> QFrame:
        """Membangun baris pengalih tab segmented untuk Kategori dan Satuan.

        Returns:
            Frame berisi tombol tab Kategori Produk dan Satuan.
        """
        bar = QFrame(self)
        bar.setObjectName("TabBarFrame")
        bar.setFixedHeight(44)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)

        seg_frame = QFrame(bar)
        seg_frame.setObjectName("TabSegmented")
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(3, 3, 3, 3)
        seg_layout.setSpacing(3)

        self._tab_cat_btn.setObjectName("SegmentBtn")
        self._tab_cat_btn.setCheckable(True)
        self._tab_cat_btn.setChecked(True)
        self._tab_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_cat_btn.setIcon(
            _svg_pixmap("tag", 14, _C.MAUVE).__class__(  # type: ignore[attr-defined]
                _svg_pixmap("tag", 14, _C.MAUVE)
            )
        )

        self._tab_unit_btn.setObjectName("SegmentBtn")
        self._tab_unit_btn.setCheckable(True)
        self._tab_unit_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        seg_layout.addWidget(self._tab_cat_btn)
        seg_layout.addWidget(self._tab_unit_btn)

        hint = QLabel("Perubahan otomatis tersimpan ke database dan memperbarui filter produk.", bar)
        hint.setObjectName("HeaderHint")

        layout.addWidget(seg_frame)
        layout.addStretch(1)
        layout.addWidget(hint)
        return bar

    def _build_categories_tab(self) -> QWidget:
        """Membangun halaman tab pengelolaan master kategori beserta hierarki induk.

        Returns:
            Widget tab berisi formulir inline berkartu dan tabel daftar kategori.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form_card = QFrame(page)
        form_card.setObjectName("FormSectionCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(14, 10, 14, 10)
        form_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        badge = _make_icon_badge("tag", _C.MAUVE, icon_size=14, badge_size=26)
        top_row.addWidget(badge)

        self._cat_form_title.setObjectName("SectionTitle")
        top_row.addWidget(self._cat_form_title)
        top_row.addStretch(1)

        self._cat_cancel_edit_btn.setObjectName("GhostCancelBtn")
        self._cat_cancel_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cat_cancel_edit_btn.setIcon(
            _svg_pixmap("x", 12, _C.PINK).__class__(_svg_pixmap("x", 12, _C.PINK))  # type: ignore[attr-defined]
        )
        self._cat_cancel_edit_btn.hide()
        top_row.addWidget(self._cat_cancel_edit_btn)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        self._cat_name_input.setObjectName("FormInput")
        self._cat_name_input.setPlaceholderText("Contoh: Kertas & Media")

        self._cat_parent_combo.setObjectName("FormCombo")
        self._cat_active_check.setObjectName("FormCheckbox")
        self._cat_active_check.setChecked(True)

        self._cat_save_btn.setObjectName("SaveBtn")
        self._cat_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cat_save_btn.setIcon(
            _svg_pixmap("save", 14, "#FFFFFF").__class__(  # type: ignore[attr-defined]
                _svg_pixmap("save", 14, "#FFFFFF")
            )
        )

        grid.addWidget(self._make_field_label("Nama Kategori *"), 0, 0)
        grid.addWidget(self._make_field_label("Kategori Induk (Opsional)"), 0, 1)
        grid.addWidget(self._make_field_label("Status"), 0, 2)
        grid.addWidget(self._cat_name_input, 1, 0)
        grid.addWidget(self._cat_parent_combo, 1, 1)
        grid.addWidget(self._cat_active_check, 1, 2)
        grid.addWidget(self._cat_save_btn, 1, 3)

        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 0)

        self._cat_error_label.setObjectName("FormErrorLabel")
        self._cat_error_label.setWordWrap(True)
        self._cat_error_label.hide()

        form_layout.addLayout(top_row)
        form_layout.addLayout(grid)
        form_layout.addWidget(self._cat_error_label)

        self._configure_table(
            self._cat_table,
            ["Nama Kategori", "Kategori Induk", "Status", "Aksi"],
        )
        cat_header = self._cat_table.horizontalHeader()
        if cat_header is not None:
            cat_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            cat_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            cat_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            cat_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            self._cat_table.setColumnWidth(2, 76)
            self._cat_table.setColumnWidth(3, 72)

        layout.addWidget(form_card)
        layout.addWidget(self._cat_table, 1)
        return page

    def _build_units_tab(self) -> QWidget:
        """Membangun halaman tab pengelolaan master satuan (units).

        Returns:
            Widget tab berisi formulir inline berkartu dan tabel daftar satuan.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form_card = QFrame(page)
        form_card.setObjectName("FormSectionCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(14, 10, 14, 10)
        form_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        badge = _make_icon_badge("ruler", _C.TEAL, icon_size=14, badge_size=26)
        top_row.addWidget(badge)

        self._unit_form_title.setObjectName("SectionTitle")
        top_row.addWidget(self._unit_form_title)
        top_row.addStretch(1)

        self._unit_cancel_edit_btn.setObjectName("GhostCancelBtn")
        self._unit_cancel_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unit_cancel_edit_btn.setIcon(
            _svg_pixmap("x", 12, _C.PINK).__class__(_svg_pixmap("x", 12, _C.PINK))  # type: ignore[attr-defined]
        )
        self._unit_cancel_edit_btn.hide()
        top_row.addWidget(self._unit_cancel_edit_btn)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        self._unit_name_input.setObjectName("FormInput")
        self._unit_name_input.setPlaceholderText("Contoh: Lembar, Rim, Pieces")

        self._unit_symbol_input.setObjectName("FormInputMono")
        self._unit_symbol_input.setPlaceholderText("Contoh: Lbr, Rim, Pcs")

        self._unit_save_btn.setObjectName("SaveBtn")
        self._unit_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unit_save_btn.setIcon(
            _svg_pixmap("save", 14, "#FFFFFF").__class__(  # type: ignore[attr-defined]
                _svg_pixmap("save", 14, "#FFFFFF")
            )
        )

        grid.addWidget(self._make_field_label("Nama Satuan *"), 0, 0)
        grid.addWidget(self._make_field_label("Simbol Singkat *"), 0, 1)
        grid.addWidget(self._unit_name_input, 1, 0)
        grid.addWidget(self._unit_symbol_input, 1, 1)
        grid.addWidget(self._unit_save_btn, 1, 2)

        grid.setColumnStretch(0, 5)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 0)

        self._unit_error_label.setObjectName("FormErrorLabel")
        self._unit_error_label.setWordWrap(True)
        self._unit_error_label.hide()

        form_layout.addLayout(top_row)
        form_layout.addLayout(grid)
        form_layout.addWidget(self._unit_error_label)

        self._configure_table(
            self._unit_table,
            ["Nama Satuan", "Simbol", "Aksi"],
        )
        unit_header = self._unit_table.horizontalHeader()
        if unit_header is not None:
            unit_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            unit_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            unit_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            self._unit_table.setColumnWidth(1, 130)
            self._unit_table.setColumnWidth(2, 72)

        layout.addWidget(form_card)
        layout.addWidget(self._unit_table, 1)
        return page

    def _build_footer_bar(self) -> QHBoxLayout:
        """Membangun baris bawah dialog berisi ringkasan jumlah dan tombol Tutup.

        Returns:
            QHBoxLayout berisi informasi jumlah master data dan tombol tutup.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(10)

        dot_lbl = _make_icon_badge("layers", _C.BLUE, bg_alpha=0.12, icon_size=12, badge_size=22)
        footer.addWidget(dot_lbl)

        self._footer_info_label.setObjectName("FooterInfoLabel")
        footer.addWidget(self._footer_info_label)
        footer.addStretch(1)

        self._close_btn.setObjectName("CloseFooterBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setIcon(
            _svg_pixmap("close", 14, _C.SUBTEXT).__class__(  # type: ignore[attr-defined]
                _svg_pixmap("close", 14, _C.SUBTEXT)
            )
        )
        footer.addWidget(self._close_btn)
        return footer

    def _make_field_label(self, text: str) -> QLabel:
        """Membuat label teks ringkas untuk judul kolom masukan.

        Args:
            text: Teks judul kolom masukan.

        Returns:
            Widget QLabel bergaya seragam.
        """
        label = QLabel(text, self)
        label.setObjectName("FieldLabel")
        return label

    @staticmethod
    def _configure_table(table: QTableWidget, headers: list[str]) -> None:
        """Mengonfigurasi pengaturan dasar tabel daftar master data.

        Args:
            table: Objek QTableWidget target.
            headers: Daftar teks judul kolom tabel.
        """
        table.setObjectName("MasterDataTable")
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        v_header = table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(32)

        h_header = table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(30)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS Catppuccin Mocha pada seluruh widget dialog."""
        mauve_bg = _rgba(_C.MAUVE, 0.14)
        mauve_border = _rgba(_C.MAUVE, 0.35)
        teal_bg = _rgba(_C.TEAL, 0.14)
        teal_border = _rgba(_C.TEAL, 0.35)
        blue_sel = _rgba(_C.BLUE_DARK, 0.22)
        red_bg = _rgba(_C.RED, 0.14)
        red_border = _rgba(_C.RED, 0.35)
        edit_bg = _rgba(_C.BLUE_DARK, 0.14)
        edit_border = _rgba(_C.BLUE_DARK, 0.35)
        green_bg = _rgba(_C.GREEN, 0.14)
        green_border = _rgba(_C.GREEN, 0.30)

        self.content_widget.setStyleSheet(
            f"""
            QWidget#CustomDialogContent {{
                background-color: {_C.BASE};
                color: {_C.TEXT};
            }}

            QFrame#HeaderBanner {{
                border-bottom: 1px solid {_C.BORDER};
                border-radius: 0px;
            }}

            QLabel#BannerTitle {{
                color: {_C.TEXT};
                font-size: 14px;
                font-weight: 700;
                background: transparent;
            }}

            QLabel#BannerSub {{
                color: {_C.MUTED};
                font-size: 10px;
                background: transparent;
            }}

            QFrame#TabBarFrame {{
                background-color: {_C.SURFACE};
                border-bottom: 1px solid {_C.BORDER};
                border-radius: 0px;
            }}

            QFrame#TabSegmented {{
                background-color: {_C.BASE};
                border: 1px solid {_C.BORDER};
                border-radius: 7px;
            }}

            QPushButton#SegmentBtn {{
                background-color: transparent;
                color: {_C.MUTED};
                border: none;
                border-radius: 5px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 600;
            }}

            QPushButton#SegmentBtn:hover {{
                color: {_C.TEXT};
                background-color: {_rgba(_C.MAUVE, 0.10)};
            }}

            QPushButton#SegmentBtn:checked {{
                background-color: {_C.BLUE_DARK};
                color: #FFFFFF;
            }}

            QLabel#HeaderHint {{
                color: {_C.MUTED};
                font-size: 10px;
                background: transparent;
            }}

            QFrame#FormSectionCard {{
                background-color: {_C.SURFACE};
                border: 1px solid {_C.BORDER};
                border-radius: 10px;
            }}

            QLabel#SectionTitle {{
                color: {_C.TEXT};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}

            QLabel#FieldLabel {{
                color: {_C.SUBTEXT};
                font-size: 10px;
                font-weight: 600;
                background: transparent;
            }}

            QLabel#FormErrorLabel {{
                background-color: {red_bg};
                color: {_C.RED};
                border: 1px solid {red_border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }}

            QLineEdit#FormInput, QComboBox#FormCombo {{
                background-color: {_C.BASE};
                color: {_C.TEXT};
                border: 1px solid {_C.BORDER};
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 12px;
                min-height: 24px;
            }}

            QLineEdit#FormInput:focus, QComboBox#FormCombo:focus {{
                border: 1px solid {_C.BLUE_DARK};
                background-color: {_rgba(_C.BLUE_DARK, 0.06)};
            }}

            QLineEdit#FormInputMono {{
                background-color: {_C.BASE};
                color: {_C.TEAL};
                border: 1px solid {_C.BORDER};
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                min-height: 24px;
            }}

            QLineEdit#FormInputMono:focus {{
                border: 1px solid {_C.TEAL};
                background-color: {teal_bg};
            }}

            QComboBox QAbstractItemView {{
                background-color: {_C.SURFACE};
                color: {_C.TEXT};
                border: 1px solid {_C.BORDER};
                selection-background-color: {_C.BLUE_DARK};
                selection-color: #FFFFFF;
                outline: none;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}

            QCheckBox#FormCheckbox {{
                color: {_C.TEXT};
                font-size: 12px;
                spacing: 6px;
                background: transparent;
            }}

            QCheckBox#FormCheckbox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {_C.BORDER};
                border-radius: 4px;
                background-color: {_C.BASE};
            }}

            QCheckBox#FormCheckbox::indicator:checked {{
                background-color: {_C.BLUE_DARK};
                border-color: {_C.BLUE_DARK};
            }}

            QPushButton#SaveBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_C.BLUE_DARK}, stop:1 #7C3AED);
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 5px 16px;
                font-size: 11px;
                font-weight: 700;
                min-height: 24px;
            }}

            QPushButton#SaveBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #6D28D9);
            }}

            QPushButton#SaveBtn:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #5B21B6);
            }}

            QPushButton#GhostCancelBtn {{
                background-color: {red_bg};
                color: {_C.RED};
                border: 1px solid {red_border};
                border-radius: 5px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 600;
            }}

            QPushButton#GhostCancelBtn:hover {{
                background-color: {_rgba(_C.RED, 0.25)};
                color: #FFFFFF;
            }}

            QTableWidget#MasterDataTable {{
                background-color: {_C.SURFACE};
                alternate-background-color: {_rgba(_C.SURFACE_HI, 0.60)};
                color: {_C.TEXT};
                border: 1px solid {_C.BORDER};
                border-radius: 8px;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: {blue_sel};
                selection-color: {_C.TEXT};
            }}

            QTableWidget#MasterDataTable::item {{
                padding: 2px 10px;
                border-bottom: 1px solid {_rgba(_C.BORDER, 0.5)};
            }}

            QTableWidget#MasterDataTable::item:selected {{
                background-color: {blue_sel};
                color: {_C.TEXT};
            }}

            QTableWidget#MasterDataTable QHeaderView::section {{
                background-color: {_C.SURFACE_HI};
                color: {_C.SUBTEXT};
                border: none;
                border-bottom: 1px solid {_C.BORDER};
                padding: 4px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}

            QPushButton#RowActionEdit {{
                background-color: {edit_bg};
                color: {_C.BLUE};
                border: 1px solid {edit_border};
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 600;
            }}

            QPushButton#RowActionEdit:hover {{
                background-color: {_C.BLUE_DARK};
                color: #FFFFFF;
                border-color: {_C.BLUE_DARK};
            }}

            QLabel#FooterInfoLabel {{
                color: {_C.SUBTEXT};
                font-size: 11px;
                background: transparent;
            }}

            QPushButton#CloseFooterBtn {{
                background-color: {_C.SURFACE_HI};
                color: {_C.SUBTEXT};
                border: 1px solid {_C.BORDER_HI};
                border-radius: 6px;
                padding: 5px 18px;
                font-size: 12px;
                font-weight: 600;
            }}

            QPushButton#CloseFooterBtn:hover {{
                background-color: {_C.BORDER};
                color: {_C.TEXT};
            }}

            QScrollBar:vertical {{
                background: {_C.BASE};
                width: 8px;
                border-radius: 4px;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background: {_C.BORDER_HI};
                border-radius: 4px;
                min-height: 24px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {_C.MUTED};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            """
        )

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh event tombol tab, formulir, dan tutup."""
        self._tab_cat_btn.clicked.connect(lambda _checked=False: self._switch_tab(0))
        self._tab_unit_btn.clicked.connect(lambda _checked=False: self._switch_tab(1))

        self._cat_save_btn.clicked.connect(self._handle_save_category)
        self._cat_name_input.returnPressed.connect(self._handle_save_category)
        self._cat_cancel_edit_btn.clicked.connect(self._reset_category_form)

        self._unit_save_btn.clicked.connect(self._handle_save_unit)
        self._unit_symbol_input.returnPressed.connect(self._handle_save_unit)
        self._unit_cancel_edit_btn.clicked.connect(self._reset_unit_form)

        self._close_btn.clicked.connect(self.accept)

    def _switch_tab(self, index: int) -> None:
        """Mengubah tab aktif antara Kategori Produk dan Satuan.

        Args:
            index: Indeks tab tujuan (0 untuk Kategori, 1 untuk Satuan).
        """
        self._tab_cat_btn.setChecked(index == 0)
        self._tab_unit_btn.setChecked(index == 1)
        self._stack.setCurrentIndex(index)

    def _reload_all_data(self) -> None:
        """Memuat ulang daftar kategori dan satuan terbaru dari repository."""
        self._categories = self._backend.repository.fetch_categories()
        self._units = self._backend.repository.fetch_units()
        self._populate_parent_combo()
        self._render_categories_table()
        self._render_units_table()
        self._footer_info_label.setText(
            f"{len(self._categories)} kategori · {len(self._units)} satuan"
        )

    def _populate_parent_combo(self, exclude_id: int | None = None) -> None:
        """Mengisi dropdown kategori induk sambil mengecualikan kategori yang sedang diedit.

        Args:
            exclude_id: ID kategori yang sedang diedit agar tidak menunjuk dirinya sendiri.
        """
        current_selection = self._cat_parent_combo.currentData()
        self._cat_parent_combo.clear()
        self._cat_parent_combo.addItem("Tanpa Induk (Kategori Utama)", None)

        for cat in self._categories:
            if exclude_id is not None and cat.category_id == exclude_id:
                continue
            label = f"{cat.name} (Nonaktif)" if not cat.is_active else cat.name
            self._cat_parent_combo.addItem(label, cat.category_id)

        restored_idx = self._cat_parent_combo.findData(current_selection)
        self._cat_parent_combo.setCurrentIndex(max(0, restored_idx))

    def _create_status_badge(self, is_active: bool) -> QWidget:
        """Membuat widget badge status Aktif atau Nonaktif untuk sel tabel.

        Args:
            is_active: Status aktif kategori.

        Returns:
            Widget kontainer berisi label badge status berwarna.
        """
        container = QWidget(self)
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("● Aktif" if is_active else "○ Arsip", container)
        if is_active:
            badge.setStyleSheet(
                f"background-color: {_rgba(_C.GREEN, 0.16)};"
                f"color: {_C.GREEN};"
                "border: 1px solid " + _rgba(_C.GREEN, 0.35) + ";"
                "border-radius: 4px; padding: 1px 7px; font-size: 10px; font-weight: 700;"
            )
        else:
            badge.setStyleSheet(
                f"background-color: {_rgba(_C.MUTED, 0.14)};"
                f"color: {_C.MUTED};"
                "border: 1px solid " + _rgba(_C.MUTED, 0.30) + ";"
                "border-radius: 4px; padding: 1px 7px; font-size: 10px; font-weight: 700;"
            )
        layout.addWidget(badge)
        return container

    def _render_categories_table(self) -> None:
        """Merender seluruh data master kategori ke dalam tabel kategori."""
        self._cat_table.setRowCount(len(self._categories))
        for idx, cat in enumerate(self._categories):
            name_item = QTableWidgetItem(cat.name)
            parent_text = cat.parent_name if cat.parent_name else "—"
            parent_item = QTableWidgetItem(parent_text)
            parent_item.setForeground(QColor(_C.MUTED))

            edit_wrap = QWidget(self._cat_table)
            edit_wrap.setStyleSheet("background: transparent;")
            edit_layout = QHBoxLayout(edit_wrap)
            edit_layout.setContentsMargins(4, 3, 4, 3)
            edit_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_btn = QPushButton("Edit", edit_wrap)
            edit_btn.setObjectName("RowActionEdit")
            edit_btn.setFixedHeight(22)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(
                lambda _checked=False, record=cat: self._start_edit_category(record)
            )
            edit_layout.addWidget(edit_btn)

            self._cat_table.setItem(idx, 0, name_item)
            self._cat_table.setItem(idx, 1, parent_item)
            self._cat_table.setCellWidget(idx, 2, self._create_status_badge(cat.is_active))
            self._cat_table.setCellWidget(idx, 3, edit_wrap)

    def _render_units_table(self) -> None:
        """Merender seluruh data master satuan ke dalam tabel satuan."""
        self._unit_table.setRowCount(len(self._units))
        mono_font = QFont("Consolas", 9)

        for idx, unit in enumerate(self._units):
            name_item = QTableWidgetItem(unit.name)
            symbol_item = QTableWidgetItem(unit.symbol)
            symbol_item.setFont(mono_font)
            symbol_item.setForeground(QColor(_C.TEAL))

            edit_wrap = QWidget(self._unit_table)
            edit_wrap.setStyleSheet("background: transparent;")
            edit_layout = QHBoxLayout(edit_wrap)
            edit_layout.setContentsMargins(4, 3, 4, 3)
            edit_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_btn = QPushButton("Edit", edit_wrap)
            edit_btn.setObjectName("RowActionEdit")
            edit_btn.setFixedHeight(22)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(
                lambda _checked=False, record=unit: self._start_edit_unit(record)
            )
            edit_layout.addWidget(edit_btn)

            self._unit_table.setItem(idx, 0, name_item)
            self._unit_table.setItem(idx, 1, symbol_item)
            self._unit_table.setCellWidget(idx, 2, edit_wrap)

    def _start_edit_category(self, record: CategoryRecord) -> None:
        """Mengisi formulir inline kategori dengan data baris yang akan diedit.

        Args:
            record: Data CategoryRecord dari baris tabel terpilih.
        """
        self._editing_category_id = record.category_id
        self._cat_form_title.setText(f"Edit Kategori: {record.name}")
        self._cat_save_btn.setText("  Perbarui")
        self._cat_cancel_edit_btn.show()
        self._cat_error_label.hide()

        self._populate_parent_combo(exclude_id=record.category_id)
        self._cat_name_input.setText(record.name)
        parent_idx = self._cat_parent_combo.findData(record.parent_id)
        self._cat_parent_combo.setCurrentIndex(max(0, parent_idx))
        self._cat_active_check.setChecked(record.is_active)
        self._cat_name_input.setFocus()
        self._cat_name_input.selectAll()

    def _reset_category_form(self) -> None:
        """Mengembalikan formulir kategori ke mode tambah baru."""
        self._editing_category_id = None
        self._cat_form_title.setText("Tambah Kategori Baru")
        self._cat_save_btn.setText("  Simpan")
        self._cat_cancel_edit_btn.hide()
        self._cat_error_label.hide()

        self._cat_name_input.clear()
        self._populate_parent_combo(exclude_id=None)
        self._cat_parent_combo.setCurrentIndex(0)
        self._cat_active_check.setChecked(True)

    def _handle_save_category(self) -> None:
        """Memvalidasi input kategori lalu menyimpannya melalui backend."""
        name = self._cat_name_input.text().strip()
        if not name:
            self._cat_error_label.setText("Nama kategori tidak boleh kosong.")
            self._cat_error_label.show()
            self._cat_name_input.setFocus()
            return

        raw_parent = self._cat_parent_combo.currentData()
        parent_id = raw_parent if isinstance(raw_parent, int) else None
        is_active = self._cat_active_check.isChecked()

        saved_id = self._backend.save_category(
            name=name,
            parent_id=parent_id,
            is_active=is_active,
            category_id=self._editing_category_id,
        )
        if saved_id is not None:
            self._reset_category_form()
            self._reload_all_data()

    def _start_edit_unit(self, record: UnitRecord) -> None:
        """Mengisi formulir inline satuan dengan data baris yang akan diedit.

        Args:
            record: Data UnitRecord dari baris tabel terpilih.
        """
        self._editing_unit_id = record.unit_id
        self._unit_form_title.setText(f"Edit Satuan: {record.name}")
        self._unit_save_btn.setText("  Perbarui")
        self._unit_cancel_edit_btn.show()
        self._unit_error_label.hide()

        self._unit_name_input.setText(record.name)
        self._unit_symbol_input.setText(record.symbol)
        self._unit_name_input.setFocus()
        self._unit_name_input.selectAll()

    def _reset_unit_form(self) -> None:
        """Mengembalikan formulir satuan ke mode tambah baru."""
        self._editing_unit_id = None
        self._unit_form_title.setText("Tambah Satuan Baru")
        self._unit_save_btn.setText("  Simpan")
        self._unit_cancel_edit_btn.hide()
        self._unit_error_label.hide()

        self._unit_name_input.clear()
        self._unit_symbol_input.clear()

    def _handle_save_unit(self) -> None:
        """Memvalidasi input satuan lalu menyimpannya melalui backend."""
        name = self._unit_name_input.text().strip()
        symbol = self._unit_symbol_input.text().strip()
        if not name:
            self._unit_error_label.setText("Nama satuan tidak boleh kosong.")
            self._unit_error_label.show()
            self._unit_name_input.setFocus()
            return
        if not symbol:
            self._unit_error_label.setText("Simbol satuan tidak boleh kosong.")
            self._unit_error_label.show()
            self._unit_symbol_input.setFocus()
            return

        saved_id = self._backend.save_unit(
            name=name,
            symbol=symbol,
            unit_id=self._editing_unit_id,
        )
        if saved_id is not None:
            self._reset_unit_form()
            self._reload_all_data()

    @classmethod
    def show_dialog(
        cls,
        parent: QWidget,
        backend: ManajemenProdukBackend,
    ) -> None:
        """Membuka dialog master kategori dan satuan secara modal.

        Metode ini sesuai dengan kontrak MasterDialogHandler pada ManajemenProdukHelper.

        Args:
            parent: Widget induk dialog.
            backend: Instance ManajemenProdukBackend aktif.
        """
        dialog = cls(backend=backend, parent=parent)
        dialog.exec()
