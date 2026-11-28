"""Dialog cepat penambahan supplier baru dari halaman Tambah Stok."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog, DialogTitleBarConfig
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
_TEAL = "#94E2D5"
_PEACH = "#FAB387"
_GREEN = "#A6E3A1"
_RED = "#F38BA8"

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICON_STORE = (
    '<path d="M3 9l1.6-5.2A1.2 1.2 0 0 1 5.75 3h12.5a1.2 1.2 0 0 1 1.15.8L21 9"/>'
    '<path d="M3 9h18v1.5a2.5 2.5 0 0 1-4.5 1.5 2.5 2.5 0 0 1-4.5 0 '
    '2.5 2.5 0 0 1-4.5 0A2.5 2.5 0 0 1 3 10.5z"/>'
    '<path d="M5 12.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7.5"/>'
    '<path d="M10 21v-4.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V21"/>'
)
_ICON_BUILDING = (
    '<rect x="4" y="2" width="16" height="20" rx="2"/>'
    '<path d="M9 22v-4h6v4"/>'
    '<path d="M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01'
    'M8 14h.01M12 14h.01M16 14h.01"/>'
)
_ICON_PHONE = (
    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 '
    "19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3"
    "a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91"
    "a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7"
    'A2 2 0 0 1 22 16.92z"/>'
)
_ICON_PIN = (
    '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/>'
    '<circle cx="12" cy="10" r="3"/>'
)
_ICON_ALERT = (
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 8v4"/><path d="M12 16h.01"/>'
)
_ICON_INFO = (
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 16v-4"/><path d="M12 8h.01"/>'
)
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
_ICON_CLOSE = '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>'
_ICON_CARD = (
    '<rect x="3" y="4" width="18" height="16" rx="2"/>'
    '<circle cx="9" cy="10" r="2"/>'
    '<path d="M15 8h2M15 12h2M7 16h10"/>'
)


_DIALOG_QSS = f"""
QWidget#CustomDialogContent {{
    background-color: transparent;
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
}}

/* ---------- Header ---------- */
QFrame#headerCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2E89B4FA, stop:0.55 #22CBA6F7, stop:1 #14F5C2E7);
    border: 1px solid #4D89B4FA;
    border-radius: 14px;
}}
QLabel#headerBadge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_BLUE}, stop:1 {_MAUVE});
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

/* ---------- Kartu form ---------- */
QFrame#formCard {{
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
QFrame#sectionDivider {{
    background-color: {_SURFACE0};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QLabel#fieldLabel {{
    color: {_TEXT};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}
QLabel#chipRequired {{
    color: {_RED};
    background-color: #26F38BA8;
    border: 1px solid #59F38BA8;
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#chipOptional {{
    color: {_TEAL};
    background-color: #1F94E2D5;
    border: 1px solid #4D94E2D5;
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
}}

/* ---------- Input ---------- */
QLineEdit#fieldInput {{
    background-color: {_CRUST};
    color: {_TEXT};
    border: 1px solid {_SURFACE1};
    border-radius: 10px;
    padding: 0px 12px 0px 6px;
    min-height: 40px;
    font-size: 13px;
    selection-background-color: {_BLUE};
    selection-color: {_CRUST};
}}
QLineEdit#fieldInput:hover {{
    border: 1px solid {_SURFACE2};
    background-color: #14141F;
}}
QLineEdit#fieldInput:focus {{
    border: 1px solid {_BLUE};
    background-color: #161625;
}}
QLineEdit#fieldInput[invalid="true"] {{
    border: 1px solid {_RED};
    background-color: #1AF38BA8;
}}

/* ---------- Pesan error ---------- */
QLabel#errorLabel {{
    color: {_RED};
    background-color: #1FF38BA8;
    border: 1px solid #59F38BA8;
    border-radius: 10px;
    padding: 9px 12px 9px 38px;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#errorIcon {{
    background: transparent;
    border: none;
    padding: 0px;
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
        stop:0 {_BLUE}, stop:1 {_LAVENDER});
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
        stop:0 #A6C8FF, stop:1 {_MAUVE});
}}
QPushButton#primaryBtn:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #74A0E8, stop:1 #A3AEF0);
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


