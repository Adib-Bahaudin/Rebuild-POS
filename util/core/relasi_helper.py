"""Modul helper penghubung antara RelationManagementPage dan RelasiBackend.

Modul ini bertindak sebagai jembatan (bridge/binder) antara antarmuka
RelationManagementPage (ui/relasi_page.py) dan backend manajemen relasi
RelasiBackend (core/relasi_backend.py) beserta dialog CustomDialog terkait.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, cast

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QWidget

from config import DEFAULT_DB_PATH
from core.relasi_backend import (
    BillingFilterType,
    PaymentResultDTO,
    RelasiBackend,
    RelationBackendError,
    RelationFilterDTO,
    RelationKpiDTO,
    RelationPageBundleDTO,
    RelationProfileDTO,
    RelationSummaryDTO,
    RelationType,
    SortByType,
    StatusFilterType,
)
from ui.customwindowtitlebar import ICON_PATHS, TitleBarIconConfig
from ui.dialog.dialogbayarrelasi import RelationPaymentDialog
from ui.dialog.dialogdetailrelasi import RelationDetailDialog
from ui.dialog.dialogformrelasi import (
    RelationArchiveConfirmDialog,
    RelationFormDialog,
)
from ui.relasi_page import (
    RelationFilterState,
    RelationKpiData,
    RelationManagementPage,
    RelationManagementWindow,
    RelationRecord,
)
from util.helper.formatrupiah import format_rupiah
from util.helper.toast_helper import show_toast as display_toast

logger = logging.getLogger(__name__)

_VALID_STATUS_FILTERS: frozenset[str] = frozenset({"active", "inactive", "all"})
_VALID_BILLING_FILTERS: frozenset[str] = frozenset(
    {"all", "outstanding", "overdue", "paid"}
)
_VALID_SORT_BY: frozenset[str] = frozenset(
    {"name_asc", "name_desc", "outstanding_desc", "due_date_asc", "transaction_desc"}
)


def _normalize_relation_type(raw_type: str) -> RelationType:
    """Menormalisasi string jenis relasi ke Literal 'customer' atau 'supplier'."""
    return "supplier" if raw_type == "supplier" else "customer"


def _to_filter_dto(state: RelationFilterState) -> RelationFilterDTO:
    """Mengonversi state filter UI menjadi RelationFilterDTO untuk backend."""
    status_val = state.status_filter if state.status_filter in _VALID_STATUS_FILTERS else "active"
    billing_val = (
        state.billing_filter if state.billing_filter in _VALID_BILLING_FILTERS else "all"
    )
    sort_val = state.sort_by if state.sort_by in _VALID_SORT_BY else "name_asc"
    return RelationFilterDTO(
        search_query=state.search_query,
        status_filter=cast(StatusFilterType, status_val),
        billing_filter=cast(BillingFilterType, billing_val),
        sort_by=cast(SortByType, sort_val),
    )


def _to_ui_record(dto: RelationSummaryDTO) -> RelationRecord:
    """Mengonversi DTO ringkasan backend menjadi RelationRecord untuk tabel UI."""
    return RelationRecord(
        relation_id=dto.relation_id,
        name=dto.name,
        phone=dto.phone,
        address=dto.address,
        transaction_count=dto.transaction_count,
        transaction_total=dto.transaction_total,
        outstanding_amount=dto.outstanding_amount,
        nearest_due_date=dto.nearest_due_date,
        is_overdue=dto.is_overdue,
        is_active=dto.is_active,
    )


def _to_ui_kpi(dto: RelationKpiDTO) -> RelationKpiData:
    """Mengonversi DTO metrik KPI backend menjadi RelationKpiData untuk kartu UI."""
    return RelationKpiData(
        active_count=dto.active_count,
        total_count=dto.total_count,
        outstanding_total=dto.outstanding_total,
        outstanding_relation_count=dto.outstanding_relation_count,
        overdue_invoice_count=dto.overdue_invoice_count,
    )


class RelasiHelper(QObject):
    """Helper orkestrator yang menghubungkan RelationManagementPage dan RelasiBackend.

    Signals:
        data_loaded: Dipancarkan membawa RelationPageBundleDTO saat data termuat.
        relation_saved: Dipancarkan membawa RelationProfileDTO saat tambah/ubah berhasil.
        payment_recorded: Dipancarkan membawa PaymentResultDTO saat pembayaran tercatat.
        error_occurred: Dipancarkan saat terjadi galat membawa judul dan pesan (str, str).
    """

    data_loaded = Signal(object)
    relation_saved = Signal(object)
    payment_recorded = Signal(object)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        page: RelationManagementPage,
        db_path: Optional[str | Path] = None,
        cashier_name: Optional[str] = None,
        enable_notifications: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi RelasiHelper dan memuat data awal ke halaman relasi.

        Args:
            page: Instance RelationManagementPage target.
            db_path: Path database SQLCipher opsional; default DEFAULT_DB_PATH.
            cashier_name: Nama kasir aktif untuk pencatatan pembayaran pelanggan.
            enable_notifications: Jika True, menampilkan notifikasi Toast otomatis.
            parent: Objek induk QObject opsional.
        """
        super().__init__(parent or page)
        self.page: RelationManagementPage = page
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.cashier_name: str = (cashier_name or "").strip() or "KASIR"
        self.enable_notifications: bool = enable_notifications
        self.backend: RelasiBackend = RelasiBackend(db_path=self.db_path)

        setattr(self.page, "_relasi_helper", self)
        setattr(self.page, "_relasi_backend", self.backend)

        self._connect_signals()
        self.refresh(self.page.get_active_mode())

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh sinyal interaksi halaman relasi ke handler helper."""
        self.page.active_mode_changed.connect(self._handle_mode_or_refresh)
        self.page.refresh_requested.connect(self._handle_mode_or_refresh)
        self.page.filter_changed.connect(self._handle_filter_changed)
        self.page.add_relation_requested.connect(self._handle_add_relation)
        self.page.edit_relation_requested.connect(self._handle_edit_relation)
        self.page.detail_relation_requested.connect(self._handle_detail_relation)
        self.page.payment_relation_requested.connect(self._handle_payment_relation)
        self.page.toggle_active_requested.connect(self._handle_toggle_active)
        if hasattr(self.page, "page_entered"):
            self.page.page_entered.connect(self._handle_page_entered)

    def _dialog_parent(self) -> QWidget:
        """Mengembalikan widget induk yang aman untuk menampilkan dialog."""
        return self.page.window() or self.page

    def _notify(self, title: str, message: str, *, is_success: bool = True) -> None:
        """Menampilkan notifikasi Toast melayang bila diaktifkan."""
        if not self.enable_notifications:
            return
        display_toast(
            parent=self._dialog_parent(),
            title=title,
            message=message,
            is_success=is_success,
            duration_ms=3500,
            border_radius=6,
        )

    def _report_error(self, title: str, message: str) -> None:
        """Mencatat galat, memancarkan sinyal error_occurred, dan menampilkan Toast."""
        self.error_occurred.emit(title, message)
        self._notify(title, message, is_success=False)

    def refresh(
        self,
        relation_type: Optional[RelationType] = None,
        filter_state: Optional[RelationFilterState] = None,
    ) -> Optional[RelationPageBundleDTO]:
        """Memuat ulang KPI, daftar relasi terfilter, dan badge untuk mode target.

        Args:
            relation_type: Mode target ('customer'/'supplier'); default mode aktif halaman.
            filter_state: State filter opsional; default mengambil dari panel UI.

        Returns:
            RelationPageBundleDTO jika berhasil, atau None bila terjadi kegagalan.
        """
        target_mode: RelationType = (
            relation_type if relation_type is not None else self.page.get_active_mode()
        )
        state = (
            filter_state
            if filter_state is not None
            else self.page.get_filter_state(target_mode)
        )
        filter_dto = _to_filter_dto(state)

        self.page.set_loading_state(target_mode, True)
        try:
            bundle = self.backend.get_page_bundle(target_mode, filter_dto)
            self.page.set_kpi_data(target_mode, _to_ui_kpi(bundle.kpi))
            self.page.set_relation_records(
                target_mode,
                [_to_ui_record(row) for row in bundle.records],
            )
            self.page.set_mode_badge_count(
                "customer",
                bundle.active_counts.get("customer", 0),
            )
            self.page.set_mode_badge_count(
                "supplier",
                bundle.active_counts.get("supplier", 0),
            )
            self.data_loaded.emit(bundle)
            return bundle
        except RelationBackendError as exc:
            logger.warning("Gagal memuat data relasi (%s): %s", target_mode, exc)
            self._report_error("Gagal Memuat Data", str(exc))
            return None
        except Exception as exc:
            logger.exception("Kesalahan tak terduga saat memuat halaman relasi")
            self._report_error("Kesalahan Database", str(exc))
            return None
        finally:
            self.page.set_loading_state(target_mode, False)

    def _handle_mode_or_refresh(self, raw_type: str) -> None:
        """Menyegarkan data ketika mode berganti atau muat ulang dipicu."""
        self.refresh(_normalize_relation_type(raw_type))

    def _handle_filter_changed(self, raw_type: str, state_obj: object) -> None:
        """Menyegarkan daftar relasi saat filter atau teks pencarian berubah."""
        mode = _normalize_relation_type(raw_type)
        state = state_obj if isinstance(state_obj, RelationFilterState) else None
        self.refresh(mode, filter_state=state)

    def _handle_page_entered(self) -> None:
        """Menyegarkan mode aktif saat pengguna kembali membuka halaman relasi."""
        self.refresh(self.page.get_active_mode())

    def _handle_add_relation(self, raw_type: str) -> None:
        """Membuka dialog tambah relasi lalu menyimpan hasilnya ke basis data."""
        mode = _normalize_relation_type(raw_type)
        entity = "Pelanggan" if mode == "customer" else "Supplier"
        dialog = RelationFormDialog(
            relation_type=mode,
            profile=None,
            parent=self._dialog_parent(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.get_payload()
        try:
            saved: RelationProfileDTO = self.backend.create_relation(mode, payload)
        except RelationBackendError as exc:
            self._report_error(f"Gagal Tambah {entity}", str(exc))
            return
        except Exception as exc:
            logger.exception("Kesalahan sistem saat menambah %s", mode)
            self._report_error("Kesalahan Database", str(exc))
            return

        self.relation_saved.emit(saved)
        self._notify(
            f"{entity} Ditambahkan",
            f"{saved.name} berhasil disimpan ke daftar {entity.lower()}.",
            is_success=True,
        )
        self.refresh(mode)

    def _handle_edit_relation(self, raw_type: str, relation_id: int) -> None:
        """Memuat profil relasi dan membuka dialog edit lalu memperbarui basis data."""
        mode = _normalize_relation_type(raw_type)
        entity = "Pelanggan" if mode == "customer" else "Supplier"
        try:
            profile = self.backend.get_relation_profile(mode, relation_id)
        except RelationBackendError as exc:
            self._report_error(f"Gagal Membuka {entity}", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal mengambil profil %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        dialog = RelationFormDialog(
            relation_type=mode,
            profile=profile,
            parent=self._dialog_parent(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.get_payload()
        try:
            updated = self.backend.update_relation(mode, relation_id, payload)
        except RelationBackendError as exc:
            self._report_error(f"Gagal Perbarui {entity}", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal memperbarui %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        self.relation_saved.emit(updated)
        self._notify(
            f"{entity} Diperbarui",
            f"Perubahan profil {updated.name} berhasil disimpan.",
            is_success=True,
        )
        self.refresh(mode)

    def _handle_detail_relation(self, raw_type: str, relation_id: int) -> None:
        """Membuka dialog rincian nota dan riwayat pembayaran milik relasi."""
        mode = _normalize_relation_type(raw_type)
        try:
            detail = self.backend.get_relation_detail(mode, relation_id)
        except RelationBackendError as exc:
            self._report_error("Gagal Memuat Detail", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal mengambil detail %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        dialog = RelationDetailDialog(detail=detail, parent=self._dialog_parent())
        dialog.exec()
        if dialog.pay_requested:
            self._handle_payment_relation(mode, relation_id)

    def _handle_payment_relation(self, raw_type: str, relation_id: int) -> None:
        """Membuka dialog pelunasan/cicilan tagihan untuk nota belum lunas relasi."""
        mode = _normalize_relation_type(raw_type)
        try:
            profile = self.backend.get_relation_profile(mode, relation_id)
            unpaid = self.backend.list_unpaid_invoices(mode, relation_id)
        except RelationBackendError as exc:
            self._report_error("Gagal Memuat Tagihan", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal memuat tagihan %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        if not unpaid:
            self._notify(
                "Tidak Ada Tagihan",
                f"{profile.name} tidak memiliki nota belum lunas.",
                is_success=True,
            )
            return

        dialog = RelationPaymentDialog(
            relation_type=mode,
            profile=profile,
            unpaid_invoices=unpaid,
            cashier_name=self.cashier_name,
            parent=self._dialog_parent(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payment_input = dialog.get_payment_input()
        try:
            result: PaymentResultDTO = self.backend.record_payment(
                mode,
                payment_input,
                expected_relation_id=relation_id,
            )
        except RelationBackendError as exc:
            self._report_error("Pembayaran Ditolak", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal mencatat pembayaran %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        self.payment_recorded.emit(result)
        self._notify(
            "Pembayaran Tercatat",
            f"Faktur {result.invoice_number} dibayar {format_rupiah(result.amount_applied)} "
            f"(Sisa: {format_rupiah(result.new_remaining_amount)}).",
            is_success=True,
        )
        self.refresh(mode)

    def _handle_toggle_active(
        self,
        raw_type: str,
        relation_id: int,
        target_active: bool,
    ) -> None:
        """Mengarsipkan atau mengaktifkan kembali profil relasi setelah konfirmasi."""
        mode = _normalize_relation_type(raw_type)
        entity = "Pelanggan" if mode == "customer" else "Supplier"
        try:
            impact = self.backend.check_archive_impact(mode, relation_id)
        except RelationBackendError as exc:
            self._report_error("Gagal Memeriksa Status", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal memeriksa dampak arsip %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        confirm = RelationArchiveConfirmDialog(
            impact=impact,
            target_active=target_active,
            parent=self._dialog_parent(),
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            updated = self.backend.set_relation_active(mode, relation_id, target_active)
        except RelationBackendError as exc:
            self._report_error(f"Gagal Ubah Status {entity}", str(exc))
            return
        except Exception as exc:
            logger.exception("Gagal mengubah status %s (id=%d)", mode, relation_id)
            self._report_error("Kesalahan Database", str(exc))
            return

        self.relation_saved.emit(updated)
        status_text = "diaktifkan kembali" if target_active else "diarsipkan"
        self._notify(
            f"Status {entity} Diperbarui",
            f"{updated.name} berhasil {status_text}.",
            is_success=True,
        )
        self.refresh(mode)


def bind_relasi_to_backend(
    page: RelationManagementPage,
    db_path: Optional[str | Path] = None,
    cashier_name: Optional[str] = None,
    enable_notifications: bool = True,
) -> RelasiHelper:
    """Menghubungkan instance RelationManagementPage dengan RelasiBackend SQLCipher.

    Args:
        page: Instance RelationManagementPage target.
        db_path: Lokasi file database target; default memakai DEFAULT_DB_PATH.
        cashier_name: Nama kasir aktif untuk pencatatan pembayaran pelanggan.
        enable_notifications: Aktifkan popup Toast otomatis.

    Returns:
        Instance RelasiHelper yang telah terhubung ke seluruh sinyal halaman.
    """
    return RelasiHelper(
        page=page,
        db_path=db_path,
        cashier_name=cashier_name,
        enable_notifications=enable_notifications,
    )


def create_connected_relasi_page(
    db_path: Optional[str | Path] = None,
    cashier_name: Optional[str] = None,
    enable_notifications: bool = True,
    parent: Optional[QWidget] = None,
) -> RelationManagementPage:
    """Membuat RelationManagementPage baru yang langsung terhubung ke backend relasi.

    Args:
        db_path: Lokasi file database target; default memakai DEFAULT_DB_PATH.
        cashier_name: Nama kasir aktif untuk pencatatan pembayaran pelanggan.
        enable_notifications: Aktifkan popup Toast otomatis.
        parent: Widget induk opsional.

    Returns:
        Instance RelationManagementPage siap didaftarkan ke MainShell.
    """
    page = RelationManagementPage(parent=parent)
    bind_relasi_to_backend(
        page=page,
        db_path=db_path,
        cashier_name=cashier_name,
        enable_notifications=enable_notifications,
    )
    return page


def create_connected_relasi_window(
    db_path: Optional[str | Path] = None,
    cashier_name: Optional[str] = None,
    enable_notifications: bool = True,
    icon_config: Optional[TitleBarIconConfig] = None,
    parent: Optional[QWidget] = None,
) -> RelationManagementWindow:
    """Membuat jendela mandiri RelationManagementWindow yang terhubung ke backend relasi.

    Args:
        db_path: Lokasi file database target; default memakai DEFAULT_DB_PATH.
        cashier_name: Nama kasir aktif untuk pencatatan pembayaran pelanggan.
        enable_notifications: Aktifkan popup Toast otomatis.
        icon_config: Konfigurasi ikon custom title bar; default ICON_PATHS.
        parent: Widget induk opsional.

    Returns:
        Instance RelationManagementWindow siap ditampilkan.
    """
    resolved_icons = (
        icon_config
        if icon_config is not None
        else TitleBarIconConfig.from_dict(ICON_PATHS)
    )
    window = RelationManagementWindow(icon_config=resolved_icons, parent=parent)
    bind_relasi_to_backend(
        page=window.page,
        db_path=db_path,
        cashier_name=cashier_name,
        enable_notifications=enable_notifications,
    )
    return window
