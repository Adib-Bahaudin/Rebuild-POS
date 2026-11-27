"""Modul backend manajemen produk (barang fisik, jasa, dan stok FIFO).

Modul ini menyediakan lapisan akses database (ManajemenProdukRepository) serta
pengendali PySide6 (ManajemenProdukBackend) yang menghubungkan antarmuka
ManajemenProdukPage dengan database SQLite tanpa memuat kode dialog UI secara
langsung.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import logging
import math
from pathlib import Path
import sqlite3
from typing import Any, Literal

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from config import DEFAULT_DB_PATH
from util.helper.db_connection import create_sqlite_connection
from util.helper.formatrupiah import format_ribuan
from ui.manajemenproduk import (
    CategoryOption,
    InventoryLayerDetail,
    ItemFullDetail,
    ItemRowData,
    ItemUnitDetail,
    ManajemenProdukPage,
    ProductFilterState,
    ProductMetricsData,
    ServiceFullDetail,
    ServiceMaterialDetail,
    ServiceRowData,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: int = 14
DEFAULT_LOW_STOCK_THRESHOLD: float = 10.0
SEARCH_DEBOUNCE_MS: int = 250


class ProductBackendError(Exception):
    """Pengecualian dasar untuk seluruh kesalahan logika manajemen produk."""


class ValidationError(ProductBackendError):
    """Pengecualian saat data masukan formulir produk tidak memenuhi aturan."""


class DuplicateSkuError(ProductBackendError):
    """Pengecualian saat kode SKU barang atau jasa sudah digunakan."""


class EntityNotFoundError(ProductBackendError):
    """Pengecualian saat barang, jasa, kategori, atau satuan tidak ditemukan."""


class InsufficientStockAdjustmentError(ProductBackendError):
    """Pengecualian saat penyesuaian stok keluar melebihi sisa layer FIFO."""


@dataclass(frozen=True)
class UnitRecord:
    """Data master satu baris satuan dari tabel units.

    Attributes:
        unit_id: Primary key satuan.
        name: Nama lengkap satuan, misalnya 'Lembar'.
        symbol: Simbol ringkas satuan, misalnya 'Lbr'.
    """

    unit_id: int
    name: str
    symbol: str


@dataclass(frozen=True)
class CategoryRecord:
    """Data master satu baris kategori beserta informasi induknya.

    Attributes:
        category_id: Primary key kategori.
        name: Nama kategori.
        parent_id: ID kategori induk atau None jika kategori utama.
        parent_name: Nama kategori induk atau string kosong.
        is_active: Status aktif kategori.
    """

    category_id: int
    name: str
    parent_id: int | None
    parent_name: str
    is_active: bool


@dataclass(frozen=True)
class ItemUnitPayload:
    """Struktur data input/edit untuk satu variasi satuan jual barang.

    Attributes:
        unit_id: ID satuan referensi pada tabel units.
        variant_name: Nama varian satuan jual, misalnya 'Eceran' atau '1 Rim'.
        conversion_qty: Faktor konversi terhadap satuan dasar (> 0).
        selling_price: Harga jual dalam Rupiah bulat (>= 0).
        is_default: Penanda satuan jual utama kasir.
        is_active: Status aktif varian satuan.
        item_unit_id: Primary key item_units saat mode edit, atau None saat baru.
    """

    unit_id: int
    variant_name: str
    conversion_qty: float
    selling_price: int
    is_default: bool
    is_active: bool = True
    item_unit_id: int | None = None


@dataclass(frozen=True)
class ItemFormPayload:
    """Muatan data formulir untuk pembuatan atau pembaruan barang fisik.

    Attributes:
        sku: Kode SKU unik barang.
        name: Nama barang.
        category_id: ID kategori pada tabel categories.
        base_unit_id: ID satuan dasar pada tabel units.
        description: Deskripsi opsional barang.
        is_active: Status aktif barang pada katalog.
        units: Daftar variasi satuan jual minimal satu entri.
        opening_stock_qty: Kuantitas stok awal opsional saat membuat barang baru.
        opening_stock_cost: Harga modal satuan untuk stok awal opsional.
    """

    sku: str
    name: str
    category_id: int
    base_unit_id: int
    description: str
    is_active: bool
    units: list[ItemUnitPayload]
    opening_stock_qty: float = 0.0
    opening_stock_cost: float = 0.0


@dataclass(frozen=True)
class ItemEditData:
    """Data barang lengkap siap muat ke dalam dialog edit barang.

    Attributes:
        item_id: Primary key barang.
        sku: Kode SKU barang.
        name: Nama barang.
        category_id: ID kategori barang.
        base_unit_id: ID satuan dasar barang.
        description: Deskripsi barang.
        is_active: Status aktif barang.
        is_base_unit_locked: True jika barang sudah memiliki riwayat stok/transaksi.
        units: Daftar variasi satuan jual yang terikat dengan barang.
    """

    item_id: int
    sku: str
    name: str
    category_id: int
    base_unit_id: int
    description: str
    is_active: bool
    is_base_unit_locked: bool
    units: list[ItemUnitPayload]


@dataclass(frozen=True)
class ServiceMaterialPayload:
    """Muatan satu baris bahan baku yang dipakai oleh layanan jasa.

    Attributes:
        item_id: ID barang bahan baku pada tabel items.
        quantity: Takaran pemakaian satuan dasar per satu kali jasa (> 0).
    """

    item_id: int
    quantity: float


@dataclass(frozen=True)
class ServiceFormPayload:
    """Muatan data formulir untuk pembuatan atau pembaruan layanan jasa.

    Attributes:
        sku: Kode SKU unik jasa.
        name: Nama layanan jasa.
        description: Deskripsi opsional jasa.
        selling_price: Harga jual jasa dalam Rupiah bulat.
        is_active: Status aktif jasa pada katalog.
        materials: Daftar komposisi bahan baku pemotong stok FIFO.
    """

    sku: str
    name: str
    description: str
    selling_price: int
    is_active: bool
    materials: list[ServiceMaterialPayload]


@dataclass(frozen=True)
class ServiceEditData:
    """Data layanan jasa lengkap siap muat ke dalam dialog edit jasa.

    Attributes:
        service_id: Primary key jasa.
        sku: Kode SKU jasa.
        name: Nama jasa.
        description: Deskripsi jasa.
        selling_price: Harga jual jasa.
        is_active: Status aktif jasa.
        materials: Daftar bahan baku yang terhubung dengan jasa.
    """

    service_id: int
    sku: str
    name: str
    description: str
    selling_price: int
    is_active: bool
    materials: list[ServiceMaterialPayload]


@dataclass(frozen=True)
class StockAdjustmentPayload:
    """Muatan data untuk pencatatan stok awal atau penyesuaian opname.

    Attributes:
        item_id: ID barang target penyesuaian.
        adjustment_type: Jenis penyesuaian ('OPENING_STOCK', 'ADJUSTMENT_IN',
            atau 'ADJUSTMENT_OUT').
        quantity: Kuantitas perubahan stok dalam satuan dasar (> 0).
        unit_cost: Harga modal per satuan dasar (wajib >= 0 untuk stok masuk).
        notes: Catatan keterangan opname atau stok awal.
    """

    item_id: int
    adjustment_type: Literal["OPENING_STOCK", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"]
    quantity: float
    unit_cost: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class StockMovementRecord:
    """Satu baris riwayat keluar-masuk stok untuk tampilan kartu stok.

    Attributes:
        movement_id: Primary key pada tabel stock_movements.
        movement_date: Tanggal dan waktu pergerakan stok terformat.
        movement_type: Jenis pergerakan (SALE, PURCHASE, OPENING_STOCK, dll.).
        quantity_in: Kuantitas masuk dalam satuan dasar.
        quantity_out: Kuantitas keluar dalam satuan dasar.
        notes: Catatan referensi pergerakan stok.
    """

    movement_id: int
    movement_date: str
    movement_type: str
    quantity_in: float
    quantity_out: float
    notes: str


@dataclass(frozen=True)
class PaginatedProductsResult:
    """Hasil pemuatan data halaman manajemen produk beserta metrik ringkas.

    Attributes:
        active_tab: Tab aktif ('items' atau 'services').
        items: Daftar baris barang fisik untuk halaman aktif.
        services: Daftar baris layanan jasa untuk halaman aktif.
        current_page: Nomor halaman aktif setelah validasi batas.
        total_pages: Total seluruh halaman tersedia.
        total_records: Total keseluruhan baris yang cocok dengan filter.
        metrics: Ringkasan indikator untuk empat kartu metrik atas.
    """

    active_tab: Literal["items", "services"]
    items: list[ItemRowData]
    services: list[ServiceRowData]
    current_page: int
    total_pages: int
    total_records: int
    metrics: ProductMetricsData


def format_integer(value: int) -> str:
    """Memformat bilangan bulat dengan pemisah ribuan titik gaya Indonesia.

    Args:
        value: Nilai integer yang akan diformat.

    Returns:
        String angka dengan pemisah ribuan titik.
    """
    return format_ribuan(value)


def format_rupiah(amount: int | float) -> str:
    """Memformat nominal menjadi string mata uang Rupiah bulat.

    Args:
        amount: Nilai nominal dalam Rupiah.

    Returns:
        String nominal terformat seperti 'Rp 15.000'.
    """
    rounded = int(round(amount))
    formatted = format_integer(abs(rounded))
    return f"-Rp {formatted}" if rounded < 0 else f"Rp {formatted}"


def format_qty(value: float, symbol: str = "") -> str:
    """Memformat angka kuantitas stok beserta simbol satuan opsional.

    Args:
        value: Nilai kuantitas bertipe float.
        symbol: Simbol satuan seperti 'Lbr' atau 'Pcs'.

    Returns:
        String kuantitas terformat rapi tanpa nol desimal berlebih.
    """
    if abs(value - round(value)) < 1e-6:
        num_str = format_integer(int(round(value)))
    else:
        num_str = f"{value:,.2f}".rstrip("0").rstrip(".")
        num_str = num_str.replace(",", "_").replace(".", ",").replace("_", ".")
    clean_symbol = symbol.strip()
    return f"{num_str} {clean_symbol}" if clean_symbol else num_str


def format_display_date(raw_value: str, with_time: bool = False) -> str:
    """Mengonversi timestamp ISO SQLite menjadi format tampilan ringkas.

    Args:
        raw_value: String tanggal mentah dari database.
        with_time: Jika True, menyertakan jam dan menit (HH:MM).

    Returns:
        String tanggal terformat 'DD/MM/YYYY' atau 'DD/MM/YYYY HH:MM'.
    """
    cleaned = raw_value.strip()
    if not cleaned:
        return "-"
    normalized = cleaned.replace("T", " ")
    target_fmt = "%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized[:19], fmt)
            return parsed.strftime(target_fmt)
        except ValueError:
            continue
    return cleaned


class ManajemenProdukRepository:
    """Lapisan akses database SQLite untuk seluruh operasi manajemen produk.

    Attributes:
        db_path: Path menuju file database SQLite aplikasi POS.
        low_stock_threshold: Batas kuantitas satuan dasar untuk status stok menipis.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        low_stock_threshold: float = DEFAULT_LOW_STOCK_THRESHOLD,
    ) -> None:
        """Menginisialisasi repository produk dengan lokasi database target.

        Args:
            db_path: Path file SQLite opsional. Default memakai DEFAULT_DB_PATH.
            low_stock_threshold: Ambang batas stok menipis dalam satuan dasar.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.low_stock_threshold: float = max(0.0, float(low_stock_threshold))

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite baru dengan Row factory dan foreign keys aktif.

        Returns:
            Koneksi sqlite3.Connection siap pakai.

        Raises:
            FileNotFoundError: Jika file database belum ditemukan pada disk.
        """
        return create_sqlite_connection(self.db_path)

    @staticmethod
    def _require_lastrowid(cursor: sqlite3.Cursor, table_name: str) -> int:
        """Memastikan nilai lastrowid hasil perintah INSERT bertipe integer valid.

        Args:
            cursor: Cursor SQLite setelah eksekusi INSERT.
            table_name: Nama tabel tujuan untuk pesan kesalahan.

        Returns:
            Nilai primary key integer baris baru.

        Raises:
            ProductBackendError: Jika SQLite tidak mengembalikan lastrowid.
        """
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise ProductBackendError(
                f"Gagal mendapatkan ID baris baru dari tabel '{table_name}'."
            )
        return int(lastrowid)

    def fetch_metrics(self) -> ProductMetricsData:
        """Menghitung empat indikator metrik utama katalog dan nilai aset FIFO.

        Returns:
            Objek ProductMetricsData siap ditampilkan pada kartu ringkasan atas.
        """
        with closing(self._connect()) as conn:
            item_counts = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_items,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_items
                FROM items;
                """
            ).fetchone()
            service_counts = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_services,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_services
                FROM services;
                """
            ).fetchone()
            stock_summary = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN stock_qty <= 0 THEN 1 ELSE 0 END) AS empty_count,
                    SUM(
                        CASE WHEN stock_qty > 0 AND stock_qty <= ? THEN 1 ELSE 0 END
                    ) AS low_count
                FROM (
                    SELECT
                        i.id,
                        COALESCE(SUM(il.remaining_qty), 0) AS stock_qty
                    FROM items AS i
                    LEFT JOIN inventory_layers AS il
                        ON il.item_id = i.id AND il.remaining_qty > 0
                    WHERE i.is_active = 1
                    GROUP BY i.id
                );
                """,
                (self.low_stock_threshold,),
            ).fetchone()
            asset_summary = conn.execute(
                """
                SELECT
                    COUNT(id) AS active_layers,
                    COALESCE(SUM(remaining_qty * unit_cost), 0) AS total_value
                FROM inventory_layers
                WHERE remaining_qty > 0;
                """
            ).fetchone()

        active_items = int(item_counts["active_items"] or 0) if item_counts else 0
        inactive_items = int(item_counts["inactive_items"] or 0) if item_counts else 0
        active_services = (
            int(service_counts["active_services"] or 0) if service_counts else 0
        )
        inactive_services = (
            int(service_counts["inactive_services"] or 0) if service_counts else 0
        )
        empty_count = int(stock_summary["empty_count"] or 0) if stock_summary else 0
        low_count = int(stock_summary["low_count"] or 0) if stock_summary else 0
        active_layers = (
            int(asset_summary["active_layers"] or 0) if asset_summary else 0
        )
        total_value = float(asset_summary["total_value"] or 0.0) if asset_summary else 0.0

        return ProductMetricsData(
            active_catalog_count=active_items + active_services,
            active_catalog_sub=f"{active_items} barang · {active_services} jasa",
            low_stock_count=empty_count + low_count,
            low_stock_sub=f"{empty_count} habis · {low_count} menipis",
            inventory_value_text=format_rupiah(total_value),
            inventory_value_sub=f"{active_layers} layer FIFO aktif",
            inactive_count=inactive_items + inactive_services,
            inactive_sub="Disembunyikan kasir",
        )

    def fetch_category_options(
        self,
        include_inactive: bool = False,
    ) -> list[CategoryOption]:
        """Mengambil daftar opsi kategori terurut dengan format hierarki induk.

        Args:
            include_inactive: Jika True, menyertakan kategori berstatus nonaktif.

        Returns:
            Daftar objek CategoryOption untuk dropdown filter dan formulir.
        """
        where_clause = "" if include_inactive else "WHERE c.is_active = 1"
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    c.id,
                    c.name,
                    COALESCE(p.name, '') AS parent_name
                FROM categories AS c
                LEFT JOIN categories AS p ON p.id = c.parent_id
                {where_clause}
                ORDER BY
                    CASE WHEN p.name IS NULL THEN c.name ELSE p.name END ASC,
                    c.parent_id IS NOT NULL ASC,
                    c.name ASC;
                """
            ).fetchall()

        options: list[CategoryOption] = []
        for row in rows:
            parent_name = str(row["parent_name"] or "").strip()
            name = str(row["name"] or "")
            label = f"{parent_name} > {name}" if parent_name else name
            options.append(CategoryOption(category_id=int(row["id"]), label=label))
        return options

    def fetch_categories(self) -> list[CategoryRecord]:
        """Mengambil seluruh data master kategori untuk manajemen kategori.

        Returns:
            Daftar objek CategoryRecord lengkap.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.parent_id,
                    COALESCE(p.name, '') AS parent_name,
                    c.is_active
                FROM categories AS c
                LEFT JOIN categories AS p ON p.id = c.parent_id
                ORDER BY c.is_active DESC, c.name ASC;
                """
            ).fetchall()

        return [
            CategoryRecord(
                category_id=int(row["id"]),
                name=str(row["name"] or ""),
                parent_id=(
                    int(row["parent_id"]) if row["parent_id"] is not None else None
                ),
                parent_name=str(row["parent_name"] or ""),
                is_active=bool(int(row["is_active"] or 0)),
            )
            for row in rows
        ]

    def fetch_units(self) -> list[UnitRecord]:
        """Mengambil seluruh data master satuan dari tabel units.

        Returns:
            Daftar objek UnitRecord terurut berdasarkan nama satuan.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, name, symbol
                FROM units
                ORDER BY name ASC;
                """
            ).fetchall()

        return [
            UnitRecord(
                unit_id=int(row["id"]),
                name=str(row["name"] or ""),
                symbol=str(row["symbol"] or ""),
            )
            for row in rows
        ]

    def save_category(
        self,
        name: str,
        parent_id: int | None = None,
        is_active: bool = True,
        category_id: int | None = None,
    ) -> int:
        """Menyimpan kategori baru atau memperbarui kategori yang sudah ada.

        Args:
            name: Nama kategori yang wajib unik.
            parent_id: ID kategori induk opsional.
            is_active: Status aktif kategori.
            category_id: ID kategori saat pembaruan, atau None saat tambah baru.

        Returns:
            ID kategori yang tersimpan.

        Raises:
            ValidationError: Jika nama kosong, parent menunjuk diri sendiri,
                atau nama kategori sudah digunakan.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("Nama kategori tidak boleh kosong.")
        if category_id is not None and parent_id == category_id:
            raise ValidationError("Kategori induk tidak boleh menunjuk dirinya sendiri.")

        active_flag = 1 if is_active else 0
        try:
            with closing(self._connect()) as conn:
                with conn:
                    if category_id is None:
                        cursor = conn.execute(
                            """
                            INSERT INTO categories (name, parent_id, is_active)
                            VALUES (?, ?, ?);
                            """,
                            (clean_name, parent_id, active_flag),
                        )
                        return self._require_lastrowid(cursor, "categories")

                    cursor = conn.execute(
                        """
                        UPDATE categories
                        SET name = ?, parent_id = ?, is_active = ?
                        WHERE id = ?;
                        """,
                        (clean_name, parent_id, active_flag, category_id),
                    )
                    if cursor.rowcount == 0:
                        raise EntityNotFoundError(
                            f"Kategori dengan ID {category_id} tidak ditemukan."
                        )
                    return category_id
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Nama kategori '{clean_name}' sudah terdaftar atau induk tidak valid."
            ) from exc

    def save_unit(
        self,
        name: str,
        symbol: str,
        unit_id: int | None = None,
    ) -> int:
        """Menyimpan satuan baru atau memperbarui satuan yang sudah ada.

        Args:
            name: Nama lengkap satuan yang wajib unik.
            symbol: Simbol ringkas satuan yang wajib unik.
            unit_id: ID satuan saat pembaruan, atau None saat tambah baru.

        Returns:
            ID satuan yang tersimpan.

        Raises:
            ValidationError: Jika nama/simbol kosong atau sudah terdaftar.
        """
        clean_name = name.strip()
        clean_symbol = symbol.strip()
        if not clean_name or not clean_symbol:
            raise ValidationError("Nama dan simbol satuan wajib diisi.")

        try:
            with closing(self._connect()) as conn:
                with conn:
                    if unit_id is None:
                        cursor = conn.execute(
                            """
                            INSERT INTO units (name, symbol)
                            VALUES (?, ?);
                            """,
                            (clean_name, clean_symbol),
                        )
                        return self._require_lastrowid(cursor, "units")

                    cursor = conn.execute(
                        """
                        UPDATE units
                        SET name = ?, symbol = ?
                        WHERE id = ?;
                        """,
                        (clean_name, clean_symbol, unit_id),
                    )
                    if cursor.rowcount == 0:
                        raise EntityNotFoundError(
                            f"Satuan dengan ID {unit_id} tidak ditemukan."
                        )
                    return unit_id
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Nama satuan '{clean_name}' atau simbol '{clean_symbol}' sudah digunakan."
            ) from exc

    def _build_items_filter_sql(
        self,
        filter_state: ProductFilterState,
    ) -> tuple[str, list[Any]]:
        """Menyusun klausa WHERE dan parameter terikat untuk query tabel barang.

        Args:
            filter_state: Snapshot kondisi filter dari antarmuka pengguna.

        Returns:
            Tuple berisi string klausa WHERE dan daftar parameter SQL.
        """
        conditions: list[str] = ["1 = 1"]
        params: list[Any] = []

        if filter_state.search_text:
            pattern = f"%{filter_state.search_text}%"
            conditions.append(
                "(LOWER(base.sku) LIKE LOWER(?) OR LOWER(base.name) LIKE LOWER(?))"
            )
            params.extend([pattern, pattern])

        if filter_state.category_id is not None:
            conditions.append(
                "(base.category_id = ? OR base.parent_category_id = ?)"
            )
            params.extend([filter_state.category_id, filter_state.category_id])

        status = filter_state.status_filter.upper()
        if status == "ACTIVE":
            conditions.append("base.is_active = 1")
        elif status == "INACTIVE":
            conditions.append("base.is_active = 0")

        stock_filter = filter_state.stock_filter.upper()
        if stock_filter == "AVAILABLE":
            conditions.append("base.total_stock > 0")
        elif stock_filter == "LOW":
            conditions.append("base.total_stock > 0 AND base.total_stock <= ?")
            params.append(self.low_stock_threshold)
        elif stock_filter == "EMPTY":
            conditions.append("base.total_stock <= 0")

        return " AND ".join(conditions), params

    def fetch_paginated_items(
        self,
        filter_state: ProductFilterState,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[ItemRowData], int, int, int]:
        """Mengambil daftar barang fisik berpaginasi sesuai filter aktif.

        Args:
            filter_state: Kriteria pencarian, kategori, stok, dan status aktif.
            page: Nomor halaman target berbasis 1.
            page_size: Jumlah baris maksimal per halaman.

        Returns:
            Tuple (rows, safe_page, total_pages, total_records).
        """
        safe_page_size = max(1, page_size)
        where_sql, params = self._build_items_filter_sql(filter_state)
        base_cte = """
            WITH item_summary AS (
                SELECT
                    i.id AS item_id,
                    i.sku AS sku,
                    i.name AS name,
                    i.category_id AS category_id,
                    c.parent_id AS parent_category_id,
                    c.name AS category_name,
                    u.symbol AS base_unit_symbol,
                    i.is_active AS is_active,
                    COALESCE(
                        (
                            SELECT SUM(il.remaining_qty)
                            FROM inventory_layers AS il
                            WHERE il.item_id = i.id AND il.remaining_qty > 0
                        ),
                        0
                    ) AS total_stock,
                    COALESCE(
                        (
                            SELECT iu.selling_price
                            FROM item_units AS iu
                            WHERE iu.item_id = i.id AND iu.is_active = 1
                            ORDER BY iu.is_default DESC, iu.conversion_qty ASC, iu.id ASC
                            LIMIT 1
                        ),
                        0
                    ) AS default_price,
                    COALESCE(
                        (
                            SELECT u2.symbol
                            FROM item_units AS iu
                            INNER JOIN units AS u2 ON u2.id = iu.unit_id
                            WHERE iu.item_id = i.id AND iu.is_active = 1
                            ORDER BY iu.is_default DESC, iu.conversion_qty ASC, iu.id ASC
                            LIMIT 1
                        ),
                        u.symbol
                    ) AS default_unit_symbol,
                    (
                        SELECT COUNT(iu.id)
                        FROM item_units AS iu
                        WHERE iu.item_id = i.id AND iu.is_active = 1
                    ) AS active_unit_count
                FROM items AS i
                INNER JOIN categories AS c ON c.id = i.category_id
                INNER JOIN units AS u ON u.id = i.base_unit_id
            )
        """

        with closing(self._connect()) as conn:
            count_row = conn.execute(
                f"{base_cte} SELECT COUNT(*) AS total FROM item_summary AS base "
                f"WHERE {where_sql};",
                params,
            ).fetchone()
            total_records = int(count_row["total"] or 0) if count_row else 0
            total_pages = max(1, math.ceil(total_records / safe_page_size))
            safe_page = max(1, min(page, total_pages))
            offset = (safe_page - 1) * safe_page_size

            db_rows = conn.execute(
                f"{base_cte} "
                "SELECT * FROM item_summary AS base "
                f"WHERE {where_sql} "
                "ORDER BY base.is_active DESC, base.name ASC, base.item_id ASC "
                "LIMIT ? OFFSET ?;",
                [*params, safe_page_size, offset],
            ).fetchall()

        mapped: list[ItemRowData] = []
        for row in db_rows:
            stock_val = float(row["total_stock"] or 0.0)
            stock_state: Literal["ok", "low", "empty"]
            if stock_val <= 0.0:
                stock_state = "empty"
            elif stock_val <= self.low_stock_threshold:
                stock_state = "low"
            else:
                stock_state = "ok"

            unit_count = int(row["active_unit_count"] or 0)
            default_symbol = str(row["default_unit_symbol"] or "")
            extra_units = max(0, unit_count - 1)
            unit_summary = (
                f"{default_symbol} · +{extra_units} varian"
                if extra_units > 0
                else default_symbol
            )

            mapped.append(
                ItemRowData(
                    item_id=int(row["item_id"]),
                    sku=str(row["sku"] or ""),
                    name=str(row["name"] or ""),
                    category_name=str(row["category_name"] or ""),
                    default_price_text=format_rupiah(int(row["default_price"] or 0)),
                    unit_summary=unit_summary,
                    stock_text=format_qty(
                        stock_val,
                        str(row["base_unit_symbol"] or ""),
                    ),
                    stock_state=stock_state,
                    is_active=bool(int(row["is_active"] or 0)),
                )
            )

        return mapped, safe_page, total_pages, total_records

    def fetch_paginated_services(
        self,
        filter_state: ProductFilterState,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[ServiceRowData], int, int, int]:
        """Mengambil daftar layanan jasa berpaginasi sesuai filter aktif.

        Args:
            filter_state: Kriteria pencarian dan status aktif dari UI.
            page: Nomor halaman target berbasis 1.
            page_size: Jumlah baris maksimal per halaman.

        Returns:
            Tuple (rows, safe_page, total_pages, total_records).
        """
        safe_page_size = max(1, page_size)
        conditions: list[str] = ["1 = 1"]
        params: list[Any] = []

        if filter_state.search_text:
            pattern = f"%{filter_state.search_text}%"
            conditions.append(
                "(LOWER(s.sku) LIKE LOWER(?) OR LOWER(s.name) LIKE LOWER(?))"
            )
            params.extend([pattern, pattern])

        status = filter_state.status_filter.upper()
        if status == "ACTIVE":
            conditions.append("s.is_active = 1")
        elif status == "INACTIVE":
            conditions.append("s.is_active = 0")

        where_sql = " AND ".join(conditions)

        with closing(self._connect()) as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) AS total FROM services AS s WHERE {where_sql};",
                params,
            ).fetchone()
            total_records = int(count_row["total"] or 0) if count_row else 0
            total_pages = max(1, math.ceil(total_records / safe_page_size))
            safe_page = max(1, min(page, total_pages))
            offset = (safe_page - 1) * safe_page_size

            db_rows = conn.execute(
                f"""
                SELECT
                    s.id AS service_id,
                    s.sku AS sku,
                    s.name AS name,
                    s.selling_price AS selling_price,
                    s.is_active AS is_active,
                    (
                        SELECT COUNT(sm.id)
                        FROM service_materials AS sm
                        WHERE sm.service_id = s.id
                    ) AS material_count
                FROM services AS s
                WHERE {where_sql}
                ORDER BY s.is_active DESC, s.name ASC, s.id ASC
                LIMIT ? OFFSET ?;
                """,
                [*params, safe_page_size, offset],
            ).fetchall()

        mapped: list[ServiceRowData] = []
        for row in db_rows:
            mat_count = int(row["material_count"] or 0)
            mat_summary = (
                f"{mat_count} bahan baku" if mat_count > 0 else "Tanpa bahan"
            )
            mapped.append(
                ServiceRowData(
                    service_id=int(row["service_id"]),
                    sku=str(row["sku"] or ""),
                    name=str(row["name"] or ""),
                    selling_price_text=format_rupiah(int(row["selling_price"] or 0)),
                    material_summary=mat_summary,
                    is_active=bool(int(row["is_active"] or 0)),
                )
            )

        return mapped, safe_page, total_pages, total_records

    def fetch_item_detail(self, item_id: int) -> ItemFullDetail | None:
        """Mengambil detail lengkap satu barang termasuk satuan jual dan layer FIFO.

        Args:
            item_id: Primary key barang pada tabel items.

        Returns:
            Objek ItemFullDetail atau None jika barang tidak ditemukan.
        """
        with closing(self._connect()) as conn:
            item_row = conn.execute(
                """
                SELECT
                    i.id,
                    i.sku,
                    i.name,
                    i.description,
                    i.is_active,
                    c.name AS category_name,
                    u.name AS base_unit_name,
                    u.symbol AS base_unit_symbol
                FROM items AS i
                INNER JOIN categories AS c ON c.id = i.category_id
                INNER JOIN units AS u ON u.id = i.base_unit_id
                WHERE i.id = ?
                LIMIT 1;
                """,
                (item_id,),
            ).fetchone()
            if item_row is None:
                return None

            unit_rows = conn.execute(
                """
                SELECT
                    iu.variant_name,
                    u.symbol AS unit_symbol,
                    iu.conversion_qty,
                    iu.selling_price,
                    iu.is_default,
                    iu.is_active
                FROM item_units AS iu
                INNER JOIN units AS u ON u.id = iu.unit_id
                WHERE iu.item_id = ?
                ORDER BY iu.is_default DESC, iu.is_active DESC, iu.conversion_qty ASC;
                """,
                (item_id,),
            ).fetchall()

            layer_rows = conn.execute(
                """
                SELECT
                    received_at,
                    source_type,
                    remaining_qty,
                    unit_cost
                FROM inventory_layers
                WHERE item_id = ? AND remaining_qty > 0
                ORDER BY received_at ASC, id ASC;
                """,
                (item_id,),
            ).fetchall()

        base_symbol = str(item_row["base_unit_symbol"] or "")
        total_stock = sum(float(layer["remaining_qty"] or 0.0) for layer in layer_rows)
        total_value = sum(
            float(layer["remaining_qty"] or 0.0) * float(layer["unit_cost"] or 0.0)
            for layer in layer_rows
        )

        units = [
            ItemUnitDetail(
                variant_name=str(row["variant_name"] or ""),
                unit_symbol=base_symbol,
                conversion_qty=float(row["conversion_qty"] or 1.0),
                selling_price_text=format_rupiah(int(row["selling_price"] or 0)),
                is_default=bool(int(row["is_default"] or 0)),
                is_active=bool(int(row["is_active"] or 0)),
            )
            for row in unit_rows
        ]
        fifo_layers = [
            InventoryLayerDetail(
                received_at=format_display_date(str(layer["received_at"] or "")),
                source_type=str(layer["source_type"] or ""),
                remaining_qty_text=format_qty(
                    float(layer["remaining_qty"] or 0.0),
                    base_symbol,
                ),
                unit_cost_text=format_rupiah(float(layer["unit_cost"] or 0.0)),
            )
            for layer in layer_rows
        ]

        return ItemFullDetail(
            item_id=int(item_row["id"]),
            sku=str(item_row["sku"] or ""),
            name=str(item_row["name"] or ""),
            category_name=str(item_row["category_name"] or ""),
            base_unit_name=f"{item_row['base_unit_name']} ({base_symbol})",
            description=str(item_row["description"] or ""),
            total_stock_text=format_qty(total_stock, base_symbol),
            total_value_text=format_rupiah(total_value),
            is_active=bool(int(item_row["is_active"] or 0)),
            units=units,
            fifo_layers=fifo_layers,
        )

    def fetch_stock_item_options(self) -> list[tuple[int, str, str, str, float]]:
        """Mengambil daftar barang beserta total sisa stok FIFO aktifnya."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    i.id,
                    i.sku,
                    i.name,
                    u.symbol AS base_unit_symbol,
                    COALESCE(
                        (
                            SELECT SUM(il.remaining_qty)
                            FROM inventory_layers AS il
                            WHERE il.item_id = i.id AND il.remaining_qty > 0
                        ),
                        0
                    ) AS current_stock
                FROM items AS i
                INNER JOIN units AS u ON u.id = i.base_unit_id
                WHERE i.is_active = 1
                ORDER BY i.name ASC;
                """
            ).fetchall()
        return [
            (
                int(row["id"]),
                str(row["sku"] or ""),
                str(row["name"] or ""),
                str(row["base_unit_symbol"] or ""),
                float(row["current_stock"] or 0.0),
            )
            for row in rows
        ]

    def fetch_material_item_options(
        self,
        include_inactive: bool = False,
    ) -> list[tuple[int, str, str, str]]:
        """Mengambil daftar ringkas barang (id, sku, name, unit_symbol) untuk bahan baku."""
        where_clause = "" if include_inactive else "WHERE i.is_active = 1"
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT i.id, i.sku, i.name, u.symbol AS base_unit_symbol
                FROM items AS i
                INNER JOIN units AS u ON u.id = i.base_unit_id
                {where_clause}
                ORDER BY i.is_active DESC, i.name ASC;
                """
            ).fetchall()
        return [
            (
                int(row["id"]),
                str(row["sku"] or ""),
                str(row["name"] or ""),
                str(row["base_unit_symbol"] or ""),
            )
            for row in rows
        ]

    def fetch_item_edit_data(self, item_id: int) -> ItemEditData | None:
        """Mengambil data barang untuk kebutuhan pengisian dialog edit.

        Args:
            item_id: Primary key barang.

        Returns:
            Objek ItemEditData lengkap termasuk status penguncian satuan dasar.
        """
        with closing(self._connect()) as conn:
            item_row = conn.execute(
                """
                SELECT id, sku, name, category_id, base_unit_id, description, is_active
                FROM items
                WHERE id = ?
                LIMIT 1;
                """,
                (item_id,),
            ).fetchone()
            if item_row is None:
                return None

            unit_rows = conn.execute(
                """
                SELECT
                    id,
                    unit_id,
                    variant_name,
                    conversion_qty,
                    selling_price,
                    is_default,
                    is_active
                FROM item_units
                WHERE item_id = ?
                ORDER BY is_default DESC, conversion_qty ASC, id ASC;
                """,
                (item_id,),
            ).fetchall()

            usage_row = conn.execute(
                """
                SELECT (
                    EXISTS (SELECT 1 FROM inventory_layers WHERE item_id = ?)
                    OR EXISTS (SELECT 1 FROM sale_details WHERE item_id = ?)
                    OR EXISTS (SELECT 1 FROM purchase_details WHERE item_id = ?)
                ) AS is_used;
                """,
                (item_id, item_id, item_id),
            ).fetchone()

        is_locked = bool(int(usage_row["is_used"] or 0)) if usage_row else False
        units = [
            ItemUnitPayload(
                item_unit_id=int(row["id"]),
                unit_id=int(row["unit_id"]),
                variant_name=str(row["variant_name"] or ""),
                conversion_qty=float(row["conversion_qty"] or 1.0),
                selling_price=int(row["selling_price"] or 0),
                is_default=bool(int(row["is_default"] or 0)),
                is_active=bool(int(row["is_active"] or 0)),
            )
            for row in unit_rows
        ]
        return ItemEditData(
            item_id=int(item_row["id"]),
            sku=str(item_row["sku"] or ""),
            name=str(item_row["name"] or ""),
            category_id=int(item_row["category_id"]),
            base_unit_id=int(item_row["base_unit_id"]),
            description=str(item_row["description"] or ""),
            is_active=bool(int(item_row["is_active"] or 0)),
            is_base_unit_locked=is_locked,
            units=units,
        )

    def fetch_service_detail(self, service_id: int) -> ServiceFullDetail | None:
        """Mengambil detail lengkap layanan jasa beserta estimasi modal bahan baku.

        Args:
            service_id: Primary key layanan jasa.

        Returns:
            Objek ServiceFullDetail atau None jika jasa tidak ditemukan.
        """
        with closing(self._connect()) as conn:
            service_row = conn.execute(
                """
                SELECT id, sku, name, description, selling_price, is_active
                FROM services
                WHERE id = ?
                LIMIT 1;
                """,
                (service_id,),
            ).fetchone()
            if service_row is None:
                return None

            mat_rows = conn.execute(
                """
                SELECT
                    i.sku AS item_sku,
                    i.name AS item_name,
                    u.symbol AS unit_symbol,
                    sm.quantity AS quantity,
                    COALESCE(
                        (
                            SELECT il.unit_cost
                            FROM inventory_layers AS il
                            WHERE il.item_id = i.id AND il.remaining_qty > 0
                            ORDER BY il.received_at ASC, il.id ASC
                            LIMIT 1
                        ),
                        (
                            SELECT il2.unit_cost
                            FROM inventory_layers AS il2
                            WHERE il2.item_id = i.id
                            ORDER BY il2.received_at DESC, il2.id DESC
                            LIMIT 1
                        ),
                        0
                    ) AS fifo_unit_cost
                FROM service_materials AS sm
                INNER JOIN items AS i ON i.id = sm.item_id
                INNER JOIN units AS u ON u.id = i.base_unit_id
                WHERE sm.service_id = ?
                ORDER BY i.name ASC;
                """,
                (service_id,),
            ).fetchall()

        total_hpp = 0.0
        materials: list[ServiceMaterialDetail] = []
        for row in mat_rows:
            qty = float(row["quantity"] or 0.0)
            unit_cost = float(row["fifo_unit_cost"] or 0.0)
            est_cost = qty * unit_cost
            total_hpp += est_cost
            materials.append(
                ServiceMaterialDetail(
                    item_sku=str(row["item_sku"] or ""),
                    item_name=str(row["item_name"] or ""),
                    quantity_text=format_qty(qty, str(row["unit_symbol"] or "")),
                    estimated_cost_text=format_rupiah(est_cost),
                )
            )

        return ServiceFullDetail(
            service_id=int(service_row["id"]),
            sku=str(service_row["sku"] or ""),
            name=str(service_row["name"] or ""),
            description=str(service_row["description"] or ""),
            selling_price_text=format_rupiah(int(service_row["selling_price"] or 0)),
            estimated_hpp_text=format_rupiah(total_hpp),
            is_active=bool(int(service_row["is_active"] or 0)),
            materials=materials,
        )

    def fetch_service_edit_data(self, service_id: int) -> ServiceEditData | None:
        """Mengambil data layanan jasa untuk kebutuhan pengisian dialog edit.

        Args:
            service_id: Primary key layanan jasa.

        Returns:
            Objek ServiceEditData atau None jika jasa tidak ditemukan.
        """
        with closing(self._connect()) as conn:
            service_row = conn.execute(
                """
                SELECT id, sku, name, description, selling_price, is_active
                FROM services
                WHERE id = ?
                LIMIT 1;
                """,
                (service_id,),
            ).fetchone()
            if service_row is None:
                return None

            mat_rows = conn.execute(
                """
                SELECT item_id, quantity
                FROM service_materials
                WHERE service_id = ?
                ORDER BY id ASC;
                """,
                (service_id,),
            ).fetchall()

        materials = [
            ServiceMaterialPayload(
                item_id=int(row["item_id"]),
                quantity=float(row["quantity"] or 0.0),
            )
            for row in mat_rows
        ]
        return ServiceEditData(
            service_id=int(service_row["id"]),
            sku=str(service_row["sku"] or ""),
            name=str(service_row["name"] or ""),
            description=str(service_row["description"] or ""),
            selling_price=int(service_row["selling_price"] or 0),
            is_active=bool(int(service_row["is_active"] or 0)),
            materials=materials,
        )

    @staticmethod
    def _validate_item_payload(payload: ItemFormPayload) -> None:
        """Memvalidasi aturan bisnis sebelum menyimpan data barang fisik.

        Args:
            payload: Objek ItemFormPayload dari formulir.

        Raises:
            ValidationError: Jika SKU, nama, satuan jual, atau stok awal tidak valid.
        """
        if not payload.sku.strip():
            raise ValidationError("Kode SKU barang wajib diisi.")
        if not payload.name.strip():
            raise ValidationError("Nama barang wajib diisi.")
        if not payload.units:
            raise ValidationError("Minimal harus terdapat satu variasi satuan jual.")
        if payload.opening_stock_qty < 0 or payload.opening_stock_cost < 0:
            raise ValidationError("Stok awal dan harga modal tidak boleh bernilai negatif.")

        active_units = [unit for unit in payload.units if unit.is_active]
        if not active_units:
            raise ValidationError("Minimal satu variasi satuan jual harus berstatus aktif.")

        seen_variants: set[str] = set()
        default_count = 0
        for unit in payload.units:
            variant_key = unit.variant_name.strip().lower()
            if not variant_key:
                raise ValidationError("Nama varian satuan jual tidak boleh kosong.")
            if variant_key in seen_variants:
                raise ValidationError(
                    f"Nama varian satuan '{unit.variant_name}' duplikat."
                )
            seen_variants.add(variant_key)
            if unit.conversion_qty <= 0:
                raise ValidationError("Nilai konversi satuan harus lebih dari 0.")
            if unit.selling_price < 0:
                raise ValidationError("Harga jual satuan tidak boleh negatif.")
            if unit.is_default and unit.is_active:
                default_count += 1

        if default_count != 1:
            raise ValidationError(
                "Tepat satu variasi satuan jual aktif harus dipilih sebagai satuan default."
            )

    def create_item(self, payload: ItemFormPayload) -> int:
        """Menyimpan barang fisik baru, variasi satuan, serta stok awal opsional.

        Args:
            payload: Muatan formulir barang baru.

        Returns:
            ID barang baru yang berhasil tersimpan.

        Raises:
            ValidationError: Jika data masukan tidak valid.
            DuplicateSkuError: Jika SKU barang sudah terdaftar.
        """
        self._validate_item_payload(payload)
        clean_sku = payload.sku.strip()
        clean_name = payload.name.strip()
        clean_desc = payload.description.strip() or None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with closing(self._connect()) as conn:
                with conn:
                    item_cursor = conn.execute(
                        """
                        INSERT INTO items (
                            sku, name, category_id, base_unit_id,
                            description, is_active, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            clean_sku,
                            clean_name,
                            payload.category_id,
                            payload.base_unit_id,
                            clean_desc,
                            1 if payload.is_active else 0,
                            now_str,
                            now_str,
                        ),
                    )
                    item_id = self._require_lastrowid(item_cursor, "items")

                    for unit in payload.units:
                        conn.execute(
                            """
                            INSERT INTO item_units (
                                item_id, unit_id, variant_name,
                                conversion_qty, selling_price, is_default, is_active
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?);
                            """,
                            (
                                item_id,
                                unit.unit_id,
                                unit.variant_name.strip(),
                                float(unit.conversion_qty),
                                int(unit.selling_price),
                                1 if unit.is_default else 0,
                                1 if unit.is_active else 0,
                            ),
                        )

                    if payload.opening_stock_qty > 0:
                        self._insert_stock_in(
                            conn=conn,
                            item_id=item_id,
                            source_type="OPENING_STOCK",
                            quantity=float(payload.opening_stock_qty),
                            unit_cost=float(payload.opening_stock_cost),
                            movement_date=now_str,
                            notes=f"Stok awal pembuatan barang {clean_sku}",
                        )

                    return item_id
        except sqlite3.IntegrityError as exc:
            if "items.sku" in str(exc):
                raise DuplicateSkuError(
                    f"Kode SKU '{clean_sku}' sudah digunakan barang lain."
                ) from exc
            raise ValidationError(
                f"Gagal menyimpan barang karena konflik relasi data: {exc}"
            ) from exc

    def update_item(self, item_id: int, payload: ItemFormPayload) -> None:
        """Memperbarui informasi barang fisik dan variasi satuannya secara aman.

        Satuan dasar tidak diubah apabila barang telah memiliki riwayat stok
        atau transaksi. Variasi satuan yang dihapus pada form akan dinonaktifkan
        apabila sudah pernah direferensikan oleh transaksi.

        Args:
            item_id: Primary key barang target.
            payload: Muatan data pembaruan barang.

        Raises:
            EntityNotFoundError: Jika barang tidak ditemukan.
            DuplicateSkuError: Jika SKU baru bentrok dengan barang lain.
            ValidationError: Jika validasi formulir gagal.
        """
        self._validate_item_payload(payload)
        clean_sku = payload.sku.strip()
        clean_name = payload.name.strip()
        clean_desc = payload.description.strip() or None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with closing(self._connect()) as conn:
                with conn:
                    existing = conn.execute(
                        "SELECT base_unit_id FROM items WHERE id = ?;",
                        (item_id,),
                    ).fetchone()
                    if existing is None:
                        raise EntityNotFoundError(
                            f"Barang dengan ID {item_id} tidak ditemukan."
                        )

                    usage_row = conn.execute(
                        """
                        SELECT (
                            EXISTS (SELECT 1 FROM inventory_layers WHERE item_id = ?)
                            OR EXISTS (SELECT 1 FROM sale_details WHERE item_id = ?)
                            OR EXISTS (SELECT 1 FROM purchase_details WHERE item_id = ?)
                        ) AS is_used;
                        """,
                        (item_id, item_id, item_id),
                    ).fetchone()
                    is_locked = bool(int(usage_row["is_used"] or 0)) if usage_row else False
                    effective_base_unit_id = (
                        int(existing["base_unit_id"])
                        if is_locked
                        else payload.base_unit_id
                    )

                    conn.execute(
                        """
                        UPDATE items
                        SET sku = ?,
                            name = ?,
                            category_id = ?,
                            base_unit_id = ?,
                            description = ?,
                            is_active = ?,
                            updated_at = ?
                        WHERE id = ?;
                        """,
                        (
                            clean_sku,
                            clean_name,
                            payload.category_id,
                            effective_base_unit_id,
                            clean_desc,
                            1 if payload.is_active else 0,
                            now_str,
                            item_id,
                        ),
                    )

                    existing_unit_rows = conn.execute(
                        "SELECT id FROM item_units WHERE item_id = ?;",
                        (item_id,),
                    ).fetchall()
                    existing_unit_ids = {int(row["id"]) for row in existing_unit_rows}
                    kept_unit_ids: set[int] = set()

                    for unit in payload.units:
                        if unit.item_unit_id is not None and unit.item_unit_id in existing_unit_ids:
                            kept_unit_ids.add(unit.item_unit_id)
                            conn.execute(
                                """
                                UPDATE item_units
                                SET unit_id = ?,
                                    variant_name = ?,
                                    conversion_qty = ?,
                                    selling_price = ?,
                                    is_default = ?,
                                    is_active = ?
                                WHERE id = ? AND item_id = ?;
                                """,
                                (
                                    unit.unit_id,
                                    unit.variant_name.strip(),
                                    float(unit.conversion_qty),
                                    int(unit.selling_price),
                                    1 if unit.is_default else 0,
                                    1 if unit.is_active else 0,
                                    unit.item_unit_id,
                                    item_id,
                                ),
                            )
                        else:
                            conn.execute(
                                """
                                INSERT INTO item_units (
                                    item_id, unit_id, variant_name,
                                    conversion_qty, selling_price, is_default, is_active
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?);
                                """,
                                (
                                    item_id,
                                    unit.unit_id,
                                    unit.variant_name.strip(),
                                    float(unit.conversion_qty),
                                    int(unit.selling_price),
                                    1 if unit.is_default else 0,
                                    1 if unit.is_active else 0,
                                ),
                            )

                    removed_unit_ids = existing_unit_ids - kept_unit_ids
                    for removed_id in removed_unit_ids:
                        ref_row = conn.execute(
                            """
                            SELECT (
                                EXISTS (SELECT 1 FROM sale_details WHERE item_unit_id = ?)
                                OR EXISTS (SELECT 1 FROM purchase_details WHERE item_unit_id = ?)
                            ) AS is_referenced;
                            """,
                            (removed_id, removed_id),
                        ).fetchone()
                        is_referenced = (
                            bool(int(ref_row["is_referenced"] or 0))
                            if ref_row
                            else True
                        )
                        if is_referenced:
                            conn.execute(
                                """
                                UPDATE item_units
                                SET is_active = 0, is_default = 0
                                WHERE id = ?;
                                """,
                                (removed_id,),
                            )
                        else:
                            conn.execute(
                                "DELETE FROM item_units WHERE id = ?;",
                                (removed_id,),
                            )
        except sqlite3.IntegrityError as exc:
            if "items.sku" in str(exc):
                raise DuplicateSkuError(
                    f"Kode SKU '{clean_sku}' sudah digunakan barang lain."
                ) from exc
            raise ValidationError(
                f"Gagal memperbarui barang karena konflik data: {exc}"
            ) from exc

    def toggle_item_status(self, item_id: int, is_active: bool) -> None:
        """Mengubah status aktif atau arsip untuk satu barang fisik.

        Args:
            item_id: Primary key barang.
            is_active: Status aktif baru.

        Raises:
            EntityNotFoundError: Jika barang tidak ditemukan.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE items
                    SET is_active = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (1 if is_active else 0, now_str, item_id),
                )
                if cursor.rowcount == 0:
                    raise EntityNotFoundError(
                        f"Barang dengan ID {item_id} tidak ditemukan."
                    )

    @staticmethod
    def _validate_service_payload(payload: ServiceFormPayload) -> None:
        """Memvalidasi aturan bisnis sebelum menyimpan data layanan jasa.

        Args:
            payload: Objek ServiceFormPayload dari formulir.

        Raises:
            ValidationError: Jika SKU, nama, harga jual, atau bahan baku tidak valid.
        """
        if not payload.sku.strip():
            raise ValidationError("Kode SKU jasa wajib diisi.")
        if not payload.name.strip():
            raise ValidationError("Nama layanan jasa wajib diisi.")
        if payload.selling_price < 0:
            raise ValidationError("Harga jual jasa tidak boleh negatif.")

        seen_items: set[int] = set()
        for mat in payload.materials:
            if mat.quantity <= 0:
                raise ValidationError("Takaran bahan baku jasa harus lebih dari 0.")
            if mat.item_id in seen_items:
                raise ValidationError(
                    "Bahan baku yang sama tidak boleh dimasukkan lebih dari sekali."
                )
            seen_items.add(mat.item_id)

    def create_service(self, payload: ServiceFormPayload) -> int:
        """Menyimpan layanan jasa baru beserta komposisi bahan bakunya.

        Args:
            payload: Muatan formulir layanan jasa baru.

        Returns:
            ID layanan jasa baru yang tersimpan.

        Raises:
            DuplicateSkuError: Jika SKU jasa sudah digunakan.
            ValidationError: Jika data formulir tidak valid.
        """
        self._validate_service_payload(payload)
        clean_sku = payload.sku.strip()
        clean_name = payload.name.strip()
        clean_desc = payload.description.strip() or None

        try:
            with closing(self._connect()) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO services (
                            sku, name, description, selling_price, is_active
                        )
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            clean_sku,
                            clean_name,
                            clean_desc,
                            int(payload.selling_price),
                            1 if payload.is_active else 0,
                        ),
                    )
                    service_id = self._require_lastrowid(cursor, "services")

                    for mat in payload.materials:
                        conn.execute(
                            """
                            INSERT INTO service_materials (
                                service_id, item_id, quantity
                            )
                            VALUES (?, ?, ?);
                            """,
                            (service_id, mat.item_id, float(mat.quantity)),
                        )
                    return service_id
        except sqlite3.IntegrityError as exc:
            if "services.sku" in str(exc):
                raise DuplicateSkuError(
                    f"Kode SKU jasa '{clean_sku}' sudah digunakan."
                ) from exc
            raise ValidationError(
                f"Gagal menyimpan jasa karena konflik relasi data: {exc}"
            ) from exc

    def update_service(self, service_id: int, payload: ServiceFormPayload) -> None:
        """Memperbarui layanan jasa beserta daftar komposisi bahan bakunya.

        Args:
            service_id: Primary key layanan jasa.
            payload: Muatan data pembaruan jasa.

        Raises:
            EntityNotFoundError: Jika jasa tidak ditemukan.
            DuplicateSkuError: Jika SKU baru bentrok dengan jasa lain.
            ValidationError: Jika validasi formulir gagal.
        """
        self._validate_service_payload(payload)
        clean_sku = payload.sku.strip()
        clean_name = payload.name.strip()
        clean_desc = payload.description.strip() or None

        try:
            with closing(self._connect()) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE services
                        SET sku = ?, name = ?, description = ?,
                            selling_price = ?, is_active = ?
                        WHERE id = ?;
                        """,
                        (
                            clean_sku,
                            clean_name,
                            clean_desc,
                            int(payload.selling_price),
                            1 if payload.is_active else 0,
                            service_id,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise EntityNotFoundError(
                            f"Jasa dengan ID {service_id} tidak ditemukan."
                        )

                    conn.execute(
                        "DELETE FROM service_materials WHERE service_id = ?;",
                        (service_id,),
                    )
                    for mat in payload.materials:
                        conn.execute(
                            """
                            INSERT INTO service_materials (
                                service_id, item_id, quantity
                            )
                            VALUES (?, ?, ?);
                            """,
                            (service_id, mat.item_id, float(mat.quantity)),
                        )
        except sqlite3.IntegrityError as exc:
            if "services.sku" in str(exc):
                raise DuplicateSkuError(
                    f"Kode SKU jasa '{clean_sku}' sudah digunakan."
                ) from exc
            raise ValidationError(
                f"Gagal memperbarui jasa karena konflik data: {exc}"
            ) from exc

    def toggle_service_status(self, service_id: int, is_active: bool) -> None:
        """Mengubah status aktif atau arsip untuk satu layanan jasa.

        Args:
            service_id: Primary key layanan jasa.
            is_active: Status aktif baru.

        Raises:
            EntityNotFoundError: Jika layanan jasa tidak ditemukan.
        """
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    "UPDATE services SET is_active = ? WHERE id = ?;",
                    (1 if is_active else 0, service_id),
                )
                if cursor.rowcount == 0:
                    raise EntityNotFoundError(
                        f"Jasa dengan ID {service_id} tidak ditemukan."
                    )

    @staticmethod
    def _insert_stock_in(
        conn: sqlite3.Connection,
        item_id: int,
        source_type: Literal["OPENING_STOCK", "ADJUSTMENT_IN"],
        quantity: float,
        unit_cost: float,
        movement_date: str,
        notes: str,
    ) -> None:
        """Menambahkan layer FIFO baru dan catatan pergerakan stok masuk.

        Args:
            conn: Koneksi SQLite dalam transaksi aktif.
            item_id: ID barang target.
            source_type: Jenis sumber stok ('OPENING_STOCK' atau 'ADJUSTMENT_IN').
            quantity: Kuantitas stok masuk dalam satuan dasar.
            unit_cost: Harga modal satuan dasar.
            movement_date: Tanggal dan waktu pencatatan.
            notes: Catatan keterangan stok masuk.
        """
        conn.execute(
            """
            INSERT INTO inventory_layers (
                item_id, source_type, purchase_detail_id,
                received_qty, remaining_qty, unit_cost, received_at
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?);
            """,
            (
                item_id,
                source_type,
                quantity,
                quantity,
                unit_cost,
                movement_date,
            ),
        )
        conn.execute(
            """
            INSERT INTO stock_movements (
                item_id, movement_type, purchase_detail_id,
                sale_detail_id, sale_detail_material_id,
                quantity_in, quantity_out, movement_date, notes
            )
            VALUES (?, ?, NULL, NULL, NULL, ?, 0, ?, ?);
            """,
            (item_id, source_type, quantity, movement_date, notes),
        )

    def _allocate_fifo_adjustment_out(
        self,
        conn: sqlite3.Connection,
        item_id: int,
        required_qty: float,
        movement_date: str,
        notes: str,
    ) -> None:
        """Memotong layer stok FIFO untuk penyesuaian stok keluar (opname kurang).

        Args:
            conn: Koneksi SQLite dalam transaksi aktif.
            item_id: ID barang target.
            required_qty: Jumlah pengurangan stok dalam satuan dasar.
            movement_date: Tanggal dan waktu pencatatan.
            notes: Catatan keterangan penyesuaian keluar.

        Raises:
            InsufficientStockAdjustmentError: Jika total sisa layer tidak mencukupi.
        """
        layers = conn.execute(
            """
            SELECT id, remaining_qty, unit_cost
            FROM inventory_layers
            WHERE item_id = ? AND remaining_qty > 0
            ORDER BY received_at ASC, id ASC;
            """,
            (item_id,),
        ).fetchall()

        total_available = sum(float(layer["remaining_qty"]) for layer in layers)
        if total_available + 1e-9 < required_qty:
            raise InsufficientStockAdjustmentError(
                f"Stok tersedia ({total_available:g}) tidak mencukupi untuk "
                f"pengurangan sebesar {required_qty:g}."
            )

        movement_cursor = conn.execute(
            """
            INSERT INTO stock_movements (
                item_id, movement_type, purchase_detail_id,
                sale_detail_id, sale_detail_material_id,
                quantity_in, quantity_out, movement_date, notes
            )
            VALUES (?, 'ADJUSTMENT_OUT', NULL, NULL, NULL, 0, ?, ?, ?);
            """,
            (item_id, required_qty, movement_date, notes),
        )
        movement_id = self._require_lastrowid(movement_cursor, "stock_movements")

        remaining_to_issue = required_qty
        for layer in layers:
            if remaining_to_issue <= 1e-9:
                break
            layer_id = int(layer["id"])
            layer_available = float(layer["remaining_qty"])
            layer_cost = float(layer["unit_cost"])

            take_qty = min(layer_available, remaining_to_issue)
            new_remaining = max(0.0, layer_available - take_qty)

            conn.execute(
                "UPDATE inventory_layers SET remaining_qty = ? WHERE id = ?;",
                (new_remaining, layer_id),
            )
            conn.execute(
                """
                INSERT INTO stock_issue_allocations (
                    stock_movement_id, inventory_layer_id,
                    quantity, unit_cost, subtotal_cost
                )
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    movement_id,
                    layer_id,
                    take_qty,
                    layer_cost,
                    take_qty * layer_cost,
                ),
            )
            remaining_to_issue -= take_qty

    def record_stock_adjustment(self, payload: StockAdjustmentPayload) -> None:
        """Mencatat stok awal atau penyesuaian stok masuk/keluar berbasis FIFO.

        Args:
            payload: Objek StockAdjustmentPayload dari dialog penyesuaian stok.

        Raises:
            ValidationError: Jika kuantitas <= 0 atau harga modal negatif.
            EntityNotFoundError: Jika barang target tidak ditemukan.
            InsufficientStockAdjustmentError: Jika stok keluar melebihi sisa FIFO.
        """
        if payload.quantity <= 0:
            raise ValidationError("Kuantitas penyesuaian stok harus lebih dari 0.")
        if payload.adjustment_type != "ADJUSTMENT_OUT" and payload.unit_cost < 0:
            raise ValidationError("Harga modal satuan tidak boleh negatif.")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_notes = payload.notes.strip() or f"Penyesuaian {payload.adjustment_type}"

        with closing(self._connect()) as conn:
            with conn:
                exists = conn.execute(
                    "SELECT 1 FROM items WHERE id = ?;",
                    (payload.item_id,),
                ).fetchone()
                if exists is None:
                    raise EntityNotFoundError(
                        f"Barang dengan ID {payload.item_id} tidak ditemukan."
                    )

                if payload.adjustment_type == "ADJUSTMENT_OUT":
                    self._allocate_fifo_adjustment_out(
                        conn=conn,
                        item_id=payload.item_id,
                        required_qty=float(payload.quantity),
                        movement_date=now_str,
                        notes=clean_notes,
                    )
                else:
                    self._insert_stock_in(
                        conn=conn,
                        item_id=payload.item_id,
                        source_type=payload.adjustment_type,
                        quantity=float(payload.quantity),
                        unit_cost=float(payload.unit_cost),
                        movement_date=now_str,
                        notes=clean_notes,
                    )

    def fetch_stock_card(
        self,
        item_id: int,
        limit: int = 100,
    ) -> list[StockMovementRecord]:
        """Mengambil riwayat mutasi stok untuk dialog kartu stok barang.

        Args:
            item_id: Primary key barang target.
            limit: Batas jumlah baris mutasi terbaru yang diambil.

        Returns:
            Daftar objek StockMovementRecord terurut dari yang paling baru.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    movement_date,
                    movement_type,
                    quantity_in,
                    quantity_out,
                    COALESCE(notes, '') AS notes
                FROM stock_movements
                WHERE item_id = ?
                ORDER BY movement_date DESC, id DESC
                LIMIT ?;
                """,
                (item_id, max(1, limit)),
            ).fetchall()

        return [
            StockMovementRecord(
                movement_id=int(row["id"]),
                movement_date=format_display_date(
                    str(row["movement_date"] or ""),
                    with_time=True,
                ),
                movement_type=str(row["movement_type"] or ""),
                quantity_in=float(row["quantity_in"] or 0.0),
                quantity_out=float(row["quantity_out"] or 0.0),
                notes=str(row["notes"] or ""),
            )
            for row in rows
        ]