class QuickSupplierDialog(CustomDialog):
    """Dialog cepat untuk menambahkan supplier baru langsung dari halaman kulakan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi QuickSupplierDialog.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self.setWindowTitle("Tambah Supplier Baru")
        self.setMinimumWidth(440)

        content = self.content_widget
        content.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        self.setLayout(layout)

        layout.addWidget(self._build_header(content))

        card = QFrame(content)
        card.setObjectName("formCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(14)

        section_row = QHBoxLayout()
        section_row.setSpacing(8)
        section_icon = QLabel(card)
        section_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=2.0, body=_ICON_CARD),
                size=14,
                dpr=3.0,
            )
        )
        section_icon.setStyleSheet("background: transparent;")
        section_title = QLabel("INFORMASI SUPPLIER", card)
        section_title.setObjectName("sectionTitle")
        section_row.addWidget(section_icon)
        section_row.addWidget(section_title)
        section_row.addStretch(1)
        card_layout.addLayout(section_row)

        divider = QFrame(card)
        divider.setObjectName("sectionDivider")
        card_layout.addWidget(divider)

        self.name_input = QLineEdit(card)
        self.name_input.setPlaceholderText("Contoh: CV Kertas Nusantara")
        self.phone_input = QLineEdit(card)
        self.phone_input.setPlaceholderText("Contoh: 0812-3456-7890 (opsional)")
        self.address_input = QLineEdit(card)
        self.address_input.setPlaceholderText("Alamat toko / distributor (opsional)")

        card_layout.addWidget(
            self._build_field(
                card, "Nama Supplier", True, _ICON_BUILDING, _BLUE, self.name_input
            )
        )
        card_layout.addWidget(
            self._build_field(
                card, "No. Telepon", False, _ICON_PHONE, _GREEN, self.phone_input
            )
        )
        card_layout.addWidget(
            self._build_field(
                card, "Alamat", False, _ICON_PIN, _PEACH, self.address_input
            )
        )
        layout.addWidget(card)

        self.error_label = QLabel("", content)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        error_icon_layout = QHBoxLayout(self.error_label)
        error_icon_layout.setContentsMargins(12, 0, 0, 0)
        error_icon = QLabel(self.error_label)
        error_icon.setObjectName("errorIcon")
        error_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_RED, stroke=2.0, body=_ICON_ALERT),
                size=16,
                dpr=3.0,
            )
        )
        error_icon_layout.addWidget(error_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        error_icon_layout.addStretch(1)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

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
        hint_label = QLabel("Kolom bertanda Wajib harus diisi", content)
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

        save_btn = QPushButton("Simpan Supplier", content)
        save_btn.setObjectName("primaryBtn")
        save_btn.setIcon(
            build_svg_icon(
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.6, body=_ICON_CHECK),
                size=16,
                dpr=3.0,
            )
        )
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.name_input.textChanged.connect(self._clear_name_error)
        self.name_input.setFocus()

    def _build_header(self, parent: QWidget) -> QFrame:
        """Membangun kartu header bergradasi dengan badge ikon.

        Args:
            parent: Widget induk header.

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
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.1, body=_ICON_STORE),
                size=26,
                dpr=3.0,
            )
        )
        glow = QGraphicsDropShadowEffect(badge)
        glow.setBlurRadius(26)
        glow.setOffset(0, 4)
        glow.setColor(QColor(137, 180, 250, 120))
        badge.setGraphicsEffect(glow)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        title = QLabel("Tambah Supplier Baru", header)
        title.setObjectName("headerTitle")
        subtitle = QLabel(
            "Supplier baru langsung tersedia dan dipilih pada nota aktif.", header
        )
        subtitle.setObjectName("headerSubtitle")
        subtitle.setWordWrap(True)
        text_box.addStretch(1)
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        text_box.addStretch(1)

        header_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(text_box, 1)
        return header

    def _build_field(
        self,
        parent: QWidget,
        label_text: str,
        required: bool,
        icon_body: str,
        icon_color: str,
        line_edit: QLineEdit,
    ) -> QWidget:
        """Membangun satu blok field: label, chip status, dan input berikon.

        Args:
            parent: Widget induk field.
            label_text: Teks label field.
            required: True jika field wajib diisi.
            icon_body: Potongan SVG ikon di dalam input.
            icon_color: Warna ikon input.
            line_edit: QLineEdit yang ditampilkan pada field.

        Returns:
            Widget berisi satu field lengkap.
        """
        wrapper = QWidget(parent)
        wrapper.setStyleSheet("background: transparent;")
        box = QVBoxLayout(wrapper)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        label = QLabel(label_text, wrapper)
        label.setObjectName("fieldLabel")
        chip = QLabel("Wajib" if required else "Opsional", wrapper)
        chip.setObjectName("chipRequired" if required else "chipOptional")
        top.addWidget(label)
        top.addWidget(chip)
        top.addStretch(1)

        line_edit.setParent(wrapper)
        line_edit.setObjectName("fieldInput")
        line_edit.setClearButtonEnabled(True)
        line_edit.addAction(
            build_svg_icon(
                _SVG_TEMPLATE.format(color=icon_color, stroke=2.0, body=icon_body),
                size=16,
                dpr=3.0,
            ),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        label.setBuddy(line_edit)

        box.addLayout(top)
        box.addWidget(line_edit)
        return wrapper

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        """Memaksa QSS diterapkan ulang setelah properti dinamis berubah.

        Args:
            widget: Widget yang akan di-repolish.
        """
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _clear_name_error(self, _text: str) -> None:
        """Menghapus sorotan merah dan pesan error saat nama mulai diisi.

        Args:
            _text: Teks terbaru input nama (tidak digunakan).
        """
        if self.name_input.property("invalid"):
            self.name_input.setProperty("invalid", False)
            self._repolish(self.name_input)
            self.error_label.setVisible(False)

    def _validate_and_accept(self) -> None:
        """Memvalidasi nama supplier wajib diisi sebelum menutup dialog."""
        if not self.name_input.text().strip():
            self.error_label.setText("Nama supplier wajib diisi.")
            self.error_label.setVisible(True)
            self.name_input.setProperty("invalid", True)
            self._repolish(self.name_input)
            self.name_input.setFocus()
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str]:
        """Mengambil nilai input nama, telepon, dan alamat supplier.

        Returns:
            Tuple (name, phone, address).
        """
        return (
            self.name_input.text().strip(),
            self.phone_input.text().strip(),
            self.address_input.text().strip(),
        )