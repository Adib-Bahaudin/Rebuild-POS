"""Modul helper penghubung antara ManajemenProdukPage dan backend produk.

Modul ini bertindak sebagai jembatan (bridge/binder) antara antarmuka
ManajemenProdukPage (ui/manajemenproduk.py) dan pengendali backend
ManajemenProdukBackend (core/manajemen_produk_backend.py).

Fasilitas yang disediakan meliputi:
    - Pengikatan (binding) controller ManajemenProdukBackend ke ManajemenProdukPage.
    - Integrasi notifikasi popup Toast untuk status keberhasilan dan kesalahan.
    - Pendaftaran handler dialog modular (barang, jasa, stok, kartu stok, master)
      agar dialog dapat dipasang terpisah tanpa mengubah logika backend.
    - Fungsi pabrik (factory functions) untuk pendaftaran langsung pada MainShell
      maupun eksekusi jendela standalone ManajemenProdukWindow.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from config import DEFAULT_DB_PATH
from core.manajemen_produk_backend import (
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_PAGE_SIZE,
    ItemEditData,
    ItemFormPayload,
    ManajemenProdukBackend,
    ManajemenProdukRepository,
    PaginatedProductsResult,
    ServiceEditData,
    ServiceFormPayload,
    StockAdjustmentPayload,
    StockMovementRecord,
    UnitRecord,
)
from ui.customwindowtitlebar import ICON_PATHS, TitleBarIconConfig
from ui.dialog.dialogtambahedititem import ItemFormDialog
from ui.dialog.ServiceFormDialog import MaterialItemOption, ServiceFormDialog
from ui.dialog.StockCardDialog import StockCardDialog, StockCardItemInfo
from ui.dialog.dialogeditkategoriunit import MasterCategoryUnitDialog
from ui.manajemenproduk import (
    CategoryOption,
    ManajemenProdukPage,
    ManajemenProdukWindow,
    ProductFilterState,
)
from ui.dialog.dialogopname import (
    StockAdjustmentDialog,
    StockItemOption,
)
from util.helper.toast_helper import show_toast as display_toast

logger = logging.getLogger(__name__)

ItemDialogHandler = Callable[
    [QWidget, ItemEditData | None, list[CategoryOption], list[UnitRecord]],
    ItemFormPayload | None,
]
ServiceDialogHandler = Callable[
    [QWidget, ServiceEditData | None],
    ServiceFormPayload | None,
]
StockAdjustmentDialogHandler = Callable[
    [QWidget, int | None],
    StockAdjustmentPayload | None,
]
StockCardDialogHandler = Callable[
    [QWidget, int, list[StockMovementRecord]],
    None,
]
MasterDialogHandler = Callable[
    [QWidget, ManajemenProdukBackend],
    None,
]


class ManajemenProdukHelper(QObject):
    """Helper orkestrator yang mengikat ManajemenProdukPage dengan backend produk.

    Signals:
        data_loaded: Dipancarkan membawa PaginatedProductsResult saat data termuat.
        open_add_item_dialog: Diteruskan saat tombol tambah barang ditekan.
        open_edit_item_dialog: Diteruskan membawa ItemEditData saat edit barang.
        open_add_service_dialog: Diteruskan saat tombol tambah jasa ditekan.
        open_edit_service_dialog: Diteruskan membawa ServiceEditData saat edit jasa.
        open_stock_adjustment_dialog: Diteruskan membawa item_id opsional.
        open_stock_card_dialog: Diteruskan membawa (item_id, list[StockMovementRecord]).
        open_master_dialog: Diteruskan saat tombol kategori dan satuan ditekan.
        action_succeeded: Dipancarkan membawa (judul, pesan) saat operasi tulis sukses.
        error_occurred: Dipancarkan membawa (judul, pesan) saat terjadi kesalahan.
    """

    data_loaded = Signal(object)
    open_add_item_dialog = Signal()
    open_edit_item_dialog = Signal(object)
    open_add_service_dialog = Signal()
    open_edit_service_dialog = Signal(object)
    open_stock_adjustment_dialog = Signal(object)
    open_stock_card_dialog = Signal(int, list)
    open_master_dialog = Signal()
    action_succeeded = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        page: ManajemenProdukPage,
        db_path: str | Path | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
        enable_notifications: bool = True,
        auto_load: bool = True,
        parent: QObject | None = None,
    ) -> None:
        """Menginisialisasi helper dan menghubungkan halaman produk ke backend.

        Args:
            page: Instance antarmuka ManajemenProdukPage yang akan dikelola.
            db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
            page_size: Jumlah maksimal baris data per halaman tabel.
            low_stock_threshold: Ambang batas stok menipis dalam satuan dasar.
            enable_notifications: Aktifkan popup notifikasi Toast otomatis.
            auto_load: Jika True, langsung memuat data awal setelah inisialisasi.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or page)
        self.page: ManajemenProdukPage = page
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.enable_notifications: bool = enable_notifications

        self.backend: ManajemenProdukBackend = ManajemenProdukBackend(
            page=self.page,
            db_path=self.db_path,
            page_size=page_size,
            low_stock_threshold=low_stock_threshold,
            show_dialogs=not enable_notifications,
        )
        self.repository: ManajemenProdukRepository = self.backend.repository

        self._item_dialog_handler: ItemDialogHandler | None = None
        self._service_dialog_handler: ServiceDialogHandler | None = None
        self._stock_adjustment_handler: StockAdjustmentDialogHandler | None = None
        self._stock_card_handler: StockCardDialogHandler | None = None
        self._master_dialog_handler: MasterDialogHandler | None = None

        self.set_item_dialog_handler(ItemFormDialog.get_item_payload)
        self.set_stock_card_dialog_handler(self._open_stock_card_dialog)
        self.set_master_dialog_handler(MasterCategoryUnitDialog.show_dialog)
        
        self.set_service_dialog_handler(
            lambda parent, edit_data: ServiceFormDialog.get_service_payload(
                parent=parent,
                edit_data=edit_data,
                material_options=[
                    MaterialItemOption(*row)
                    for row in self.repository.fetch_material_item_options(
                        include_inactive=edit_data is not None
                    )
                ],
            )
        )

        self.set_stock_adjustment_dialog_handler(
            lambda parent, item_id: StockAdjustmentDialog.get_adjustment_payload(
                parent=parent,
                item_options=[
                    StockItemOption(*row)
                    for row in self.repository.fetch_stock_item_options()
                ],
                preselected_item_id=item_id,
            )
        )

        self._on_data_loaded_callbacks: list[
            Callable[[PaginatedProductsResult], None]
        ] = []

        self._attach_references()
        self._setup_connections()

        if auto_load:
            self.refresh()

        logger.info(
            "ManajemenProdukHelper berhasil diinisialisasi (DB: %s)",
            self.db_path,
        )

    def _attach_references(self) -> None:
        """Menyimpan referensi helper dan backend pada atribut instance halaman."""
        setattr(self.page, "_produk_helper", self)
        setattr(self.page, "_produk_backend", self.backend)

    def _setup_connections(self) -> None:
        """Menghubungkan seluruh sinyal ManajemenProdukBackend ke handler helper."""
        self.backend.data_loaded.connect(self._handle_data_loaded)
        self.backend.open_add_item_dialog.connect(self._handle_open_add_item)
        self.backend.open_edit_item_dialog.connect(self._handle_open_edit_item)
        self.backend.open_add_service_dialog.connect(self._handle_open_add_service)
        self.backend.open_edit_service_dialog.connect(
            self._handle_open_edit_service
        )
        self.backend.open_stock_adjustment_dialog.connect(
            self._handle_open_stock_adjustment
        )
        self.backend.open_stock_card_dialog.connect(self._handle_open_stock_card)
        self.backend.open_master_dialog.connect(self._handle_open_master_dialog)
        self.backend.action_succeeded.connect(self._handle_action_succeeded)
        self.backend.error_occurred.connect(self._handle_error_occurred)

    def set_item_dialog_handler(self, handler: ItemDialogHandler | None) -> None:
        """Mendaftarkan handler pembuka dialog tambah dan edit barang fisik.

        Args:
            handler: Callable yang menampilkan dialog barang dan mengembalikan
                ItemFormPayload apabila pengguna menekan Simpan.
        """
        self._item_dialog_handler = handler

    def set_service_dialog_handler(
        self,
        handler: ServiceDialogHandler | None,
    ) -> None:
        """Mendaftarkan handler pembuka dialog tambah dan edit layanan jasa.

        Args:
            handler: Callable yang menampilkan dialog jasa dan mengembalikan
                ServiceFormPayload apabila pengguna menekan Simpan.
        """
        self._service_dialog_handler = handler

    def set_stock_adjustment_dialog_handler(
        self,
        handler: StockAdjustmentDialogHandler | None,
    ) -> None:
        """Mendaftarkan handler pembuka dialog stok awal dan penyesuaian opname.

        Args:
            handler: Callable yang menampilkan dialog penyesuaian stok dan
                mengembalikan StockAdjustmentPayload apabila disimpan.
        """
        self._stock_adjustment_handler = handler

    def set_stock_card_dialog_handler(
        self,
        handler: StockCardDialogHandler | None,
    ) -> None:
        """Mendaftarkan handler pembuka dialog kartu stok barang.

        Args:
            handler: Callable yang menampilkan riwayat mutasi stok barang.
        """
        self._stock_card_handler = handler

    def set_master_dialog_handler(
        self,
        handler: MasterDialogHandler | None,
    ) -> None:
        """Mendaftarkan handler pembuka dialog master kategori dan satuan.

        Args:
            handler: Callable yang menampilkan dialog manajemen kategori dan satuan.
        """
        self._master_dialog_handler = handler

    def _handle_data_loaded(self, result: object) -> None:
        """Menangani sinyal data termuat dan menjalankan callback terdaftar.

        Args:
            result: Objek hasil pemuatan halaman dari backend.
        """
        if not isinstance(result, PaginatedProductsResult):
            return
        self.data_loaded.emit(result)
        for callback in self._on_data_loaded_callbacks:
            try:
                callback(result)
            except Exception:
                logger.exception("Kesalahan pada callback data_loaded produk")

    def _handle_open_add_item(self) -> None:
        """Menangani permintaan buka dialog tambah barang baru."""
        self.open_add_item_dialog.emit()
        if self._item_dialog_handler is None:
            self._notify_dialog_unregistered("Form Tambah Barang")
            return

        categories = self.repository.fetch_category_options()
        units = self.repository.fetch_units()
        payload = self._item_dialog_handler(self.page, None, categories, units)
        if payload is not None:
            self.backend.create_item(payload)

    def _handle_open_edit_item(self, edit_data: object) -> None:
        """Menangani permintaan buka dialog edit barang fisik.

        Args:
            edit_data: Objek ItemEditData berisi data barang terpilih.
        """
        if not isinstance(edit_data, ItemEditData):
            return
        self.open_edit_item_dialog.emit(edit_data)
        if self._item_dialog_handler is None:
            self._notify_dialog_unregistered("Form Edit Barang")
            return

        categories = self.repository.fetch_category_options(include_inactive=True)
        units = self.repository.fetch_units()
        payload = self._item_dialog_handler(
            self.page,
            edit_data,
            categories,
            units,
        )
        if payload is not None:
            self.backend.update_item(edit_data.item_id, payload)

    def _handle_open_add_service(self) -> None:
        """Menangani permintaan buka dialog tambah layanan jasa baru."""
        self.open_add_service_dialog.emit()
        if self._service_dialog_handler is None:
            self._notify_dialog_unregistered("Form Tambah Jasa")
            return

        payload = self._service_dialog_handler(self.page, None)
        if payload is not None:
            self.backend.create_service(payload)

    def _handle_open_edit_service(self, edit_data: object) -> None:
        """Menangani permintaan buka dialog edit layanan jasa.

        Args:
            edit_data: Objek ServiceEditData berisi data jasa terpilih.
        """
        if not isinstance(edit_data, ServiceEditData):
            return
        self.open_edit_service_dialog.emit(edit_data)
        if self._service_dialog_handler is None:
            self._notify_dialog_unregistered("Form Edit Jasa")
            return

        payload = self._service_dialog_handler(self.page, edit_data)
        if payload is not None:
            self.backend.update_service(edit_data.service_id, payload)

    def _handle_open_stock_adjustment(self, item_id: object) -> None:
        """Menangani permintaan buka dialog stok awal atau penyesuaian opname.

        Args:
            item_id: ID barang terpilih secara opsional atau None.
        """
        resolved_id = item_id if isinstance(item_id, int) else None
        self.open_stock_adjustment_dialog.emit(resolved_id)
        if self._stock_adjustment_handler is None:
            self._notify_dialog_unregistered("Dialog Stok Awal / Opname")
            return

        payload = self._stock_adjustment_handler(self.page, resolved_id)
        if payload is not None:
            self.backend.record_stock_adjustment(payload)

    def _handle_open_stock_card(
        self,
        item_id: int,
        records: list[object],
    ) -> None:
        """Menangani permintaan buka dialog kartu stok riwayat mutasi barang.

        Args:
            item_id: Primary key barang target.
            records: Daftar catatan StockMovementRecord dari backend.
        """
        typed_records = [
            rec for rec in records if isinstance(rec, StockMovementRecord)
        ]
        self.open_stock_card_dialog.emit(item_id, typed_records)
        if self._stock_card_handler is None:
            self._notify_dialog_unregistered("Dialog Kartu Stok")
            return

        self._stock_card_handler(self.page, item_id, typed_records)

    def _handle_open_master_dialog(self) -> None:
        """Menangani permintaan buka dialog manajemen master kategori dan satuan."""
        self.open_master_dialog.emit()
        if self._master_dialog_handler is None:
            self._notify_dialog_unregistered("Dialog Kategori & Satuan")
            return

        self._master_dialog_handler(self.page, self.backend)

    def _open_stock_card_dialog(
        self,
        parent: QWidget,
        item_id: int,
        records: list[StockMovementRecord],
    ) -> None:
        """Membuka StockCardDialog lengkap dengan informasi header barang."""
        detail = self.repository.fetch_item_detail(item_id)
        item_info: StockCardItemInfo | None = None
        if detail is not None:
            symbol = detail.base_unit_name.split("(")[-1].rstrip(")").strip()
            item_info = StockCardItemInfo(
                item_id=detail.item_id,
                sku=detail.sku,
                name=detail.name,
                base_unit_symbol=symbol,
                current_stock_text=detail.total_stock_text,
            )
        StockCardDialog.show_stock_card(
            parent=parent,
            records=records,
            item_info=item_info,
        )

    def _handle_action_succeeded(self, title: str, message: str) -> None:
        """Menangani notifikasi keberhasilan operasi simpan atau ubah data.

        Args:
            title: Judul notifikasi keberhasilan.
            message: Rincian pesan keberhasilan.
        """
        self.action_succeeded.emit(title, message)
        if self.enable_notifications:
            self.show_toast(title=title, message=message, is_success=True)

    def _handle_error_occurred(self, title: str, message: str) -> None:
        """Menangani notifikasi kesalahan dari lapisan backend.

        Args:
            title: Judul pesan kesalahan.
            message: Rincian pesan kesalahan.
        """
        self.error_occurred.emit(title, message)
        if self.enable_notifications:
            self.show_toast(title=title, message=message, is_success=False)

    def _notify_dialog_unregistered(self, dialog_name: str) -> None:
        """Menampilkan informasi bahwa dialog terkait belum dihubungkan.

        Args:
            dialog_name: Nama tampilan dialog yang belum terpasang.
        """
        logger.info("%s belum dihubungkan pada ManajemenProdukHelper", dialog_name)
        if self.enable_notifications:
            self.show_toast(
                title=dialog_name,
                message=f"{dialog_name} belum dihubungkan ke halaman ini.",
                is_success=False,
            )

    def show_toast(
        self,
        title: str,
        message: str,
        is_success: bool = True,
    ) -> None:
        """Menampilkan notifikasi popup Toast pada halaman manajemen produk.

        Args:
            title: Judul notifikasi.
            message: Isi pesan notifikasi.
            is_success: True untuk preset sukses, False untuk preset kesalahan.
        """
        display_toast(
            parent=self.page,
            title=title,
            message=message,
            is_success=is_success,
            duration_ms=4000,
            border_radius=6,
        )

    def refresh(self) -> PaginatedProductsResult | None:
        """Memuat ulang seluruh data kategori, metrik, tabel, dan panel detail.

        Returns:
            Objek PaginatedProductsResult jika pemuatan sukses, atau None.
        """
        return self.backend.refresh()

    def load_page(
        self,
        filter_state: ProductFilterState | None = None,
        page: int = 1,
    ) -> PaginatedProductsResult | None:
        """Memuat data halaman produk secara manual dengan filter tertentu.

        Args:
            filter_state: Snapshot filter opsional.
            page: Nomor halaman tujuan berbasis 1.

        Returns:
            Objek PaginatedProductsResult jika berhasil, atau None.
        """
        return self.backend.load_page(filter_state=filter_state, page=page)

    def add_on_data_loaded_callback(
        self,
        callback: Callable[[PaginatedProductsResult], None],
    ) -> None:
        """Mendaftarkan callback eksternal setiap kali data halaman termuat.

        Args:
            callback: Fungsi penerima objek PaginatedProductsResult.
        """
        if callback not in self._on_data_loaded_callbacks:
            self._on_data_loaded_callbacks.append(callback)


