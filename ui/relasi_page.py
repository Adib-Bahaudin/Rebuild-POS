"""Modul antarmuka halaman manajemen Pelanggan dan Supplier berbasis PySide6.

Modul ini menyediakan komponen UI terpisah dari logika backend untuk mengelola
tampilan daftar pelanggan dan supplier dalam satu jendela menggunakan
QStackedWidget dan tombol pengalih dinamis, terintegrasi dengan
FramelessMainWindow dari customwindowtitlebar.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Literal

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
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

from ui.customwindowtitlebar import (
    FramelessMainWindow,
    ICON_PATHS,
    TitleBarIconConfig,
)

RelationType = Literal["customer", "supplier"]


@dataclass(frozen=True)
class RelationRecord:
    """Representasi data satu baris pelanggan atau supplier untuk tampilan tabel.

    Attributes:
        relation_id: ID unik relasi dari basis data.
        name: Nama pelanggan atau supplier.
        phone: Nomor telepon atau WhatsApp relasi.
        address: Alamat lengkap relasi.
        transaction_count: Jumlah total nota transaksi yang pernah tercatat.
        transaction_total: Akumulasi nilai transaksi dalam satuan Rupiah.
        outstanding_amount: Sisa piutang (pelanggan) atau utang (supplier).
        nearest_due_date: Tanggal jatuh tempo terdekat dalam format teks.
        is_overdue: Penanda apakah terdapat tagihan yang telah melewati jatuh tempo.
        is_active: Status aktif relasi sesuai kolom is_active di basis data.
    """

    relation_id: int
    name: str
    phone: str = ""
    address: str = ""
    transaction_count: int = 0
    transaction_total: int = 0
    outstanding_amount: int = 0
    nearest_due_date: str = ""
    is_overdue: bool = False
    is_active: bool = True


@dataclass(frozen=True)
class RelationKpiData:
    """Data ringkasan metrik KPI untuk ditampilkan pada kartu statistik atas.

    Attributes:
        active_count: Jumlah total relasi berstatus aktif.
        total_count: Jumlah seluruh relasi (aktif dan nonaktif).
        outstanding_total: Akumulasi sisa piutang atau utang berjalan.
        outstanding_relation_count: Jumlah relasi yang memiliki tunggakan.
        overdue_invoice_count: Jumlah nota yang jatuh tempo atau terlewati.
    """

    active_count: int = 0
    total_count: int = 0
    outstanding_total: int = 0
    outstanding_relation_count: int = 0
    overdue_invoice_count: int = 0


@dataclass(frozen=True)
class RelationFilterState:
    """Keadaan filter, pencarian, dan pengurutan aktif pada satu tampilan relasi.

    Attributes:
        search_query: Kata kunci pencarian nama, telepon, atau alamat.
        status_filter: Filter status data ('active', 'inactive', atau 'all').
        billing_filter: Filter status tagihan ('all', 'outstanding', 'overdue', 'paid').
        sort_by: Kriteria pengurutan data yang dipilih pengguna.
    """

    search_query: str = ""
    status_filter: str = "active"
    billing_filter: str = "all"
    sort_by: str = "name_asc"


def format_rupiah(amount: int) -> str:
    """Memformat bilangan bulat nominal ke format mata uang Rupiah.

    Args:
        amount: Nilai nominal dalam bilangan bulat.

    Returns:
        String terformat dengan pemisah ribuan titik, contoh 'Rp 1.250.000'.
    """
    prefix = "-Rp " if amount < 0 else "Rp "
    formatted_number = f"{abs(amount):,}".replace(",", ".")
    return f"{prefix}{formatted_number}"


def refresh_widget_style(widget: QWidget) -> None:
    """Memaksa pembaruan tampilan QSS saat properti dinamis widget berubah.

    Args:
        widget: Objek QWidget yang perlu dirender ulang gayanya.
    """
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


class KpiCardWidget(QFrame):
    """Komponen kartu metrik ringkas dengan judul, nilai utama, dan subteks.

    Attributes:
        accent_role: Peran warna aksen kartu ('primary', 'warning', 'danger').
    """

    def __init__(
        self,
        title: str,
        accent_role: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi instance KpiCardWidget.

        Args:
            title: Label judul kartu yang menjelaskan metrik.
            accent_role: Kategori warna aksen nilai ('primary', 'warning', 'danger').
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.accent_role = accent_role
        self.setObjectName("KpiCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(84)

        self._title_label = QLabel(title, self)
        self._value_label = QLabel("0", self)
        self._hint_label = QLabel("-", self)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Menyusun tata letak vertikal internal kartu KPI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 11, 16, 11)
        layout.setSpacing(3)

        self._title_label.setObjectName("KpiTitle")
        self._value_label.setObjectName("KpiValue")
        self._value_label.setProperty("accentRole", self.accent_role)
        self._hint_label.setObjectName("KpiHint")

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._hint_label)

    def set_metrics(
        self,
        value_text: str,
        hint_text: str,
        accent_role: str | None = None,
    ) -> None:
        """Memperbarui nilai utama, keterangan bawah, dan warna aksen kartu.

        Args:
            value_text: Teks angka atau nominal utama yang ditampilkan.
            hint_text: Teks keterangan kontekstual singkat di bawah nilai.
            accent_role: Peran aksen opsional untuk memperbarui warna nilai.
        """
        self._value_label.setText(value_text)
        self._hint_label.setText(hint_text)
        if accent_role is not None and accent_role != self.accent_role:
            self.accent_role = accent_role
            self._value_label.setProperty("accentRole", accent_role)
            refresh_widget_style(self._value_label)


class RelationSwitcherWidget(QFrame):
    """Tombol pengalih segmen (segmented control) untuk mode Pelanggan dan Supplier.

    Attributes:
        mode_changed: Sinyal yang dipancarkan ketika mode aktif berubah.
    """

    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi RelationSwitcherWidget dengan dua tombol dinamis.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("RelationSwitcher")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._active_mode: RelationType = "customer"
        self._badge_counts: dict[RelationType, int] = {
            "customer": 0,
            "supplier": 0,
        }

        self._customer_button = QPushButton(self)
        self._supplier_button = QPushButton(self)

        self._setup_ui()
        self._connect_signals()
        self._sync_button_visuals()

    def _setup_ui(self) -> None:
        """Menyusun tata letak horizontal tombol pengalih segmen."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for button in (self._customer_button, self._supplier_button):
            button.setObjectName("SwitcherButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(32)
            button.setMinimumWidth(134)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(button)

    def _connect_signals(self) -> None:
        """Menghubungkan event klik tombol ke perubahan mode aktif."""
        self._customer_button.clicked.connect(
            lambda _checked=False: self.set_active_mode("customer", emit_signal=True)
        )
        self._supplier_button.clicked.connect(
            lambda _checked=False: self.set_active_mode("supplier", emit_signal=True)
        )

    def _sync_button_visuals(self) -> None:
        """Menyinkronkan label angka dan status properti aktif kedua tombol."""
        self._customer_button.setText(f"Pelanggan  ·  {self._badge_counts['customer']}")
        self._supplier_button.setText(f"Supplier  ·  {self._badge_counts['supplier']}")

        is_customer = self._active_mode == "customer"
        self._customer_button.setProperty("active", is_customer)
        self._supplier_button.setProperty("active", not is_customer)
        refresh_widget_style(self._customer_button)
        refresh_widget_style(self._supplier_button)

    def set_active_mode(
        self,
        relation_type: RelationType,
        emit_signal: bool = False,
    ) -> None:
        """Mengatur mode segmen aktif dan memperbarui gaya tombol.

        Args:
            relation_type: Jenis relasi tujuan ('customer' atau 'supplier').
            emit_signal: Jika True dan mode berubah, sinyal mode_changed dipancarkan.
        """
        changed = relation_type != self._active_mode
        self._active_mode = relation_type
        self._sync_button_visuals()
        if emit_signal and changed:
            self.mode_changed.emit(relation_type)

    def get_active_mode(self) -> RelationType:
        """Mengembalikan mode relasi yang sedang aktif.

        Returns:
            Literal 'customer' atau 'supplier'.
        """
        return self._active_mode

    def set_badge_count(self, relation_type: RelationType, count: int) -> None:
        """Memperbarui angka indikator jumlah data pada salah satu tombol segmen.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
            count: Angka jumlah yang akan ditampilkan.
        """
        self._badge_counts[relation_type] = max(0, count)
        self._sync_button_visuals()


class RelationFilterBar(QFrame):
    """Bilah pencarian, filter status data, filter tagihan, dan pengurutan.

    Attributes:
        filter_changed: Sinyal yang dipancarkan saat kriteria filter berubah.
        refresh_requested: Sinyal yang dipancarkan saat tombol muat ulang ditekan.
    """

    filter_changed = Signal(object)
    refresh_requested = Signal()

    def __init__(
        self,
        relation_type: RelationType,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationFilterBar sesuai konteks relasi.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._relation_type: RelationType = relation_type
        self.setObjectName("FilterBar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._search_input = QLineEdit(self)
        self._status_combo = QComboBox(self)
        self._billing_combo = QComboBox(self)
        self._sort_combo = QComboBox(self)
        self._refresh_button = QPushButton("Muat Ulang", self)

        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(220)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Menyusun komponen input pencarian, dropdown filter, dan tombol refresh."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        entity_label = "pelanggan" if self._relation_type == "customer" else "supplier"
        debt_label = "Piutang" if self._relation_type == "customer" else "Utang"

        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText(
            f"Cari nama, nomor telepon, atau alamat {entity_label}... (Ctrl+F)"
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedHeight(34)

        self._status_combo.setObjectName("FilterCombo")
        self._status_combo.setFixedHeight(34)
        self._status_combo.setMinimumWidth(124)
        self._status_combo.addItem("Status: Aktif", "active")
        self._status_combo.addItem("Status: Nonaktif", "inactive")
        self._status_combo.addItem("Status: Semua", "all")

        self._billing_combo.setObjectName("FilterCombo")
        self._billing_combo.setFixedHeight(34)
        self._billing_combo.setMinimumWidth(164)
        self._billing_combo.addItem(f"{debt_label}: Semua", "all")
        self._billing_combo.addItem(f"Ada {debt_label}", "outstanding")
        self._billing_combo.addItem("Jatuh Tempo", "overdue")
        self._billing_combo.addItem("Lunas", "paid")

        self._sort_combo.setObjectName("FilterCombo")
        self._sort_combo.setFixedHeight(34)
        self._sort_combo.setMinimumWidth(182)
        self._sort_combo.addItem("Urut: Nama (A-Z)", "name_asc")
        self._sort_combo.addItem("Urut: Nama (Z-A)", "name_desc")
        self._sort_combo.addItem(f"Urut: {debt_label} Terbesar", "outstanding_desc")
        self._sort_combo.addItem("Urut: Jatuh Tempo Terdekat", "due_date_asc")
        self._sort_combo.addItem("Urut: Transaksi Terbanyak", "transaction_desc")

        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_button.setFixedHeight(34)
        self._refresh_button.setMinimumWidth(96)
        self._refresh_button.setToolTip("Muat ulang data (F5)")

        layout.addWidget(self._search_input, 3)
        layout.addWidget(self._status_combo, 0)
        layout.addWidget(self._billing_combo, 0)
        layout.addWidget(self._sort_combo, 0)
        layout.addWidget(self._refresh_button, 0)

    def _connect_signals(self) -> None:
        """Menghubungkan perubahan input pencarian dan filter ke sinyal keluar."""
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_debounce.timeout.connect(self._emit_filter_state)
        self._status_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._billing_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._sort_combo.currentIndexChanged.connect(self._emit_filter_state)
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

    def _on_search_text_changed(self, _text: str) -> None:
        """Memulai ulang timer debounce ketika teks pencarian berubah.

        Args:
            _text: Teks pencarian terkini dari QLineEdit.
        """
        self._search_debounce.start()

    def _emit_filter_state(self) -> None:
        """Memancarkan objek RelationFilterState terbaru ke konsumen sinyal."""
        self.filter_changed.emit(self.get_filter_state())

    def get_filter_state(self) -> RelationFilterState:
        """Membaca seluruh nilai filter dan pencarian saat ini.

        Returns:
            Objek RelationFilterState yang mencerminkan input pengguna.
        """
        return RelationFilterState(
            search_query=self._search_input.text().strip(),
            status_filter=str(self._status_combo.currentData() or "active"),
            billing_filter=str(self._billing_combo.currentData() or "all"),
            sort_by=str(self._sort_combo.currentData() or "name_asc"),
        )

    def focus_search(self) -> None:
        """Memindahkan fokus keyboard ke kolom pencarian dan memilih teksnya."""
        self._search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search_input.selectAll()

    def clear_search(self) -> None:
        """Mengosongkan kolom pencarian tanpa memicu debounce tertunda."""
        self._search_debounce.stop()
        self._search_input.clear()

    def set_loading(self, is_loading: bool) -> None:
        """Mengatur status aktif tombol muat ulang saat data sedang diambil.

        Args:
            is_loading: True jika sedang memuat data, False jika selesai.
        """
        self._refresh_button.setEnabled(not is_loading)
        self._refresh_button.setText("Memuat..." if is_loading else "Muat Ulang")


class RelationTableView(QTableWidget):
    """Tabel data pelanggan atau supplier dengan sel status dan tombol aksi bersih.

    Attributes:
        detail_requested: Sinyal saat tombol Detail atau klik ganda baris dipicu.
        payment_requested: Sinyal saat tombol Bayar/Terima dipicu.
        edit_requested: Sinyal saat tombol Edit dipicu.
        toggle_active_requested: Sinyal saat tombol Arsip/Aktifkan dipicu.
        phone_copied: Sinyal saat nomor telepon berhasil disalin ke clipboard.
    """

    detail_requested = Signal(int)
    payment_requested = Signal(int)
    edit_requested = Signal(int)
    toggle_active_requested = Signal(int, bool)
    phone_copied = Signal(str, str)

    COLUMN_NAME: int = 0
    COLUMN_PHONE: int = 1
    COLUMN_ADDRESS: int = 2
    COLUMN_TRANSACTIONS: int = 3
    COLUMN_OUTSTANDING: int = 4
    COLUMN_STATUS: int = 5
    COLUMN_ACTIONS: int = 6

    def __init__(
        self,
        relation_type: RelationType,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationTableView dengan konfigurasi kolom proporsional.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            parent: Widget induk opsional.
        """
        super().__init__(0, 7, parent)
        self._relation_type: RelationType = relation_type
        self._row_ids: list[int] = []

        self._configure_table()
        self.cellDoubleClicked.connect(self._handle_double_click)

    def _configure_table(self) -> None:
        """Mengatur header, mode seleksi, dimensi kolom, dan perilaku tabel."""
        self.setObjectName("RelationTable")
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWordWrap(False)

        debt_header = "Piutang" if self._relation_type == "customer" else "Utang"
        self.setHorizontalHeaderLabels(
            [
                "Nama",
                "Kontak",
                "Alamat",
                "Transaksi",
                debt_header,
                "Status",
                "Aksi",
            ]
        )

        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(48)

        h_header = self.horizontalHeader()
        if h_header is not None:
            h_header.setDefaultAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            h_header.setHighlightSections(False)
            h_header.setStretchLastSection(False)
            h_header.setSectionResizeMode(
                self.COLUMN_NAME, QHeaderView.ResizeMode.Stretch
            )
            h_header.setSectionResizeMode(
                self.COLUMN_PHONE, QHeaderView.ResizeMode.Fixed
            )
            h_header.setSectionResizeMode(
                self.COLUMN_ADDRESS, QHeaderView.ResizeMode.Stretch
            )
            h_header.setSectionResizeMode(
                self.COLUMN_TRANSACTIONS, QHeaderView.ResizeMode.Fixed
            )
            h_header.setSectionResizeMode(
                self.COLUMN_OUTSTANDING, QHeaderView.ResizeMode.Fixed
            )
            h_header.setSectionResizeMode(
                self.COLUMN_STATUS, QHeaderView.ResizeMode.Fixed
            )
            h_header.setSectionResizeMode(
                self.COLUMN_ACTIONS, QHeaderView.ResizeMode.Fixed
            )

        self.setColumnWidth(self.COLUMN_PHONE, 162)
        self.setColumnWidth(self.COLUMN_TRANSACTIONS, 146)
        self.setColumnWidth(self.COLUMN_OUTSTANDING, 158)
        self.setColumnWidth(self.COLUMN_STATUS, 88)
        self.setColumnWidth(self.COLUMN_ACTIONS, 232)

    def _handle_double_click(self, row: int, _column: int) -> None:
        """Membuka detail relasi ketika pengguna melakukan klik ganda pada baris.

        Args:
            row: Indeks baris yang diklik ganda.
            _column: Indeks kolom yang diklik ganda.
        """
        if 0 <= row < len(self._row_ids):
            self.detail_requested.emit(self._row_ids[row])

    def _create_text_item(
        self,
        text: str,
        tooltip: str = "",
        alignment: Qt.AlignmentFlag = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        ),
    ) -> QTableWidgetItem:
        """Membuat QTableWidgetItem standar dengan perataan dan tooltip opsional.

        Args:
            text: Teks yang ditampilkan di dalam sel.
            tooltip: Teks tooltip yang muncul saat pointer diarahkan ke sel.
            alignment: Kombinasi flag perataan teks Qt.

        Returns:
            Objek QTableWidgetItem siap dipasang ke tabel.
        """
        item = QTableWidgetItem(text)
        item.setTextAlignment(alignment)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def _create_phone_cell(self, record: RelationRecord) -> QWidget:
        """Membuat widget sel telepon dengan tombol salin cepat tanpa latar gelap.

        Args:
            record: Objek RelationRecord untuk baris terkait.

        Returns:
            Widget kontainer transparan berisi nomor telepon dan tombol salin.
        """
        container = QWidget(self)
        container.setObjectName("TransparentCell")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        phone_text = record.phone.strip() or "-"
        phone_label = QLabel(phone_text, container)
        phone_label.setObjectName("CellPhoneText")
        phone_label.setToolTip(phone_text)
        layout.addWidget(phone_label, 1)

        if record.phone.strip():
            copy_button = QPushButton("Salin", container)
            copy_button.setObjectName("InlineCopyButton")
            copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_button.setFixedHeight(22)
            copy_button.setToolTip(f"Salin nomor {record.phone}")
            copy_button.clicked.connect(
                lambda _checked=False, name=record.name, phone=record.phone: (
                    self._copy_phone(name, phone)
                )
            )
            layout.addWidget(copy_button, 0)

        return container

    def _copy_phone(self, name: str, phone: str) -> None:
        """Menyalin nomor telepon ke clipboard sistem dan memancarkan sinyal.

        Args:
            name: Nama relasi pemilik nomor.
            phone: Nomor telepon yang disalin.
        """
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(phone)
        self.phone_copied.emit(name, phone)

    def _create_outstanding_cell(self, record: RelationRecord) -> QWidget:
        """Membuat widget sel piutang/utang dengan indikator jatuh tempo.

        Args:
            record: Objek RelationRecord untuk baris terkait.

        Returns:
            Widget kontainer transparan berisi nominal tagihan dan tanggal tempo.
        """
        container = QWidget(self)
        container.setObjectName("TransparentCell")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        amount_label = QLabel(format_rupiah(record.outstanding_amount), container)
        amount_label.setObjectName("OutstandingAmount")
        if record.outstanding_amount <= 0:
            state = "clear"
        elif record.is_overdue:
            state = "overdue"
        else:
            state = "pending"
        amount_label.setProperty("billingState", state)
        layout.addWidget(amount_label)

        if record.outstanding_amount > 0 and record.nearest_due_date:
            prefix = "Lewat: " if record.is_overdue else "Tempo: "
            due_label = QLabel(f"{prefix}{record.nearest_due_date}", container)
            due_label.setObjectName("DueDateSubtext")
            due_label.setProperty("overdue", record.is_overdue)
            layout.addWidget(due_label)

        return container

    def _create_status_cell(self, is_active: bool) -> QWidget:
        """Membuat widget badge status Aktif atau Nonaktif berlatar transparan.

        Args:
            is_active: True untuk status aktif, False untuk nonaktif.

        Returns:
            Widget kontainer transparan dengan badge teks status.
        """
        container = QWidget(self)
        container.setObjectName("TransparentCell")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("Aktif" if is_active else "Nonaktif", container)
        badge.setObjectName("StatusBadge")
        badge.setProperty("active", is_active)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(24)
        badge.setMinimumWidth(68)
        layout.addWidget(badge)

        return container

    def _create_actions_cell(self, record: RelationRecord) -> QWidget:
        """Membuat baris tombol aksi per relasi tanpa kontainer gelap tambahan.

        Args:
            record: Objek RelationRecord untuk baris terkait.

        Returns:
            Widget kontainer transparan berisi tombol Detail, Bayar, Edit, dan Arsip.
        """
        container = QWidget(self)
        container.setObjectName("TransparentCell")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 6, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        detail_button = QPushButton("Detail", container)
        detail_button.setObjectName("RowActionNeutral")
        detail_button.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_button.setFixedHeight(26)
        detail_button.clicked.connect(
            lambda _checked=False, rid=record.relation_id: (
                self.detail_requested.emit(rid)
            )
        )

        pay_label = "Terima" if self._relation_type == "customer" else "Bayar"
        pay_button = QPushButton(pay_label, container)
        pay_button.setObjectName("RowActionAccent")
        pay_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pay_button.setFixedHeight(26)
        pay_button.setEnabled(record.outstanding_amount > 0)
        pay_button.setToolTip(
            "Catat pembayaran atau cicilan"
            if record.outstanding_amount > 0
            else "Tidak ada sisa tagihan"
        )
        pay_button.clicked.connect(
            lambda _checked=False, rid=record.relation_id: (
                self.payment_requested.emit(rid)
            )
        )

        edit_button = QPushButton("Edit", container)
        edit_button.setObjectName("RowActionNeutral")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.setFixedHeight(26)
        edit_button.clicked.connect(
            lambda _checked=False, rid=record.relation_id: (
                self.edit_requested.emit(rid)
            )
        )

        archive_text = "Arsip" if record.is_active else "Aktifkan"
        archive_button = QPushButton(archive_text, container)
        archive_button.setObjectName(
            "RowActionDanger" if record.is_active else "RowActionSuccess"
        )
        archive_button.setCursor(Qt.CursorShape.PointingHandCursor)
        archive_button.setFixedHeight(26)
        target_active = not record.is_active
        archive_button.clicked.connect(
            lambda _checked=False, rid=record.relation_id, state=target_active: (
                self.toggle_active_requested.emit(rid, state)
            )
        )

        layout.addWidget(detail_button)
        layout.addWidget(pay_button)
        layout.addWidget(edit_button)
        layout.addWidget(archive_button)

        return container

    def set_records(self, records: list[RelationRecord]) -> None:
        """Mengisi ulang seluruh baris tabel dari daftar RelationRecord.

        Args:
            records: Daftar objek RelationRecord yang siap ditampilkan.
        """
        self.setRowCount(0)
        self._row_ids = []
        self.setRowCount(len(records))

        metrics = QFontMetrics(self.font())
        for row_index, record in enumerate(records):
            self._row_ids.append(record.relation_id)

            name_item = self._create_text_item(record.name, tooltip=record.name)
            address_raw = record.address.strip() or "-"
            elided_address = metrics.elidedText(
                address_raw, Qt.TextElideMode.ElideRight, 260
            )
            address_item = self._create_text_item(elided_address, tooltip=address_raw)

            tx_summary = (
                f"{record.transaction_count} nota · "
                f"{format_rupiah(record.transaction_total)}"
            )
            tx_item = self._create_text_item(tx_summary, tooltip=tx_summary)

            self.setItem(row_index, self.COLUMN_NAME, name_item)
            self.setCellWidget(
                row_index, self.COLUMN_PHONE, self._create_phone_cell(record)
            )
            self.setItem(row_index, self.COLUMN_ADDRESS, address_item)
            self.setItem(row_index, self.COLUMN_TRANSACTIONS, tx_item)
            self.setCellWidget(
                row_index,
                self.COLUMN_OUTSTANDING,
                self._create_outstanding_cell(record),
            )
            self.setCellWidget(
                row_index,
                self.COLUMN_STATUS,
                self._create_status_cell(record.is_active),
            )
            self.setCellWidget(
                row_index,
                self.COLUMN_ACTIONS,
                self._create_actions_cell(record),
            )


class RelationPanelWidget(QWidget):
    """Satu panel lengkap (KPI, filter, tabel, dan empty state) untuk satu jenis relasi.

    Attributes:
        filter_changed: Sinyal perubahan filter khusus panel ini.
        refresh_requested: Sinyal permintaan muat ulang data panel ini.
        detail_requested: Sinyal permintaan tampilan detail relasi.
        payment_requested: Sinyal permintaan pelunasan atau cicilan.
        edit_requested: Sinyal permintaan pengubahan profil relasi.
        toggle_active_requested: Sinyal permintaan arsip atau aktivasi ulang.
        phone_copied: Sinyal salin nomor telepon berhasil.
    """

    filter_changed = Signal(object)
    refresh_requested = Signal()
    detail_requested = Signal(int)
    payment_requested = Signal(int)
    edit_requested = Signal(int)
    toggle_active_requested = Signal(int, bool)
    phone_copied = Signal(str, str)

    def __init__(
        self,
        relation_type: RelationType,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationPanelWidget untuk pelanggan atau supplier.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._relation_type: RelationType = relation_type

        entity_title = "Pelanggan" if relation_type == "customer" else "Supplier"
        debt_title = (
            "Total Piutang Pelanggan"
            if relation_type == "customer"
            else "Total Utang ke Supplier"
        )
        overdue_title = (
            "Piutang Jatuh Tempo"
            if relation_type == "customer"
            else "Utang Jatuh Tempo"
        )

        self._population_card = KpiCardWidget(
            f"{entity_title} Aktif", accent_role="primary", parent=self
        )
        self._outstanding_card = KpiCardWidget(
            debt_title, accent_role="warning", parent=self
        )
        self._overdue_card = KpiCardWidget(
            overdue_title, accent_role="danger", parent=self
        )
        self._filter_bar = RelationFilterBar(relation_type, self)
        self._table_stack = QStackedWidget(self)
        self._table = RelationTableView(relation_type, self)
        self._empty_state = self._build_empty_state(entity_title)
        self._row_count: int = 0

        self._setup_ui()
        self._connect_signals()
        self.set_kpi_data(RelationKpiData())
        self.set_records([])

    def _build_empty_state(self, entity_title: str) -> QFrame:
        """Membangun tampilan informasi saat data tabel sedang kosong.

        Args:
            entity_title: Nama jenis entitas ('Pelanggan' atau 'Supplier').

        Returns:
            QFrame berisi judul dan arahan singkat untuk kondisi tabel kosong.
        """
        container = QFrame(self)
        container.setObjectName("EmptyStateCard")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        title = QLabel(f"Belum ada data {entity_title.lower()} yang cocok", container)
        title.setObjectName("EmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            f"Tambahkan {entity_title.lower()} baru melalui tombol di pojok kanan atas "
            "atau sesuaikan filter pencarian.",
            container,
        )
        subtitle.setObjectName("EmptyStateSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return container

    def _setup_ui(self) -> None:
        """Menyusun tata letak vertikal KPI, filter bar, dan kontainer tabel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        kpi_layout = QHBoxLayout()
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(12)
        kpi_layout.addWidget(self._population_card, 1)
        kpi_layout.addWidget(self._outstanding_card, 1)
        kpi_layout.addWidget(self._overdue_card, 1)

        table_wrapper = QFrame(self)
        table_wrapper.setObjectName("TableContainer")
        table_wrapper_layout = QVBoxLayout(table_wrapper)
        table_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        table_wrapper_layout.setSpacing(0)

        self._table_stack.addWidget(self._table)
        self._table_stack.addWidget(self._empty_state)
        table_wrapper_layout.addWidget(self._table_stack)

        layout.addLayout(kpi_layout)
        layout.addWidget(self._filter_bar)
        layout.addWidget(table_wrapper, 1)

    def _connect_signals(self) -> None:
        """Meneruskan seluruh sinyal dari filter bar dan tabel ke level panel."""
        self._filter_bar.filter_changed.connect(self.filter_changed.emit)
        self._filter_bar.refresh_requested.connect(self.refresh_requested.emit)
        self._table.detail_requested.connect(self.detail_requested.emit)
        self._table.payment_requested.connect(self.payment_requested.emit)
        self._table.edit_requested.connect(self.edit_requested.emit)
        self._table.toggle_active_requested.connect(self.toggle_active_requested.emit)
        self._table.phone_copied.connect(self.phone_copied.emit)

    def set_kpi_data(self, kpi: RelationKpiData) -> None:
        """Memperbarui nilai ketiga kartu KPI pada panel ini.

        Args:
            kpi: Objek RelationKpiData berisi ringkasan terbaru dari backend.
        """
        entity = "pelanggan" if self._relation_type == "customer" else "supplier"
        self._population_card.set_metrics(
            value_text=f"{kpi.active_count:,}".replace(",", "."),
            hint_text=f"Dari total {kpi.total_count} {entity} terdaftar",
            accent_role="primary",
        )
        self._outstanding_card.set_metrics(
            value_text=format_rupiah(kpi.outstanding_total),
            hint_text=f"{kpi.outstanding_relation_count} {entity} memiliki tagihan berjalan",
            accent_role="warning" if kpi.outstanding_total > 0 else "success",
        )
        self._overdue_card.set_metrics(
            value_text=f"{kpi.overdue_invoice_count} Nota",
            hint_text=(
                "Perlu segera ditindaklanjuti"
                if kpi.overdue_invoice_count > 0
                else "Tidak ada nota lewat jatuh tempo"
            ),
            accent_role="danger" if kpi.overdue_invoice_count > 0 else "success",
        )

    def set_records(self, records: list[RelationRecord]) -> None:
        """Memperbarui isi tabel dan beralih otomatis ke empty state bila kosong.

        Args:
            records: Daftar objek RelationRecord hasil query backend.
        """
        self._row_count = len(records)
        self._table.set_records(records)
        self._table_stack.setCurrentIndex(0 if records else 1)

    def get_row_count(self) -> int:
        """Mengembalikan jumlah baris data yang sedang ditampilkan pada tabel.

        Returns:
            Bilangan bulat jumlah baris aktif di tabel.
        """
        return self._row_count

    def get_filter_state(self) -> RelationFilterState:
        """Mengembalikan status filter saat ini dari bilah filter panel.

        Returns:
            Objek RelationFilterState terkini.
        """
        return self._filter_bar.get_filter_state()

    def focus_search(self) -> None:
        """Mengarahkan fokus kursor ke kolom pencarian panel ini."""
        self._filter_bar.focus_search()

    def clear_search(self) -> None:
        """Membersihkan input pencarian pada panel ini."""
        self._filter_bar.clear_search()

    def set_loading(self, is_loading: bool) -> None:
        """Menampilkan status pemuatan pada bilah filter panel.

        Args:
            is_loading: True saat memuat data, False saat selesai.
        """
        self._filter_bar.set_loading(is_loading)


class RelationManagementPage(QWidget):
    """Halaman utama manajemen Pelanggan dan Supplier berbasis QStackedWidget.

    Halaman ini memaksimalkan ruang kerja tanpa QTabWidget dengan memadukan
    header kompak, tombol pengalih segmen dinamis, tombol aksi primer kontekstual,
    dan QStackedWidget berisi panel Pelanggan serta Supplier yang independen.

    Attributes:
        active_mode_changed: Dipancarkan saat mode aktif berubah ('customer'/'supplier').
        add_relation_requested: Dipancarkan saat tombol Tambah ditekan.
        edit_relation_requested: Dipancarkan saat tombol Edit baris ditekan.
        detail_relation_requested: Dipancarkan saat Detail/klik ganda baris dipicu.
        payment_relation_requested: Dipancarkan saat tombol Bayar/Terima ditekan.
        toggle_active_requested: Dipancarkan saat status aktif relasi diubah.
        filter_changed: Dipancarkan saat filter atau pencarian berubah.
        refresh_requested: Dipancarkan saat muat ulang data diminta.
        phone_copied: Dipancarkan saat nomor telepon disalin ke clipboard.
    """

    active_mode_changed = Signal(str)
    add_relation_requested = Signal(str)
    edit_relation_requested = Signal(str, int)
    detail_relation_requested = Signal(str, int)
    payment_relation_requested = Signal(str, int)
    toggle_active_requested = Signal(str, int, bool)
    filter_changed = Signal(str, object)
    refresh_requested = Signal(str)
    phone_copied = Signal(str, str)
    page_entered = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi halaman RelationManagementPage lengkap dengan shortcut.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setObjectName("RelationManagementPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._active_mode: RelationType = "customer"
        self._title_label = QLabel("Pelanggan & Supplier", self)
        self._subtitle_label = QLabel(self)
        self._switcher = RelationSwitcherWidget(self)
        self._add_button = QPushButton(self)
        self._content_stack = QStackedWidget(self)

        self._customer_panel = RelationPanelWidget("customer", self)
        self._supplier_panel = RelationPanelWidget("supplier", self)
        self._panels: dict[RelationType, RelationPanelWidget] = {
            "customer": self._customer_panel,
            "supplier": self._supplier_panel,
        }

        self._footer_count_label = QLabel("Menampilkan 0 pelanggan", self)
        self._footer_feedback_label = QLabel("", self)
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.setInterval(2600)

        self._shortcuts: list[QShortcut] = []

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
        self._setup_shortcuts()
        self._sync_mode_ui()

    def _setup_ui(self) -> None:
        """Menyusun struktur header, QStackedWidget konten, dan footer ringkas."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 14, 18, 12)
        root_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)

        self._title_label.setObjectName("PageTitle")
        self._subtitle_label.setObjectName("PageSubtitle")
        title_column.addWidget(self._title_label)
        title_column.addWidget(self._subtitle_label)

        self._add_button.setObjectName("PrimaryButton")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.setFixedHeight(38)
        self._add_button.setMinimumWidth(168)
        self._add_button.setToolTip("Tambah data baru sesuai mode aktif (Ctrl+N)")

        header_layout.addLayout(title_column, 1)
        header_layout.addWidget(self._switcher, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self._add_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._content_stack.addWidget(self._customer_panel)
        self._content_stack.addWidget(self._supplier_panel)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(2, 0, 2, 0)
        footer_layout.setSpacing(12)

        self._footer_count_label.setObjectName("FooterMeta")
        self._footer_feedback_label.setObjectName("FooterFeedback")

        shortcut_hint = QLabel(
            "Ctrl+F Cari  •  Ctrl+N Tambah  •  Ctrl+Tab Ganti Mode  •  F5 Muat Ulang",
            self,
        )
        shortcut_hint.setObjectName("FooterHint")

        footer_layout.addWidget(self._footer_count_label, 0)
        footer_layout.addWidget(self._footer_feedback_label, 1)
        footer_layout.addWidget(shortcut_hint, 0)

        root_layout.addLayout(header_layout)
        root_layout.addWidget(self._content_stack, 1)
        root_layout.addLayout(footer_layout)

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal internal seluruh subkomponen ke sinyal publik halaman."""
        self._switcher.mode_changed.connect(self._on_switcher_changed)
        self._add_button.clicked.connect(self._on_add_clicked)
        self._feedback_timer.timeout.connect(self._clear_footer_feedback)

        self._bind_panel_signals("customer", self._customer_panel)
        self._bind_panel_signals("supplier", self._supplier_panel)

    def _bind_panel_signals(
        self,
        relation_type: RelationType,
        panel: RelationPanelWidget,
    ) -> None:
        """Mengikat sinyal dari satu panel relasi ke sinyal publik terklasifikasi.

        Args:
            relation_type: Jenis relasi panel ('customer' atau 'supplier').
            panel: Instance RelationPanelWidget yang dihubungkan.
        """
        panel.filter_changed.connect(
            lambda state, rtype=relation_type: self.filter_changed.emit(rtype, state)
        )
        panel.refresh_requested.connect(
            lambda rtype=relation_type: self.refresh_requested.emit(rtype)
        )
        panel.detail_requested.connect(
            lambda rid, rtype=relation_type: self.detail_relation_requested.emit(
                rtype, rid
            )
        )
        panel.payment_requested.connect(
            lambda rid, rtype=relation_type: self.payment_relation_requested.emit(
                rtype, rid
            )
        )
        panel.edit_requested.connect(
            lambda rid, rtype=relation_type: self.edit_relation_requested.emit(
                rtype, rid
            )
        )
        panel.toggle_active_requested.connect(
            lambda rid, target_active, rtype=relation_type: (
                self.toggle_active_requested.emit(rtype, rid, target_active)
            )
        )
        panel.phone_copied.connect(self._handle_phone_copied)

    def _setup_shortcuts(self) -> None:
        """Mendaftarkan pintasan keyboard untuk navigasi cepat halaman."""
        bindings: list[tuple[str, object]] = [
            ("Ctrl+N", self._on_add_clicked),
            ("Ctrl+F", self._focus_active_search),
            ("Ctrl+Tab", self.toggle_mode),
            ("F5", self._emit_active_refresh),
        ]
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            if callable(callback):
                shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _on_switcher_changed(self, relation_type: str) -> None:
        """Menangani perubahan mode dari tombol pengalih segmen.

        Args:
            relation_type: String mode baru ('customer' atau 'supplier').
        """
        target: RelationType = "supplier" if relation_type == "supplier" else "customer"
        self._active_mode = target
        self._sync_mode_ui()
        self.active_mode_changed.emit(target)

    def _on_add_clicked(self) -> None:
        """Memancarkan sinyal permintaan penambahan data untuk mode aktif."""
        self.add_relation_requested.emit(self._active_mode)

    def _focus_active_search(self) -> None:
        """Memfokuskan kolom pencarian pada panel yang sedang ditampilkan."""
        self._panels[self._active_mode].focus_search()

    def _emit_active_refresh(self) -> None:
        """Memancarkan sinyal muat ulang data untuk mode yang sedang aktif."""
        self.refresh_requested.emit(self._active_mode)

    def _handle_phone_copied(self, name: str, phone: str) -> None:
        """Menampilkan umpan balik singkat pada footer saat nomor berhasil disalin.

        Args:
            name: Nama relasi pemilik nomor.
            phone: Nomor telepon yang disalin.
        """
        self._footer_feedback_label.setText(f"Nomor {name} ({phone}) disalin")
        self._feedback_timer.start()
        self.phone_copied.emit(name, phone)

    def _clear_footer_feedback(self) -> None:
        """Menghapus pesan umpan balik sementara pada footer."""
        self._footer_feedback_label.setText("")

    def _sync_mode_ui(self) -> None:
        """Menyinkronkan indeks QStackedWidget, label dinamis, dan footer."""
        is_customer = self._active_mode == "customer"
        self._content_stack.setCurrentIndex(0 if is_customer else 1)

        if is_customer:
            self._subtitle_label.setText(
                "Kelola profil pelanggan, pantau piutang berjalan, dan catat pelunasan."
            )
            self._add_button.setText("+ Tambah Pelanggan")
        else:
            self._subtitle_label.setText(
                "Kelola data pemasok, pantau utang pembelian, dan jadwalkan pembayaran."
            )
            self._add_button.setText("+ Tambah Supplier")

        self._update_footer_count()

    def _update_footer_count(self) -> None:
        """Memperbarui teks jumlah baris yang ditampilkan pada footer."""
        panel = self._panels[self._active_mode]
        entity = "pelanggan" if self._active_mode == "customer" else "supplier"
        self._footer_count_label.setText(f"Menampilkan {panel.get_row_count()} {entity}")

    def toggle_mode(self) -> None:
        """Mengalihkan mode aktif secara bergantian antara Pelanggan dan Supplier."""
        next_mode: RelationType = (
            "supplier" if self._active_mode == "customer" else "customer"
        )
        self.set_active_mode(next_mode, emit_signal=True)

    def on_page_entered(self) -> None:
        """Hook siklus hidup yang dipanggil otomatis oleh MainShell saat halaman dibuka."""
        self.page_entered.emit()

    def set_active_mode(
        self,
        relation_type: RelationType,
        emit_signal: bool = False,
    ) -> None:
        """Mengatur mode tampilan aktif secara terprogram.

        Args:
            relation_type: Mode tujuan ('customer' atau 'supplier').
            emit_signal: Jika True, memancarkan active_mode_changed saat berubah.
        """
        changed = relation_type != self._active_mode
        self._active_mode = relation_type
        self._switcher.set_active_mode(relation_type, emit_signal=False)
        self._sync_mode_ui()
        if emit_signal and changed:
            self.active_mode_changed.emit(relation_type)

    def get_active_mode(self) -> RelationType:
        """Mengembalikan mode relasi yang sedang aktif.

        Returns:
            Literal 'customer' atau 'supplier'.
        """
        return self._active_mode

    def get_filter_state(self, relation_type: RelationType) -> RelationFilterState:
        """Mengambil keadaan filter aktif untuk panel relasi tertentu.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').

        Returns:
            Objek RelationFilterState panel terkait.
        """
        return self._panels[relation_type].get_filter_state()

    def set_relation_records(
        self,
        relation_type: RelationType,
        records: list[RelationRecord],
    ) -> None:
        """Memperbarui data tabel untuk panel pelanggan atau supplier.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
            records: Daftar objek RelationRecord dari backend.
        """
        self._panels[relation_type].set_records(records)
        if relation_type == self._active_mode:
            self._update_footer_count()

    def set_kpi_data(
        self,
        relation_type: RelationType,
        kpi: RelationKpiData,
    ) -> None:
        """Memperbarui kartu KPI dan angka badge pengalih untuk panel tertentu.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
            kpi: Objek RelationKpiData dari backend.
        """
        self._panels[relation_type].set_kpi_data(kpi)
        self._switcher.set_badge_count(relation_type, kpi.active_count)

    def set_mode_badge_count(self, relation_type: RelationType, count: int) -> None:
        """Memperbarui angka badge pada tombol pengalih segmen secara mandiri.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
            count: Jumlah data yang ditampilkan pada badge tombol.
        """
        self._switcher.set_badge_count(relation_type, count)

    def set_loading_state(
        self,
        relation_type: RelationType,
        is_loading: bool,
    ) -> None:
        """Mengatur indikator status pemuatan pada panel tertentu.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
            is_loading: True jika sedang memproses pengambilan data.
        """
        self._panels[relation_type].set_loading(is_loading)

    def clear_search(self, relation_type: RelationType) -> None:
        """Mengosongkan kolom pencarian pada panel relasi yang ditentukan.

        Args:
            relation_type: Jenis relasi target ('customer' atau 'supplier').
        """
        self._panels[relation_type].clear_search()

    def _apply_styles(self) -> None:
        """Menerapkan lembar gaya QSS tema gelap yang selaras dengan title bar."""
        self.setStyleSheet(
            """
            QWidget#RelationManagementPage {
                background-color: #11111B;
                color: #CDD6F4;
                font-family: "Segoe UI";
            }
            QLabel#PageTitle {
                color: #CDD6F4;
                font-size: 20px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#PageSubtitle {
                color: #9399B2;
                font-size: 12px;
                background: transparent;
            }
            QFrame#RelationSwitcher {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QPushButton#SwitcherButton {
                background-color: transparent;
                color: #A6ADC8;
                border: none;
                border-radius: 7px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#SwitcherButton:hover {
                color: #CDD6F4;
                background-color: rgba(205, 214, 244, 0.06);
            }
            QPushButton#SwitcherButton[active="true"] {
                background-color: #313244;
                color: #89B4FA;
            }
            QPushButton#PrimaryButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 0px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #2563EB;
            }
            QPushButton#PrimaryButton:pressed {
                background-color: #1D4ED8;
            }
            QPushButton#SecondaryButton {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #2A2A40;
                border-color: #45475A;
            }
            QPushButton#SecondaryButton:disabled {
                color: #6C7086;
                border-color: #262637;
            }
            QFrame#KpiCard {
                background-color: #181825;
                border: 1px solid #2A2A40;
                border-radius: 10px;
            }
            QLabel#KpiTitle {
                color: #9399B2;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#KpiValue {
                color: #CDD6F4;
                font-size: 20px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#KpiValue[accentRole="primary"] {
                color: #89B4FA;
            }
            QLabel#KpiValue[accentRole="warning"] {
                color: #FAB387;
            }
            QLabel#KpiValue[accentRole="danger"] {
                color: #F38BA8;
            }
            QLabel#KpiValue[accentRole="success"] {
                color: #A6E3A1;
            }
            QLabel#KpiHint {
                color: #6C7086;
                font-size: 11px;
                background: transparent;
            }
            QFrame#FilterBar {
                background-color: #181825;
                border: 1px solid #2A2A40;
                border-radius: 10px;
            }
            QLineEdit#SearchInput {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 0px 10px;
                font-size: 12px;
                selection-background-color: #3B82F6;
            }
            QLineEdit#SearchInput:focus {
                border-color: #89B4FA;
            }
            QComboBox#FilterCombo {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 7px;
                padding: 0px 10px;
                font-size: 12px;
            }
            QComboBox#FilterCombo:hover {
                border-color: #45475A;
            }
            QComboBox#FilterCombo:focus {
                border-color: #89B4FA;
            }
            QComboBox#FilterCombo::drop-down {
                border: none;
                width: 22px;
            }
            QComboBox#FilterCombo QAbstractItemView {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                selection-background-color: #313244;
                selection-color: #89B4FA;
                outline: 0;
            }
            QFrame#TableContainer {
                background-color: #181825;
                border: 1px solid #2A2A40;
                border-radius: 10px;
            }
            QTableWidget#RelationTable {
                background-color: transparent;
                alternate-background-color: #161622;
                color: #CDD6F4;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                selection-background-color: rgba(137, 180, 250, 0.14);
                selection-color: #CDD6F4;
                outline: 0;
            }
            QTableWidget#RelationTable::item {
                padding: 0px 10px;
                border-bottom: 1px solid #242436;
            }
            QTableWidget#RelationTable::item:selected {
                background-color: rgba(137, 180, 250, 0.14);
                color: #CDD6F4;
            }
            QHeaderView::section {
                background-color: #1E1E2E;
                color: #A6ADC8;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 10px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QWidget#TransparentCell {
                background-color: transparent;
                border: none;
            }
            QLabel#CellPhoneText {
                color: #BAC2DE;
                font-size: 12px;
                background: transparent;
            }
            QPushButton#InlineCopyButton {
                background-color: rgba(137, 180, 250, 0.10);
                color: #89B4FA;
                border: none;
                border-radius: 5px;
                padding: 0px 7px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#InlineCopyButton:hover {
                background-color: rgba(137, 180, 250, 0.22);
            }
            QLabel#OutstandingAmount {
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#OutstandingAmount[billingState="clear"] {
                color: #6C7086;
                font-weight: 500;
            }
            QLabel#OutstandingAmount[billingState="pending"] {
                color: #FAB387;
            }
            QLabel#OutstandingAmount[billingState="overdue"] {
                color: #F38BA8;
            }
            QLabel#DueDateSubtext {
                color: #9399B2;
                font-size: 10px;
                background: transparent;
            }
            QLabel#DueDateSubtext[overdue="true"] {
                color: #F38BA8;
            }
            QLabel#StatusBadge {
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 8px;
            }
            QLabel#StatusBadge[active="true"] {
                background-color: rgba(166, 227, 161, 0.14);
                color: #A6E3A1;
            }
            QLabel#StatusBadge[active="false"] {
                background-color: rgba(108, 112, 134, 0.20);
                color: #A6ADC8;
            }
            QPushButton#RowActionNeutral {
                background-color: rgba(205, 214, 244, 0.08);
                color: #CDD6F4;
                border: none;
                border-radius: 6px;
                padding: 0px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#RowActionNeutral:hover {
                background-color: rgba(205, 214, 244, 0.16);
            }
            QPushButton#RowActionAccent {
                background-color: rgba(137, 180, 250, 0.16);
                color: #89B4FA;
                border: none;
                border-radius: 6px;
                padding: 0px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#RowActionAccent:hover {
                background-color: rgba(137, 180, 250, 0.28);
            }
            QPushButton#RowActionAccent:disabled {
                background-color: rgba(108, 112, 134, 0.08);
                color: #585B70;
            }
            QPushButton#RowActionDanger {
                background-color: rgba(243, 139, 168, 0.14);
                color: #F38BA8;
                border: none;
                border-radius: 6px;
                padding: 0px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#RowActionDanger:hover {
                background-color: rgba(243, 139, 168, 0.26);
            }
            QPushButton#RowActionSuccess {
                background-color: rgba(166, 227, 161, 0.14);
                color: #A6E3A1;
                border: none;
                border-radius: 6px;
                padding: 0px 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#RowActionSuccess:hover {
                background-color: rgba(166, 227, 161, 0.26);
            }
            QFrame#EmptyStateCard {
                background-color: transparent;
                border: none;
            }
            QLabel#EmptyStateTitle {
                color: #BAC2DE;
                font-size: 15px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#EmptyStateSubtitle {
                color: #6C7086;
                font-size: 12px;
                background: transparent;
            }
            QLabel#FooterMeta {
                color: #9399B2;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#FooterFeedback {
                color: #A6E3A1;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#FooterHint {
                color: #6C7086;
                font-size: 11px;
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: #161622;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #313244;
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #45475A;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #161622;
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #313244;
                min-width: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #45475A;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            """
        )


class RelationManagementWindow(FramelessMainWindow):
    """Jendela frameless mandiri yang membungkus RelationManagementPage.

    Mengintegrasikan CustomTitleBar dari customwindowtitlebar.py dengan
    halaman manajemen Pelanggan dan Supplier serta menyinkronkan judul
    title bar sesuai mode aktif.

    Attributes:
        page: Instance RelationManagementPage sebagai konten utama jendela.
    """

    def __init__(
        self,
        icon_config: TitleBarIconConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RelationManagementWindow beserta halaman relasi.

        Args:
            icon_config: Konfigurasi ikon custom title bar. Jika None, akan
                memuat konfigurasi bawaan dari ICON_PATHS.
            parent: Widget induk opsional.
        """
        resolved_config = (
            icon_config
            if icon_config is not None
            else TitleBarIconConfig.from_dict(ICON_PATHS)
        )
        super().__init__(
            icon_config=resolved_config,
            page_title="Pelanggan & Supplier - Pelanggan",
            parent=parent,
        )
        self.page = RelationManagementPage(self)
        self.set_content_widget(self.page)
        self.page.active_mode_changed.connect(self._sync_window_title)

    def _sync_window_title(self, relation_type: str) -> None:
        """Memperbarui judul pada CustomTitleBar mengikuti mode aktif.

        Args:
            relation_type: Mode aktif ('customer' atau 'supplier').
        """
        suffix = "Pelanggan" if relation_type == "customer" else "Supplier"
        self.setWindowTitle(f"Pelanggan & Supplier - {suffix}")


