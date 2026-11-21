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
import sqlite3
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from core.transaksi_backend import (
    TransactionController,
    TransactionRepository,
    TransactionResult,
)
from ui.dashboard_ui import DashboardPOS

try:
    from pyqttoast import Toast, ToastPreset
    _HAS_TOAST = True
except ImportError:
    Toast = None
    ToastPreset = None
    _HAS_TOAST = False

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

    def __init__(
        self,
        dashboard: DashboardPOS,
        db_path: str | Path = "data/transaksi.db",
        cashier_name: Optional[str] = None,
        enable_notifications: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi helper dan menghubungkan dashboard ke backend transaksi.

        Args:
            dashboard: Instance antarmuka DashboardPOS yang akan dihubungkan.
            db_path: Path file database SQLite transaksi.
            cashier_name: Nama kasir aktif (default mengambil dari header dashboard jika None).
            enable_notifications: Aktifkan notifikasi popup/toast otomatis.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or dashboard)
        self.dashboard: DashboardPOS = dashboard
        self.db_path: Path = Path(db_path)
        self.enable_notifications: bool = enable_notifications

        effective_cashier = cashier_name or self._extract_cashier_name_from_ui()

        self.controller: TransactionController = TransactionController(
            dashboard=self.dashboard,
            db_path=self.db_path,
            cashier_name=effective_cashier,
            parent=self,
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
                message=f"Faktur {result.invoice_number} berhasil dicatat (Total: Rp {result.total:,})".replace(",", "."),
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
        if not _HAS_TOAST or Toast is None or ToastPreset is None:
            return

        try:
            target_parent: QWidget = self.dashboard.window() or self.dashboard
            toast = Toast(target_parent)
            toast.setDuration(3500)
            toast.setBorderRadius(6)
            toast.setTitle(title)
            toast.setText(message)
            preset = ToastPreset.SUCCESS if is_success else ToastPreset.ERROR
            toast.applyPreset(preset)
            toast.show()
        except Exception:
            logger.debug("Gagal memunculkan widget Toast pada antarmuka")

    def load_categories(self) -> list[str]:
        """Membaca daftar kategori aktif dari database dan menerapkannya ke dropdown pencarian.

        Returns:
            Daftar lengkap nama kategori yang disetel pada dropdown pencarian.
        """
        standard_categories = ["Semua Produk", "Produk Satuan", "Produk Paket", "Jasa"]
        db_categories: list[str] = []

        if self.db_path.exists():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        """
                        SELECT name
                        FROM categories
                        WHERE is_active = 1
                        ORDER BY name COLLATE NOCASE ASC;
                        """
                    )
                    db_categories = [row[0] for row in cursor.fetchall() if row[0]]
            except sqlite3.Error:
                logger.debug("Tabel categories belum tersedia atau gagal dibaca pada %s", self.db_path)

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
    db_path: str | Path = "data/transaksi.db",
    cashier_name: Optional[str] = None,
    enable_notifications: bool = True,
) -> DashboardTransaksiHelper:
    """Fungsi pembantu untuk menghubungkan instance DashboardPOS yang ada ke backend transaksi.

    Args:
        dashboard: Objek DashboardPOS yang sudah diinstansiasi.
        db_path: Lokasi file database transaksi SQLite.
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
    db_path: str | Path = "data/transaksi.db",
    parent: Optional[QWidget] = None,
    enable_notifications: bool = True,
) -> DashboardPOS:
    """Membuat instance DashboardPOS baru sekaligus mengikatnya dengan backend transaksi.

    Args:
        user_name: Nama kasir aktif.
        user_role: Role akses kasir (USER / ADMIN / SUPER USER).
        db_path: Lokasi file database transaksi SQLite.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan popup notifikasi toast.

    Returns:
        Tuple berisi (dashboard_instance, helper_instance).
    """
    dashboard = DashboardPOS(user_name=user_name, user_role=user_role, parent=parent)
    bind_dashboard_to_backend(
        dashboard=dashboard,
        db_path=db_path,
        cashier_name=user_name,
        enable_notifications=enable_notifications,
    )
    return dashboard
