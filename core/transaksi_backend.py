"""Modul backend pemrosesan transaksi penjualan POS dan alokasi stok FIFO.

Modul ini menyediakan lapisan akses database (repository) serta controller
PySide6 yang menghubungkan antarmuka DashboardPOS ke database SQLite sesuai
skema transaksi dan inventaris FIFO pada inittransaksidatabase.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget
from util.custominputdialog import CustomInputDialog

if TYPE_CHECKING:
    from ui.dashboard_ui import DashboardPOS
    from util.core.product_completer import ProductSearchCompleter


from config import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Pengecualian dasar untuk seluruh kesalahan pemrosesan transaksi."""


class EmptyCartError(TransactionError):
    """Pengecualian saat proses pembayaran dijalankan dengan keranjang kosong."""


class InsufficientPaymentError(TransactionError):
    """Pengecualian saat nominal pembayaran kurang dari total tagihan."""


class InsufficientStockError(TransactionError):
    """Pengecualian saat stok layer FIFO tidak mencukupi kebutuhan transaksi."""


class ItemNotFoundError(TransactionError):
    """Pengecualian saat produk atau jasa tidak ditemukan pada database."""


@dataclass(frozen=True)
class CatalogProduct:
    """Merepresentasikan satu entri produk barang atau jasa dari katalog database.

    Attributes:
        line_type: Jenis baris transaksi, bernilai 'ITEM' atau 'SERVICE'.
        sku: Kode SKU unik milik barang atau jasa.
        name: Nama tampilan produk atau jasa.
        category_name: Nama kategori produk atau label 'Jasa'.
        selling_price: Harga jual satuan dalam rupiah.
        item_id: ID barang pada tabel items jika line_type adalah 'ITEM'.
        service_id: ID jasa pada tabel services jika line_type adalah 'SERVICE'.
        item_unit_id: ID satuan jual pada tabel item_units untuk barang.
        variant_name: Nama varian satuan jual seperti Pcs, Rim, atau Box.
        conversion_qty: Faktor konversi satuan jual terhadap satuan dasar.
        available_stock: Estimasi sisa stok dalam satuan dasar untuk barang.
    """

    line_type: str
    sku: str
    name: str
    category_name: str
    selling_price: int
    item_id: Optional[int] = None
    service_id: Optional[int] = None
    item_unit_id: Optional[int] = None
    variant_name: str = ""
    conversion_qty: float = 1.0
    available_stock: float = 0.0

    @property
    def display_type(self) -> str:
        """Menghasilkan label tipe singkat untuk ditampilkan pada tabel keranjang.

        Returns:
            String tipe item berupa 'Jasa', 'Paket', atau 'Satuan'.
        """
        if self.line_type == "SERVICE":
            return "Jasa"
        if self.conversion_qty > 1:
            return f"Paket ({self.variant_name})" if self.variant_name else "Paket"
        return self.variant_name if self.variant_name else "Satuan"

    @property
    def display_name(self) -> str:
        """Menghasilkan nama produk lengkap beserta varian satuan bila relevan.

        Returns:
            Nama tampilan produk atau jasa untuk keranjang dan detail nota.
        """
        if self.line_type == "ITEM" and self.variant_name:
            return f"{self.name} ({self.variant_name})"
        return self.name


@dataclass
class CartLineItem:
    """Merepresentasikan satu baris item yang sedang berada di keranjang belanja.

    Attributes:
        line_id: Pengenal sementara unik untuk baris keranjang pada sesi aktif.
        product: Objek CatalogProduct yang dipilih oleh kasir.
        quantity: Jumlah pembelian dalam satuan jual atau satuan jasa.
    """

    line_id: int
    product: CatalogProduct
    quantity: int = 1

    @property
    def subtotal(self) -> int:
        """Menghitung subtotal harga jual untuk baris keranjang ini.

        Returns:
            Nilai subtotal hasil perkalian harga jual dan kuantitas.
        """
        return int(self.product.selling_price * self.quantity)

    @property
    def base_quantity(self) -> Optional[float]:
        """Menghitung kebutuhan kuantitas dalam satuan dasar untuk produk barang.

        Returns:
            Total kuantitas satuan dasar jika bertipe 'ITEM', atau None jika 'SERVICE'.
        """
        if self.product.line_type != "ITEM":
            return None
        return float(self.quantity) * float(self.product.conversion_qty)

    def to_ui_dict(self) -> dict[str, Any]:
        """Mengonversi baris keranjang ke format dictionary milik CartPanel.

        Returns:
            Dictionary dengan kunci id, sku, name, item_type, price, qty, dan subtotal.
        """
        return {
            "id": self.line_id,
            "sku": self.product.sku,
            "name": self.product.display_name,
            "item_type": self.product.display_type,
            "price": self.product.selling_price,
            "qty": self.quantity,
            "subtotal": self.subtotal,
        }


@dataclass(frozen=True)
class TransactionResult:
    """Menyimpan ringkasan hasil transaksi penjualan yang berhasil disimpan.

    Attributes:
        sale_id: Primary key transaksi pada tabel sales.
        invoice_number: Nomor faktur unik yang dihasilkan sistem.
        sale_date: Tanggal dan waktu transaksi dalam format ISO SQLite.
        customer_name: Nama pelanggan atau 'Umum' jika kosong.
        cashier_name: Nama kasir yang memproses transaksi.
        payment_method: Metode pembayaran yang dipilih.
        subtotal: Total kotor seluruh item sebelum penyesuaian.
        discount: Nominal diskon transaksi.
        rounding: Nominal pembulatan transaksi.
        tip: Nominal tip atau bonus kasir.
        total: Total tagihan akhir transaksi.
        amount_paid: Nominal pembayaran yang diterima dari pelanggan.
        change_amount: Nominal kembalian yang diberikan ke pelanggan.
        print_receipt: Status apakah kasir memilih opsi cetak nota.
        items: Daftar salinan dictionary item yang dibeli.
    """

    sale_id: int
    invoice_number: str
    sale_date: str
    customer_name: str
    cashier_name: str
    payment_method: str
    subtotal: int
    discount: int
    rounding: int
    tip: int
    total: int
    amount_paid: int
    change_amount: int
    print_receipt: bool
    items: list[dict[str, Any]]


