"""Modul helper untuk menghubungkan antarmuka DashboardPOS dan backend transaksi.

Modul ini bertindak sebagai jembatan (bridge/binder) antara UI DashboardPOS
(ui/dashboard_ui.py) dan backend pemrosesan transaksi FIFO (core/transaksi_backend.py).
Fasilitas yang disediakan meliputi:
    - Pengikatan (binding) controller transaksi ke dashboard.
    - Sinkronisasi kategori produk dari database ke panel pencarian UI.
    - Penanganan notifikasi transaksi berhasil dan gagal (terintegrasi Toast).
    - Manajemen siklus hidup controller dan pembaruan identitas kasir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from config import DEFAULT_DB_PATH
from core.transaksi_backend import (
    TransactionController,
    TransactionRepository,
    TransactionResult,
)
from ui.dashboard_ui import DashboardPOS
from util.custominputdialog import CustomInputDialog
from util.helper.formatrupiah import format_rupiah
from util.helper.toast_helper import show_toast as display_toast

logger = logging.getLogger(__name__)


class DashboardTransaksiHelper(QObject):
    """Helper orkestrator yang mengikat DashboardPOS dengan TransactionController.

    Signals:
        sale_succeeded: Dipancarkan ketika transaksi berhasil disimpan membawa TransactionResult.
        sale_failed: Dipancarkan ketika transaksi gagal membawa pesan kesalahan (str).
        nav_selected: Dipancarkan ketika kasir menavigasi menu sidebar membawa nama menu (str).
    """

    sale_succeeded = Signal(object)
    sale_failed = Signal(str)
    nav_selected = Signal(str)
    DP_PAYMENT_METHODS: tuple[str, ...] = ("Tunai", "QRIS", "Transfer")

    def __init__(
        self,
        dashboard: DashboardPOS,
        db_path: Optional[str | Path] = None,
        cashier_name: Optional[str] = None,
        enable_notifications: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi helper dan menghubungkan dashboard ke backend transaksi.

        Args:
            dashboard: Instance antarmuka DashboardPOS yang akan dihubungkan.
            db_path: Path file database SQLite transaksi. Default menggunakan DEFAULT_DB_PATH.
            cashier_name: Nama kasir aktif (default mengambil dari header dashboard jika None).
            enable_notifications: Aktifkan notifikasi popup/toast otomatis.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or dashboard)
        self.dashboard: DashboardPOS = dashboard
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.enable_notifications: bool = enable_notifications

        effective_cashier = cashier_name or self._extract_cashier_name_from_ui()

        self.controller: TransactionController = TransactionController(
            dashboard=self.dashboard,
            db_path=self.db_path,
            cashier_name=effective_cashier,
            parent=self,
            auto_connect_checkout=False,
        )

        self.repository: TransactionRepository = self.controller.repository

        self._on_completed_callbacks: list[Callable[[TransactionResult], None]] = []
        self._on_failed_callbacks: list[Callable[[str], None]] = []

        self._attach_references()
        self._setup_connections()
        self.load_categories()

        logger.info(
            "DashboardTransaksiHelper berhasil diinisialisasi untuk kasir '%s' (DB: %s)",
            effective_cashier,
            self.db_path,
        )

    def _extract_cashier_name_from_ui(self) -> str:
        """Mengekstrak nama kasir dari teks badge header dashboard jika tersedia.

        Returns:
            Nama kasir string atau default 'KASIR'.
        """
        try:
            badge_text = self.dashboard.header.cashier_badge.text()
            if "NAMA KASIR :" in badge_text:
                return badge_text.replace("NAMA KASIR :", "").strip() or "KASIR"
            return badge_text.strip() or "KASIR"
        except Exception:
            return "KASIR"

    def _attach_references(self) -> None:
        """Menyimpan referensi helper dan controller pada atribut instance dashboard."""
        setattr(self.dashboard, "_transaksi_helper", self)
        setattr(self.dashboard, "_transaksi_controller", self.controller)

    def _setup_connections(self) -> None:
        """Menghubungkan sinyal controller dan navigasi dashboard ke handler helper."""
        self.controller.transaction_completed.connect(self._handle_transaction_completed)
        self.controller.transaction_failed.connect(self._handle_transaction_failed)
        self.dashboard.navigation_requested.connect(self._handle_navigation)
        self.dashboard.checkout_requested.connect(self._handle_checkout_requested)

    def _get_dialog_parent(self) -> QWidget:
        """Mengembalikan widget induk yang aman untuk menampilkan modal dialog.

        Returns:
            Widget jendela utama atau instance dashboard sebagai induk dialog.
        """
        return self.dashboard.window() or self.dashboard

    def _is_partial_unpaid_transaction(self) -> bool:
        """Memeriksa apakah transaksi termasuk pembayaran belum lunas dengan uang muka (DP).

        Kondisi bernilai True apabila dropdown metode bayar bernilai 'Belum Lunas',
        nominal pada kolom bayar lebih dari Rp 1.000, serta hasil get_payment_status()
        mengembalikan 'PARTIAL'.

        Returns:
            True jika transaksi merupakan pembayaran parsial (DP), False sebaliknya.
        """
        payment_panel = self.dashboard.payment_panel
        selected_method = payment_panel.method_combo.currentText().strip()
        payment_data = self.dashboard.get_payment_data()
        amount_paid = int(payment_data.get("amount_paid", 0))
        payment_status = payment_panel.get_payment_status().strip().upper()

        return (
            selected_method == "Belum Lunas"
            and amount_paid > 1000
            and payment_status == "PARTIAL"
        )

    def _prompt_dp_payment_method(self) -> str | None:
        """Menampilkan CustomInputDialog untuk memilih metode pembayaran uang muka (DP).

        Returns:
            Nama metode pembayaran terpilih ('Tunai', 'QRIS', atau 'Transfer'),
            atau None jika kasir membatalkan dialog.
        """
        selected_method, accepted = CustomInputDialog.getItem(
            self._get_dialog_parent(),
            "Metode Pembayaran DP",
            "Pilih metode pembayaran uang muka (DP):",
            list(self.DP_PAYMENT_METHODS),
            0,
            False,
        )
        if not accepted:
            return None

        cleaned_method = selected_method.strip()
        return cleaned_method if cleaned_method else None

    def _handle_checkout_requested(self) -> None:
        """Menangani penekanan tombol Bayar dengan dialog metode DP saat status PARTIAL."""
        if not self.dashboard.get_cart_items():
            self.controller.execute_checkout()
            return

        is_valid, _ = self.dashboard.validate_payment()
        if not is_valid:
            self.controller.execute_checkout()
            return

        if self._is_partial_unpaid_transaction():
            payment_data = self.dashboard.get_payment_data()
            amount_paid = int(payment_data.get("amount_paid", 0))
            current_total = self.controller.get_current_total()

            if current_total > 0 and amount_paid >= current_total:
                self.controller.execute_checkout()
                return

            dp_payment_method = self._prompt_dp_payment_method()
            if dp_payment_method is None:
                logger.debug("Proses pembayaran DP dibatalkan oleh kasir.")
                return

            self.controller.execute_checkout(dp_payment_method=dp_payment_method)
            return

        self.controller.execute_checkout()

    def _handle_transaction_completed(self, result: TransactionResult) -> None:
        """Menangani event transaksi berhasil dari controller.

        Args:
            result: Objek ringkasan transaksi dari backend.
        """
        logger.info(
            "Transaksi berhasil diproses: Faktur %s, Total Rp %d, Kasir: %s",
            result.invoice_number,
            result.total,
            result.cashier_name,
        )

        if self.enable_notifications:
            self.show_toast(
                title="Transaksi Berhasil",
                message=f"Faktur {result.invoice_number} berhasil dicatat (Total: {format_rupiah(result.total)})",
                is_success=True,
            )

        self.sale_succeeded.emit(result)

        for callback in self._on_completed_callbacks:
            try:
                callback(result)
            except Exception:
                logger.exception("Kesalahan saat mengeksekusi callback on_completed")

    def _handle_transaction_failed(self, error_message: str) -> None:
        """Menangani event transaksi gagal dari controller.

        Args:
            error_message: Pesan rincian penyebab kegagalan.
        """
        logger.warning("Transaksi ditolak atau gagal: %s", error_message)

        if self.enable_notifications:
            self.show_toast(
                title="Transaksi Ditolak",
                message=error_message,
                is_success=False,
            )

        self.sale_failed.emit(error_message)

        for callback in self._on_failed_callbacks:
            try:
                callback(error_message)
            except Exception:
                logger.exception("Kesalahan saat mengeksekusi callback on_failed")

    def _handle_navigation(self, menu_key: str) -> None:
        """Menangani pergantian menu sidebar dari dashboard.

        Args:
            menu_key: Kunci pengenal menu yang dipilih kasir.
        """
        logger.debug("Menu sidebar dipilih: %s", menu_key)
        self.nav_selected.emit(menu_key)

    def show_toast(self, title: str, message: str, is_success: bool = True) -> None:
        """Menampilkan notifikasi toast melayang jika library pyqttoast terpasang.

        Args:
            title: Judul pop-up notifikasi.
            message: Isi teks ringkas pesan.
            is_success: True untuk status sukses (hijau), False untuk status gagal (merah).
        """
        target_parent: QWidget = self.dashboard.window() or self.dashboard
        display_toast(
            parent=target_parent,
            title=title,
            message=message,
            is_success=is_success,
            duration_ms=3500,
            border_radius=6,
        )

    def load_categories(self) -> list[str]:
        """Membaca daftar kategori aktif dari repository dan menerapkannya ke dropdown pencarian.

        Returns:
            Daftar lengkap nama kategori yang disetel pada dropdown pencarian.
        """
        standard_categories = ["Semua Produk", "Produk Satuan", "Produk Paket", "Jasa"]
        db_categories = self.repository.fetch_active_categories()

        all_categories = list(standard_categories)
        for cat in db_categories:
            if cat not in all_categories:
                all_categories.append(cat)

        self.dashboard.search_panel.set_categories(all_categories)
        logger.debug("Kategori pencarian berhasil diselaraskan: %s", all_categories)
        return all_categories

    def update_cashier(self, cashier_name: str, user_role: Optional[str] = None) -> None:
        """Memperbarui nama kasir dan hak akses pada controller dan header visual.

        Args:
            cashier_name: Nama pengguna atau kasir baru.
            user_role: Peran hak akses baru (opsional).
        """
        self.controller.set_cashier_name(cashier_name)
        role = user_role or "USER"
        self.dashboard.set_user_info(cashier_name, role)
        logger.info("Kasir diperbarui menjadi: %s (Role: %s)", cashier_name, role)

    def reset_transaction(self) -> None:
        """Mereset seluruh keranjang transaksi, input pembayaran, dan ringkasan."""
        self.controller._handle_clear_cart()

    def add_on_completed_callback(self, callback: Callable[[TransactionResult], None]) -> None:
        """Mendaftarkan fungsi callback tambahan yang dipanggil saat transaksi sukses.

        Args:
            callback: Fungsi yang menerima objek TransactionResult.
        """
        if callback not in self._on_completed_callbacks:
            self._on_completed_callbacks.append(callback)

    def add_on_failed_callback(self, callback: Callable[[str], None]) -> None:
        """Mendaftarkan fungsi callback tambahan yang dipanggil saat transaksi gagal.

        Args:
            callback: Fungsi yang menerima string pesan kesalahan.
        """
        if callback not in self._on_failed_callbacks:
            self._on_failed_callbacks.append(callback)


def bind_dashboard_to_backend(
    dashboard: DashboardPOS,
    db_path: Optional[str | Path] = None,
    cashier_name: Optional[str] = None,
    enable_notifications: bool = True,
) -> DashboardTransaksiHelper:
    """Fungsi pembantu untuk menghubungkan instance DashboardPOS yang ada ke backend transaksi.

    Args:
        dashboard: Objek DashboardPOS yang sudah diinstansiasi.
        db_path: Lokasi file database transaksi SQLite. Default DEFAULT_DB_PATH.
        cashier_name: Nama kasir aktif (opsional).
        enable_notifications: Status aktifkan popup notifikasi toast.

    Returns:
        Instance DashboardTransaksiHelper yang telah terhubung.
    """
    return DashboardTransaksiHelper(
        dashboard=dashboard,
        db_path=db_path,
        cashier_name=cashier_name,
        enable_notifications=enable_notifications,
    )


def create_connected_dashboard(
    user_name: str = "KASIR",
    user_role: str = "USER",
    db_path: Optional[str | Path] = None,
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
) -> DashboardPOS:
    """Membuat instance DashboardPOS baru sekaligus mengikatnya dengan backend transaksi.

    Args:
        user_name: Nama kasir aktif.
        user_role: Role akses kasir (USER / ADMIN / SUPER USER).
        db_path: Lokasi file database transaksi SQLite. Default DEFAULT_DB_PATH.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.

    Returns:
        DashboardPOS: Instance dashboard yang telah terhubung.
    """
    dashboard = DashboardPOS(user_name=user_name, user_role=user_role, parent=parent)
    bind_dashboard_to_backend(
        dashboard=dashboard,
        db_path=db_path,
        cashier_name=user_name,
        enable_notifications=enable_notifications,
    )
    return dashboard
