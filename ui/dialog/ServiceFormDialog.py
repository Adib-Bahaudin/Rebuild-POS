"""Modul dialog formulir tambah dan edit layanan jasa berbasis CustomDialog.

Modul ini menyediakan antarmuka modal ringkas untuk mengelola informasi dasar
layanan jasa serta daftar komposisi bahan baku (service_materials) yang akan
memotong stok FIFO saat transaksi berlangsung.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
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
    QPushButton,
    QSpinBox,
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
from util.helper.dialog_form_helper import (
    build_footer_actions,
    make_field_label,
    show_inline_error,
)


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

        is_edit = edit_data is not None
        self.setWindowTitle(
            f"Edit Jasa - {edit_data.sku}"
            if edit_data is not None
            else "Tambah Layanan / Jasa Baru"
        )
        self.setMinimumWidth(620)
        self.resize(650, 450)

        self._sku_input = QLineEdit(self)
        self._name_input = QLineEdit(self)
        self._price_spin = QSpinBox(self)
        self._active_checkbox = QCheckBox("Aktif di Katalog Kasir", self)
        self._desc_input = QLineEdit(self)

        self._materials_table = QTableWidget(0, 3, self)
        self._add_material_btn = QPushButton("+ Tambah Bahan", self)

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

    def _setup_ui(self) -> None:
        """Menyusun tata letak formulir yang padat, rapi, dan proporsional."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_basic_info_section())
        root_layout.addWidget(self._build_materials_section(), 1)

        self._error_label.setObjectName("FormErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root_layout.addWidget(self._error_label)

        root_layout.addLayout(self._build_footer_actions())
        self.setLayout(root_layout)

    def _build_basic_info_section(self) -> QFrame:
        """Membangun kartu isian informasi dasar layanan jasa.

        Returns:
            Frame berisi input SKU, nama jasa, harga jual, status, dan deskripsi.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self._sku_input.setObjectName("FormInput")
        self._sku_input.setPlaceholderText("Contoh: JS-FC-A4")

        self._name_input.setObjectName("FormInput")
        self._name_input.setPlaceholderText("Nama layanan jasa")

        self._price_spin.setObjectName("FormSpin")
        self._price_spin.setRange(0, 999_999_999)
        self._price_spin.setSingleStep(500)
        self._price_spin.setPrefix("Rp ")
        self._price_spin.setValue(0)

        self._active_checkbox.setObjectName("FormCheckbox")
        self._active_checkbox.setChecked(True)

        self._desc_input.setObjectName("FormInput")
        self._desc_input.setPlaceholderText(
            "Keterangan atau syarat layanan (opsional)"
        )

        grid.addWidget(self._make_field_label("Kode SKU *"), 0, 0)
        grid.addWidget(self._make_field_label("Nama Layanan / Jasa *"), 0, 1)
        grid.addWidget(self._sku_input, 1, 0)
        grid.addWidget(self._name_input, 1, 1)

        grid.addWidget(self._make_field_label("Harga Jual *"), 2, 0)
        grid.addWidget(self._make_field_label("Status"), 2, 1)
        grid.addWidget(self._price_spin, 3, 0)
        grid.addWidget(self._active_checkbox, 3, 1)

        grid.addWidget(self._make_field_label("Deskripsi"), 4, 0, 1, 2)
        grid.addWidget(self._desc_input, 5, 0, 1, 2)

        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 6)
        return card

    def _build_materials_section(self) -> QFrame:
        """Membangun bagian tabel dinamis komposisi bahan baku layanan.

        Returns:
            Frame berisi tombol tambah bahan dan tabel komposisi bahan baku.
        """
        card = QFrame(self)
        card.setObjectName("FormSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)

        section_title = QLabel("Komposisi Bahan Baku (Opsional)", card)
        section_title.setObjectName("SectionTitle")

        section_hint = QLabel(
            "Bahan yang ditambahkan akan otomatis memotong stok FIFO per 1x transaksi jasa.",
            card,
        )
        section_hint.setObjectName("SectionHint")

        title_box.addWidget(section_title)
        title_box.addWidget(section_hint)

        self._add_material_btn.setObjectName("SmallSecondaryBtn")
        self._add_material_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_material_btn.setEnabled(len(self._material_options) > 0)
        if not self._material_options:
            self._add_material_btn.setToolTip(
                "Belum ada data barang fisik yang dapat dijadikan bahan baku."
            )

        header_row.addLayout(title_box, 1)
        header_row.addWidget(self._add_material_btn)

        self._materials_table.setObjectName("MaterialEditTable")
        self._materials_table.setHorizontalHeaderLabels(
            ["Barang Bahan Baku", "Takaran / 1x Jasa", ""]
        )
        self._materials_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._materials_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._materials_table.setShowGrid(False)
        self._materials_table.setMinimumHeight(140)

        v_header = self._materials_table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(32)

        h_header = self._materials_table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(26)
            h_header.setHighlightSections(False)
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            self._materials_table.setColumnWidth(1, 145)
            self._materials_table.setColumnWidth(2, 34)

        layout.addLayout(header_row)
        layout.addWidget(self._materials_table, 1)
        return card

    def _build_footer_actions(self) -> QHBoxLayout:
        """Membangun baris tombol aksi Batal dan Simpan pada bagian bawah dialog.

        Returns:
            QHBoxLayout berisi tombol aksi sejajar kanan.
        """
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
            QLabel#SectionHint {
                color: #6C7086;
                font-size: 10px;
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
            QSpinBox#FormSpin,
            QComboBox#CellCombo,
            QDoubleSpinBox#CellDoubleSpin {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FormInput:focus,
            QSpinBox#FormSpin:focus,
            QComboBox#CellCombo:focus,
            QDoubleSpinBox#CellDoubleSpin:focus {
                border: 1px solid #3B82F6;
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
            QTableWidget#MaterialEditTable {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 11px;
            }
            QTableWidget#MaterialEditTable QHeaderView::section {
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
                padding: 4px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#SmallSecondaryBtn:hover:enabled {
                background-color: #313244;
            }
            QPushButton#SmallSecondaryBtn:disabled {
                color: #585B70;
                border-color: #313244;
            }
            QPushButton#RemoveRowBtn {
                background-color: rgba(239, 68, 68, 0.14);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.30);
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#RemoveRowBtn:hover {
                background-color: #EF4444;
                color: #FFFFFF;
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
        for opt in self._material_options:
            label = f"[{opt.sku}] {opt.name} ({opt.base_unit_symbol})"
            item_combo.addItem(label, opt.item_id)

        found_idx = item_combo.findData(item_id)
        if found_idx >= 0:
            item_combo.setCurrentIndex(found_idx)

        qty_spin = QDoubleSpinBox(self._materials_table)
        qty_spin.setObjectName("CellDoubleSpin")
        qty_spin.setRange(0.001, 100_000.0)
        qty_spin.setDecimals(3)
        qty_spin.setSingleStep(1.0)
        qty_spin.setValue(max(0.001, float(quantity)))
        self._sync_qty_suffix(item_combo, qty_spin)

        item_combo.currentIndexChanged.connect(
            lambda _idx=0, combo=item_combo, spin=qty_spin: self._sync_qty_suffix(
                combo,
                spin,
            )
        )

        remove_wrap = QWidget(self._materials_table)
        remove_layout = QHBoxLayout(remove_wrap)
        remove_layout.setContentsMargins(2, 2, 2, 2)
        remove_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        remove_btn = QPushButton("✕", remove_wrap)
        remove_btn.setObjectName("RemoveRowBtn")
        remove_btn.setFixedSize(24, 22)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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