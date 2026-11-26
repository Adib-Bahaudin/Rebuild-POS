"""Modul dialog manajemen master kategori dan satuan berbasis CustomDialog.

Modul ini menyediakan antarmuka modal dua tab untuk menambah dan memperbarui
data kategori (termasuk hierarki parent_id dan status aktif) serta data satuan
(nama dan simbol) secara langsung melalui ManajemenProdukBackend.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
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


class MasterCategoryUnitDialog(CustomDialog):
    """Dialog kustom dua tab untuk mengelola master kategori dan satuan.

    Menyediakan formulir tambah/edit inline yang terhubung ke tabel daftar
    kategori serta tabel daftar satuan agar pengelolaan master data cepat
    dan padat informasi.
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
        self.setMinimumSize(640, 450)
        self.resize(680, 490)

        self._tab_cat_btn = QPushButton("Kategori Produk", self)
        self._tab_unit_btn = QPushButton("Satuan (Units)", self)
        self._stack = QStackedWidget(self)

        self._cat_form_title = QLabel("Tambah Kategori Baru", self)
        self._cat_cancel_edit_btn = QPushButton("Batal Edit", self)
        self._cat_name_input = QLineEdit(self)
        self._cat_parent_combo = QComboBox(self)
        self._cat_active_check = QCheckBox("Aktif", self)
        self._cat_save_btn = QPushButton("Simpan", self)
        self._cat_error_label = QLabel("", self)
        self._cat_table = QTableWidget(0, 4, self)

        self._unit_form_title = QLabel("Tambah Satuan Baru", self)
        self._unit_cancel_edit_btn = QPushButton("Batal Edit", self)
        self._unit_name_input = QLineEdit(self)
        self._unit_symbol_input = QLineEdit(self)
        self._unit_save_btn = QPushButton("Simpan", self)
        self._unit_error_label = QLabel("", self)
        self._unit_table = QTableWidget(0, 3, self)

        self._footer_info_label = QLabel("0 kategori · 0 satuan", self)
        self._close_btn = QPushButton("Tutup", self)

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._reload_all_data()

    def _setup_ui(self) -> None:
        """Menyusun tata letak utama dialog dengan pengalih tab dan stack konten."""
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_tab_header())

        self._stack.addWidget(self._build_categories_tab())
        self._stack.addWidget(self._build_units_tab())
        self._stack.setCurrentIndex(0)

        root_layout.addWidget(self._stack, 1)
        root_layout.addLayout(self._build_footer_bar())
        self.setLayout(root_layout)

    def _build_tab_header(self) -> QFrame:
        """Membangun baris pengalih tab segmented untuk Kategori dan Satuan.

        Returns:
            Frame berisi tombol tab Kategori Produk dan Satuan.
        """
        bar = QFrame(self)
        bar.setObjectName("TabHeaderBar")
        bar.setFixedHeight(38)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        seg_frame = QFrame(bar)
        seg_frame.setObjectName("TabSegmented")
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self._tab_cat_btn.setObjectName("SegmentBtn")
        self._tab_cat_btn.setCheckable(True)
        self._tab_cat_btn.setChecked(True)
        self._tab_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._tab_unit_btn.setObjectName("SegmentBtn")
        self._tab_unit_btn.setCheckable(True)
        self._tab_unit_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        seg_layout.addWidget(self._tab_cat_btn)
        seg_layout.addWidget(self._tab_unit_btn)

        hint = QLabel(
            "Perubahan otomatis tersimpan ke database dan memperbarui filter produk.",
            bar,
        )
        hint.setObjectName("HeaderHint")

        layout.addWidget(seg_frame)
        layout.addWidget(hint, 1)
        return bar

    def _build_categories_tab(self) -> QWidget:
        """Membangun halaman tab pengelolaan master kategori beserta hierarki induk.

        Returns:
            Widget tab berisi formulir inline dan tabel daftar kategori.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form_card = QFrame(page)
        form_card.setObjectName("FormSectionCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(10, 8, 10, 8)
        form_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        self._cat_form_title.setObjectName("SectionTitle")
        self._cat_cancel_edit_btn.setObjectName("GhostBtn")
        self._cat_cancel_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cat_cancel_edit_btn.hide()
        top_row.addWidget(self._cat_form_title)
        top_row.addStretch(1)
        top_row.addWidget(self._cat_cancel_edit_btn)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self._cat_name_input.setObjectName("FormInput")
        self._cat_name_input.setPlaceholderText("Contoh: Kertas & Media")

        self._cat_parent_combo.setObjectName("FormCombo")
        self._cat_active_check.setObjectName("FormCheckbox")
        self._cat_active_check.setChecked(True)

        self._cat_save_btn.setObjectName("PrimaryBtn")
        self._cat_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

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
            self._cat_table.setColumnWidth(2, 72)
            self._cat_table.setColumnWidth(3, 70)

        layout.addWidget(form_card)
        layout.addWidget(self._cat_table, 1)
        return page

    def _build_units_tab(self) -> QWidget:
        """Membangun halaman tab pengelolaan master satuan (units).

        Returns:
            Widget tab berisi formulir inline dan tabel daftar satuan.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form_card = QFrame(page)
        form_card.setObjectName("FormSectionCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(10, 8, 10, 8)
        form_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        self._unit_form_title.setObjectName("SectionTitle")
        self._unit_cancel_edit_btn.setObjectName("GhostBtn")
        self._unit_cancel_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unit_cancel_edit_btn.hide()
        top_row.addWidget(self._unit_form_title)
        top_row.addStretch(1)
        top_row.addWidget(self._unit_cancel_edit_btn)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self._unit_name_input.setObjectName("FormInput")
        self._unit_name_input.setPlaceholderText("Contoh: Lembar, Rim, Pieces")

        self._unit_symbol_input.setObjectName("FormInput")
        self._unit_symbol_input.setPlaceholderText("Contoh: Lbr, Rim, Pcs")

        self._unit_save_btn.setObjectName("PrimaryBtn")
        self._unit_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

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
            self._unit_table.setColumnWidth(1, 120)
            self._unit_table.setColumnWidth(2, 70)

        layout.addWidget(form_card)
        layout.addWidget(self._unit_table, 1)
        return page

    def _build_footer_bar(self) -> QHBoxLayout:
        """Membangun baris bawah dialog berisi ringkasan jumlah dan tombol Tutup.

        Returns:
            QHBoxLayout berisi informasi jumlah master data dan tombol tutup.
        """
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)

        self._footer_info_label.setObjectName("FooterInfoLabel")
        self._close_btn.setObjectName("CloseFooterBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        footer.addWidget(self._footer_info_label)
        footer.addStretch(1)
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
            v_header.setDefaultSectionSize(30)

        h_header = table.horizontalHeader()
        if h_header is not None:
            h_header.setFixedHeight(28)
            h_header.setHighlightSections(False)
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS gelap serasi dengan CustomDialog."""
        self.content_widget.setStyleSheet(
            """
            QWidget#CustomDialogContent {
                background-color: #181825;
                color: #CDD6F4;
            }
            QFrame#TabHeaderBar, QFrame#FormSectionCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QFrame#TabSegmented {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 5px;
            }
            QPushButton#SegmentBtn {
                background-color: transparent;
                color: #9399B2;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#SegmentBtn:hover {
                color: #CDD6F4;
            }
            QPushButton#SegmentBtn:checked {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QLabel#HeaderHint {
                color: #6C7086;
                font-size: 10px;
                background: transparent;
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
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit#FormInput, QComboBox#FormCombo {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 12px;
                min-height: 22px;
            }
            QLineEdit#FormInput:focus, QComboBox#FormCombo:focus {
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
            QPushButton#PrimaryBtn {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 700;
                min-height: 20px;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #2563EB;
            }
            QPushButton#PrimaryBtn:pressed {
                background-color: #1D4ED8;
            }
            QPushButton#GhostBtn {
                background-color: transparent;
                color: #9399B2;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#GhostBtn:hover {
                background-color: #252638;
                color: #CDD6F4;
            }
            QTableWidget#MasterDataTable {
                background-color: #1E1E2E;
                alternate-background-color: #222335;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                font-size: 12px;
                selection-background-color: rgba(59, 130, 246, 0.20);
                selection-color: #FFFFFF;
            }
            QTableWidget#MasterDataTable::item {
                padding: 2px 8px;
                border-bottom: 1px solid #26273A;
            }
            QTableWidget#MasterDataTable QHeaderView::section {
                background-color: #252638;
                color: #9399B2;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#RowActionEdit {
                background-color: rgba(59, 130, 246, 0.16);
                color: #89B4FA;
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#RowActionEdit:hover {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QLabel#FooterInfoLabel {
                color: #9399B2;
                font-size: 11px;
                background: transparent;
            }
            QPushButton#CloseFooterBtn {
                background-color: #252638;
                color: #CDD6F4;
                border: 1px solid #3B3D54;
                border-radius: 5px;
                padding: 5px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#CloseFooterBtn:hover {
                background-color: #313244;
            }
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
            Widget kontainer berisi label badge status.
        """
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("Aktif" if is_active else "Arsip", container)
        if is_active:
            badge.setStyleSheet(
                "background-color: rgba(34, 197, 94, 0.16); color: #4ADE80; "
                "border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
        else:
            badge.setStyleSheet(
                "background-color: rgba(148, 163, 184, 0.16); color: #94A3B8; "
                "border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
        layout.addWidget(badge)
        return container

    def _render_categories_table(self) -> None:
        """Merender seluruh data master kategori ke dalam tabel kategori."""
        self._cat_table.setRowCount(len(self._categories))
        for idx, cat in enumerate(self._categories):
            name_item = QTableWidgetItem(cat.name)
            parent_item = QTableWidgetItem(cat.parent_name if cat.parent_name else "-")
            parent_item.setForeground(QColor("#9399B2"))

            edit_wrap = QWidget(self._cat_table)
            edit_layout = QHBoxLayout(edit_wrap)
            edit_layout.setContentsMargins(4, 2, 4, 2)
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
            self._cat_table.setCellWidget(
                idx, 2, self._create_status_badge(cat.is_active)
            )
            self._cat_table.setCellWidget(idx, 3, edit_wrap)

    def _render_units_table(self) -> None:
        """Merender seluruh data master satuan ke dalam tabel satuan."""
        self._unit_table.setRowCount(len(self._units))
        mono_font = QFont("Consolas", 9)

        for idx, unit in enumerate(self._units):
            name_item = QTableWidgetItem(unit.name)
            symbol_item = QTableWidgetItem(unit.symbol)
            symbol_item.setFont(mono_font)
            symbol_item.setForeground(QColor("#89B4FA"))

            edit_wrap = QWidget(self._unit_table)
            edit_layout = QHBoxLayout(edit_wrap)
            edit_layout.setContentsMargins(4, 2, 4, 2)
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
        self._cat_save_btn.setText("Perbarui")
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
        self._cat_save_btn.setText("Simpan")
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
        self._unit_save_btn.setText("Perbarui")
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
        self._unit_save_btn.setText("Simpan")
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