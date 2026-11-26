"""Modul dialog formulir tambah dan edit barang fisik berbasis CustomDialog.

Modul ini menyediakan antarmuka modal ringkas untuk mengelola data dasar
barang, variasi multi-satuan jual (item_units), serta input stok awal opsional
untuk layer FIFO tanpa menyertakan logika query basis data secara langsung.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
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
        active_check: Kotak centang status aktif varian satuan.
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

        is_edit = edit_data is not None
        self.setWindowTitle(
            f"Edit Barang - {edit_data.sku}" if edit_data is not None else "Tambah Barang Baru"
        )
        self.setMinimumWidth(680)
        self.resize(700, 520 if not is_edit else 470)

        self._sku_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._category_combo = QComboBox(self)
        self._base_unit_combo = QComboBox(self)
        self._desc_input = QLineEdit(self)
        self._active_checkbox = QCheckBox("Aktif di Katalog Kasir", self)

        self._units_table = QTableWidget(0, 7, self)
        self._add_unit_btn = QPushButton("+ Tambah Satuan", self)

        self._opening_stock_frame = QFrame(self)
        self._opening_qty_spin = QDoubleSpinBox(self._opening_stock_frame)
        self._opening_cost_spin = QDoubleSpinBox(self._opening_stock_frame)

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

    def _setup_ui(self) -> None:
        """Menyusun tata letak formulir yang padat, rapi, dan proporsional."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

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

    def _build_basic_info_section(self) -> QFrame:
        """Membangun kartu isian informasi dasar barang dalam grid dua kolom.

        Returns:
            Frame berisi input SKU, nama, kategori, satuan dasar, dan deskripsi.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self._sku_input.setObjectName("FormInput")
        self._sku_input.setPlaceholderText("Contoh: KRT-A4-70")

        self._name_input.setObjectName("FormInput")
        self._name_input.setPlaceholderText("Nama lengkap barang")

        self._category_combo.setObjectName("FormCombo")
        self._base_unit_combo.setObjectName("FormCombo")

        self._desc_input.setObjectName("FormInput")
        self._desc_input.setPlaceholderText("Catatan atau spesifikasi singkat (opsional)")

        self._active_checkbox.setObjectName("FormCheckbox")
        self._active_checkbox.setChecked(True)

        grid.addWidget(self._make_field_label("Kode SKU *"), 0, 0)
        grid.addWidget(self._make_field_label("Nama Barang *"), 0, 1)
        grid.addWidget(self._sku_input, 1, 0)
        grid.addWidget(self._name_input, 1, 1)

        grid.addWidget(self._make_field_label("Kategori *"), 2, 0)
        grid.addWidget(self._make_field_label("Satuan Dasar *"), 2, 1)
        grid.addWidget(self._category_combo, 3, 0)
        grid.addWidget(self._base_unit_combo, 3, 1)

        grid.addWidget(self._make_field_label("Deskripsi"), 4, 0)
        grid.addWidget(self._make_field_label("Status"), 4, 1)
        grid.addWidget(self._desc_input, 5, 0)
        grid.addWidget(self._active_checkbox, 5, 1)

        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 6)
        return card

    def _build_units_section(self) -> QFrame:
        """Membangun bagian tabel dinamis variasi satuan jual (item_units).

        Returns:
            Frame berisi header tombol tambah satuan dan tabel variasi satuan.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        section_title = QLabel("Variasi Satuan Jual (Multi-Satuan)", card)
        section_title.setObjectName("SectionTitle")

        self._add_unit_btn.setObjectName("SmallSecondaryBtn")
        self._add_unit_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        header_row.addWidget(section_title)
        header_row.addStretch(1)
        header_row.addWidget(self._add_unit_btn)

        self._units_table.setObjectName("UnitEditTable")
        self._units_table.setHorizontalHeaderLabels(
            [
                "Nama Varian",
                "Satuan",
                "Konversi",
                "Harga Jual",
                "Utama",
                "Aktif",
                "",
            ]
        )
        self._units_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._units_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._units_table.setShowGrid(False)
        self._units_table.setMinimumHeight(150)

        v_header = self._units_table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(32)

        h_header = self._units_table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(26)
            h_header.setHighlightSections(False)
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            self._units_table.setColumnWidth(1, 105)
            self._units_table.setColumnWidth(2, 84)
            self._units_table.setColumnWidth(3, 122)
            self._units_table.setColumnWidth(4, 48)
            self._units_table.setColumnWidth(5, 44)
            self._units_table.setColumnWidth(6, 32)

        layout.addLayout(header_row)
        layout.addWidget(self._units_table, 1)
        return card

    def _build_opening_stock_section(self) -> QFrame:
        """Membangun bagian input stok awal opsional khusus mode tambah barang.

        Returns:
            Frame berisi input kuantitas stok awal dan harga modal satuan.
        """
        self._opening_stock_frame.setObjectName("FormSectionCard")
        grid = QGridLayout(self._opening_stock_frame)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        title = QLabel("Stok Awal FIFO (Opsional)", self._opening_stock_frame)
        title.setObjectName("SectionTitle")

        self._opening_qty_spin.setObjectName("FormSpin")
        self._opening_qty_spin.setRange(0.0, 1_000_000.0)
        self._opening_qty_spin.setDecimals(2)
        self._opening_qty_spin.setValue(0.0)

        self._opening_cost_spin.setObjectName("FormSpin")
        self._opening_cost_spin.setRange(0.0, 999_999_999.0)
        self._opening_cost_spin.setDecimals(2)
        self._opening_cost_spin.setPrefix("Rp ")
        self._opening_cost_spin.setSingleStep(100.0)
        self._opening_cost_spin.setValue(0.0)

        grid.addWidget(title, 0, 0, 1, 2)
        grid.addWidget(self._make_field_label("Qty Awal (Satuan Dasar)"), 1, 0)
        grid.addWidget(self._make_field_label("Harga Modal / Satuan Dasar"), 1, 1)
        grid.addWidget(self._opening_qty_spin, 2, 0)
        grid.addWidget(self._opening_cost_spin, 2, 1)
        return self._opening_stock_frame

    def _build_footer_actions(self) -> QHBoxLayout:
        """Membangun baris tombol aksi Batal dan Simpan pada bagian bawah dialog.

        Returns:
            QHBoxLayout berisi tombol aksi sejajar kanan.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)

        self._cancel_btn.setObjectName("CancelBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._save_btn.setObjectName("SaveBtn")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        footer.addStretch(1)
        footer.addWidget(self._cancel_btn)
        footer.addWidget(self._save_btn)
        return footer

    def _make_field_label(self, text: str) -> QLabel:
        """Membuat label teks ringkas untuk judul field formulir.

        Args:
            text: Teks label kolom masukan.

        Returns:
            Widget QLabel bergaya seragam.
        """
        label = QLabel(text, self)
        label.setObjectName("FieldLabel")
        return label

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #181825;
                color: #CDD6F4;
            }
            QFrame#FormSectionCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QLabel#SectionTitle {
                color: #CDD6F4;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#FieldLabel {
                color: #9399B2;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#FormErrorLabel {
                background-color: rgba(239, 68, 68, 0.14);
                color: #FCA5A5;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLineEdit#FormInput,
            QComboBox#FormCombo,
            QDoubleSpinBox#FormSpin,
            QSpinBox#CellSpin,
            QDoubleSpinBox#CellDoubleSpin,
            QLineEdit#CellInput,
            QComboBox#CellCombo {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FormInput:focus,
            QComboBox#FormCombo:focus,
            QDoubleSpinBox#FormSpin:focus,
            QSpinBox#CellSpin:focus,
            QDoubleSpinBox#CellDoubleSpin:focus,
            QLineEdit#CellInput:focus,
            QComboBox#CellCombo:focus {
                border: 1px solid #3B82F6;
            }
            QComboBox#FormCombo:disabled {
                color: #6C7086;
                background-color: #161622;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QCheckBox#FormCheckbox {
                color: #CDD6F4;
                font-size: 12px;
                spacing: 6px;
                background: transparent;
            }
            QTableWidget#UnitEditTable {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 11px;
            }
            QTableWidget#UnitEditTable QHeaderView::section {
                background-color: #252638;
                color: #9399B2;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 3px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#SmallSecondaryBtn {
                background-color: #252638;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 4px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#SmallSecondaryBtn:hover {
                background-color: #313244;
            }
            QPushButton#RemoveRowBtn {
                background-color: rgba(239, 68, 68, 0.14);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.30);
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#RemoveRowBtn:hover:enabled {
                background-color: #EF4444;
                color: #FFFFFF;
            }
            QPushButton#RemoveRowBtn:disabled {
                background-color: #1E1E2E;
                color: #45475A;
                border-color: #313244;
            }
            QPushButton#CancelBtn {
                background-color: #252638;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CancelBtn:hover {
                background-color: #313244;
            }
            QPushButton#SaveBtn {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#SaveBtn:hover {
                background-color: #2563EB;
            }
            QPushButton#SaveBtn:pressed {
                background-color: #1D4ED8;
            }
            """
        )

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
        """Menghubungkan aksi tombol tambah satuan, batal, dan simpan."""
        self._add_unit_btn.clicked.connect(self._handle_add_empty_unit_row)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._handle_save_clicked)

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
        for unit in self._units:
            unit_combo.addItem(f"{unit.symbol} ({unit.name})", unit.unit_id)
        found_idx = unit_combo.findData(unit_data.unit_id)
        if found_idx >= 0:
            unit_combo.setCurrentIndex(found_idx)

        conv_spin = QDoubleSpinBox(self._units_table)
        conv_spin.setObjectName("CellDoubleSpin")
        conv_spin.setRange(0.001, 1_000_000.0)
        conv_spin.setDecimals(3)
        conv_spin.setValue(max(0.001, float(unit_data.conversion_qty)))

        price_spin = QSpinBox(self._units_table)
        price_spin.setObjectName("CellSpin")
        price_spin.setRange(0, 999_999_999)
        price_spin.setSingleStep(500)
        price_spin.setPrefix("Rp ")
        price_spin.setValue(max(0, int(unit_data.selling_price)))

        radio_wrap = QWidget(self._units_table)
        radio_layout = QHBoxLayout(radio_wrap)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_radio = QRadioButton(radio_wrap)
        default_radio.setChecked(unit_data.is_default)
        self._default_group.addButton(default_radio)
        radio_layout.addWidget(default_radio)

        check_wrap = QWidget(self._units_table)
        check_layout = QHBoxLayout(check_wrap)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        active_check = QCheckBox(check_wrap)
        active_check.setChecked(unit_data.is_active)
        check_layout.addWidget(active_check)

        remove_wrap = QWidget(self._units_table)
        remove_layout = QHBoxLayout(remove_wrap)
        remove_layout.setContentsMargins(2, 2, 2, 2)
        remove_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remove_btn = QPushButton("✕", remove_wrap)
        remove_btn.setObjectName("RemoveRowBtn")
        remove_btn.setFixedSize(24, 22)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def _show_error(self, message: str) -> None:
        """Menampilkan pesan kesalahan validasi secara inline di dalam dialog.

        Args:
            message: Teks pesan kesalahan yang harus diperbaiki pengguna.
        """
        self._error_label.setText(message)
        self._error_label.show()

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