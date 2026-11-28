"""Dialog penyesuaian harga jual varian satuan barang langsung saat kulakan."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.tambahstok import CurrencySpinBox, ItemUnitOption
from util.customdialog import CustomDialog, DialogTitleBarConfig
from util.helper.formatrupiah import format_qty as format_quantity, format_rupiah
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
_YELLOW = "#F9E2AF"
_RED = "#F38BA8"

_ROW_ACCENTS: tuple[str, ...] = (_BLUE, _GREEN, _PEACH, _MAUVE, _TEAL, _YELLOW)

_MAX_VISIBLE_ROWS = 4

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICON_TAG = (
    '<path d="M12.59 2.59A2 2 0 0 0 11.17 2H4a2 2 0 0 0-2 2v7.17a2 2 0 0 0 '
    '.59 1.42l8.7 8.7a2.43 2.43 0 0 0 3.42 0l6.58-6.58a2.43 2.43 0 0 0 0-3.42z"/>'
    '<circle cx="7.5" cy="7.5" r="1.5"/>'
)
_ICON_BOX = (
    '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8'
    'a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
    '<path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>'
)
_ICON_WALLET = (
    '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3'
    'a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/>'
    '<path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'
)
_ICON_LAYERS = (
    '<path d="m12 2 10 5-10 5L2 7z"/>'
    '<path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>'
)
_ICON_INFO = (
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M12 16v-4"/><path d="M12 8h.01"/>'
)
_ICON_CHECK = '<path d="M20 6 9 17l-5-5"/>'
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


_DIALOG_QSS = f"""
QWidget#CustomDialogContent {{
    background-color: transparent;
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
}}

/* ---------- Header ---------- */
QFrame#headerCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2EA6E3A1, stop:0.55 #2294E2D5, stop:1 #1489B4FA);
    border: 1px solid #4DA6E3A1;
    border-radius: 14px;
}}
QLabel#headerBadge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_GREEN}, stop:1 {_TEAL});
    border-radius: 14px;
}}
QLabel#headerTitle {{
    color: {_TEXT};
    font-size: 17px;
    font-weight: 700;
    background: transparent;
}}
QLabel#headerItemName {{
    color: {_GREEN};
    background-color: #1FA6E3A1;
    border: 1px solid #4DA6E3A1;
    border-radius: 8px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
}}
QLabel#headerSubtitle {{
    color: {_SUBTEXT};
    font-size: 12px;
    background: transparent;
}}

/* ---------- Kartu daftar varian ---------- */
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
QLabel#sectionCount {{
    color: {_LAVENDER};
    background-color: #1FB4BEFE;
    border: 1px solid #4DB4BEFE;
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
}}
QFrame#sectionDivider {{
    background-color: {_SURFACE0};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QScrollArea#unitScroll, QWidget#unitList {{
    background: transparent;
    border: none;
}}

/* ---------- Baris varian ---------- */
QFrame#unitRow {{
    background-color: {_CRUST};
    border: 1px solid {_SURFACE0};
    border-radius: 12px;
}}
QFrame#unitRow:hover {{
    border: 1px solid {_SURFACE1};
}}
QLabel#unitName {{
    color: {_TEXT};
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}}
QLabel#convChip {{
    color: {_LAVENDER};
    background-color: #1FB4BEFE;
    border: 1px solid #40B4BEFE;
    border-radius: 7px;
    padding: 0px 7px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#costText {{
    color: {_SUBTEXT};
    font-size: 11px;
    background: transparent;
}}
QLabel#costIcon {{
    background: transparent;
}}
QLabel#marginChip {{
    border-radius: 7px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
    color: {_SUBTEXT};
    background-color: #1F7F849C;
    border: 1px solid #407F849C;
}}
QLabel#marginChip[state="up"] {{
    color: {_GREEN};
    background-color: #1FA6E3A1;
    border: 1px solid #4DA6E3A1;
}}
QLabel#marginChip[state="down"] {{
    color: {_RED};
    background-color: #1FF38BA8;
    border: 1px solid #4DF38BA8;
}}
QLabel#marginChip[state="flat"] {{
    color: {_YELLOW};
    background-color: #1FF9E2AF;
    border: 1px solid #4DF9E2AF;
}}

/* ---------- Input harga ---------- */
#priceSpin {{
    background-color: {_MANTLE};
    color: {_TEXT};
    border: 1px solid {_SURFACE1};
    border-radius: 10px;
    padding: 0px 10px;
    font-size: 14px;
    font-weight: 700;
    selection-background-color: {_GREEN};
    selection-color: {_CRUST};
}}
#priceSpin:hover {{
    border: 1px solid {_SURFACE2};
}}
#priceSpin:focus {{
    border: 1px solid {_GREEN};
    background-color: #161625;
}}
#priceSpin::up-button, #priceSpin::down-button {{
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background: transparent;
}}
#priceSpin::up-button {{
    subcontrol-position: top right;
    margin: 4px 4px 0px 0px;
}}
#priceSpin::down-button {{
    subcontrol-position: bottom right;
    margin: 0px 4px 4px 0px;
}}
#priceSpin::up-button:hover, #priceSpin::down-button:hover {{
    background-color: {_SURFACE0};
    border-radius: 5px;
}}

