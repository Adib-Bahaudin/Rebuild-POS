"""Modul helper untuk menghubungkan antarmuka RiwayatTransaksiPage dan backend transaksi.

Modul ini bertindak sebagai jembatan (bridge/binder) antara UI RiwayatTransaksiPage
(ui/riwayat_transaksi.py) dan backend pemrosesan query serta laporan transaksi
(core/riwayat_backend.py).
Fasilitas yang disediakan meliputi:
    - Pengikatan (binding) controller RiwayatBackend ke RiwayatTransaksiPage.
    - Dialog detail transaksi interaktif (TransactionDetailDialog) saat tombol 'Detail' diklik.
    - Penanganan pencetakan struk dan notifikasi Toast terintegrasi.
    - Penanganan notifikasi ekspor Excel & PDF berhasil atau gagal.
    - Fungsi pabrik (factory functions) untuk inisialisasi instan dan pendaftaran di MainShell.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import DEFAULT_DB_PATH
from core.riwayat_backend import (
    DEFAULT_PAGE_SIZE,
    PaginatedTransactionsResult,
    RiwayatBackend,
    RiwayatExporter,
    RiwayatRepository,
    TransactionFullDetail,
    format_integer,
    format_rupiah,
)
from ui.riwayat_transaksi import (
    FilterCriteria,
    RiwayatTransaksiPage,
    RiwayatTransaksiWindow,
)
from util.customdialog import CustomDialog

try:
    from pyqttoast import Toast, ToastPreset

    _HAS_TOAST = True
except ImportError:
    Toast = None
    ToastPreset = None
    _HAS_TOAST = False

logger = logging.getLogger(__name__)


class TransactionDetailDialog(CustomDialog):
    """Dialog modal elegan untuk menampilkan rincian lengkap satu faktur transaksi."""

    print_requested = Signal(object)

    def __init__(
        self,
        detail: TransactionFullDetail,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Menginisialisasi dialog detail transaksi.

        Args:
            detail: Objek TransactionFullDetail yang memuat rincian transaksi lengkap.
            parent: Widget induk opsional.
        """
        super().__init__(parent=parent)
        self.detail: TransactionFullDetail = detail

        self.setWindowTitle(f"Detail Transaksi - {detail.metadata.invoice_number}")
        self.setFixedSize(680, 640)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Menyusun antarmuka dan komponen tata letak dialog detail."""
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(14)

        header_card = self._build_header_card()
        main_layout.addWidget(header_card)

        items_table = self._build_items_table()
        main_layout.addWidget(items_table, stretch=1)

        totals_card = self._build_totals_card()
        main_layout.addWidget(totals_card)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        print_btn = QPushButton("Cetak Struk", self)
        print_btn.setFixedHeight(36)
        print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3B82F6,
                    stop: 1 #2563EB
                );
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #60A5FA,
                    stop: 1 #3B82F6
                );
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            """
        )
        print_btn.clicked.connect(self._on_print_clicked)

        close_btn = QPushButton("Tutup", self)
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 6px;
                padding: 0px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
                border-color: #585B70;
            }
            QPushButton:pressed {
                background-color: #1E1E2E;
            }
            """
        )
        close_btn.clicked.connect(self.accept)

        footer_layout.addStretch()
        footer_layout.addWidget(print_btn)
        footer_layout.addWidget(close_btn)
        main_layout.addLayout(footer_layout)

    def _build_header_card(self) -> QFrame:
        """Membangun kartu informasi metadata faktur."""
        card = QFrame(self)
        card.setObjectName("DetailHeaderCard")
        card.setStyleSheet(
            """
            QFrame#DetailHeaderCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(4)

        invoice_label = QLabel(self.detail.metadata.invoice_number, card)
        invoice_label.setStyleSheet("color: #60A5FA; font-size: 16px; font-weight: 700;")

        date_label = QLabel(f"Waktu: {self.detail.metadata.sale_date}", card)
        date_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")

        left_col.addWidget(invoice_label)
        left_col.addWidget(date_label)
        layout.addLayout(left_col, stretch=2)

        mid_col = QVBoxLayout()
        mid_col.setSpacing(4)

        cashier_label = QLabel(f"Kasir: {self.detail.metadata.cashier_name}", card)
        cashier_label.setStyleSheet("color: #CDD6F4; font-size: 12px;")

        customer_label = QLabel(f"Pelanggan: {self.detail.metadata.customer_name}", card)
        customer_label.setStyleSheet("color: #CDD6F4; font-size: 12px;")

        mid_col.addWidget(cashier_label)
        mid_col.addWidget(customer_label)
        layout.addLayout(mid_col, stretch=2)

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        status_text = self.detail.payment.payment_status.upper()
        if status_text == "PAID":
            badge_text = "LUNAS"
            badge_style = "background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid #16A34A;"
        else:
            badge_text = "BELUM LUNAS"
            badge_style = "background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid #DC2626;"

        badge = QLabel(f" {badge_text} ", card)
        badge.setStyleSheet(
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700; {badge_style}"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        method_label = QLabel(f"Metode: {self.detail.payment.payment_method}", card)
        method_label.setStyleSheet("color: #BAC2DE; font-size: 12px; font-weight: 600;")
        method_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_col.addWidget(badge)
        right_col.addWidget(method_label)
        layout.addLayout(right_col, stretch=1)

        return card

    def _build_items_table(self) -> QTableWidget:
        """Membangun tabel daftar barang dan jasa pada faktur."""
        table = QTableWidget(self)
        table.setObjectName("DetailItemsTable")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["No", "Barang / Jasa", "Qty", "Harga", "Subtotal"])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 60)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 120)

        table.setStyleSheet(
            """
            QTableWidget#DetailItemsTable {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
                color: #CDD6F4;
            }
            QHeaderView::section {
                background-color: #1E1E2E;
                color: #A6ADC8;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 6px 8px;
            }
            """
        )

        items = self.detail.items
        table.setRowCount(len(items))

        for idx, it in enumerate(items, start=1):
            qty_str = (
                f"{int(it.quantity)}"
                if it.quantity.is_integer()
                else f"{it.quantity:.2f}"
            )
            col_no = QTableWidgetItem(str(idx))
            col_no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_desc = QTableWidgetItem(it.description)
            col_desc.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            col_qty = QTableWidgetItem(qty_str)
            col_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_price = QTableWidgetItem(format_rupiah(it.unit_price))
            col_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            col_sub = QTableWidgetItem(format_rupiah(it.subtotal))
            col_sub.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            table.setItem(idx - 1, 0, col_no)
            table.setItem(idx - 1, 1, col_desc)
            table.setItem(idx - 1, 2, col_qty)
            table.setItem(idx - 1, 3, col_price)
            table.setItem(idx - 1, 4, col_sub)
            table.setRowHeight(idx - 1, 32)

        return table

    def _build_totals_card(self) -> QFrame:
        """Membangun kartu ringkasan nominal subtotal, diskon, pembulatan, dan total."""
        card = QFrame(self)
        card.setObjectName("DetailTotalsCard")
        card.setStyleSheet(
            """
            QFrame#DetailTotalsCard {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 10px 14px;
            }
            """
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        paid_str = format_rupiah(self.detail.payment.amount_paid)
        change_str = format_rupiah(self.detail.payment.change_amount)

        bayar_label = QLabel(f"Jumlah Diterima: {paid_str}", card)
        bayar_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")

        kembalian_label = QLabel(f"Kembalian: {change_str}", card)
        kembalian_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")

        left_layout.addWidget(bayar_label)
        left_layout.addWidget(kembalian_label)

        if self.detail.metadata.notes:
            notes_label = QLabel(f"Catatan: {self.detail.metadata.notes}", card)
            notes_label.setStyleSheet("color: #9399B2; font-size: 11px; font-style: italic;")
            left_layout.addWidget(notes_label)

        layout.addLayout(left_layout, stretch=1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        subtotal_str = format_rupiah(self.detail.amounts.subtotal)
        discount_str = format_rupiah(self.detail.amounts.discount)
        tip_str = format_rupiah(self.detail.amounts.tip)
        rounding_str = format_rupiah(self.detail.amounts.rounding, show_sign=True)
        total_str = format_rupiah(self.detail.amounts.total)

        sub_label = QLabel(f"Subtotal: {subtotal_str}", card)
        sub_label.setStyleSheet("color: #CDD6F4; font-size: 12px;")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.addWidget(sub_label)

        if self.detail.amounts.discount > 0:
            disc_label = QLabel(f"Diskon: -{discount_str}", card)
            disc_label.setStyleSheet("color: #F87171; font-size: 12px;")
            disc_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(disc_label)

        if self.detail.amounts.tip > 0:
            tip_label = QLabel(f"Tip: +{tip_str}", card)
            tip_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
            tip_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(tip_label)

        if self.detail.amounts.rounding != 0:
            round_label = QLabel(f"Pembulatan: {rounding_str}", card)
            round_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
            round_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(round_label)

        total_label = QLabel(f"TOTAL: {total_str}", card)
        total_label.setStyleSheet("color: #4ADE80; font-size: 16px; font-weight: 700;")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_layout.addWidget(total_label)

        layout.addLayout(right_layout, stretch=1)
        return card

    def _on_print_clicked(self) -> None:
        """Memancarkan sinyal print_requested dan menutup dialog."""
        self.print_requested.emit(self.detail)
        self.accept()


class RiwayatTransaksiHelper(QObject):
    """Helper orkestrator yang mengikat RiwayatTransaksiPage dengan RiwayatBackend.

    Signals:
        data_loaded: Dipancarkan saat data halaman transaksi berhasil dimuat (PaginatedTransactionsResult).
        detail_loaded: Dipancarkan saat detail faktur berhasil diambil (TransactionFullDetail).
        print_data_ready: Dipancarkan saat data faktur siap dicetak (TransactionFullDetail).
        export_succeeded: Dipancarkan saat ekspor Excel/PDF berhasil membawa format dan path (str, str).
        error_occurred: Dipancarkan saat terjadi kesalahan pada backend membawa judul dan pesan (str, str).
    """

    data_loaded = Signal(object)
    detail_loaded = Signal(object)
    print_data_ready = Signal(object)
    export_succeeded = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        page: RiwayatTransaksiPage,
        db_path: Optional[str | Path] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        enable_notifications: bool = True,
        auto_show_detail_dialog: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi helper dan menghubungkan halaman riwayat ke backend.

        Args:
            page: Instance antarmuka RiwayatTransaksiPage yang akan dihubungkan.
            db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
            page_size: Jumlah baris data per halaman tabel.
            enable_notifications: Aktifkan popup notifikasi toast otomatis.
            auto_show_detail_dialog: Tampilkan TransactionDetailDialog otomatis saat tombol Detail diklik.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or page)
        self.page: RiwayatTransaksiPage = page
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.enable_notifications: bool = enable_notifications
        self.auto_show_detail_dialog: bool = auto_show_detail_dialog

        self.backend: RiwayatBackend = RiwayatBackend(
            page=self.page,
            db_path=self.db_path,
            page_size=page_size,
            show_dialogs=not enable_notifications,
        )

        self.repository: RiwayatRepository = self.backend._repository
        self.exporter: RiwayatExporter = self.backend._exporter

        self._on_data_loaded_callbacks: list[Callable[[PaginatedTransactionsResult], None]] = []
        self._on_detail_callbacks: list[Callable[[TransactionFullDetail], None]] = []
        self._on_print_callbacks: list[Callable[[TransactionFullDetail], None]] = []
        self._on_export_callbacks: list[Callable[[str, str], None]] = []

        self._attach_references()
        self._setup_connections()

        logger.info(
            "RiwayatTransaksiHelper berhasil diinisialisasi (DB: %s)",
            self.db_path,
        )

    def _attach_references(self) -> None:
        """Menyimpan referensi helper dan backend pada atribut instance page."""
        setattr(self.page, "_riwayat_helper", self)
        setattr(self.page, "_riwayat_backend", self.backend)

    def _setup_connections(self) -> None:
        """Menghubungkan sinyal-sinyal RiwayatBackend ke handler internal helper."""
        self.backend.data_loaded.connect(self._handle_data_loaded)
        self.backend.detail_loaded.connect(self._handle_detail_loaded)
        self.backend.print_data_ready.connect(self._handle_print_data_ready)
        self.backend.export_succeeded.connect(self._handle_export_succeeded)
        self.backend.error_occurred.connect(self._handle_error_occurred)

    def _handle_data_loaded(self, result: PaginatedTransactionsResult) -> None:
        """Menangani event pemuatan data berhasil dari backend.

        Args:
            result: Objek PaginatedTransactionsResult dari backend.
        """
        self.data_loaded.emit(result)
        for callback in self._on_data_loaded_callbacks:
            try:
                callback(result)
            except Exception:
                logger.exception("Kesalahan pada callback data_loaded")

    def _handle_detail_loaded(self, detail: TransactionFullDetail) -> None:
        """Menangani event pembacaan detail transaksi dan menampilkan dialog jika diaktifkan.

        Args:
            detail: Objek TransactionFullDetail rincian transaksi.
        """
        self.detail_loaded.emit(detail)

        for callback in self._on_detail_callbacks:
            try:
                callback(detail)
            except Exception:
                logger.exception("Kesalahan pada callback detail_loaded")

        if self.auto_show_detail_dialog:
            dialog = TransactionDetailDialog(detail=detail, parent=self.page)
            dialog.print_requested.connect(self._handle_print_data_ready)
            dialog.exec()

    def _handle_print_data_ready(self, detail: TransactionFullDetail) -> None:
        """Menangani permintaan cetak struk dari baris tabel atau dialog detail.

        Args:
            detail: Objek TransactionFullDetail rincian faktur yang akan dicetak.
        """
        self.print_data_ready.emit(detail)

        if self.enable_notifications:
            self.show_toast(
                title="Pencetakan Struk",
                message=f"Data struk faktur {detail.metadata.invoice_number} siap dicetak.",
                is_success=True,
            )

        for callback in self._on_print_callbacks:
            try:
                callback(detail)
            except Exception:
                logger.exception("Kesalahan pada callback print_data_ready")

    def _handle_export_succeeded(self, export_format: str, file_path: str) -> None:
        """Menangani notifikasi ekspor laporan berhasil.

        Args:
            export_format: Format file hasil ekspor ('excel' atau 'pdf').
            file_path: Lokasi file laporan tersimpan.
        """
        self.export_succeeded.emit(export_format, file_path)

        if self.enable_notifications:
            filename = Path(file_path).name
            self.show_toast(
                title="Ekspor Berhasil",
                message=f"Laporan {export_format.upper()} tersimpan: {filename}",
                is_success=True,
            )

        for callback in self._on_export_callbacks:
            try:
                callback(export_format, file_path)
            except Exception:
                logger.exception("Kesalahan pada callback export_succeeded")

    def _handle_error_occurred(self, title: str, message: str) -> None:
        """Menangani kesalahan yang dilaporkan oleh backend.

        Args:
            title: Judul kesalahan.
            message: Rincian pesan kesalahan.
        """
        self.error_occurred.emit(title, message)

        if self.enable_notifications:
            self.show_toast(
                title=title,
                message=message,
                is_success=False,
            )

    def show_toast(self, title: str, message: str, is_success: bool = True) -> None:
        """Menampilkan notifikasi popup Toast elegan pada halaman.

        Args:
            title: Judul notifikasi.
            message: Isi pesan notifikasi.
            is_success: True untuk gaya sukses (hijau), False untuk kesalahan (merah).
        """
        if not _HAS_TOAST or Toast is None or ToastPreset is None:
            return

        try:
            toast = Toast(self.page)
            toast.setDuration(4000)
            toast.setBorderRadius(6)
            toast.setTitle(title)
            toast.setText(message)
            preset = ToastPreset.SUCCESS if is_success else ToastPreset.ERROR
            toast.applyPreset(preset)
            toast.show()
        except Exception:
            logger.debug("Gagal memunculkan widget Toast pada antarmuka riwayat")

    def refresh(self) -> None:
        """Memuat ulang transaksi pada halaman aktif."""
        self.backend.refresh()

    def load_transactions(
        self,
        criteria: Optional[FilterCriteria] = None,
        page: int = 1,
    ) -> Optional[PaginatedTransactionsResult]:
        """Mengambil data transaksi dari backend secara manual.

        Args:
            criteria: Kriteria filter opsional.
            page: Nomor halaman.

        Returns:
            Objek PaginatedTransactionsResult jika sukses.
        """
        return self.backend.load_transactions(criteria=criteria, page=page)

    def get_transaction_detail(self, invoice_number: str) -> Optional[TransactionFullDetail]:
        """Mengambil detail transaksi lengkap berdasarkan nomor faktur.

        Args:
            invoice_number: Nomor faktur transaksi.

        Returns:
            Objek TransactionFullDetail jika ditemukan.
        """
        return self.backend.get_transaction_detail(invoice_number)

    def export_excel(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Mengekspor data transaksi saat ini ke format Excel."""
        return self.backend.export_excel(output_path=output_path)

    def export_pdf(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Mengekspor data transaksi saat ini ke format PDF."""
        return self.backend.export_pdf(output_path=output_path)

    def add_on_data_loaded_callback(
        self,
        callback: Callable[[PaginatedTransactionsResult], None],
    ) -> None:
        """Mendaftarkan callback saat data transaksi berhasil dimuat."""
        if callback not in self._on_data_loaded_callbacks:
            self._on_data_loaded_callbacks.append(callback)

    def add_on_detail_callback(
        self,
        callback: Callable[[TransactionFullDetail], None],
    ) -> None:
        """Mendaftarkan callback saat detail transaksi berhasil diambil."""
        if callback not in self._on_detail_callbacks:
            self._on_detail_callbacks.append(callback)

    def add_on_print_callback(
        self,
        callback: Callable[[TransactionFullDetail], None],
    ) -> None:
        """Mendaftarkan callback saat transaksi siap dicetak."""
        if callback not in self._on_print_callbacks:
            self._on_print_callbacks.append(callback)

    def add_on_export_callback(
        self,
        callback: Callable[[str, str], None],
    ) -> None:
        """Mendaftarkan callback saat ekspor laporan selesai."""
        if callback not in self._on_export_callbacks:
            self._on_export_callbacks.append(callback)


def bind_riwayat_to_backend(
    page: RiwayatTransaksiPage,
    db_path: Optional[str | Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    enable_notifications: bool = True,
    auto_show_detail_dialog: bool = True,
) -> RiwayatTransaksiHelper:
    """Menghubungkan instance RiwayatTransaksiPage yang ada ke backend transaksi.

    Args:
        page: Instance RiwayatTransaksiPage yang sudah diinstansiasi.
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.

    Returns:
        Instance RiwayatTransaksiHelper yang telah terhubung.
    """
    return RiwayatTransaksiHelper(
        page=page,
        db_path=db_path,
        page_size=page_size,
        enable_notifications=enable_notifications,
        auto_show_detail_dialog=auto_show_detail_dialog,
    )


def create_connected_riwayat_page(
    db_path: Optional[str | Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
    auto_show_detail_dialog: bool = True,
) -> RiwayatTransaksiPage:
    """Membuat instance RiwayatTransaksiPage baru sekaligus mengikatnya dengan backend transaksi.

    Args:
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.

    Returns:
        RiwayatTransaksiPage: Instance halaman riwayat yang telah terhubung ke database.
    """
    page = RiwayatTransaksiPage(parent=parent)
    bind_riwayat_to_backend(
        page=page,
        db_path=db_path,
        page_size=page_size,
        enable_notifications=enable_notifications,
        auto_show_detail_dialog=auto_show_detail_dialog,
    )
    return page


def create_connected_riwayat_window(
    db_path: Optional[str | Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
    auto_show_detail_dialog: bool = True,
) -> RiwayatTransaksiWindow:
    """Membuat jendela standalone RiwayatTransaksiWindow yang telah terhubung ke backend.

    Args:
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.

    Returns:
        RiwayatTransaksiWindow: Jendela mandiri riwayat yang siap ditampilkan.
    """
    window = RiwayatTransaksiWindow(parent=parent)
    bind_riwayat_to_backend(
        page=window.page,
        db_path=db_path,
        page_size=page_size,
        enable_notifications=enable_notifications,
        auto_show_detail_dialog=auto_show_detail_dialog,
    )
    window.page.on_page_entered()
    return window