def bind_manajemen_produk_to_backend(
    page: ManajemenProdukPage,
    db_path: str | Path | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
    enable_notifications: bool = True,
    auto_load: bool = True,
) -> ManajemenProdukHelper:
    """Menghubungkan instance ManajemenProdukPage yang ada ke backend produk.

    Args:
        page: Instance ManajemenProdukPage yang sudah dibuat.
        db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman tabel.
        low_stock_threshold: Ambang batas stok menipis dalam satuan dasar.
        enable_notifications: Status aktifkan notifikasi Toast otomatis.
        auto_load: Status muat data otomatis saat inisialisasi.

    Returns:
        Instance ManajemenProdukHelper yang telah terhubung ke backend.
    """
    return ManajemenProdukHelper(
        page=page,
        db_path=db_path,
        page_size=page_size,
        low_stock_threshold=low_stock_threshold,
        enable_notifications=enable_notifications,
        auto_load=auto_load,
    )


def create_connected_manajemen_produk_page(
    db_path: str | Path | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
    parent: QWidget | None = None,
    enable_notifications: bool = True,
    auto_load: bool = True,
) -> ManajemenProdukPage:
    """Membuat ManajemenProdukPage baru sekaligus mengikatnya dengan backend.

    Args:
        db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman tabel.
        low_stock_threshold: Ambang batas stok menipis dalam satuan dasar.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan notifikasi Toast otomatis.
        auto_load: Status muat data otomatis saat inisialisasi.

    Returns:
        Instance ManajemenProdukPage yang siap didaftarkan ke MainShell.
    """
    page = ManajemenProdukPage(parent=parent)
    bind_manajemen_produk_to_backend(
        page=page,
        db_path=db_path,
        page_size=page_size,
        low_stock_threshold=low_stock_threshold,
        enable_notifications=enable_notifications,
        auto_load=auto_load,
    )
    return page


def create_connected_manajemen_produk_window(
    db_path: str | Path | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
    icon_config: TitleBarIconConfig | None = None,
    parent: QWidget | None = None,
    enable_notifications: bool = True,
) -> ManajemenProdukWindow:
    """Membuat jendela mandiri ManajemenProdukWindow yang terhubung ke backend.

    Args:
        db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
        page_size: Jumlah baris data per halaman tabel.
        low_stock_threshold: Ambang batas stok menipis dalam satuan dasar.
        icon_config: Konfigurasi ikon custom title bar. Jika None, memakai ICON_PATHS.
        parent: Widget induk opsional.
        enable_notifications: Status aktifkan notifikasi Toast otomatis.

    Returns:
        Instance ManajemenProdukWindow siap ditampilkan dengan data database asli.
    """
    resolved_icons = (
        icon_config
        if icon_config is not None
        else TitleBarIconConfig.from_dict(ICON_PATHS)
    )
    window = ManajemenProdukWindow(icon_config=resolved_icons, parent=parent)
    bind_manajemen_produk_to_backend(
        page=window.page,
        db_path=db_path,
        page_size=page_size,
        low_stock_threshold=low_stock_threshold,
        enable_notifications=enable_notifications,
        auto_load=True,
    )
    return window