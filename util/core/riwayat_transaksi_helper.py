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

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from config import DEFAULT_DB_PATH
from core.riwayat_backend import (
    DEFAULT_PAGE_SIZE,
    PaginatedTransactionsResult,
    RiwayatBackend,
    RiwayatExporter,
    RiwayatRepository,
    TransactionFullDetail,
)
from util.helper.formatrupiah import format_rupiah
from ui.dialog.dialogdetailtransaksi import TransactionDetailDialog
from ui.riwayat_transaksi import (
    FilterCriteria,
    RiwayatTransaksiPage,
    RiwayatTransaksiWindow,
)

try:
    from pyqttoast import Toast, ToastPreset

    _HAS_TOAST = True
except ImportError:
    Toast = None
    ToastPreset = None
    _HAS_TOAST = False

logger = logging.getLogger(__name__)


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
        cashier_name: Optional[str] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi helper dan menghubungkan halaman riwayat ke backend.

        Args:
            page: Instance antarmuka RiwayatTransaksiPage yang akan dihubungkan.
            db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
            page_size: Jumlah baris data per halaman tabel.
            enable_notifications: Aktifkan popup notifikasi toast otomatis.
            auto_show_detail_dialog: Tampilkan TransactionDetailDialog otomatis saat tombol Detail diklik.
            cashier_name: Nama kasir yang sedang login saat ini.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or page)
        self.page: RiwayatTransaksiPage = page
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.enable_notifications: bool = enable_notifications
        self.auto_show_detail_dialog: bool = auto_show_detail_dialog
        self.cashier_name: str = (cashier_name or "").strip() or "KASIR"

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
            dialog = TransactionDetailDialog(
                detail=detail,
                parent=self.page,
                payment_handler=self._handle_debt_payment,
            )
            dialog.print_requested.connect(self._handle_print_data_ready)
            dialog.exec()

    def _handle_debt_payment(
        self,
        invoice_number: str,
        amount: int,
        payment_method: str,
        notes: str = "",
    ) -> Optional[TransactionFullDetail]:
        """Memproses pembayaran hutang dari dialog detail transaksi.

        Args:
            invoice_number: Nomor faktur transaksi yang dibayar.
            amount: Nominal pembayaran yang dimasukkan pengguna.
            payment_method: Metode pembayaran yang dipilih.
            notes: Catatan tambahan pembayaran dari pengguna.

        Returns:
            Objek TransactionFullDetail terbaru jika pembayaran berhasil dicatat.
        """
        updated_detail = self.backend.record_debt_payment(
            invoice_number=invoice_number,
            tendered_amount=amount,
            payment_method=payment_method,
            cashier_name=self.cashier_name,
            notes=notes,
        )
        if updated_detail is not None and self.enable_notifications:
            self.show_toast(
                title="Pembayaran Dicatat",
                message=(
                    f"Pembayaran {format_rupiah(amount)} ({payment_method}) "
                    f"untuk {invoice_number} berhasil disimpan."
                ),
                is_success=True,
            )
        return updated_detail

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
    cashier_name: Optional[str] = None,
) -> RiwayatTransaksiHelper:
    """Menghubungkan instance RiwayatTransaksiPage yang ada ke backend transaksi.

    Args:
        page: Instance RiwayatTransaksiPage yang sudah diinstansiasi.
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.
        cashier_name: Nama kasir yang sedang login saat ini.

    Returns:
        Instance RiwayatTransaksiHelper yang telah terhubung.
    """
    return RiwayatTransaksiHelper(
        page=page,
        db_path=db_path,
        page_size=page_size,
        enable_notifications=enable_notifications,
        auto_show_detail_dialog=auto_show_detail_dialog,
        cashier_name=cashier_name,
    )


def create_connected_riwayat_page(
    db_path: Optional[str | Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
    auto_show_detail_dialog: bool = True,
    cashier_name: Optional[str] = None,
) -> RiwayatTransaksiPage:
    """Membuat instance RiwayatTransaksiPage baru sekaligus mengikatnya dengan backend transaksi.

    Args:
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.
        cashier_name: Nama kasir yang sedang login saat ini.

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
        cashier_name=cashier_name,
    )
    return page


def create_connected_riwayat_window(
    db_path: Optional[str | Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
    auto_show_detail_dialog: bool = True,
    cashier_name: Optional[str] = None,
) -> RiwayatTransaksiWindow:
    """Membuat jendela standalone RiwayatTransaksiWindow yang telah terhubung ke backend.

    Args:
        db_path: Lokasi file database SQLite transaksi. Default DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.
        auto_show_detail_dialog: Status tampilkan dialog modal detail otomatis saat tombol Detail diklik.
        cashier_name: Nama kasir yang sedang login saat ini.

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
        cashier_name=cashier_name,
    )
    window.page.on_page_entered()
    return window