class ManajemenProdukBackend(QObject):
    """Pengendali backend penghubung antara ManajemenProdukPage dan database SQLite.

    Signals:
        data_loaded: Dipancarkan membawa PaginatedProductsResult setelah data termuat.
        open_add_item_dialog: Meminta lapisan helper membuka dialog tambah barang.
        open_edit_item_dialog: Meminta lapisan helper membuka dialog edit (ItemEditData).
        open_add_service_dialog: Meminta lapisan helper membuka dialog tambah jasa.
        open_edit_service_dialog: Meminta lapisan helper membuka dialog edit (ServiceEditData).
        open_stock_adjustment_dialog: Meminta dialog stok opname (item_id opsional).
        open_stock_card_dialog: Meminta dialog kartu stok (item_id, list[StockMovementRecord]).
        open_master_dialog: Meminta dialog manajemen kategori dan satuan.
        action_succeeded: Dipancarkan membawa (judul, pesan) saat operasi tulis berhasil.
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
        show_dialogs: bool = True,
    ) -> None:
        """Menginisialisasi pengendali backend dan mengikat sinyal halaman produk.

        Args:
            page: Instance ManajemenProdukPage yang akan dikelola.
            db_path: Lokasi file database SQLite opsional.
            page_size: Jumlah baris maksimal per halaman tabel.
            low_stock_threshold: Batas stok menipis dalam satuan dasar.
            show_dialogs: Jika True, menampilkan QMessageBox saat terjadi kesalahan.
        """
        super().__init__(page)
        self._page = page
        self._repository = ManajemenProdukRepository(
            db_path=db_path,
            low_stock_threshold=low_stock_threshold,
        )
        self._page_size = max(1, page_size)
        self._current_page = 1
        self._selected_item_id: int | None = None
        self._selected_service_id: int | None = None
        self._show_dialogs = show_dialogs

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(SEARCH_DEBOUNCE_MS)

        self._connect_signals()

    @property
    def repository(self) -> ManajemenProdukRepository:
        """Mengembalikan instance repository database yang digunakan backend.

        Returns:
            Instance ManajemenProdukRepository aktif.
        """
        return self._repository

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh sinyal interaksi ManajemenProdukPage ke slot backend."""
        self._page.refresh_requested.connect(self.refresh)
        self._page.filter_changed.connect(self._on_filter_changed)
        self._page.page_changed.connect(self._on_page_changed)
        self._page.item_selected.connect(self._on_item_selected)
        self._page.service_selected.connect(self._on_service_selected)

        self._page.add_item_requested.connect(self.open_add_item_dialog.emit)
        self._page.add_service_requested.connect(self.open_add_service_dialog.emit)
        self._page.adjust_stock_global_requested.connect(
            lambda: self.open_stock_adjustment_dialog.emit(None)
        )
        self._page.manage_master_requested.connect(self.open_master_dialog.emit)

        self._page.edit_item_requested.connect(self._on_edit_item_requested)
        self._page.edit_service_requested.connect(self._on_edit_service_requested)
        self._page.adjust_item_stock_requested.connect(
            self.open_stock_adjustment_dialog.emit
        )
        self._page.stock_card_requested.connect(self._on_stock_card_requested)
        self._page.toggle_item_status_requested.connect(
            self._on_toggle_item_status
        )
        self._page.toggle_service_status_requested.connect(
            self._on_toggle_service_status
        )
        self._filter_timer.timeout.connect(self._on_filter_timeout)

    def refresh(self) -> PaginatedProductsResult | None:
        """Memuat ulang daftar kategori, metrik, tabel aktif, dan panel detail.

        Returns:
            Objek PaginatedProductsResult jika berhasil, atau None jika gagal.
        """
        self._reload_category_filter()
        result = self.load_page(
            filter_state=self._page.get_filter_state(),
            page=self._current_page,
        )
        self._refresh_active_detail()
        return result

    def _reload_category_filter(self) -> None:
        """Memperbarui isi dropdown filter kategori dari database."""
        try:
            categories = self._repository.fetch_category_options()
            self._page.set_categories(categories)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat daftar kategori produk")
            self._notify_error("Gagal Memuat Kategori", str(exc))

    def load_page(
        self,
        filter_state: ProductFilterState | None = None,
        page: int = 1,
    ) -> PaginatedProductsResult | None:
        """Mengambil data halaman sesuai tab aktif dan menerapkannya ke UI.

        Args:
            filter_state: Snapshot filter opsional. Jika None, dibaca dari UI.
            page: Nomor halaman target berbasis 1.

        Returns:
            Objek PaginatedProductsResult apabila sukses, atau None jika gagal.
        """
        state = (
            filter_state
            if filter_state is not None
            else self._page.get_filter_state()
        )
        try:
            metrics = self._repository.fetch_metrics()
            if state.active_tab == "items":
                items, safe_page, total_pages, total_records = (
                    self._repository.fetch_paginated_items(
                        filter_state=state,
                        page=page,
                        page_size=self._page_size,
                    )
                )
                services: list[ServiceRowData] = []
            else:
                services, safe_page, total_pages, total_records = (
                    self._repository.fetch_paginated_services(
                        filter_state=state,
                        page=page,
                        page_size=self._page_size,
                    )
                )
                items = []
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat data halaman manajemen produk")
            self._notify_error(
                "Gagal Memuat Produk",
                f"Tidak dapat membaca database produk: {exc}",
            )
            return None

        self._current_page = safe_page
        self._page.set_metrics(metrics)
        if state.active_tab == "items":
            self._page.set_items(items)
            shown_count = len(items)
        else:
            self._page.set_services(services)
            shown_count = len(services)

        self._page.set_pagination(
            current_page=safe_page,
            total_pages=total_pages,
            total_records=total_records,
            shown_records=shown_count,
        )

        result = PaginatedProductsResult(
            active_tab=state.active_tab,
            items=items,
            services=services,
            current_page=safe_page,
            total_pages=total_pages,
            total_records=total_records,
            metrics=metrics,
        )
        self.data_loaded.emit(result)
        return result

    def _refresh_active_detail(self) -> None:
        """Menyegarkan isi panel detail samping jika ada baris yang sedang dibuka."""
        active_tab = self._page.get_filter_state().active_tab
        if active_tab == "items" and self._selected_item_id is not None:
            self._on_item_selected(self._selected_item_id)
        elif active_tab == "services" and self._selected_service_id is not None:
            self._on_service_selected(self._selected_service_id)

    def _on_filter_changed(self, _filter_state: object) -> None:
        """Memulai ulang timer debounce saat pengguna mengubah pencarian/filter."""
        self._filter_timer.start()

    def _on_filter_timeout(self) -> None:
        """Menjalankan query ulang dari halaman pertama setelah debounce selesai."""
        self._current_page = 1
        self._selected_item_id = None
        self._selected_service_id = None
        self._page.clear_detail_panel()
        self.load_page(page=1)

    def _on_page_changed(self, target_page: int) -> None:
        """Memuat halaman tabel sesuai tombol navigasi paginasi yang ditekan.

        Args:
            target_page: Nomor halaman tujuan berbasis 1.
        """
        self._current_page = max(1, target_page)
        self.load_page(page=self._current_page)

    def _on_item_selected(self, item_id: int) -> None:
        """Mengambil detail barang dan menampilkannya pada panel samping kanan.

        Args:
            item_id: Primary key barang terpilih.
        """
        self._selected_item_id = item_id
        self._selected_service_id = None
        try:
            detail = self._repository.fetch_item_detail(item_id)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal mengambil detail barang ID %d", item_id)
            self._notify_error("Gagal Memuat Detail", str(exc))
            return

        if detail is None:
            self._page.clear_detail_panel()
            return
        self._page.set_item_detail(detail)

    def _on_service_selected(self, service_id: int) -> None:
        """Mengambil detail layanan jasa dan menampilkannya pada panel samping kanan.

        Args:
            service_id: Primary key layanan jasa terpilih.
        """
        self._selected_service_id = service_id
        self._selected_item_id = None
        try:
            detail = self._repository.fetch_service_detail(service_id)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal mengambil detail jasa ID %d", service_id)
            self._notify_error("Gagal Memuat Detail", str(exc))
            return

        if detail is None:
            self._page.clear_detail_panel()
            return
        self._page.set_service_detail(detail)

    def _on_edit_item_requested(self, item_id: int) -> None:
        """Mengambil data edit barang lalu memancarkan sinyal pembuka dialog edit.

        Args:
            item_id: Primary key barang yang akan diedit.
        """
        try:
            edit_data = self._repository.fetch_item_edit_data(item_id)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat data edit barang ID %d", item_id)
            self._notify_error("Gagal Memuat Data Edit", str(exc))
            return

        if edit_data is None:
            self._notify_error(
                "Barang Tidak Ditemukan",
                f"Barang dengan ID {item_id} tidak ditemukan di database.",
            )
            return
        self.open_edit_item_dialog.emit(edit_data)

    def _on_edit_service_requested(self, service_id: int) -> None:
        """Mengambil data edit jasa lalu memancarkan sinyal pembuka dialog edit.

        Args:
            service_id: Primary key jasa yang akan diedit.
        """
        try:
            edit_data = self._repository.fetch_service_edit_data(service_id)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat data edit jasa ID %d", service_id)
            self._notify_error("Gagal Memuat Data Edit", str(exc))
            return

        if edit_data is None:
            self._notify_error(
                "Jasa Tidak Ditemukan",
                f"Layanan jasa dengan ID {service_id} tidak ditemukan di database.",
            )
            return
        self.open_edit_service_dialog.emit(edit_data)

    def _on_stock_card_requested(self, item_id: int) -> None:
        """Mengambil riwayat mutasi stok lalu memancarkan sinyal dialog kartu stok.

        Args:
            item_id: Primary key barang target kartu stok.
        """
        try:
            records = self._repository.fetch_stock_card(item_id=item_id)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat kartu stok barang ID %d", item_id)
            self._notify_error("Gagal Memuat Kartu Stok", str(exc))
            return
        self.open_stock_card_dialog.emit(item_id, records)

    def _on_toggle_item_status(self, item_id: int, target_active: bool) -> None:
        """Mengubah status aktif/arsip barang lalu menyegarkan tampilan halaman.

        Args:
            item_id: Primary key barang.
            target_active: Status aktif tujuan.
        """
        try:
            self._repository.toggle_item_status(item_id, target_active)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal mengubah status barang ID %d", item_id)
            self._notify_error("Gagal Mengubah Status", str(exc))
            return

        status_text = "diaktifkan kembali" if target_active else "diarsipkan"
        logger.info(
            "Database berubah: status barang ID %d diubah menjadi %s",
            item_id,
            "aktif" if target_active else "arsip",
        )
        self.action_succeeded.emit(
            "Status Diperbarui",
            f"Barang berhasil {status_text}.",
        )
        self.refresh()

    def _on_toggle_service_status(
        self,
        service_id: int,
        target_active: bool,
    ) -> None:
        """Mengubah status aktif/arsip layanan jasa lalu menyegarkan halaman.

        Args:
            service_id: Primary key jasa.
            target_active: Status aktif tujuan.
        """
        try:
            self._repository.toggle_service_status(service_id, target_active)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal mengubah status jasa ID %d", service_id)
            self._notify_error("Gagal Mengubah Status", str(exc))
            return

        status_text = "diaktifkan kembali" if target_active else "diarsipkan"
        logger.info(
            "Database berubah: status jasa ID %d diubah menjadi %s",
            service_id,
            "aktif" if target_active else "arsip",
        )
        self.action_succeeded.emit(
            "Status Diperbarui",
            f"Layanan jasa berhasil {status_text}.",
        )
        self.refresh()

    def create_item(self, payload: ItemFormPayload) -> int | None:
        """Menyimpan barang baru melalui repository dan menyegarkan UI.

        Args:
            payload: Data formulir barang baru.

        Returns:
            ID barang baru jika sukses, atau None jika terjadi kesalahan.
        """
        try:
            item_id = self._repository.create_item(payload)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal menambah barang '%s': %s", payload.sku, exc)
            self._notify_error("Gagal Menambah Barang", str(exc))
            return None

        self._selected_item_id = item_id
        logger.info(
            "Database berubah: barang baru ditambahkan (ID=%d, SKU='%s', Nama='%s')",
            item_id,
            payload.sku.strip(),
            payload.name.strip(),
        )
        self.action_succeeded.emit(
            "Barang Ditambahkan",
            f"Barang '{payload.name.strip()}' berhasil disimpan.",
        )
        self.refresh()
        return item_id

    def update_item(self, item_id: int, payload: ItemFormPayload) -> bool:
        """Memperbarui barang yang sudah ada dan menyegarkan UI.

        Args:
            item_id: Primary key barang target.
            payload: Data pembaruan barang.

        Returns:
            True jika pembaruan berhasil, False jika gagal.
        """
        try:
            self._repository.update_item(item_id, payload)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal memperbarui barang ID %d: %s", item_id, exc)
            self._notify_error("Gagal Memperbarui Barang", str(exc))
            return False

        self._selected_item_id = item_id
        logger.info(
            "Database berubah: barang diperbarui (ID=%d, SKU='%s', Nama='%s')",
            item_id,
            payload.sku.strip(),
            payload.name.strip(),
        )
        self.action_succeeded.emit(
            "Barang Diperbarui",
            f"Perubahan pada '{payload.name.strip()}' berhasil disimpan.",
        )
        self.refresh()
        return True

    def create_service(self, payload: ServiceFormPayload) -> int | None:
        """Menyimpan layanan jasa baru melalui repository dan menyegarkan UI.

        Args:
            payload: Data formulir jasa baru.

        Returns:
            ID jasa baru jika sukses, atau None jika gagal.
        """
        try:
            service_id = self._repository.create_service(payload)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal menambah jasa '%s': %s", payload.sku, exc)
            self._notify_error("Gagal Menambah Jasa", str(exc))
            return None

        self._selected_service_id = service_id
        logger.info(
            "Database berubah: jasa baru ditambahkan (ID=%d, SKU='%s', Nama='%s')",
            service_id,
            payload.sku.strip(),
            payload.name.strip(),
        )
        self.action_succeeded.emit(
            "Jasa Ditambahkan",
            f"Layanan '{payload.name.strip()}' berhasil disimpan.",
        )
        self.refresh()
        return service_id

    def update_service(self, service_id: int, payload: ServiceFormPayload) -> bool:
        """Memperbarui layanan jasa yang sudah ada dan menyegarkan UI.

        Args:
            service_id: Primary key jasa target.
            payload: Data pembaruan jasa.

        Returns:
            True jika pembaruan berhasil, False jika gagal.
        """
        try:
            self._repository.update_service(service_id, payload)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal memperbarui jasa ID %d: %s", service_id, exc)
            self._notify_error("Gagal Memperbarui Jasa", str(exc))
            return False

        self._selected_service_id = service_id
        logger.info(
            "Database berubah: jasa diperbarui (ID=%d, SKU='%s', Nama='%s')",
            service_id,
            payload.sku.strip(),
            payload.name.strip(),
        )
        self.action_succeeded.emit(
            "Jasa Diperbarui",
            f"Perubahan pada '{payload.name.strip()}' berhasil disimpan.",
        )
        self.refresh()
        return True

    def record_stock_adjustment(self, payload: StockAdjustmentPayload) -> bool:
        """Mencatat stok awal atau penyesuaian stok opname lalu menyegarkan UI.

        Args:
            payload: Data penyesuaian stok.

        Returns:
            True jika pencatatan berhasil, False jika gagal.
        """
        try:
            self._repository.record_stock_adjustment(payload)
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal mencatat penyesuaian stok: %s", exc)
            self._notify_error("Gagal Menyesuaikan Stok", str(exc))
            return False

        self._selected_item_id = payload.item_id
        logger.info(
            "Database berubah: penyesuaian stok dicatat (item_id=%d, tipe=%s, qty=%s, modal=%s)",
            payload.item_id,
            payload.adjustment_type,
            payload.quantity,
            payload.unit_cost,
        )
        self.action_succeeded.emit(
            "Stok Diperbarui",
            "Penyesuaian stok FIFO berhasil dicatat ke database.",
        )
        self.refresh()
        return True

    def save_category(
        self,
        name: str,
        parent_id: int | None = None,
        is_active: bool = True,
        category_id: int | None = None,
    ) -> int | None:
        """Menyimpan atau memperbarui data master kategori lalu menyegarkan filter.

        Args:
            name: Nama kategori.
            parent_id: ID kategori induk opsional.
            is_active: Status aktif kategori.
            category_id: ID kategori jika mode edit.

        Returns:
            ID kategori tersimpan atau None jika gagal.
        """
        try:
            saved_id = self._repository.save_category(
                name=name,
                parent_id=parent_id,
                is_active=is_active,
                category_id=category_id,
            )
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal menyimpan kategori '%s': %s", name, exc)
            self._notify_error("Gagal Menyimpan Kategori", str(exc))
            return None

        logger.info(
            "Database berubah: kategori %s (ID=%d, Nama='%s', ParentID=%s, Aktif=%s)",
            "diperbarui" if category_id is not None else "ditambahkan",
            saved_id,
            name.strip(),
            parent_id,
            is_active,
        )
        self.action_succeeded.emit(
            "Kategori Tersimpan",
            f"Kategori '{name.strip()}' berhasil disimpan.",
        )
        self.refresh()
        return saved_id

    def save_unit(
        self,
        name: str,
        symbol: str,
        unit_id: int | None = None,
    ) -> int | None:
        """Menyimpan atau memperbarui data master satuan lalu menyegarkan tampilan.

        Args:
            name: Nama lengkap satuan.
            symbol: Simbol satuan.
            unit_id: ID satuan jika mode edit.

        Returns:
            ID satuan tersimpan atau None jika gagal.
        """
        try:
            saved_id = self._repository.save_unit(
                name=name,
                symbol=symbol,
                unit_id=unit_id,
            )
        except (ProductBackendError, FileNotFoundError, sqlite3.Error) as exc:
            logger.warning("Gagal menyimpan satuan '%s': %s", name, exc)
            self._notify_error("Gagal Menyimpan Satuan", str(exc))
            return None

        logger.info(
            "Database berubah: satuan %s (ID=%d, Nama='%s', Simbol='%s')",
            "diperbarui" if unit_id is not None else "ditambahkan",
            saved_id,
            name.strip(),
            symbol.strip(),
        )
        self.action_succeeded.emit(
            "Satuan Tersimpan",
            f"Satuan '{name.strip()} ({symbol.strip()})' berhasil disimpan.",
        )
        self.refresh()
        return saved_id

    def _notify_error(self, title: str, message: str) -> None:
        """Memancarkan sinyal error_occurred dan menampilkan dialog peringatan bila aktif.

        Args:
            title: Judul pesan kesalahan.
            message: Rincian pesan kesalahan.
        """
        self.error_occurred.emit(title, message)
        if self._show_dialogs:
            QMessageBox.warning(self._page, title, message)