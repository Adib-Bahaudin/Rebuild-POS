"""Modul backend murni untuk manajemen data Pelanggan dan Supplier.

Modul ini menangani seluruh logika bisnis dan operasi basis data SQLite/SQLCipher
untuk entitas pelanggan, supplier, ringkasan KPI, riwayat nota transaksi,
riwayat pembayaran, analisis dampak pengarsipan, serta pencatatan pelunasan
atau cicilan tanpa ketergantungan pada lapisan antarmuka (Qt/PySide6).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Final, Iterator, Literal

from sqlcipher3 import dbapi2 as sqlite3

from config import DEFAULT_DB_PATH
from util.helper.database.db_connection import create_sqlite_connection

logger = logging.getLogger(__name__)

RelationType = Literal["customer", "supplier"]
StatusFilterType = Literal["active", "inactive", "all"]
BillingFilterType = Literal["all", "outstanding", "overdue", "paid"]
SortByType = Literal[
    "name_asc",
    "name_desc",
    "outstanding_desc",
    "due_date_asc",
    "transaction_desc",
]

MAX_NAME_LENGTH: Final[int] = 150
MAX_PHONE_LENGTH: Final[int] = 32
MAX_ADDRESS_LENGTH: Final[int] = 500
MAX_NOTES_LENGTH: Final[int] = 500
MAX_REFERENCE_LENGTH: Final[int] = 100
PHONE_ALLOWED_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9+\-\s()./]+$")


class RelationBackendError(Exception):
    """Pengecualian dasar untuk seluruh kesalahan pada backend relasi."""


class RelationValidationError(RelationBackendError):
    """Pengecualian ketika data masukan gagal memenuhi aturan validasi bisnis."""


class RelationNotFoundError(RelationBackendError):
    """Pengecualian ketika data relasi atau nota transaksi tidak ditemukan."""


class RelationConflictError(RelationBackendError):
    """Pengecualian ketika operasi melanggar keunikan atau konflik status data."""


@dataclass(frozen=True)
class _RelationTableSpec:
    """Pemetaan statis nama tabel dan kolom untuk jenis relasi tertentu.

    Attributes:
        relation_type: Jenis relasi ('customer' atau 'supplier').
        relation_table: Nama tabel master relasi.
        tx_table: Nama tabel transaksi utama (sales atau purchases).
        payment_table: Nama tabel pembayaran transaksi.
        relation_fk_col: Nama kolom foreign key relasi pada tabel transaksi.
        tx_fk_col: Nama kolom foreign key transaksi pada tabel pembayaran.
        tx_date_col: Nama kolom tanggal transaksi pada tabel transaksi.
        entity_label: Label entitas berbahasa Indonesia untuk pesan kesalahan.
    """

    relation_type: RelationType
    relation_table: str
    tx_table: str
    payment_table: str
    relation_fk_col: str
    tx_fk_col: str
    tx_date_col: str
    entity_label: str


@dataclass(frozen=True)
class RelationFilterDTO:
    """Kriteria pencarian, penyaringan, dan pengurutan daftar relasi.

    Attributes:
        search_query: Kata kunci pencarian pada nama, telepon, atau alamat.
        status_filter: Filter status aktif ('active', 'inactive', atau 'all').
        billing_filter: Filter tagihan ('all', 'outstanding', 'overdue', 'paid').
        sort_by: Kunci kriteria pengurutan hasil query.
    """

    search_query: str = ""
    status_filter: StatusFilterType = "active"
    billing_filter: BillingFilterType = "all"
    sort_by: SortByType = "name_asc"


@dataclass(frozen=True)
class RelationInputDTO:
    """Data masukan terstruktur untuk pembuatan atau pembaruan profil relasi.

    Attributes:
        name: Nama pelanggan atau supplier (wajib diisi).
        phone: Nomor telepon atau WhatsApp opsional.
        address: Alamat lengkap opsional.
        is_active: Status aktif data pada basis data.
    """

    name: str
    phone: str = ""
    address: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class RelationProfileDTO:
    """Representasi profil dasar satu pelanggan atau supplier.

    Attributes:
        relation_id: ID unik relasi pada basis data.
        relation_type: Jenis relasi ('customer' atau 'supplier').
        name: Nama pelanggan atau supplier.
        phone: Nomor telepon relasi.
        address: Alamat relasi.
        is_active: Penanda apakah relasi berstatus aktif.
    """

    relation_id: int
    relation_type: RelationType
    name: str
    phone: str
    address: str
    is_active: bool


@dataclass(frozen=True)
class RelationSummaryDTO:
    """Ringkasan baris relasi lengkap dengan agregasi transaksi dan tagihan.

    Attributes:
        relation_id: ID unik relasi pada basis data.
        name: Nama pelanggan atau supplier.
        phone: Nomor telepon atau WhatsApp relasi.
        address: Alamat lengkap relasi.
        transaction_count: Jumlah nota transaksi yang tercatat.
        transaction_total: Total nominal seluruh nota transaksi.
        outstanding_amount: Sisa piutang (pelanggan) atau utang (supplier).
        nearest_due_date: Tanggal jatuh tempo terdekat untuk nota belum lunas.
        is_overdue: Penanda apakah ada nota belum lunas yang sudah jatuh tempo.
        is_active: Status aktif relasi.
    """

    relation_id: int
    name: str
    phone: str
    address: str
    transaction_count: int
    transaction_total: int
    outstanding_amount: int
    nearest_due_date: str
    is_overdue: bool
    is_active: bool


@dataclass(frozen=True)
class RelationKpiDTO:
    """Ringkasan metrik KPI untuk kartu statistik halaman relasi.

    Attributes:
        active_count: Jumlah relasi berstatus aktif.
        total_count: Jumlah seluruh relasi terdaftar.
        outstanding_total: Akumulasi sisa piutang atau utang berjalan.
        outstanding_relation_count: Jumlah relasi yang memiliki tunggakan.
        overdue_invoice_count: Jumlah nota yang melewati atau tepat jatuh tempo.
    """

    active_count: int
    total_count: int
    outstanding_total: int
    outstanding_relation_count: int
    overdue_invoice_count: int


@dataclass(frozen=True)
class RelationPageBundleDTO:
    """Paket data terpadu untuk menyegarkan satu tampilan halaman dalam satu koneksi.

    Attributes:
        relation_type: Mode relasi yang dimuat ('customer' atau 'supplier').
        kpi: Data metrik KPI untuk mode aktif.
        records: Daftar baris ringkasan relasi sesuai filter.
        active_counts: Jumlah data aktif untuk kedua mode (pelanggan dan supplier).
    """

    relation_type: RelationType
    kpi: RelationKpiDTO
    records: list[RelationSummaryDTO]
    active_counts: dict[RelationType, int]


@dataclass(frozen=True)
class RelationInvoiceDTO:
    """Representasi satu nota penjualan atau pembelian milik suatu relasi.

    Attributes:
        invoice_id: ID unik nota pada tabel sales atau purchases.
        invoice_number: Nomor invoice transaksi.
        transaction_date: Tanggal transaksi tercatat.
        subtotal: Nilai subtotal sebelum diskon.
        discount: Nilai potongan diskon nota.
        total: Nilai total akhir nota.
        amount_paid: Total nominal yang telah dibayarkan.
        remaining_amount: Sisa tagihan yang belum dibayarkan.
        payment_status: Status pembayaran ('PAID', 'PARTIAL', atau 'UNPAID').
        due_date: Tanggal jatuh tempo pembayaran jika ada.
        is_overdue: True jika nota belum lunas dan melewati/tepat jatuh tempo.
        payment_method: Metode pembayaran utama nota.
        status: Status operasional transaksi.
        notes: Catatan tambahan nota.
    """

    invoice_id: int
    invoice_number: str
    transaction_date: str
    subtotal: int
    discount: int
    total: int
    amount_paid: int
    remaining_amount: int
    payment_status: str
    due_date: str
    is_overdue: bool
    payment_method: str
    status: str
    notes: str


@dataclass(frozen=True)
class RelationPaymentDTO:
    """Representasi satu catatan pembayaran atau cicilan atas nota relasi.

    Attributes:
        payment_id: ID unik catatan pembayaran.
        invoice_id: ID nota yang dibayarkan.
        invoice_number: Nomor invoice terkait.
        payment_date: Tanggal dan waktu pembayaran dicatat.
        amount: Nominal pembayaran yang mengurangi tagihan.
        payment_method: Metode pembayaran yang digunakan.
        reference_number: Nomor referensi transfer atau bukti bayar opsional.
        notes: Catatan tambahan pembayaran.
        tendered_amount: Nominal uang diserahkan (khusus pelanggan, 0 untuk supplier).
        change_given: Nominal kembalian (khusus pelanggan, 0 untuk supplier).
        cashier_name: Nama kasir pencatat (khusus pelanggan, kosong untuk supplier).
    """

    payment_id: int
    invoice_id: int
    invoice_number: str
    payment_date: str
    amount: int
    payment_method: str
    reference_number: str
    notes: str
    tendered_amount: int = 0
    change_given: int = 0
    cashier_name: str = ""


@dataclass(frozen=True)
class RelationDetailDTO:
    """Data detail lengkap profil, agregasi, daftar nota, dan riwayat pembayaran.

    Attributes:
        profile: Informasi profil dasar relasi.
        transaction_count: Jumlah total nota transaksi relasi.
        transaction_total: Akumulasi nilai transaksi relasi.
        outstanding_amount: Sisa piutang atau utang aktif relasi.
        nearest_due_date: Tanggal jatuh tempo terdekat untuk tagihan aktif.
        is_overdue: True jika ada nota belum lunas yang sudah jatuh tempo.
        invoices: Daftar nota transaksi milik relasi.
        payments: Daftar riwayat pembayaran atau cicilan milik relasi.
    """

    profile: RelationProfileDTO
    transaction_count: int
    transaction_total: int
    outstanding_amount: int
    nearest_due_date: str
    is_overdue: bool
    invoices: list[RelationInvoiceDTO]
    payments: list[RelationPaymentDTO]


@dataclass(frozen=True)
class ArchiveImpactDTO:
    """Ringkasan dampak sebelum mengubah status aktif atau mengarsipkan relasi.

    Attributes:
        relation_id: ID unik relasi.
        relation_type: Jenis relasi ('customer' atau 'supplier').
        name: Nama relasi.
        is_active: Status aktif saat ini sebelum diubah.
        outstanding_amount: Sisa tagihan berjalan pada relasi tersebut.
        unpaid_invoice_count: Jumlah nota berstatus UNPAID atau PARTIAL.
        overdue_invoice_count: Jumlah nota yang sudah jatuh tempo.
    """

    relation_id: int
    relation_type: RelationType
    name: str
    is_active: bool
    outstanding_amount: int
    unpaid_invoice_count: int
    overdue_invoice_count: int


@dataclass(frozen=True)
class PaymentInputDTO:
    """Data masukan untuk mencatat pembayaran pelunasan atau cicilan nota.

    Attributes:
        invoice_id: ID nota pada tabel sales atau purchases.
        amount: Nominal pembayaran yang akan memotong sisa tagihan (> 0).
        payment_method: Metode pembayaran (contoh: 'Tunai', 'Transfer', 'QRIS').
        reference_number: Nomor referensi bukti pembayaran opsional.
        notes: Catatan tambahan pembayaran opsional.
        tendered_amount: Nominal uang diterima dari pelanggan (opsional).
        cashier_name: Nama kasir pencatat untuk pembayaran pelanggan.
        payment_date: Tanggal/waktu pembayaran kustom dalam format ISO opsional.
    """

    invoice_id: int
    amount: int
    payment_method: str = "Tunai"
    reference_number: str = ""
    notes: str = ""
    tendered_amount: int | None = None
    cashier_name: str = "KASIR"
    payment_date: str | None = None


@dataclass(frozen=True)
class PaymentResultDTO:
    """Hasil pencatatan pembayaran setelah sinkronisasi trigger basis data.

    Attributes:
        payment_id: ID baris pembayaran baru yang tersimpan.
        invoice_id: ID nota yang dibayarkan.
        invoice_number: Nomor invoice terkait.
        amount_applied: Nominal yang efektif mengurangi sisa tagihan.
        tendered_amount: Nominal uang diserahkan (pelanggan) atau sama dengan amount.
        change_given: Nominal kembalian yang diberikan (pelanggan).
        new_amount_paid: Total akumulasi terbayar terbaru pada nota.
        new_remaining_amount: Sisa tagihan terbaru pada nota.
        new_payment_status: Status pembayaran terbaru ('PAID', 'PARTIAL', 'UNPAID').
    """

    payment_id: int
    invoice_id: int
    invoice_number: str
    amount_applied: int
    tendered_amount: int
    change_given: int
    new_amount_paid: int
    new_remaining_amount: int
    new_payment_status: str


TABLE_SPECS: Final[dict[RelationType, _RelationTableSpec]] = {
    "customer": _RelationTableSpec(
        relation_type="customer",
        relation_table="customers",
        tx_table="sales",
        payment_table="sale_payments",
        relation_fk_col="customer_id",
        tx_fk_col="sale_id",
        tx_date_col="sale_date",
        entity_label="Pelanggan",
    ),
    "supplier": _RelationTableSpec(
        relation_type="supplier",
        relation_table="suppliers",
        tx_table="purchases",
        payment_table="purchase_payments",
        relation_fk_col="supplier_id",
        tx_fk_col="purchase_id",
        tx_date_col="purchase_date",
        entity_label="Supplier",
    ),
}

SORT_ORDER_CLAUSES: Final[dict[str, str]] = {
    "name_asc": "LOWER(r.name) ASC, r.id ASC",
    "name_desc": "LOWER(r.name) DESC, r.id DESC",
    "outstanding_desc": "COALESCE(t.outstanding_total, 0) DESC, LOWER(r.name) ASC",
    "due_date_asc": (
        "CASE WHEN t.nearest_due_date IS NULL OR TRIM(t.nearest_due_date) = '' "
        "THEN 1 ELSE 0 END ASC, "
        "t.nearest_due_date ASC, "
        "COALESCE(t.outstanding_total, 0) DESC, "
        "LOWER(r.name) ASC"
    ),
    "transaction_desc": (
        "COALESCE(t.tx_count, 0) DESC, "
        "COALESCE(t.tx_total, 0) DESC, "
        "LOWER(r.name) ASC"
    ),
}


class RelasiBackend:
    """Layanan backend murni untuk operasional data Pelanggan dan Supplier.

    Kelas ini menyediakan operasi baca agregasi teroptimasi menggunakan CTE,
    pemuatan paket halaman dalam satu siklus koneksi SQLCipher, validasi
    masukan ketat, serta transaksi tulis atomik yang selaras dengan trigger
    sinkronisasi pembayaran pada skema database.

    Attributes:
        db_path: Path file database SQLite/SQLCipher yang digunakan.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Menginisialisasi instance RelasiBackend.

        Args:
            db_path: Path file database opsional. Jika None, memakai DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    @staticmethod
    def _resolve_spec(relation_type: str) -> _RelationTableSpec:
        """Memvalidasi dan mengambil spesifikasi tabel untuk jenis relasi.

        Args:
            relation_type: String jenis relasi ('customer' atau 'supplier').

        Returns:
            Objek _RelationTableSpec sesuai jenis relasi.

        Raises:
            RelationValidationError: Jika relation_type tidak dikenali.
        """
        if relation_type == "customer":
            return TABLE_SPECS["customer"]
        if relation_type == "supplier":
            return TABLE_SPECS["supplier"]
        raise RelationValidationError(
            f"Jenis relasi tidak valid: '{relation_type}'. "
            "Gunakan 'customer' atau 'supplier'."
        )

    @staticmethod
    def _escape_like_pattern(raw_text: str) -> str:
        """Mengamankan karakter wildcard LIKE pada kata kunci pencarian.

        Args:
            raw_text: Teks pencarian mentah dari pengguna.

        Returns:
            Pola LIKE terbungkus wildcard persen dengan karakter khusus ter-escape.
        """
        escaped = (
            raw_text.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"%{escaped.lower()}%"

    @staticmethod
    def _normalize_phone_digits(phone: str) -> str:
        """Menghasilkan representasi ringkas nomor telepon untuk perbandingan duplikasi.

        Args:
            phone: Nomor telepon mentah.

        Returns:
            String digit nomor telepon tanpa tanda pemisah.
        """
        return re.sub(r"[^0-9]", "", phone)

    @classmethod
    def _validate_relation_input(
        cls,
        payload: RelationInputDTO,
        entity_label: str,
    ) -> tuple[str, str | None, str | None, int]:
        """Memvalidasi dan menormalkan data masukan profil relasi.

        Args:
            payload: Objek RelationInputDTO berisi nama, telepon, alamat, dan status.
            entity_label: Nama entitas untuk kejelasan pesan galat.

        Returns:
            Tuple berisi (name, phone_or_none, address_or_none, is_active_int).

        Raises:
            RelationValidationError: Jika salah satu kolom tidak memenuhi aturan.
        """
        clean_name = " ".join(payload.name.split())
        if not clean_name:
            raise RelationValidationError(f"Nama {entity_label.lower()} wajib diisi.")
        if len(clean_name) > MAX_NAME_LENGTH:
            raise RelationValidationError(
                f"Nama {entity_label.lower()} maksimal {MAX_NAME_LENGTH} karakter."
            )

        clean_phone = " ".join(payload.phone.split())
        if clean_phone:
            if len(clean_phone) > MAX_PHONE_LENGTH:
                raise RelationValidationError(
                    f"Nomor telepon maksimal {MAX_PHONE_LENGTH} karakter."
                )
            if not PHONE_ALLOWED_PATTERN.match(clean_phone):
                raise RelationValidationError(
                    "Nomor telepon hanya boleh memuat angka dan simbol +, -, (), spasi."
                )

        clean_address = payload.address.strip()
        if len(clean_address) > MAX_ADDRESS_LENGTH:
            raise RelationValidationError(
                f"Alamat maksimal {MAX_ADDRESS_LENGTH} karakter."
            )

        return (
            clean_name,
            clean_phone if clean_phone else None,
            clean_address if clean_address else None,
            1 if payload.is_active else 0,
        )

    @contextmanager
    def _open_connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Membuka koneksi SQLite/SQLCipher terkelola dengan transaksi aman.

        Args:
            write: Jika True, memulai transaksi BEGIN IMMEDIATE dan commit otomatis.

        Yields:
            Koneksi sqlite3.Connection aktif.

        Raises:
            RelationBackendError: Jika koneksi atau operasi basis data gagal.
        """
        conn = create_sqlite_connection(
            self.db_path,
            require_exists=True,
            row_factory=False,
            foreign_keys=True,
            wal_mode=True,
        )
        try:
            if write and not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE;")
            yield conn
            if write:
                conn.commit()
        except RelationBackendError:
            if write and conn.in_transaction:
                conn.rollback()
            raise
        except sqlite3.Error as exc:
            if write and conn.in_transaction:
                conn.rollback()
            logger.exception("Kesalahan SQLite pada RelasiBackend")
            raise RelationBackendError(f"Kesalahan basis data: {exc}") from exc
        except Exception:
            if write and conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _query_kpi(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
    ) -> RelationKpiDTO:
        """Menghitung metrik KPI untuk satu jenis relasi pada koneksi aktif.

        Args:
            conn: Koneksi basis data yang sedang terbuka.
            spec: Spesifikasi tabel untuk relasi target.

        Returns:
            Objek RelationKpiDTO hasil agregasi terkini.
        """
        population_row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END), 0),
                COUNT(*)
            FROM {spec.relation_table};
            """
        ).fetchone()

        active_count = int(population_row[0]) if population_row is not None else 0
        total_count = int(population_row[1]) if population_row is not None else 0

        billing_row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(remaining_amount), 0),
                COUNT(DISTINCT {spec.relation_fk_col}),
                COALESCE(
                    SUM(
                        CASE
                            WHEN due_date IS NOT NULL
                                 AND TRIM(due_date) != ''
                                 AND date(due_date) <= date('now', 'localtime')
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                )
            FROM {spec.tx_table}
            WHERE {spec.relation_fk_col} IS NOT NULL
              AND payment_status IN ('UNPAID', 'PARTIAL')
              AND remaining_amount > 0
              AND UPPER(COALESCE(status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID');
            """
        ).fetchone()

        outstanding_total = int(billing_row[0]) if billing_row is not None else 0
        outstanding_rel_count = int(billing_row[1]) if billing_row is not None else 0
        overdue_invoice_count = int(billing_row[2]) if billing_row is not None else 0

        return RelationKpiDTO(
            active_count=active_count,
            total_count=total_count,
            outstanding_total=outstanding_total,
            outstanding_relation_count=outstanding_rel_count,
            overdue_invoice_count=overdue_invoice_count,
        )

    def _query_active_badge_counts(
        self,
        conn: sqlite3.Connection,
    ) -> dict[RelationType, int]:
        """Mengambil jumlah data aktif untuk pelanggan dan supplier sekaligus.

        Args:
            conn: Koneksi basis data yang sedang terbuka.

        Returns:
            Dictionary berisi jumlah aktif untuk 'customer' dan 'supplier'.
        """
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM customers WHERE is_active = 1),
                (SELECT COUNT(*) FROM suppliers WHERE is_active = 1);
            """
        ).fetchone()

        customer_count = int(row[0]) if row is not None else 0
        supplier_count = int(row[1]) if row is not None else 0
        return {
            "customer": customer_count,
            "supplier": supplier_count,
        }

    def _query_relations(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
        filter_dto: RelationFilterDTO,
    ) -> list[RelationSummaryDTO]:
        """Mengambil daftar ringkasan relasi teragregasi sesuai kriteria filter.

        Args:
            conn: Koneksi basis data yang sedang terbuka.
            spec: Spesifikasi tabel untuk relasi target.
            filter_dto: Kriteria pencarian, status, tagihan, dan pengurutan.

        Returns:
            Daftar objek RelationSummaryDTO terurut.
        """
        where_clauses: list[str] = []
        params: list[str] = []

        if filter_dto.status_filter == "active":
            where_clauses.append("r.is_active = 1")
        elif filter_dto.status_filter == "inactive":
            where_clauses.append("r.is_active = 0")

        if filter_dto.billing_filter == "outstanding":
            where_clauses.append("COALESCE(t.outstanding_total, 0) > 0")
        elif filter_dto.billing_filter == "overdue":
            where_clauses.append("COALESCE(t.has_overdue, 0) = 1")
        elif filter_dto.billing_filter == "paid":
            where_clauses.append("COALESCE(t.outstanding_total, 0) = 0")

        cleaned_query = filter_dto.search_query.strip()
        if cleaned_query:
            pattern = self._escape_like_pattern(cleaned_query)
            where_clauses.append(
                "(LOWER(r.name) LIKE ? ESCAPE '\\' "
                "OR LOWER(COALESCE(r.phone, '')) LIKE ? ESCAPE '\\' "
                "OR LOWER(COALESCE(r.address, '')) LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern, pattern])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_sql = SORT_ORDER_CLAUSES.get(
            filter_dto.sort_by, SORT_ORDER_CLAUSES["name_asc"]
        )

        query = f"""
            WITH tx_summary AS (
                SELECT
                    {spec.relation_fk_col} AS rel_id,
                    COUNT(*) AS tx_count,
                    COALESCE(SUM(total), 0) AS tx_total,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                THEN remaining_amount
                                ELSE 0
                            END
                        ),
                        0
                    ) AS outstanding_total,
                    MIN(
                        CASE
                            WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                 AND remaining_amount > 0
                                 AND due_date IS NOT NULL
                                 AND TRIM(due_date) != ''
                            THEN due_date
                            ELSE NULL
                        END
                    ) AS nearest_due_date,
                    MAX(
                        CASE
                            WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                 AND remaining_amount > 0
                                 AND due_date IS NOT NULL
                                 AND TRIM(due_date) != ''
                                 AND date(due_date) <= date('now', 'localtime')
                            THEN 1
                            ELSE 0
                        END
                    ) AS has_overdue
                FROM {spec.tx_table}
                WHERE {spec.relation_fk_col} IS NOT NULL
                  AND UPPER(COALESCE(status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID')
                GROUP BY {spec.relation_fk_col}
            )
            SELECT
                r.id,
                r.name,
                COALESCE(r.phone, ''),
                COALESCE(r.address, ''),
                COALESCE(t.tx_count, 0),
                COALESCE(t.tx_total, 0),
                COALESCE(t.outstanding_total, 0),
                COALESCE(t.nearest_due_date, ''),
                COALESCE(t.has_overdue, 0),
                r.is_active
            FROM {spec.relation_table} AS r
            LEFT JOIN tx_summary AS t ON t.rel_id = r.id
            {where_sql}
            ORDER BY {order_sql};
        """

        rows = conn.execute(query, params).fetchall()
        return [
            RelationSummaryDTO(
                relation_id=int(row[0]),
                name=str(row[1]),
                phone=str(row[2]),
                address=str(row[3]),
                transaction_count=int(row[4]),
                transaction_total=int(row[5]),
                outstanding_amount=int(row[6]),
                nearest_due_date=str(row[7]),
                is_overdue=bool(row[8]),
                is_active=bool(row[9]),
            )
            for row in rows
        ]

    def _fetch_profile_or_raise(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
        relation_id: int,
    ) -> RelationProfileDTO:
        """Mengambil profil satu relasi atau memunculkan RelationNotFoundError.

        Args:
            conn: Koneksi basis data aktif.
            spec: Spesifikasi tabel relasi.
            relation_id: ID relasi yang dicari.

        Returns:
            Objek RelationProfileDTO.

        Raises:
            RelationNotFoundError: Jika baris relasi tidak ditemukan.
        """
        row = conn.execute(
            f"""
            SELECT id, name, COALESCE(phone, ''), COALESCE(address, ''), is_active
            FROM {spec.relation_table}
            WHERE id = ?;
            """,
            (relation_id,),
        ).fetchone()
        if row is None:
            raise RelationNotFoundError(
                f"{spec.entity_label} dengan ID {relation_id} tidak ditemukan."
            )
        return RelationProfileDTO(
            relation_id=int(row[0]),
            relation_type=spec.relation_type,
            name=str(row[1]),
            phone=str(row[2]),
            address=str(row[3]),
            is_active=bool(row[4]),
        )

    def _ensure_no_duplicate_relation(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
        clean_name: str,
        clean_phone: str | None,
        clean_address: str | None,
        exclude_id: int | None = None,
    ) -> None:
        """Mencegah duplikasi identik berdasarkan kombinasi nama dan kontak/alamat.

        Args:
            conn: Koneksi basis data aktif.
            spec: Spesifikasi tabel relasi.
            clean_name: Nama relasi yang telah dinormalisasi.
            clean_phone: Nomor telepon tervalidasi atau None.
            clean_address: Alamat tervalidasi atau None.
            exclude_id: ID relasi yang dikecualikan saat mode edit.

        Raises:
            RelationConflictError: Jika ditemukan entri yang identik.
        """
        params: list[str | int] = [clean_name.lower()]
        exclude_clause = ""
        if exclude_id is not None:
            exclude_clause = "AND id != ?"
            params.append(exclude_id)

        rows = conn.execute(
            f"""
            SELECT id, COALESCE(phone, ''), COALESCE(address, '')
            FROM {spec.relation_table}
            WHERE LOWER(TRIM(name)) = ? {exclude_clause};
            """,
            params,
        ).fetchall()

        incoming_digits = self._normalize_phone_digits(clean_phone or "")
        incoming_address = (clean_address or "").strip().lower()

        for row in rows:
            existing_digits = self._normalize_phone_digits(str(row[1]))
            existing_address = str(row[2]).strip().lower()
            if incoming_digits and existing_digits == incoming_digits:
                raise RelationConflictError(
                    f"{spec.entity_label} '{clean_name}' dengan nomor telepon tersebut "
                    "sudah terdaftar."
                )
            if (
                not incoming_digits
                and not existing_digits
                and incoming_address == existing_address
            ):
                raise RelationConflictError(
                    f"{spec.entity_label} '{clean_name}' dengan alamat yang sama "
                    "sudah terdaftar."
                )

    def _query_invoices(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
        relation_id: int,
        only_unpaid: bool = False,
        limit: int | None = None,
    ) -> list[RelationInvoiceDTO]:
        """Mengambil daftar nota transaksi milik suatu relasi.

        Args:
            conn: Koneksi basis data aktif.
            spec: Spesifikasi tabel relasi.
            relation_id: ID pelanggan atau supplier.
            only_unpaid: Jika True, hanya mengembalikan nota berstatus belum lunas.
            limit: Batas maksimum jumlah baris yang dikembalikan.

        Returns:
            Daftar objek RelationInvoiceDTO.
        """
        extra_filter = (
            "AND payment_status IN ('UNPAID', 'PARTIAL') AND remaining_amount > 0"
            if only_unpaid
            else ""
        )
        order_clause = (
            "CASE WHEN due_date IS NULL OR TRIM(due_date) = '' THEN 1 ELSE 0 END ASC, "
            f"due_date ASC, {spec.tx_date_col} ASC, id ASC"
            if only_unpaid
            else f"{spec.tx_date_col} DESC, id DESC"
        )
        limit_clause = "LIMIT ?" if limit is not None else ""
        params: list[int] = [relation_id]
        if limit is not None:
            params.append(limit)

        rows = conn.execute(
            f"""
            SELECT
                id,
                invoice_number,
                {spec.tx_date_col},
                subtotal,
                discount,
                total,
                amount_paid,
                remaining_amount,
                payment_status,
                COALESCE(due_date, ''),
                CASE
                    WHEN payment_status IN ('UNPAID', 'PARTIAL')
                         AND remaining_amount > 0
                         AND due_date IS NOT NULL
                         AND TRIM(due_date) != ''
                         AND date(due_date) <= date('now', 'localtime')
                    THEN 1
                    ELSE 0
                END AS is_overdue,
                COALESCE(payment_method, 'Tunai'),
                COALESCE(status, 'COMPLETED'),
                COALESCE(notes, '')
            FROM {spec.tx_table}
            WHERE {spec.relation_fk_col} = ?
              AND UPPER(COALESCE(status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID')
              {extra_filter}
            ORDER BY {order_clause}
            {limit_clause};
            """,
            params,
        ).fetchall()

        return [
            RelationInvoiceDTO(
                invoice_id=int(row[0]),
                invoice_number=str(row[1]),
                transaction_date=str(row[2]),
                subtotal=int(row[3]),
                discount=int(row[4]),
                total=int(row[5]),
                amount_paid=int(row[6]),
                remaining_amount=int(row[7]),
                payment_status=str(row[8]),
                due_date=str(row[9]),
                is_overdue=bool(row[10]),
                payment_method=str(row[11]),
                status=str(row[12]),
                notes=str(row[13]),
            )
            for row in rows
        ]

    def _query_payments(
        self,
        conn: sqlite3.Connection,
        spec: _RelationTableSpec,
        relation_id: int,
        limit: int = 100,
    ) -> list[RelationPaymentDTO]:
        """Mengambil riwayat pembayaran atau cicilan milik suatu relasi.

        Args:
            conn: Koneksi basis data aktif.
            spec: Spesifikasi tabel relasi.
            relation_id: ID pelanggan atau supplier.
            limit: Batas maksimum jumlah riwayat pembayaran.

        Returns:
            Daftar objek RelationPaymentDTO terurut dari yang terbaru.
        """
        if spec.relation_type == "customer":
            rows = conn.execute(
                """
                SELECT
                    p.id,
                    p.sale_id,
                    t.invoice_number,
                    p.payment_date,
                    p.amount,
                    COALESCE(p.payment_method, 'Tunai'),
                    COALESCE(p.reference_number, ''),
                    COALESCE(p.notes, ''),
                    COALESCE(p.tendered_amount, 0),
                    COALESCE(p.change_given, 0),
                    COALESCE(p.cashier_name, 'KASIR')
                FROM sale_payments AS p
                INNER JOIN sales AS t ON t.id = p.sale_id
                WHERE t.customer_id = ?
                  AND UPPER(COALESCE(t.status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID')
                ORDER BY p.payment_date DESC, p.id DESC
                LIMIT ?;
                """,
                (relation_id, limit),
            ).fetchall()
            return [
                RelationPaymentDTO(
                    payment_id=int(row[0]),
                    invoice_id=int(row[1]),
                    invoice_number=str(row[2]),
                    payment_date=str(row[3]),
                    amount=int(row[4]),
                    payment_method=str(row[5]),
                    reference_number=str(row[6]),
                    notes=str(row[7]),
                    tendered_amount=int(row[8]),
                    change_given=int(row[9]),
                    cashier_name=str(row[10]),
                )
                for row in rows
            ]

        rows = conn.execute(
            """
            SELECT
                p.id,
                p.purchase_id,
                t.invoice_number,
                p.payment_date,
                p.amount,
                COALESCE(p.payment_method, 'Tunai'),
                COALESCE(p.reference_number, ''),
                COALESCE(p.notes, '')
            FROM purchase_payments AS p
            INNER JOIN purchases AS t ON t.id = p.purchase_id
            WHERE t.supplier_id = ?
              AND UPPER(COALESCE(t.status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID')
            ORDER BY p.payment_date DESC, p.id DESC
            LIMIT ?;
            """,
            (relation_id, limit),
        ).fetchall()
        return [
            RelationPaymentDTO(
                payment_id=int(row[0]),
                invoice_id=int(row[1]),
                invoice_number=str(row[2]),
                payment_date=str(row[3]),
                amount=int(row[4]),
                payment_method=str(row[5]),
                reference_number=str(row[6]),
                notes=str(row[7]),
            )
            for row in rows
        ]

    def get_page_bundle(
        self,
        relation_type: RelationType,
        filter_dto: RelationFilterDTO | None = None,
    ) -> RelationPageBundleDTO:
        """Memuat seluruh data utama halaman relasi dalam satu koneksi basis data.

        Metode ini dirancang untuk meminimalkan overhead pembukaan koneksi
        SQLCipher dengan menggabungkan pembacaan KPI, baris tabel terfilter,
        serta angka badge kedua mode secara bersamaan.

        Args:
            relation_type: Mode aktif ('customer' atau 'supplier').
            filter_dto: Kriteria filter opsional. Default memakai RelationFilterDTO().

        Returns:
            Objek RelationPageBundleDTO siap diteruskan oleh lapisan bridging.
        """
        spec = self._resolve_spec(relation_type)
        active_filter = filter_dto if filter_dto is not None else RelationFilterDTO()

        with self._open_connection(write=False) as conn:
            kpi = self._query_kpi(conn, spec)
            records = self._query_relations(conn, spec, active_filter)
            active_counts = self._query_active_badge_counts(conn)

        return RelationPageBundleDTO(
            relation_type=spec.relation_type,
            kpi=kpi,
            records=records,
            active_counts=active_counts,
        )

    def list_relations(
        self,
        relation_type: RelationType,
        filter_dto: RelationFilterDTO | None = None,
    ) -> list[RelationSummaryDTO]:
        """Mengambil daftar pelanggan atau supplier teragregasi sesuai filter.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            filter_dto: Kriteria pencarian, status, tagihan, dan pengurutan.

        Returns:
            Daftar objek RelationSummaryDTO.
        """
        spec = self._resolve_spec(relation_type)
        active_filter = filter_dto if filter_dto is not None else RelationFilterDTO()

        with self._open_connection(write=False) as conn:
            return self._query_relations(conn, spec, active_filter)

    def get_kpi(self, relation_type: RelationType) -> RelationKpiDTO:
        """Mengambil metrik KPI ringkas untuk satu jenis relasi.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').

        Returns:
            Objek RelationKpiDTO terbaru.
        """
        spec = self._resolve_spec(relation_type)
        with self._open_connection(write=False) as conn:
            return self._query_kpi(conn, spec)

    def get_active_badge_counts(self) -> dict[RelationType, int]:
        """Mengambil jumlah data aktif untuk tombol pengalih Pelanggan dan Supplier.

        Returns:
            Dictionary memetakan 'customer' dan 'supplier' ke jumlah aktifnya.
        """
        with self._open_connection(write=False) as conn:
            return self._query_active_badge_counts(conn)

    def get_relation_profile(
        self,
        relation_type: RelationType,
        relation_id: int,
    ) -> RelationProfileDTO:
        """Mengambil profil satu pelanggan atau supplier berdasarkan ID.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID unik relasi.

        Returns:
            Objek RelationProfileDTO.

        Raises:
            RelationNotFoundError: Jika relasi tidak ditemukan.
        """
        spec = self._resolve_spec(relation_type)
        with self._open_connection(write=False) as conn:
            return self._fetch_profile_or_raise(conn, spec, relation_id)

    def get_relation_detail(
        self,
        relation_type: RelationType,
        relation_id: int,
        invoice_limit: int = 100,
        payment_limit: int = 100,
    ) -> RelationDetailDTO:
        """Mengambil detail lengkap profil, ringkasan tagihan, nota, dan pembayaran.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID unik relasi.
            invoice_limit: Batas maksimum jumlah nota yang dimuat.
            payment_limit: Batas maksimum jumlah riwayat pembayaran yang dimuat.

        Returns:
            Objek RelationDetailDTO lengkap dalam satu siklus koneksi.

        Raises:
            RelationValidationError: Jika batas limit bernilai tidak positif.
            RelationNotFoundError: Jika relasi tidak ditemukan.
        """
        if invoice_limit <= 0 or payment_limit <= 0:
            raise RelationValidationError("Batas jumlah data detail harus lebih dari 0.")

        spec = self._resolve_spec(relation_type)
        with self._open_connection(write=False) as conn:
            profile = self._fetch_profile_or_raise(conn, spec, relation_id)

            agg_row = conn.execute(
                f"""
                SELECT
                    COUNT(*),
                    COALESCE(SUM(total), 0),
                    COALESCE(
                        SUM(
                            CASE
                                WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                THEN remaining_amount
                                ELSE 0
                            END
                        ),
                        0
                    ),
                    COALESCE(
                        MIN(
                            CASE
                                WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                     AND remaining_amount > 0
                                     AND due_date IS NOT NULL
                                     AND TRIM(due_date) != ''
                                THEN due_date
                                ELSE NULL
                            END
                        ),
                        ''
                    ),
                    COALESCE(
                        MAX(
                            CASE
                                WHEN payment_status IN ('UNPAID', 'PARTIAL')
                                     AND remaining_amount > 0
                                     AND due_date IS NOT NULL
                                     AND TRIM(due_date) != ''
                                     AND date(due_date) <= date('now', 'localtime')
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    )
                FROM {spec.tx_table}
                WHERE {spec.relation_fk_col} = ?
                  AND UPPER(COALESCE(status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID');
                """,
                (relation_id,),
            ).fetchone()

            tx_count = int(agg_row[0]) if agg_row is not None else 0
            tx_total = int(agg_row[1]) if agg_row is not None else 0
            outstanding = int(agg_row[2]) if agg_row is not None else 0
            nearest_due = str(agg_row[3]) if agg_row is not None else ""
            is_overdue = bool(agg_row[4]) if agg_row is not None else False

            invoices = self._query_invoices(
                conn,
                spec,
                relation_id,
                only_unpaid=False,
                limit=invoice_limit,
            )
            payments = self._query_payments(
                conn,
                spec,
                relation_id,
                limit=payment_limit,
            )

        return RelationDetailDTO(
            profile=profile,
            transaction_count=tx_count,
            transaction_total=tx_total,
            outstanding_amount=outstanding,
            nearest_due_date=nearest_due,
            is_overdue=is_overdue,
            invoices=invoices,
            payments=payments,
        )

    def list_unpaid_invoices(
        self,
        relation_type: RelationType,
        relation_id: int,
    ) -> list[RelationInvoiceDTO]:
        """Mengambil daftar nota berstatus UNPAID/PARTIAL untuk keperluan pelunasan.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID unik relasi.

        Returns:
            Daftar nota yang masih memiliki sisa tagihan, diurutkan berdasarkan
            jatuh tempo terdekat.

        Raises:
            RelationNotFoundError: Jika relasi tidak ditemukan.
        """
        spec = self._resolve_spec(relation_type)
        with self._open_connection(write=False) as conn:
            self._fetch_profile_or_raise(conn, spec, relation_id)
            return self._query_invoices(
                conn,
                spec,
                relation_id,
                only_unpaid=True,
                limit=None,
            )

    def check_archive_impact(
        self,
        relation_type: RelationType,
        relation_id: int,
    ) -> ArchiveImpactDTO:
        """Memeriksa sisa tagihan aktif sebelum relasi diarsipkan atau diaktifkan.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID unik relasi.

        Returns:
            Objek ArchiveImpactDTO berisi jumlah nota dan nominal tunggakan.

        Raises:
            RelationNotFoundError: Jika relasi tidak ditemukan.
        """
        spec = self._resolve_spec(relation_type)
        with self._open_connection(write=False) as conn:
            profile = self._fetch_profile_or_raise(conn, spec, relation_id)
            row = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(remaining_amount), 0),
                    COUNT(*),
                    COALESCE(
                        SUM(
                            CASE
                                WHEN due_date IS NOT NULL
                                     AND TRIM(due_date) != ''
                                     AND date(due_date) <= date('now', 'localtime')
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    )
                FROM {spec.tx_table}
                WHERE {spec.relation_fk_col} = ?
                  AND payment_status IN ('UNPAID', 'PARTIAL')
                  AND remaining_amount > 0
                  AND UPPER(COALESCE(status, 'COMPLETED')) NOT IN ('CANCELLED', 'VOID');
                """,
                (relation_id,),
            ).fetchone()

        outstanding_amount = int(row[0]) if row is not None else 0
        unpaid_count = int(row[1]) if row is not None else 0
        overdue_count = int(row[2]) if row is not None else 0

        return ArchiveImpactDTO(
            relation_id=profile.relation_id,
            relation_type=spec.relation_type,
            name=profile.name,
            is_active=profile.is_active,
            outstanding_amount=outstanding_amount,
            unpaid_invoice_count=unpaid_count,
            overdue_invoice_count=overdue_count,
        )

    def create_relation(
        self,
        relation_type: RelationType,
        payload: RelationInputDTO,
    ) -> RelationProfileDTO:
        """Menambahkan data pelanggan atau supplier baru secara atomik.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            payload: Objek RelationInputDTO berisi profil relasi baru.

        Returns:
            Objek RelationProfileDTO yang baru tersimpan beserta ID-nya.

        Raises:
            RelationValidationError: Jika validasi input gagal.
            RelationConflictError: Jika ditemukan entri identik pada basis data.
        """
        spec = self._resolve_spec(relation_type)
        clean_name, clean_phone, clean_address, active_int = (
            self._validate_relation_input(payload, spec.entity_label)
        )

        with self._open_connection(write=True) as conn:
            self._ensure_no_duplicate_relation(
                conn,
                spec,
                clean_name,
                clean_phone,
                clean_address,
                exclude_id=None,
            )
            cursor = conn.execute(
                f"""
                INSERT INTO {spec.relation_table} (name, phone, address, is_active)
                VALUES (?, ?, ?, ?);
                """,
                (clean_name, clean_phone, clean_address, active_int),
            )
            new_id = cursor.lastrowid
            if new_id is None:
                raise RelationBackendError(
                    f"Gagal memperoleh ID baru untuk {spec.entity_label.lower()}."
                )

        logger.info(
            "%s baru berhasil dibuat (id=%d, nama=%s)",
            spec.entity_label,
            int(new_id),
            clean_name,
        )
        return RelationProfileDTO(
            relation_id=int(new_id),
            relation_type=spec.relation_type,
            name=clean_name,
            phone=clean_phone or "",
            address=clean_address or "",
            is_active=bool(active_int),
        )

    def update_relation(
        self,
        relation_type: RelationType,
        relation_id: int,
        payload: RelationInputDTO,
    ) -> RelationProfileDTO:
        """Memperbarui profil pelanggan atau supplier yang sudah ada.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID relasi yang akan diperbarui.
            payload: Data profil baru dalam RelationInputDTO.

        Returns:
            Objek RelationProfileDTO terbaru setelah disimpan.

        Raises:
            RelationValidationError: Jika data masukan tidak valid.
            RelationNotFoundError: Jika relasi tidak ditemukan.
            RelationConflictError: Jika data baru berbenturan dengan relasi lain.
        """
        spec = self._resolve_spec(relation_type)
        clean_name, clean_phone, clean_address, active_int = (
            self._validate_relation_input(payload, spec.entity_label)
        )

        with self._open_connection(write=True) as conn:
            self._fetch_profile_or_raise(conn, spec, relation_id)
            self._ensure_no_duplicate_relation(
                conn,
                spec,
                clean_name,
                clean_phone,
                clean_address,
                exclude_id=relation_id,
            )
            conn.execute(
                f"""
                UPDATE {spec.relation_table}
                SET name = ?, phone = ?, address = ?, is_active = ?
                WHERE id = ?;
                """,
                (clean_name, clean_phone, clean_address, active_int, relation_id),
            )

        logger.info(
            "%s berhasil diperbarui (id=%d, nama=%s)",
            spec.entity_label,
            relation_id,
            clean_name,
        )
        return RelationProfileDTO(
            relation_id=relation_id,
            relation_type=spec.relation_type,
            name=clean_name,
            phone=clean_phone or "",
            address=clean_address or "",
            is_active=bool(active_int),
        )

    def set_relation_active(
        self,
        relation_type: RelationType,
        relation_id: int,
        is_active: bool,
    ) -> RelationProfileDTO:
        """Mengubah status aktif relasi (arsip lunak / aktivasi kembali).

        Menggunakan mekanisme soft-archive agar integritas referensial foreign key
        dengan riwayat transaksi tetap terjaga tanpa menghapus baris historis.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            relation_id: ID relasi target.
            is_active: True untuk mengaktifkan, False untuk mengarsipkan.

        Returns:
            Objek RelationProfileDTO dengan status is_active terbaru.

        Raises:
            RelationNotFoundError: Jika relasi tidak ditemukan.
        """
        spec = self._resolve_spec(relation_type)
        active_int = 1 if is_active else 0

        with self._open_connection(write=True) as conn:
            existing = self._fetch_profile_or_raise(conn, spec, relation_id)
            conn.execute(
                f"UPDATE {spec.relation_table} SET is_active = ? WHERE id = ?;",
                (active_int, relation_id),
            )

        logger.info(
            "Status %s (id=%d) diubah menjadi %s",
            spec.entity_label,
            relation_id,
            "AKTIF" if is_active else "NONAKTIF",
        )
        return RelationProfileDTO(
            relation_id=existing.relation_id,
            relation_type=existing.relation_type,
            name=existing.name,
            phone=existing.phone,
            address=existing.address,
            is_active=is_active,
        )

    @staticmethod
    def _validate_payment_input(
        relation_type: RelationType,
        payload: PaymentInputDTO,
        remaining_amount: int,
    ) -> tuple[int, int, int, str, str | None, str | None, str, str | None]:
        """Memvalidasi parameter pembayaran cicilan atau pelunasan terhadap sisa nota.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            payload: Data masukan pembayaran.
            remaining_amount: Sisa tagihan aktual nota di basis data.

        Returns:
            Tuple (amount, tendered, change_given, method, ref_or_none,
            notes_or_none, cashier_name, payment_date_or_none).

        Raises:
            RelationValidationError: Jika nominal, metode, atau uang diterima tidak valid.
        """
        if payload.amount <= 0:
            raise RelationValidationError("Nominal pembayaran harus lebih dari Rp 0.")
        if payload.amount > remaining_amount:
            raise RelationValidationError(
                f"Nominal pembayaran ({payload.amount}) melebihi sisa tagihan "
                f"({remaining_amount})."
            )

        clean_method = payload.payment_method.strip()
        if not clean_method:
            raise RelationValidationError("Metode pembayaran wajib dipilih.")

        clean_ref = payload.reference_number.strip()
        if len(clean_ref) > MAX_REFERENCE_LENGTH:
            raise RelationValidationError(
                f"Nomor referensi maksimal {MAX_REFERENCE_LENGTH} karakter."
            )

        clean_notes = payload.notes.strip()
        if len(clean_notes) > MAX_NOTES_LENGTH:
            raise RelationValidationError(
                f"Catatan pembayaran maksimal {MAX_NOTES_LENGTH} karakter."
            )

        clean_cashier = payload.cashier_name.strip() or "KASIR"
        clean_date = (
            payload.payment_date.strip()
            if payload.payment_date is not None and payload.payment_date.strip()
            else None
        )

        if relation_type == "customer":
            if payload.tendered_amount is None:
                resolved_tendered = payload.amount
                change_given = 0
            else:
                if payload.tendered_amount < payload.amount:
                    raise RelationValidationError(
                        "Nominal uang diterima tidak boleh kurang dari nominal bayar."
                    )
                if (
                    clean_method.lower() != "tunai"
                    and payload.tendered_amount > payload.amount
                ):
                    raise RelationValidationError(
                        "Pembayaran non-tunai tidak dapat memiliki uang kembalian."
                    )
                resolved_tendered = payload.tendered_amount
                change_given = resolved_tendered - payload.amount
        else:
            resolved_tendered = payload.amount
            change_given = 0

        return (
            payload.amount,
            resolved_tendered,
            change_given,
            clean_method,
            clean_ref if clean_ref else None,
            clean_notes if clean_notes else None,
            clean_cashier,
            clean_date,
        )

    def record_payment(
        self,
        relation_type: RelationType,
        payload: PaymentInputDTO,
        expected_relation_id: int | None = None,
    ) -> PaymentResultDTO:
        """Mencatat pembayaran cicilan atau pelunasan nota secara atomik.

        Setelah baris pembayaran dimasukkan ke tabel sale_payments atau
        purchase_payments, trigger basis data secara otomatis memperbarui
        amount_paid, remaining_amount, dan payment_status pada tabel nota.

        Args:
            relation_type: Jenis relasi ('customer' atau 'supplier').
            payload: Objek PaymentInputDTO berisi detail pembayaran.
            expected_relation_id: ID relasi opsional untuk memastikan kepemilikan nota.

        Returns:
            Objek PaymentResultDTO yang mencerminkan saldo nota terbaru dari database.

        Raises:
            RelationNotFoundError: Jika nota tidak ditemukan.
            RelationConflictError: Jika nota sudah lunas, dibatalkan, atau bukan milik relasi.
            RelationValidationError: Jika nominal atau atribut pembayaran tidak valid.
        """
        spec = self._resolve_spec(relation_type)

        with self._open_connection(write=True) as conn:
            invoice_row = conn.execute(
                f"""
                SELECT
                    id,
                    invoice_number,
                    {spec.relation_fk_col},
                    remaining_amount,
                    payment_status,
                    COALESCE(status, 'COMPLETED')
                FROM {spec.tx_table}
                WHERE id = ?;
                """,
                (payload.invoice_id,),
            ).fetchone()

            if invoice_row is None:
                raise RelationNotFoundError(
                    f"Nota dengan ID {payload.invoice_id} tidak ditemukan."
                )

            invoice_number = str(invoice_row[1])
            owner_id = int(invoice_row[2]) if invoice_row[2] is not None else None
            remaining_before = int(invoice_row[3])
            payment_status_before = str(invoice_row[4])
            tx_status = str(invoice_row[5]).upper()

            if (
                expected_relation_id is not None
                and owner_id != expected_relation_id
            ):
                raise RelationConflictError(
                    f"Nota '{invoice_number}' bukan milik {spec.entity_label.lower()} "
                    "yang dipilih."
                )

            if tx_status in ("CANCELLED", "VOID"):
                raise RelationConflictError(
                    f"Nota '{invoice_number}' sudah dibatalkan dan tidak dapat dibayar."
                )

            if payment_status_before == "PAID" or remaining_before <= 0:
                raise RelationConflictError(
                    f"Nota '{invoice_number}' sudah berstatus lunas."
                )

            (
                amount_applied,
                tendered_amount,
                change_given,
                payment_method,
                reference_number,
                notes,
                cashier_name,
                payment_date,
            ) = self._validate_payment_input(
                spec.relation_type, payload, remaining_before
            )

            payment_id = self._insert_payment_row(
                conn=conn,
                relation_type=spec.relation_type,
                invoice_id=payload.invoice_id,
                amount=amount_applied,
                tendered_amount=tendered_amount,
                change_given=change_given,
                payment_method=payment_method,
                reference_number=reference_number,
                cashier_name=cashier_name,
                notes=notes,
                payment_date=payment_date,
            )

            updated_row = conn.execute(
                f"""
                SELECT amount_paid, remaining_amount, payment_status
                FROM {spec.tx_table}
                WHERE id = ?;
                """,
                (payload.invoice_id,),
            ).fetchone()
            if updated_row is None:
                raise RelationBackendError(
                    f"Gagal membaca ulang status nota '{invoice_number}'."
                )

            new_amount_paid = int(updated_row[0])
            new_remaining = int(updated_row[1])
            new_status = str(updated_row[2])

        logger.info(
            "Pembayaran %s dicatat (payment_id=%d, invoice=%s, nominal=%d, sisa=%d)",
            spec.entity_label,
            payment_id,
            invoice_number,
            amount_applied,
            new_remaining,
        )
        return PaymentResultDTO(
            payment_id=payment_id,
            invoice_id=payload.invoice_id,
            invoice_number=invoice_number,
            amount_applied=amount_applied,
            tendered_amount=tendered_amount,
            change_given=change_given,
            new_amount_paid=new_amount_paid,
            new_remaining_amount=new_remaining,
            new_payment_status=new_status,
        )

    @staticmethod
    def _insert_payment_row(
        conn: sqlite3.Connection,
        relation_type: RelationType,
        invoice_id: int,
        amount: int,
        tendered_amount: int,
        change_given: int,
        payment_method: str,
        reference_number: str | None,
        cashier_name: str,
        notes: str | None,
        payment_date: str | None,
    ) -> int:
        """Menyisipkan satu baris pembayaran ke tabel sale_payments atau purchase_payments.

        Args:
            conn: Koneksi basis data dalam transaksi aktif.
            relation_type: Jenis relasi ('customer' atau 'supplier').
            invoice_id: ID nota yang dibayarkan.
            amount: Nominal pembayaran efektif.
            tendered_amount: Uang diterima untuk pelanggan.
            change_given: Uang kembalian untuk pelanggan.
            payment_method: Metode pembayaran.
            reference_number: Nomor referensi bukti bayar opsional.
            cashier_name: Nama kasir pencatat untuk pelanggan.
            notes: Catatan tambahan opsional.
            payment_date: Waktu pembayaran kustom atau None untuk default database.

        Returns:
            ID baris pembayaran yang baru dibuat.

        Raises:
            RelationBackendError: Jika lastrowid tidak dikembalikan oleh SQLite.
        """
        if relation_type == "customer":
            if payment_date is not None:
                cursor = conn.execute(
                    """
                    INSERT INTO sale_payments (
                        sale_id,
                        payment_date,
                        amount,
                        tendered_amount,
                        change_given,
                        payment_method,
                        reference_number,
                        cashier_name,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        invoice_id,
                        payment_date,
                        amount,
                        tendered_amount,
                        change_given,
                        payment_method,
                        reference_number,
                        cashier_name,
                        notes,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO sale_payments (
                        sale_id,
                        amount,
                        tendered_amount,
                        change_given,
                        payment_method,
                        reference_number,
                        cashier_name,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        invoice_id,
                        amount,
                        tendered_amount,
                        change_given,
                        payment_method,
                        reference_number,
                        cashier_name,
                        notes,
                    ),
                )
        else:
            if payment_date is not None:
                cursor = conn.execute(
                    """
                    INSERT INTO purchase_payments (
                        purchase_id,
                        payment_date,
                        amount,
                        payment_method,
                        reference_number,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        invoice_id,
                        payment_date,
                        amount,
                        payment_method,
                        reference_number,
                        notes,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO purchase_payments (
                        purchase_id,
                        amount,
                        payment_method,
                        reference_number,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        invoice_id,
                        amount,
                        payment_method,
                        reference_number,
                        notes,
                    ),
                )

        payment_id = cursor.lastrowid
        if payment_id is None:
            raise RelationBackendError("Gagal memperoleh ID pembayaran baru.")
        return int(payment_id)