/* ---------- Empty state ---------- */
QLabel#emptyState {{
    color: {_OVERLAY1};
    font-size: 12px;
    background: transparent;
    padding: 18px;
}}

/* ---------- Scrollbar ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0px 2px 0px;
}}
QScrollBar::handle:vertical {{
    background: {_SURFACE1};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {_SURFACE2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0px;
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
        stop:0 {_GREEN}, stop:1 {_TEAL});
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
        stop:0 #BDF0B8, stop:1 #ADEDE3);
}}
QPushButton#primaryBtn:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8CCB87, stop:1 #7BCCBF);
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


class EditSellingPriceDialog(CustomDialog):
    """Dialog penyesuaian harga jual varian satuan barang langsung saat kulakan."""

    def __init__(
        self,
        item_name: str,
        units: list[ItemUnitOption],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi EditSellingPriceDialog.

        Args:
            item_name: Nama barang yang sedang diedit harga jualnya.
            units: Daftar varian satuan milik barang tersebut.
            parent: Widget induk opsional.
        """
        super().__init__(parent, titlebar_config=_TITLEBAR_CONFIG)
        self._spin_by_unit_id: dict[int, CurrencySpinBox] = {}
        self.setWindowTitle(f"Ubah Harga Jual - {item_name}")
        self.setMinimumWidth(500)

        content = self.content_widget
        content.setStyleSheet(_DIALOG_QSS)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        self.setLayout(layout)

        layout.addWidget(self._build_header(content, item_name))

        card = QFrame(content)
        card.setObjectName("formCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(12)

        section_row = QHBoxLayout()
        section_row.setSpacing(8)
        section_icon = QLabel(card)
        section_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=2.0, body=_ICON_LAYERS),
                size=14,
                dpr=3.0,
            )
        )
        section_icon.setStyleSheet("background: transparent;")
        section_title = QLabel("VARIAN SATUAN", card)
        section_title.setObjectName("sectionTitle")
        section_count = QLabel(f"{len(units)} satuan", card)
        section_count.setObjectName("sectionCount")
        section_row.addWidget(section_icon)
        section_row.addWidget(section_title)
        section_row.addStretch(1)
        section_row.addWidget(section_count)
        card_layout.addLayout(section_row)

        divider = QFrame(card)
        divider.setObjectName("sectionDivider")
        card_layout.addWidget(divider)

        list_widget = QWidget()
        list_widget.setObjectName("unitList")
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)

        rows: list[QFrame] = []
        for index, unit in enumerate(units):
            accent = _ROW_ACCENTS[index % len(_ROW_ACCENTS)]
            spin = CurrencySpinBox(parent=list_widget)
            spin.setValue(max(0, unit["selling_price"]))
            row = self._build_unit_row(list_widget, unit, spin, accent)
            list_layout.addWidget(row)
            rows.append(row)
            self._spin_by_unit_id[unit["item_unit_id"]] = spin

        if not units:
            empty = QLabel("Barang ini belum memiliki varian satuan.", list_widget)
            empty.setObjectName("emptyState")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            list_layout.addWidget(empty)

        list_layout.addStretch(1)

        if len(rows) > _MAX_VISIBLE_ROWS:
            scroll = QScrollArea(card)
            scroll.setObjectName("unitScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.viewport().setStyleSheet("background: transparent;")
            scroll.setWidget(list_widget)
            visible_height = sum(
                r.sizeHint().height() for r in rows[:_MAX_VISIBLE_ROWS]
            ) + list_layout.spacing() * (_MAX_VISIBLE_ROWS - 1)
            scroll.setFixedHeight(visible_height + 4)
            card_layout.addWidget(scroll)
        else:
            list_widget.setParent(card)
            card_layout.addWidget(list_widget)

        layout.addWidget(card)

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
        hint_label = QLabel("Margin dihitung dari modal akhir per satuan", content)
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

        save_btn = QPushButton("Simpan Harga Jual", content)
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
        save_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        if self._spin_by_unit_id:
            next(iter(self._spin_by_unit_id.values())).setFocus()

    def _build_header(self, parent: QWidget, item_name: str) -> QFrame:
        """Membangun kartu header bergradasi dengan badge ikon label harga.

        Args:
            parent: Widget induk header.
            item_name: Nama barang yang ditampilkan sebagai chip.

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
                _SVG_TEMPLATE.format(color=_CRUST, stroke=2.1, body=_ICON_TAG),
                size=26,
                dpr=3.0,
            )
        )
        glow = QGraphicsDropShadowEffect(badge)
        glow.setBlurRadius(26)
        glow.setOffset(0, 4)
        glow.setColor(QColor(166, 227, 161, 110))
        badge.setGraphicsEffect(glow)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("Sesuaikan Harga Jual", header)
        title.setObjectName("headerTitle")
        name_chip = QLabel(item_name, header)
        name_chip.setObjectName("headerItemName")
        name_chip.setTextFormat(Qt.TextFormat.PlainText)
        title_row.addWidget(title)
        title_row.addWidget(name_chip)
        title_row.addStretch(1)

        subtitle = QLabel(
            "Perbarui harga jual apabila harga modal dari supplier mengalami perubahan.",
            header,
        )
        subtitle.setObjectName("headerSubtitle")
        subtitle.setWordWrap(True)

        text_box.addStretch(1)
        text_box.addLayout(title_row)
        text_box.addWidget(subtitle)
        text_box.addStretch(1)

        header_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(text_box, 1)
        return header

    def _build_unit_row(
        self,
        parent: QWidget,
        unit: ItemUnitOption,
        spin: CurrencySpinBox,
        accent: str,
    ) -> QFrame:
        """Membangun satu baris varian: badge, info satuan/modal, input dan margin.

        Args:
            parent: Widget induk baris.
            unit: Data varian satuan.
            spin: Spin box harga jual milik varian ini.
            accent: Warna aksen baris.

        Returns:
            QFrame baris varian.
        """
        row = QFrame(parent)
        row.setObjectName("unitRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(12)

        badge = QLabel(row)
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=accent, stroke=2.0, body=_ICON_BOX),
                size=18,
                dpr=3.0,
            )
        )
        badge.setStyleSheet(
            f"background-color: {_alpha(accent, '26')};"
            f"border: 1px solid {_alpha(accent, '4D')};"
            "border-radius: 10px;"
        )

        info = QVBoxLayout()
        info.setSpacing(4)

        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name = QLabel(unit["variant_name"], row)
        name.setObjectName("unitName")
        name.setTextFormat(Qt.TextFormat.PlainText)
        conv = QLabel(f"x{format_quantity(unit['conversion_qty'])}", row)
        conv.setObjectName("convChip")
        name_row.addWidget(name)
        name_row.addWidget(conv)
        name_row.addStretch(1)

        cost = unit["last_unit_cost"]
        cost_row = QHBoxLayout()
        cost_row.setSpacing(5)
        cost_icon = QLabel(row)
        cost_icon.setObjectName("costIcon")
        cost_icon.setPixmap(
            render_svg_pixmap(
                _SVG_TEMPLATE.format(color=_OVERLAY1, stroke=2.0, body=_ICON_WALLET),
                size=12,
                dpr=3.0,
            )
        )
        cost_text = QLabel(f"Modal akhir: {format_rupiah(cost)}", row)
        cost_text.setObjectName("costText")
        cost_row.addWidget(cost_icon)
        cost_row.addWidget(cost_text)
        cost_row.addStretch(1)

        info.addLayout(name_row)
        info.addLayout(cost_row)

        right = QVBoxLayout()
        right.setSpacing(5)
        spin.setParent(row)
        spin.setObjectName("priceSpin")
        spin.setFixedHeight(38)
        spin.setMinimumWidth(180)
        margin_chip = QLabel(row)
        margin_chip.setObjectName("marginChip")
        right.addWidget(spin)
        right.addWidget(margin_chip, 0, Qt.AlignmentFlag.AlignRight)

        row_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addLayout(info, 1)
        row_layout.addLayout(right)

        self._update_margin_chip(margin_chip, spin.value(), cost)
        value_changed = getattr(spin, "valueChanged", None)
        if value_changed is not None:
            value_changed.connect(
                lambda _v, s=spin, c=cost, m=margin_chip: self._update_margin_chip(
                    m, s.value(), c
                )
            )
        return row

    @staticmethod
    def _update_margin_chip(chip: QLabel, price: int, cost: float) -> None:
        """Memperbarui chip margin berdasarkan harga jual dan modal akhir.

        Args:
            chip: Label chip margin.
            price: Harga jual saat ini.
            cost: Modal akhir per satuan.
        """
        if cost <= 0:
            text, state = "Modal belum tercatat", ""
        else:
            diff = price - cost
            pct = f"{abs(diff) / cost * 100:.1f}".replace(".", ",")
            if diff > 0:
                text, state = f"▲ Untung {format_rupiah(diff)} ({pct}%)", "up"
            elif diff < 0:
                text, state = f"▼ Rugi {format_rupiah(-diff)} ({pct}%)", "down"
            else:
                text, state = "● Impas dengan modal", "flat"
        chip.setText(text)
        chip.setProperty("state", state)
        chip.style().unpolish(chip)
        chip.style().polish(chip)

    def get_updated_prices(self) -> dict[int, int]:
        """Mengembalikan peta item_unit_id ke harga jual terbaru hasil input pengguna.

        Returns:
            Dictionary item_unit_id -> selling_price.
        """
        return {
            unit_id: spin.value() for unit_id, spin in self._spin_by_unit_id.items()
        }