class TransactionRepository:
    """Mengelola operasi pembacaan katalog dan penyimpanan transaksi FIFO ke SQLite.

    Attributes:
        db_path: Path menuju file database SQLite transaksi.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Menginisialisasi repository dengan lokasi database target.

        Args:
            db_path: Lokasi file database SQLite. Default menggunakan konfigurasi default.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite dengan integritas foreign key dan row factory aktif.

        Returns:
            Objek koneksi sqlite3 siap pakai.

        Raises:
            FileNotFoundError: Jika file database tidak ditemukan di disk.
        """
        if not self.db_path.exists() or not self.db_path.is_file():
            raise FileNotFoundError(
                f"File database tidak ditemukan di: {self.db_path.resolve()}"
            )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _require_lastrowid(self, cursor: sqlite3.Cursor, table_name: str) -> int:
        """Memastikan nilai lastrowid dari cursor INSERT bertipe integer valid.

        Args:
            cursor: Objek cursor SQLite hasil eksekusi perintah INSERT.
            table_name: Nama tabel tujuan untuk konteks pesan kesalahan.

        Returns:
            Nilai primary key baris baru dalam tipe integer.

        Raises:
            TransactionError: Jika SQLite tidak mengembalikan lastrowid.
        """
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise TransactionError(
                f"Gagal mendapatkan ID baris baru dari tabel '{table_name}'."
            )
        return lastrowid

    def search_catalog(
        self,
        query: str,
        category_filter: str = "Semua Produk",
    ) -> list[CatalogProduct]:
        """Mencari produk barang dan jasa aktif berdasarkan SKU, nama, dan filter kategori.

        Args:
            query: Kata kunci pencarian berupa SKU atau sebagian nama produk/jasa.
            category_filter: Filter dropdown seperti 'Semua Produk', 'Produk Satuan',
                'Produk Paket', 'Jasa', atau nama kategori spesifik pada database.

        Returns:
            Daftar objek CatalogProduct yang cocok dengan kriteria pencarian.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        like_pattern = f"%{cleaned_query}%"
        results: list[CatalogProduct] = []

        with self._connect() as conn:
            include_items = category_filter != "Jasa"
            include_services = category_filter in ("Semua Produk", "Jasa", "")

            if include_items:
                results.extend(
                    self._search_items(conn, cleaned_query, like_pattern, category_filter)
                )

            if include_services:
                results.extend(
                    self._search_services(conn, cleaned_query, like_pattern)
                )

        results.sort(
            key=lambda prod: (
                0 if prod.sku.lower() == cleaned_query.lower() else 1,
                prod.name.lower(),
                prod.conversion_qty,
            )
        )
        return results

    def _search_items(
        self,
        conn: sqlite3.Connection,
        exact_query: str,
        like_pattern: str,
        category_filter: str,
    ) -> list[CatalogProduct]:
        """Menjalankan query pencarian pada tabel items dan item_units.

        Args:
            conn: Koneksi aktif database SQLite.
            exact_query: Kata kunci asli untuk pencocokan SKU persis.
            like_pattern: Pola wildcard LIKE untuk pencarian parsial.
            category_filter: Filter kategori atau tipe satuan dari antarmuka.

        Returns:
            Daftar CatalogProduct bertipe 'ITEM'.
        """
        extra_clause = ""
        params: list[Any] = [exact_query, like_pattern, like_pattern, like_pattern]

        if category_filter == "Produk Satuan":
            extra_clause = "AND iu.conversion_qty = 1"
        elif category_filter == "Produk Paket":
            extra_clause = "AND iu.conversion_qty > 1"
        elif category_filter not in ("Semua Produk", ""):
            extra_clause = "AND LOWER(c.name) = LOWER(?)"
            params.append(category_filter)

        sql = f"""
            SELECT
                i.id AS item_id,
                i.sku AS sku,
                i.name AS item_name,
                c.name AS category_name,
                iu.id AS item_unit_id,
                iu.variant_name AS variant_name,
                iu.conversion_qty AS conversion_qty,
                iu.selling_price AS selling_price,
                COALESCE(
                    (
                        SELECT SUM(il.remaining_qty)
                        FROM inventory_layers il
                        WHERE il.item_id = i.id AND il.remaining_qty > 0
                    ),
                    0
                ) AS available_stock
            FROM items i
            INNER JOIN item_units iu ON iu.item_id = i.id
            INNER JOIN categories c ON c.id = i.category_id
            WHERE i.is_active = 1
              AND iu.is_active = 1
              AND (
                  LOWER(i.sku) = LOWER(?)
                  OR LOWER(i.sku) LIKE LOWER(?)
                  OR LOWER(i.name) LIKE LOWER(?)
                  OR LOWER(iu.variant_name) LIKE LOWER(?)
              )
              {extra_clause}
            ORDER BY iu.is_default DESC, i.name ASC, iu.conversion_qty ASC
            LIMIT 50;
        """

        rows = conn.execute(sql, params).fetchall()
        return [
            CatalogProduct(
                line_type="ITEM",
                sku=str(row["sku"]),
                name=str(row["item_name"]),
                category_name=str(row["category_name"]),
                selling_price=int(row["selling_price"]),
                item_id=int(row["item_id"]),
                item_unit_id=int(row["item_unit_id"]),
                variant_name=str(row["variant_name"]),
                conversion_qty=float(row["conversion_qty"]),
                available_stock=float(row["available_stock"]),
            )
            for row in rows
        ]

    def _search_services(
        self,
        conn: sqlite3.Connection,
        exact_query: str,
        like_pattern: str,
    ) -> list[CatalogProduct]:
        """Menjalankan query pencarian pada tabel services.

        Args:
            conn: Koneksi aktif database SQLite.
            exact_query: Kata kunci asli untuk pencocokan SKU persis.
            like_pattern: Pola wildcard LIKE untuk pencarian parsial.

        Returns:
            Daftar CatalogProduct bertipe 'SERVICE'.
        """
        sql = """
            SELECT
                s.id AS service_id,
                s.sku AS sku,
                s.name AS service_name,
                s.selling_price AS selling_price
            FROM services s
            WHERE s.is_active = 1
              AND (
                  LOWER(s.sku) = LOWER(?)
                  OR LOWER(s.sku) LIKE LOWER(?)
                  OR LOWER(s.name) LIKE LOWER(?)
              )
            ORDER BY s.name ASC
            LIMIT 50;
        """
        rows = conn.execute(sql, (exact_query, like_pattern, like_pattern)).fetchall()
        return [
            CatalogProduct(
                line_type="SERVICE",
                sku=str(row["sku"]),
                name=str(row["service_name"]),
                category_name="Jasa",
                selling_price=int(row["selling_price"]),
                service_id=int(row["service_id"]),
                variant_name="Jasa",
                conversion_qty=1.0,
                available_stock=0.0,
            )
            for row in rows
        ]

    def get_available_stock(self, conn: sqlite3.Connection, item_id: int) -> float:
        """Menghitung total sisa stok satuan dasar dari seluruh layer FIFO aktif.

        Args:
            conn: Koneksi aktif database SQLite.
            item_id: ID barang pada tabel items.

        Returns:
            Total kuantitas stok tersedia dalam satuan dasar.
        """
        row = conn.execute(
            """
            SELECT COALESCE(SUM(remaining_qty), 0) AS total_stock
            FROM inventory_layers
            WHERE item_id = ? AND remaining_qty > 0;
            """,
            (item_id,),
        ).fetchone()
        return float(row["total_stock"]) if row else 0.0

    def _resolve_or_create_customer(
        self,
        conn: sqlite3.Connection,
        customer_name: str,
    ) -> Optional[int]:
        """Mencari ID pelanggan berdasarkan nama atau membuat entri pelanggan baru.

        Args:
            conn: Koneksi aktif database SQLite.
            customer_name: Nama pelanggan dari formulir pembayaran.

        Returns:
            ID pelanggan dari tabel customers, atau None jika nama pelanggan kosong.
        """
        cleaned_name = customer_name.strip()
        if not cleaned_name:
            return None

        existing = conn.execute(
            """
            SELECT id
            FROM customers
            WHERE LOWER(name) = LOWER(?)
            ORDER BY id ASC
            LIMIT 1;
            """,
            (cleaned_name,),
        ).fetchone()

        if existing is not None:
            return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO customers (name, is_active)
            VALUES (?, 1);
            """,
            (cleaned_name,),
        )
        return self._require_lastrowid(cursor, "customers")

    def _generate_invoice_number(
        self,
        conn: sqlite3.Connection,
        sale_dt: datetime,
    ) -> str:
        """Membuat nomor faktur penjualan unik dengan format INV-YYYYMMDD-XXXX.

        Args:
            conn: Koneksi aktif database SQLite.
            sale_dt: Timestamp terjadinya transaksi.

        Returns:
            String nomor invoice unik yang belum digunakan pada tabel sales.
        """
        date_prefix = sale_dt.strftime("%Y%m%d")
        prefix = f"INV-{date_prefix}-"
        row = conn.execute(
            """
            SELECT invoice_number
            FROM sales
            WHERE invoice_number LIKE ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (f"{prefix}%",),
        ).fetchone()

        next_sequence = 1
        if row is not None:
            last_invoice = str(row["invoice_number"])
            suffix = last_invoice.replace(prefix, "", 1)
            if suffix.isdigit():
                next_sequence = int(suffix) + 1

        return f"{prefix}{next_sequence:04d}"

    def _build_sale_notes(
        self,
        user_note: str,
    ) -> Optional[str]:
        """Menyusun catatan transaksi murni untuk disimpan pada kolom sales.notes.

        Dengan tersedianya kolom dedicated pada tabel sales (payment_method, amount_paid,
        change_amount, rounding, tip, dan cashier_name), kolom notes kini berfungsi
        secara murni untuk menyimpan catatan atau memo transaksi dari kasir/pelanggan.

        Args:
            user_note: Catatan bebas yang ditulis kasir pada form pembayaran.

        Returns:
            String catatan transaksi yang bersih, atau None jika tidak ada catatan.
        """
        cleaned_note = user_note.strip()
        return cleaned_note if cleaned_note else None

    def _allocate_fifo_stock(
        self,
        conn: sqlite3.Connection,
        item_id: int,
        required_qty: float,
        movement_type: str,
        movement_date: str,
        notes: str,
        sale_detail_id: Optional[int] = None,
        sale_detail_material_id: Optional[int] = None,
    ) -> None:
        """Memotong stok berdasarkan prinsip FIFO dan mencatat pergerakan serta alokasi biaya.

        Args:
            conn: Koneksi aktif database SQLite dalam transaksi berjalan.
            item_id: ID barang yang stoknya akan dikurangi.
            required_qty: Jumlah pengurangan stok dalam satuan dasar.
            movement_type: Jenis pergerakan stok, misalnya 'SALE' atau 'SERVICE_MATERIAL'.
            movement_date: Tanggal dan waktu pergerakan stok.
            notes: Catatan referensi pergerakan stok.
            sale_detail_id: ID referensi sale_details jika pengurangan berasal dari penjualan barang.
            sale_detail_material_id: ID referensi sale_detail_materials jika berasal dari bahan jasa.

        Raises:
            InsufficientStockError: Jika total sisa stok di seluruh layer FIFO tidak mencukupi.
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
            item_row = conn.execute(
                "SELECT sku, name FROM items WHERE id = ?;",
                (item_id,),
            ).fetchone()
            item_label = (
                f"{item_row['name']} ({item_row['sku']})"
                if item_row is not None
                else f"Item ID {item_id}"
            )
            raise InsufficientStockError(
                f"Stok '{item_label}' tidak mencukupi. "
                f"Dibutuhkan: {required_qty:g}, tersedia: {total_available:g}."
            )

        movement_cursor = conn.execute(
            """
            INSERT INTO stock_movements (
                item_id,
                movement_type,
                purchase_detail_id,
                sale_detail_id,
                sale_detail_material_id,
                quantity_in,
                quantity_out,
                movement_date,
                notes
            )
            VALUES (?, ?, NULL, ?, ?, 0, ?, ?, ?);
            """,
            (
                item_id,
                movement_type,
                sale_detail_id,
                sale_detail_material_id,
                required_qty,
                movement_date,
                notes,
            ),
        )
        stock_movement_id = self._require_lastrowid(movement_cursor, "stock_movements")

        remaining_to_issue = required_qty
        for layer in layers:
            if remaining_to_issue <= 1e-9:
                break

            layer_id = int(layer["id"])
            layer_available = float(layer["remaining_qty"])
            layer_unit_cost = float(layer["unit_cost"])

            take_qty = min(layer_available, remaining_to_issue)
            new_remaining = max(0.0, layer_available - take_qty)
            subtotal_cost = take_qty * layer_unit_cost

            conn.execute(
                """
                UPDATE inventory_layers
                SET remaining_qty = ?
                WHERE id = ?;
                """,
                (new_remaining, layer_id),
            )

            conn.execute(
                """
                INSERT INTO stock_issue_allocations (
                    stock_movement_id,
                    inventory_layer_id,
                    quantity,
                    unit_cost,
                    subtotal_cost
                )
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    stock_movement_id,
                    layer_id,
                    take_qty,
                    layer_unit_cost,
                    subtotal_cost,
                ),
            )

            remaining_to_issue -= take_qty

    def process_sale(
        self,
        cart_items: list[CartLineItem],
        discount: int,
        rounding: int,
        tip: int,
        payment_method: str,
        amount_paid: int,
        customer_name: str,
        cashier_name: str,
        note: str,
        print_receipt: bool,
    ) -> TransactionResult:
        """Memvalidasi dan menyimpan satu transaksi penjualan lengkap secara atomik.

        Alur penyimpanan mencakup insert header sales, insert sale_details,
        ekspansi bahan baku jasa ke sale_detail_materials, pencatatan
        stock_movements, serta pemotongan layer FIFO dan stock_issue_allocations.

        Args:
            cart_items: Daftar objek CartLineItem yang akan dibayar.
            discount: Nominal diskon potongan harga.
            rounding: Nominal pembulatan tagihan.
            tip: Nominal tip atau bonus.
            payment_method: Metode pembayaran yang digunakan.
            amount_paid: Nominal uang yang dibayarkan pelanggan.
            customer_name: Nama pelanggan, boleh kosong untuk pelanggan umum.
            cashier_name: Nama kasir yang bertugas.
            note: Catatan transaksi tambahan dari kasir.
            print_receipt: Penanda apakah nota perlu dicetak.

        Returns:
            Objek TransactionResult berisi detail faktur yang tersimpan.

        Raises:
            EmptyCartError: Jika keranjang belanja kosong.
            InsufficientPaymentError: Jika nominal bayar lebih kecil dari total tagihan.
            InsufficientStockError: Jika stok barang atau bahan baku jasa tidak cukup.
            sqlite3.Error: Jika terjadi kegagalan pada tingkat database SQLite.
        """
        if not cart_items:
            raise EmptyCartError("Keranjang belanja masih kosong.")

        subtotal = sum(line.subtotal for line in cart_items)
        safe_discount = max(0, int(discount))
        total = max(0, subtotal - safe_discount + int(rounding) + int(tip))

        if amount_paid < total:
            raise InsufficientPaymentError(
                f"Nominal pembayaran (Rp {amount_paid:,}) kurang dari "
                f"total tagihan (Rp {total:,}).".replace(",", ".")
            )

        change_amount = amount_paid - total
        sale_dt = datetime.now()
        sale_date_str = sale_dt.strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as conn:
            invoice_number = self._generate_invoice_number(conn, sale_dt)
            customer_id = self._resolve_or_create_customer(conn, customer_name)
            sale_notes = self._build_sale_notes(
                user_note=note,
            )

            sale_cursor = conn.execute(
                """
                INSERT INTO sales (
                    invoice_number,
                    customer_id,
                    sale_date,
                    subtotal,
                    discount,
                    rounding,
                    tip,
                    total,
                    payment_method,
                    amount_paid,
                    change_amount,
                    cashier_name,
                    status,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?);
                """,
                (
                    invoice_number,
                    customer_id,
                    sale_date_str,
                    subtotal,
                    safe_discount,
                    int(rounding),
                    int(tip),
                    total,
                    payment_method,
                    amount_paid,
                    change_amount,
                    cashier_name,
                    sale_notes,
                ),
            )
            sale_id = self._require_lastrowid(sale_cursor, "sales")

            for line in cart_items:
                product = line.product
                if product.line_type == "ITEM":
                    item_id = product.item_id
                    item_unit_id = product.item_unit_id
                    if item_id is None or item_unit_id is None:
                        raise TransactionError(
                            f"Produk '{product.display_name}' tidak memiliki ID barang atau satuan yang valid."
                        )

                    base_qty = line.base_quantity or float(line.quantity)
                    detail_cursor = conn.execute(
                        """
                        INSERT INTO sale_details (
                            sale_id,
                            line_type,
                            item_id,
                            service_id,
                            item_unit_id,
                            description,
                            quantity,
                            conversion_qty,
                            base_quantity,
                            unit_price,
                            subtotal
                        )
                        VALUES (?, 'ITEM', ?, NULL, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            sale_id,
                            item_id,
                            item_unit_id,
                            product.display_name,
                            float(line.quantity),
                            float(product.conversion_qty),
                            base_qty,
                            int(product.selling_price),
                            int(line.subtotal),
                        ),
                    )
                    sale_detail_id = self._require_lastrowid(detail_cursor, "sale_details")

                    self._allocate_fifo_stock(
                        conn=conn,
                        item_id=item_id,
                        required_qty=base_qty,
                        movement_type="SALE",
                        movement_date=sale_date_str,
                        notes=f"Penjualan {invoice_number} - {product.display_name}",
                        sale_detail_id=sale_detail_id,
                    )
                else:
                    detail_cursor = conn.execute(
                        """
                        INSERT INTO sale_details (
                            sale_id,
                            line_type,
                            item_id,
                            service_id,
                            item_unit_id,
                            description,
                            quantity,
                            conversion_qty,
                            base_quantity,
                            unit_price,
                            subtotal
                        )
                        VALUES (?, 'SERVICE', NULL, ?, NULL, ?, ?, NULL, NULL, ?, ?);
                        """,
                        (
                            sale_id,
                            product.service_id,
                            product.display_name,
                            float(line.quantity),
                            int(product.selling_price),
                            int(line.subtotal),
                        ),
                    )
                    sale_detail_id = self._require_lastrowid(detail_cursor, "sale_details")

                    materials = conn.execute(
                        """
                        SELECT item_id, quantity
                        FROM service_materials
                        WHERE service_id = ?;
                        """,
                        (product.service_id,),
                    ).fetchall()

                    for mat in materials:
                        mat_item_id = int(mat["item_id"])
                        qty_per_service = float(mat["quantity"])
                        service_qty = float(line.quantity)
                        total_mat_qty = qty_per_service * service_qty

                        mat_cursor = conn.execute(
                            """
                            INSERT INTO sale_detail_materials (
                                sale_detail_id,
                                item_id,
                                quantity_per_service,
                                service_quantity,
                                total_quantity
                            )
                            VALUES (?, ?, ?, ?, ?);
                            """,
                            (
                                sale_detail_id,
                                mat_item_id,
                                qty_per_service,
                                service_qty,
                                total_mat_qty,
                            ),
                        )
                        sale_detail_material_id = self._require_lastrowid(
                            mat_cursor,
                            "sale_detail_materials",
                        )

                        self._allocate_fifo_stock(
                            conn=conn,
                            item_id=mat_item_id,
                            required_qty=total_mat_qty,
                            movement_type="SERVICE_MATERIAL",
                            movement_date=sale_date_str,
                            notes=f"Bahan Jasa {invoice_number} - {product.display_name}",
                            sale_detail_material_id=sale_detail_material_id,
                        )

            conn.commit()

        logger.info(
            "Transaksi %s berhasil disimpan dengan total Rp %s",
            invoice_number,
            f"{total:,}",
        )

        return TransactionResult(
            sale_id=sale_id,
            invoice_number=invoice_number,
            sale_date=sale_date_str,
            customer_name=customer_name.strip() or "Umum",
            cashier_name=cashier_name,
            payment_method=payment_method,
            subtotal=subtotal,
            discount=safe_discount,
            rounding=int(rounding),
            tip=int(tip),
            total=total,
            amount_paid=amount_paid,
            change_amount=change_amount,
            print_receipt=print_receipt,
            items=[line.to_ui_dict() for line in cart_items],
        )


def auto_fill_digital_payment_amount(
    dashboard: Any,
    method: Optional[str] = None,
    total: Optional[int] = None,
) -> bool:
    """Secara otomatis mengisi nominal pembayaran pada form dashboard jika metode adalah QRIS atau Transfer.

    Memeriksa nilai metode pembayaran. Apabila metode adalah 'QRIS' atau 'Transfer'
    (tidak sensitif huruf besar/kecil), kolom nominal pembayaran (amount_input)
    akan diisi dengan nilai total tagihan transaksi.

    Args:
        dashboard: Instance antarmuka DashboardPOS atau objek yang memiliki payment_panel.
        method: Nama metode pembayaran opsional. Jika None, membaca dari method_combo pada payment_panel.
        total: Nominal total tagihan opsional. Jika None, membaca dari ringkasan atau bernilai 0.

    Returns:
        bool: True jika metode adalah QRIS/Transfer dan form berhasil diisi, False jika sebaliknya.
    """
    if dashboard is None:
        return False

    if method is None:
        if hasattr(dashboard, "payment_panel") and hasattr(
            dashboard.payment_panel, "method_combo"
        ):
            method = dashboard.payment_panel.method_combo.currentText()
        else:
            return False

    if not isinstance(method, str):
        return False

    method_normalized = method.strip().lower()
    if method_normalized in ("qris", "transfer"):
        if total is None:
            total = 0
            if hasattr(dashboard, "summary_panel") and hasattr(
                dashboard.summary_panel, "total_val"
            ):
                raw_text = dashboard.summary_panel.total_val.text()
                digits = "".join(filter(str.isdigit, raw_text))
                total = int(digits) if digits else 0

        amount_str = str(total)
        if hasattr(dashboard, "set_payment_amount"):
            dashboard.set_payment_amount(amount_str)
        elif hasattr(dashboard, "payment_panel") and hasattr(
            dashboard.payment_panel, "amount_input"
        ):
            dashboard.payment_panel.amount_input.setText(amount_str)
        return True

    return False


def calculate_auto_rounding(base_total: int) -> int:
    """Menghitung nilai penyesuaian pembulatan otomatis ke kelipatan 500 terdekat.

    Logika pembulatan:
        - Jika sisa total tagihan terhadap kelipatan 500 lebih dari 250:
          dibulatkan ke atas menjadi 500 (penyesuaian bernilai positif).
        - Jika sisa total tagihan terhadap kelipatan 500 kurang dari atau sama dengan 250:
          dibulatkan ke bawah menjadi 0 (penyesuaian bernilai negatif atau nol).

    Contoh:
        - Total 2300 -> sisa 300 (> 250) -> rounding +200 -> total menjadi 2500.
        - Total 2250 -> sisa 250 (<= 250) -> rounding -250 -> total menjadi 2000.

    Args:
        base_total: Nominal total tagihan sebelum pembulatan (subtotal - diskon + tip).

    Returns:
        int: Nilai pembulatan yang ditambahkan ke total (positif, negatif, atau 0).
    """
    if base_total <= 0:
        return 0

    remainder = base_total % 500
    if remainder == 0:
        return 0
    elif remainder > 250:
        return 500 - remainder
    else:
        return -remainder


class TransactionController(QObject):
    """Controller yang menghubungkan seluruh event DashboardPOS ke backend database.

    Signals:
        transaction_completed: Dipancarkan membawa objek TransactionResult setelah
            transaksi berhasil disimpan ke database.
        transaction_failed: Dipancarkan membawa pesan kesalahan saat transaksi gagal.
    """

    transaction_completed = Signal(object)
    transaction_failed = Signal(str)

    def __init__(
        self,
        dashboard: DashboardPOS,
        db_path: Optional[str | Path] = None,
        cashier_name: str = "KASIR",
        parent: Optional[QObject] = None,
    ) -> None:
        """Menginisialisasi controller, repository database, dan koneksi sinyal UI.

        Args:
            dashboard: Instance DashboardPOS yang akan dikendalikan.
            db_path: Lokasi file database SQLite transaksi. Default konfigurasi sistem.
            cashier_name: Nama kasir aktif untuk pencatatan transaksi.
            parent: Objek QObject induk opsional.
        """
        super().__init__(parent or dashboard)
        self.dashboard = dashboard
        self.repository = TransactionRepository(db_path=db_path)
        self.cashier_name = cashier_name

        self._cart_items: list[CartLineItem] = []
        self._next_line_id: int = 1
        self._discount: int = 0
        self._rounding: int = 0
        self._tip: int = 0

        self._connect_dashboard_signals()
        from util.core.product_completer import ProductSearchCompleter

        self._search_completer = ProductSearchCompleter(
            search_input=self.dashboard.search_panel.search_input,
            category_combo=self.dashboard.search_panel.category_combo,
            repository=self.repository,
            max_items=10,
            parent=self,
        )
        self._search_completer.product_selected.connect(
            self._handle_autocomplete_selected
        )
        self._refresh_ui_state()

    def set_cashier_name(self, cashier_name: str) -> None:
        """Memperbarui nama kasir yang tercatat pada transaksi berikutnya.

        Args:
            cashier_name: Nama kasir baru yang sedang bertugas.
        """
        self.cashier_name = cashier_name

    def _connect_dashboard_signals(self) -> None:
        """Menghubungkan seluruh sinyal publik DashboardPOS ke slot controller."""
        self.dashboard.search_requested.connect(self._handle_search_and_add)
        self.dashboard.add_to_cart_requested.connect(self._handle_add_button_clicked)
        self.dashboard.clear_cart_requested.connect(self._handle_clear_cart)
        self.dashboard.item_removed.connect(self._handle_remove_item)
        self.dashboard.item_quantity_changed.connect(self._handle_quantity_changed)
        self.dashboard.discount_requested.connect(self._handle_discount_clicked)
        self.dashboard.rounding_requested.connect(self._handle_rounding_clicked)
        self.dashboard.tip_requested.connect(self._handle_tip_clicked)
        self.dashboard.payment_amount_changed.connect(self._handle_payment_amount_changed)
        if hasattr(self.dashboard, "payment_method_changed"):
            self.dashboard.payment_method_changed.connect(self._handle_payment_method_changed)
        elif hasattr(self.dashboard, "payment_panel") and hasattr(
            self.dashboard.payment_panel, "method_changed"
        ):
            self.dashboard.payment_panel.method_changed.connect(self._handle_payment_method_changed)
        self.dashboard.checkout_requested.connect(self._handle_checkout)

    def _handle_autocomplete_selected(self, product: CatalogProduct) -> None:
        """Menambahkan produk terpilih dari dropdown autocomplete langsung ke keranjang."""
        self._add_product_to_cart(product)
        QTimer.singleShot(0, self.dashboard.search_panel.clear_search)
        QTimer.singleShot(
            0,
            lambda: self.dashboard.search_panel.set_helper_text(
                f"Ditambahkan: {product.display_name} "
                f"(Rp {product.selling_price:,})".replace(",", "."),
                is_error=False,
            ),
        )

    def _calculate_subtotal(self) -> int:
        """Menghitung total harga kotor seluruh item di dalam keranjang.

        Returns:
            Jumlah subtotal dalam rupiah.
        """
        return sum(line.subtotal for line in self._cart_items)

    def _calculate_total(self) -> int:
        """Menghitung total tagihan akhir setelah diskon, pembulatan, dan tip.

        Returns:
            Total tagihan akhir bernilai minimal nol.
        """
        subtotal = self._calculate_subtotal()
        return max(0, subtotal - self._discount + self._rounding + self._tip)

    def _refresh_ui_state(self) -> None:
        """Menyelaraskan tampilan keranjang, ringkasan nominal, kembalian, dan tombol Bayar."""
        ui_items = [line.to_ui_dict() for line in self._cart_items]
        self.dashboard.set_cart_items(ui_items)

        subtotal = self._calculate_subtotal()
        if self._discount > subtotal:
            self._discount = subtotal

        total = self._calculate_total()
        self.dashboard.update_summary(
            subtotal=subtotal,
            diskon=self._discount,
            pembulatan=self._rounding,
            tip=self._tip,
            total=total,
        )

        self._update_change_display()
        self.dashboard.action_panel.set_pay_enabled(len(self._cart_items) > 0)
        self.auto_fill_payment_amount()

    def _update_change_display(self) -> None:
        """Menghitung ulang dan memperbarui nominal kembalian pada panel pembayaran."""
        payment_data = self.dashboard.get_payment_data()
        amount_paid = int(payment_data.get("amount_paid", 0))
        total = self._calculate_total()
        change = max(0, amount_paid - total)
        self.dashboard.set_change_amount(change)

    def _handle_add_button_clicked(self) -> None:
        """Memproses klik tombol Tambah ke Keranjang berdasarkan input pencarian saat ini."""
        query = self.dashboard.search_panel.get_search_query()
        category = self.dashboard.search_panel.get_selected_category()
        self._handle_search_and_add(query, category)

    def _handle_search_and_add(self, query: str, category: str) -> None:
        """Mencari produk pada database lalu menambahkannya ke keranjang belanja.

        Args:
            query: Teks SKU atau nama produk dari panel pencarian.
            category: Kategori yang dipilih pada dropdown pencarian.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            self.dashboard.search_panel.set_helper_text(
                "Masukkan SKU atau nama produk terlebih dahulu.",
                is_error=True,
            )
            return

        try:
            matches = self.repository.search_catalog(cleaned_query, category)
        except Exception as exc:
            logger.exception("Gagal mencari produk di database")
            self.dashboard.search_panel.set_helper_text(
                f"Gagal membaca database: {exc}",
                is_error=True,
            )
            return

        if not matches:
            self.dashboard.search_panel.set_helper_text(
                f"Produk '{cleaned_query}' tidak ditemukan pada kategori '{category}'.",
                is_error=True,
            )
            return

        selected_product = self._select_product_from_matches(matches, cleaned_query)
        if selected_product is None:
            return

        self._add_product_to_cart(selected_product)
        self.dashboard.search_panel.clear_search()
        self.dashboard.search_panel.set_helper_text(
            f"Ditambahkan: {selected_product.display_name} "
            f"(Rp {selected_product.selling_price:,})".replace(",", "."),
            is_error=False,
        )

    def _select_product_from_matches(
        self,
        matches: list[CatalogProduct],
        query: str,
    ) -> Optional[CatalogProduct]:
        """Menentukan produk terpilih jika hasil pencarian lebih dari satu entri.

        Args:
            matches: Daftar produk hasil pencarian dari database.
            query: Kata kunci pencarian asli.

        Returns:
            Objek CatalogProduct yang dipilih, atau None jika kasir membatalkan dialog.
        """
        if len(matches) == 1:
            return matches[0]

        exact_sku_matches = [
            prod for prod in matches if prod.sku.lower() == query.lower()
        ]
        if len(exact_sku_matches) == 1:
            return exact_sku_matches[0]

        options = [
            (
                f"[{prod.sku}] {prod.display_name} - "
                f"Rp {prod.selling_price:,}".replace(",", ".")
                + (
                    f" (Stok: {prod.available_stock:g})"
                    if prod.line_type == "ITEM"
                    else " (Jasa)"
                )
            )
            for prod in matches
        ]

        chosen_text, accepted = CustomInputDialog.getItem(
            self._get_dialog_parent(),
            "Pilih Produk / Jasa",
            "Ditemukan beberapa hasil yang cocok:",
            options,
            0,
            False,
        )
        if not accepted:
            return None

        chosen_index = options.index(chosen_text)
        return matches[chosen_index]

    def _add_product_to_cart(self, product: CatalogProduct) -> None:
        """Menambahkan produk baru ke keranjang atau menaikkan kuantitas jika sudah ada.

        Args:
            product: Objek CatalogProduct yang akan dimasukkan ke keranjang.
        """
        for line in self._cart_items:
            same_item = (
                line.product.line_type == "ITEM"
                and product.line_type == "ITEM"
                and line.product.item_id == product.item_id
                and line.product.item_unit_id == product.item_unit_id
            )
            same_service = (
                line.product.line_type == "SERVICE"
                and product.line_type == "SERVICE"
                and line.product.service_id == product.service_id
            )
            if same_item or same_service:
                line.quantity += 1
                self._refresh_ui_state()
                return

        new_line = CartLineItem(
            line_id=self._next_line_id,
            product=product,
            quantity=1,
        )
        self._next_line_id += 1
        self._cart_items.append(new_line)
        self._refresh_ui_state()

    def _handle_remove_item(self, line_id: int) -> None:
        """Menghapus satu baris item dari keranjang berdasarkan ID baris.

        Args:
            line_id: Pengenal baris item yang dikirim oleh sinyal item_removed.
        """
        self._cart_items = [
            line for line in self._cart_items if line.line_id != line_id
        ]
        self._refresh_ui_state()

    def _handle_quantity_changed(self, line_id: int, new_qty: int) -> None:
        """Memperbarui kuantitas item di keranjang jika sinyal perubahan qty dipancarkan.

        Args:
            line_id: Pengenal baris item pada keranjang.
            new_qty: Kuantitas baru; jika kurang dari atau sama dengan nol, item dihapus.
        """
        if new_qty <= 0:
            self._handle_remove_item(line_id)
            return

        for line in self._cart_items:
            if line.line_id == line_id:
                line.quantity = int(new_qty)
                break
        self._refresh_ui_state()

    def _handle_clear_cart(self) -> None:
        """Mengosongkan seluruh isi keranjang beserta nilai penyesuaian transaksi."""
        self._cart_items.clear()
        self._discount = 0
        self._rounding = 0
        self._tip = 0
        self.dashboard.clear_transaction()
        self._refresh_ui_state()

    def _get_dialog_parent(self) -> QWidget:
        """Mengembalikan widget induk yang aman untuk modal dialog."""
        try:
            return self.dashboard.window() or self.dashboard
        except Exception:
            return self.dashboard

    def _handle_discount_clicked(self) -> None:
        """Membuka dialog input nominal diskon dan menerapkannya pada ringkasan transaksi."""
        subtotal = self._calculate_subtotal()
        if subtotal <= 0:
            QMessageBox.information(
                self._get_dialog_parent(),
                "Diskon",
                "Tambahkan produk ke keranjang terlebih dahulu.",
            )
            return

        value, accepted = CustomInputDialog.getInt(
            self._get_dialog_parent(),
            "Input Diskon",
            "Masukkan nominal diskon (Rp):",
            self._discount,
            0,
            subtotal,
            500,
        )
        if accepted:
            self._discount = value
            self._refresh_ui_state()

    def _handle_rounding_clicked(self) -> None:
        """Menerapkan pembulatan otomatis ke kelipatan 500 terdekat atau membatalkannya jika sudah aktif.

        Logika:
            - Jika sisa total tagihan terhadap kelipatan 500 > 250: rounding ke atas menjadi 500.
            - Jika sisa total tagihan terhadap kelipatan 500 <= 250: rounding ke bawah menjadi 0.
            Contoh:
                - Total tagihan 2300 -> sisa 300 (> 250) -> rounding +200 -> total menjadi 2500.
                - Total tagihan 2250 -> sisa 250 (<= 250) -> rounding -250 -> total menjadi 2000.
            Jika tombol ditekan kembali saat pembulatan otomatis sudah aktif, pembulatan di-reset ke 0.
        """
        subtotal = self._calculate_subtotal()
        if subtotal <= 0:
            QMessageBox.information(
                self._get_dialog_parent(),
                "Pembulatan",
                "Tambahkan produk ke keranjang terlebih dahulu.",
            )
            return

        base_total = max(0, subtotal - self._discount + self._tip)
        auto_val = calculate_auto_rounding(base_total)

        if self._rounding != 0 and self._rounding == auto_val:
            self._rounding = 0
        else:
            self._rounding = auto_val

        self._refresh_ui_state()

    calculate_auto_rounding = staticmethod(calculate_auto_rounding)

    def _handle_tip_clicked(self) -> None:
        """Membuka dialog input nominal tip atau bonus kasir."""
        value, accepted = CustomInputDialog.getInt(
            self._get_dialog_parent(),
            "Input Tip / Bonus",
            "Masukkan nominal tip atau bonus (Rp):",
            self._tip,
            0,
            10000000,
            1000,
        )
        if accepted:
            self._tip = value
            self._refresh_ui_state()

    def _handle_payment_amount_changed(self, _raw_text: str) -> None:
        """Memperbarui tampilan kembalian setiap kali kasir mengetik nominal bayar.

        Args:
            _raw_text: Teks mentah dari kolom input nominal pembayaran.
        """
        self._update_change_display()

    def auto_fill_payment_amount(self, method: Optional[str] = None) -> bool:
        """Secara otomatis mengisi nominal pembayaran jika metode adalah QRIS atau Transfer.

        Jika metode pembayaran yang aktif adalah QRIS atau Transfer, kolom nominal bayar
        (amount_input) pada panel pembayaran dashboard akan diisi sebesar total tagihan transaksi.

        Args:
            method: Nama metode pembayaran opsional. Jika None, membaca metode terpilih dari dashboard.

        Returns:
            bool: True jika metode adalah QRIS atau Transfer dan pengisian berhasil, False sebaliknya.
        """
        total = self._calculate_total()
        return auto_fill_digital_payment_amount(self.dashboard, method=method, total=total)

    def _handle_payment_method_changed(self, method: str) -> None:
        """Menangani pergantian metode pembayaran dari antarmuka pengguna.

        Secara otomatis mengisi nominal pembayaran jika metode yang dipilih adalah QRIS atau Transfer.

        Args:
            method: Nama metode pembayaran yang baru dipilih kasir.
        """
        self.auto_fill_payment_amount(method)

    def _handle_checkout(self) -> None:
        """Mengeksekusi penyimpanan transaksi dari DashboardPOS ke database SQLite."""
        payment_data = self.dashboard.get_payment_data()

        try:
            result = self.repository.process_sale(
                cart_items=self._cart_items,
                discount=self._discount,
                rounding=self._rounding,
                tip=self._tip,
                payment_method=str(payment_data["payment_method"]),
                amount_paid=int(payment_data["amount_paid"]),
                customer_name=str(payment_data["customer_name"]),
                cashier_name=self.cashier_name,
                note=str(payment_data["note"]),
                print_receipt=bool(payment_data["print_receipt"]),
            )
        except TransactionError as exc:
            logger.warning("Validasi transaksi ditolak: %s", exc)
            QMessageBox.warning(self._get_dialog_parent(), "Transaksi Gagal", str(exc))
            self.transaction_failed.emit(str(exc))
            return
        except Exception as exc:
            logger.exception("Terjadi kesalahan saat menyimpan transaksi")
            error_msg = f"Terjadi kesalahan sistem saat menyimpan transaksi:\n{exc}"
            QMessageBox.critical(self._get_dialog_parent(), "Kesalahan Database", error_msg)
            self.transaction_failed.emit(error_msg)
            return

        self._handle_clear_cart()
        self.transaction_completed.emit(result)