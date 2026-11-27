"""Modul backend dan controller untuk halaman Tambah Stok dan Kulakan FIFO.

Modul ini memisahkan lapisan layanan basis data SQLite (transaksi atomik FIFO,
pencatatan kulakan, draft, dan pelunasan hutang supplier) dari lapisan
controller PySide6 yang menghubungkan sinyal TambahStokPage ke operasi backend
serta dialog pendukung.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import csv
from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from typing import Any, TypedDict

from PySide6.QtCore import QDate, QDateTime, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import DEFAULT_DB_PATH
from ui.tambahstok import (
    CatalogItemData,
    CurrencySpinBox,
    HistoryFilterPayload,
    ItemUnitOption,
    PurchaseHistoryRow,
    PurchaseLinePayload,
    PurchasePayload,
    SupplierOption,
    TambahStokPage,
)
from util.helper.db_connection import create_sqlite_connection
from util.helper.formatrupiah import (
    format_qty as format_quantity,
    format_rupiah,
)

logger = logging.getLogger(__name__)


class PurchaseSaveResult(TypedDict):
    """Struktur hasil penyimpanan transaksi pembelian ke basis data.

    Attributes:
        purchase_id: ID unik nota pembelian yang baru tersimpan atau diperbarui.
        invoice_number: Nomor faktur pembelian.
        status: Status akhir dokumen berupa COMPLETED atau DRAFT.
        total: Total akhir nota pembelian.
        amount_paid: Nominal terbayar setelah sinkronisasi trigger.
        remaining_amount: Sisa hutang setelah sinkronisasi trigger.
        payment_status: Status pembayaran PAID, PARTIAL, atau UNPAID.
        layers_created: Jumlah lapisan stok FIFO baru pada inventory_layers.
    """

    purchase_id: int
    invoice_number: str
    status: str
    total: int
    amount_paid: int
    remaining_amount: int
    payment_status: str
    layers_created: int


class PaymentRecordResult(TypedDict):
    """Struktur hasil pencatatan pembayaran cicilan atau pelunasan hutang supplier.

    Attributes:
        payment_id: ID unik entri baru pada tabel purchase_payments.
        purchase_id: ID nota pembelian yang dibayarkan.
        invoice_number: Nomor faktur nota terkait.
        paid_this_time: Nominal yang dibayarkan pada transaksi ini.
        amount_paid: Akumulasi total pembayaran nota saat ini.
        remaining_amount: Sisa hutang nota setelah pembayaran ini.
        payment_status: Status pembayaran terbaru PAID, PARTIAL, atau UNPAID.
    """

    payment_id: int
    purchase_id: int
    invoice_number: str
    paid_this_time: int
    amount_paid: int
    remaining_amount: int
    payment_status: str


class PurchaseDetailLineView(TypedDict):
    """Struktur data tampilan satu baris rincian barang pada dialog detail nota.

    Attributes:
        sku: Kode SKU barang.
        item_name: Nama barang.
        variant_name: Nama varian satuan beli.
        base_unit_symbol: Simbol satuan dasar barang.
        quantity: Jumlah beli dalam satuan varian.
        conversion_qty: Faktor konversi ke satuan dasar.
        base_quantity: Jumlah stok masuk dalam satuan dasar.
        unit_cost: Harga beli per satuan varian.
        subtotal: Subtotal biaya baris.
    """

    sku: str
    item_name: str
    variant_name: str
    base_unit_symbol: str
    quantity: float
    conversion_qty: float
    base_quantity: float
    unit_cost: float
    subtotal: float


class PurchasePaymentHistoryView(TypedDict):
    """Struktur data tampilan satu baris riwayat cicilan pembayaran pembelian.

    Attributes:
        id: ID unik pembayaran pada tabel purchase_payments.
        payment_date: Tanggal dan waktu pembayaran dilakukan.
        amount: Nominal pembayaran.
        payment_method: Metode pembayaran yang digunakan.
        reference_number: Nomor bukti transfer atau referensi opsional.
        notes: Catatan pembayaran opsional.
    """

    id: int
    payment_date: str
    amount: int
    payment_method: str
    reference_number: str
    notes: str


class PurchaseDetailBundle(TypedDict):
    """Struktur paket data lengkap satu nota pembelian beserta detail dan cicilan.

    Attributes:
        id: ID nota pembelian.
        invoice_number: Nomor faktur pembelian.
        supplier_id: ID supplier atau None.
        supplier_name: Nama supplier atau label Belanja Umum.
        purchase_date: Tanggal transaksi pembelian.
        subtotal: Subtotal sebelum diskon.
        discount: Nilai diskon tingkat nota.
        total: Total akhir pembelian.
        payment_method: Metode pembayaran utama.
        amount_paid: Total yang sudah dibayarkan.
        remaining_amount: Sisa hutang yang belum dilunasi.
        payment_status: Status pembayaran PAID, PARTIAL, atau UNPAID.
        due_date: Tanggal jatuh tempo atau None.
        status: Status dokumen COMPLETED atau DRAFT.
        notes: Catatan nota pembelian.
        lines: Daftar rincian item yang dibeli.
        payments: Daftar riwayat pembayaran cicilan atau pelunasan.
    """

    id: int
    invoice_number: str
    supplier_id: int | None
    supplier_name: str
    purchase_date: str
    subtotal: int
    discount: int
    total: int
    payment_method: str
    amount_paid: int
    remaining_amount: int
    payment_status: str
    due_date: str | None
    status: str
    notes: str
    lines: list[PurchaseDetailLineView]
    payments: list[PurchasePaymentHistoryView]


class BulkCatalogItemView(TypedDict):
    """Struktur data barang dengan nama kategori untuk dialog Pilih Banyak Barang.

    Attributes:
        catalog_item: Objek CatalogItemData lengkap siap masuk keranjang.
        category_name: Nama kategori barang untuk pemfilteran.
    """

    catalog_item: CatalogItemData
    category_name: str


class CsvImportSummary(TypedDict):
    """Struktur hasil pembacaan file CSV kulakan untuk dimasukkan ke keranjang.

    Attributes:
        matched_rows: Daftar pasangan item katalog, qty, unit_id opsional, dan unit_cost opsional.
        skipped_reasons: Daftar pesan singkat baris yang gagal dicocokkan.
    """

    matched_rows: list[tuple[CatalogItemData, float, int | None, float | None]]
    skipped_reasons: list[str]


DIALOG_STYLESHEET: str = """
QDialog {
    background-color: #161622;
    color: #CDD6F4;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#dialogCard {
    background-color: #1E1E2E;
    border: 1px solid #313244;
    border-radius: 10px;
}
QLabel#dialogTitle {
    color: #CDD6F4;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}
QLabel#dialogSubtitle {
    color: #A6ADC8;
    font-size: 12px;
    background: transparent;
}
QLabel#fieldLabel {
    color: #A6ADC8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#errorLabel {
    color: #F38BA8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLineEdit, QComboBox, QDateTimeEdit, QSpinBox {
    background-color: #11111B;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QSpinBox:focus {
    border: 1px solid #89B4FA;
}
QComboBox QAbstractItemView {
    background-color: #1E1E2E;
    color: #CDD6F4;
    border: 1px solid #45475A;
    selection-background-color: #313244;
    selection-color: #89B4FA;
}
QCheckBox {
    color: #CDD6F4;
    font-size: 12px;
    spacing: 6px;
}
QTableWidget {
    background-color: #11111B;
    alternate-background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 8px;
    outline: none;
    selection-background-color: #25283D;
    selection-color: #CDD6F4;
}
QTableWidget::item {
    border-bottom: 1px solid #242538;
    padding: 4px 6px;
}
QTableWidget QHeaderView::section {
    background-color: #1E1E2E;
    color: #A6ADC8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 7px 8px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#primaryBtn {
    background-color: #A6E3A1;
    color: #11111B;
    border: none;
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#primaryBtn:hover {
    background-color: #B8EBB3;
}
QPushButton#accentBtn {
    background-color: #89B4FA;
    color: #11111B;
    border: none;
    border-radius: 7px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#accentBtn:hover {
    background-color: #A0C4FF;
}
QPushButton#secondaryBtn {
    background-color: #2A2A40;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 7px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#secondaryBtn:hover {
    background-color: #34344E;
}
"""


class TambahStokService:
    """Layanan basis data atomik untuk transaksi kulakan FIFO dan hutang supplier.

    Attributes:
        db_path: Path menuju file database SQLite aplikasi POS.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Menginisialisasi TambahStokService dengan path database target.

        Args:
            db_path: Path file database SQLite. Default menggunakan DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else Path(DEFAULT_DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite dengan dukungan row_factory, foreign key, dan WAL.

        Returns:
            Objek koneksi sqlite3.Connection siap pakai.
        """
        return create_sqlite_connection(
            self.db_path,
            require_exists=False,
            row_factory=True,
            foreign_keys=True,
            wal_mode=True,
        )

    @contextmanager
    def _atomic_write(self) -> Iterator[sqlite3.Connection]:
        """Menyediakan konteks transaksi tulis atomik dengan penguncian IMMEDIATE.

        Yields:
            Koneksi sqlite3 aktif di dalam blok transaksi BEGIN IMMEDIATE.

        Raises:
            Exception: Meneruskan galat setelah memastikan rollback dijalankan.
        """
        conn = self._connect()
        try:
            conn.isolation_level = None
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def get_active_suppliers(self) -> list[SupplierOption]:
        """Mengambil daftar seluruh supplier aktif yang diurutkan berdasarkan nama.

        Returns:
            Daftar SupplierOption untuk mengisi dropdown supplier pada UI.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, COALESCE(phone, '') AS phone
                FROM suppliers
                WHERE is_active = 1
                ORDER BY name COLLATE NOCASE ASC;
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "phone": str(row["phone"]),
            }
            for row in rows
        ]

    def create_supplier(
        self,
        name: str,
        phone: str = "",
        address: str = "",
    ) -> SupplierOption:
        """Menambahkan data supplier baru secara atomik ke tabel suppliers.

        Args:
            name: Nama supplier yang wajib diisi.
            phone: Nomor telepon supplier opsional.
            address: Alamat lengkap supplier opsional.

        Returns:
            Objek SupplierOption milik supplier yang baru dibuat.

        Raises:
            ValueError: Jika nama supplier kosong.
            RuntimeError: Jika ID baris baru gagal diperoleh dari SQLite.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Nama supplier tidak boleh kosong.")

        clean_phone = phone.strip()
        clean_address = address.strip()

        with self._atomic_write() as conn:
            cursor = conn.execute(
                """
                INSERT INTO suppliers (name, phone, address, is_active)
                VALUES (?, ?, ?, 1);
                """,
                (
                    clean_name,
                    clean_phone if clean_phone else None,
                    clean_address if clean_address else None,
                ),
            )
            supplier_id = cursor.lastrowid
            if supplier_id is None:
                raise RuntimeError("Gagal memperoleh ID supplier baru dari database.")

        return {
            "id": int(supplier_id),
            "name": clean_name,
            "phone": clean_phone,
        }

    def generate_next_invoice_number(self, reference_date: str | None = None) -> str:
        """Menghasilkan nomor faktur pembelian berurutan unik untuk tanggal tertentu.

        Args:
            reference_date: Tanggal referensi format yyyyMMdd; default hari ini.

        Returns:
            String nomor faktur berformat PO-YYYYMMDD-NNN.
        """
        date_stamp = (
            reference_date
            if reference_date is not None
            else datetime.now().strftime("%Y%m%d")
        )
        prefix = f"PO-{date_stamp}-"

        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT invoice_number
                FROM purchases
                WHERE invoice_number LIKE ?
                ORDER BY id DESC;
                """,
                (f"{prefix}%",),
            )
            existing_numbers = [str(row["invoice_number"]) for row in cursor.fetchall()]

        max_sequence = 0
        for inv in existing_numbers:
            suffix = inv[len(prefix) :]
            if suffix.isdigit():
                max_sequence = max(max_sequence, int(suffix))

        return f"{prefix}{max_sequence + 1:03d}"

    def get_catalog_items(self) -> list[CatalogItemData]:
        """Mengambil katalog barang aktif lengkap dengan stok FIFO dan harga beli terakhir.

        Returns:
            Daftar CatalogItemData siap digunakan oleh pencarian cepat dan grid.
        """
        bundles = self.get_bulk_catalog_items()
        return [bundle["catalog_item"] for bundle in bundles]

    def get_bulk_catalog_items(self) -> list[BulkCatalogItemView]:
        """Mengambil katalog barang aktif beserta kategori, stok FIFO, dan satuan beli.

        Returns:
            Daftar BulkCatalogItemView untuk kebutuhan grid dan dialog Bulk Picker.
        """
        with self._connect() as conn:
            item_rows = conn.execute(
                """
                SELECT
                    i.id AS item_id,
                    i.sku,
                    i.name,
                    COALESCE(c.name, 'Umum') AS category_name,
                    u.symbol AS base_unit_symbol
                FROM items i
                INNER JOIN units u ON u.id = i.base_unit_id
                LEFT JOIN categories c ON c.id = i.category_id
                WHERE i.is_active = 1
                ORDER BY i.name COLLATE NOCASE ASC;
                """
            ).fetchall()

            stock_rows = conn.execute(
                """
                SELECT item_id, COALESCE(SUM(remaining_qty), 0.0) AS current_stock
                FROM inventory_layers
                WHERE remaining_qty > 0
                GROUP BY item_id;
                """
            ).fetchall()
            stock_map: dict[int, float] = {
                int(row["item_id"]): float(row["current_stock"]) for row in stock_rows
            }

            layer_cost_rows = conn.execute(
                """
                SELECT item_id, unit_cost
                FROM inventory_layers
                ORDER BY received_at DESC, id DESC;
                """
            ).fetchall()
            latest_base_cost: dict[int, float] = {}
            for row in layer_cost_rows:
                item_id = int(row["item_id"])
                if item_id not in latest_base_cost:
                    latest_base_cost[item_id] = float(row["unit_cost"])

            last_purchase_cost_rows = conn.execute(
                """
                SELECT pd.item_unit_id, pd.unit_cost
                FROM purchase_details pd
                INNER JOIN purchases p ON p.id = pd.purchase_id
                WHERE p.status = 'COMPLETED'
                ORDER BY p.purchase_date DESC, pd.id DESC;
                """
            ).fetchall()
            last_unit_cost_map: dict[int, float] = {}
            for row in last_purchase_cost_rows:
                unit_id = int(row["item_unit_id"])
                if unit_id not in last_unit_cost_map:
                    last_unit_cost_map[unit_id] = float(row["unit_cost"])

            unit_rows = conn.execute(
                """
                SELECT
                    iu.id AS item_unit_id,
                    iu.item_id,
                    iu.variant_name,
                    u.symbol AS unit_symbol,
                    iu.conversion_qty,
                    iu.selling_price,
                    iu.is_default
                FROM item_units iu
                INNER JOIN units u ON u.id = iu.unit_id
                WHERE iu.is_active = 1
                ORDER BY iu.is_default DESC, iu.conversion_qty ASC, iu.id ASC;
                """
            ).fetchall()

        units_by_item: dict[int, list[ItemUnitOption]] = {}
        for row in unit_rows:
            item_id = int(row["item_id"])
            item_unit_id = int(row["item_unit_id"])
            conversion_qty = float(row["conversion_qty"])
            fallback_cost = latest_base_cost.get(item_id, 0.0) * conversion_qty
            resolved_cost = last_unit_cost_map.get(item_unit_id, fallback_cost)

            unit_entry: ItemUnitOption = {
                "item_unit_id": item_unit_id,
                "variant_name": str(row["variant_name"]),
                "unit_symbol": str(row["unit_symbol"]),
                "conversion_qty": conversion_qty,
                "selling_price": int(row["selling_price"]),
                "is_default": bool(int(row["is_default"])),
                "last_unit_cost": round(resolved_cost, 2),
            }
            units_by_item.setdefault(item_id, []).append(unit_entry)

        results: list[BulkCatalogItemView] = []
        for row in item_rows:
            item_id = int(row["item_id"])
            item_units = units_by_item.get(item_id, [])
            if not item_units:
                continue
            catalog_entry: CatalogItemData = {
                "item_id": item_id,
                "sku": str(row["sku"]),
                "name": str(row["name"]),
                "base_unit_symbol": str(row["base_unit_symbol"]),
                "current_stock": stock_map.get(item_id, 0.0),
                "units": item_units,
            }
            results.append(
                {
                    "catalog_item": catalog_entry,
                    "category_name": str(row["category_name"]),
                }
            )
        return results

    def _check_duplicate_invoice(
        self,
        conn: sqlite3.Connection,
        supplier_id: int | None,
        invoice_number: str,
        exclude_purchase_id: int | None = None,
    ) -> None:
        """Memastikan kombinasi supplier dan nomor faktur belum dipakai nota lain.

        Args:
            conn: Koneksi SQLite aktif di dalam transaksi.
            supplier_id: ID supplier atau None untuk belanja umum.
            invoice_number: Nomor faktur pembelian yang akan disimpan.
            exclude_purchase_id: ID nota yang diabaikan saat memperbarui draft.

        Raises:
            ValueError: Jika nomor faktur sudah terdaftar untuk supplier yang sama.
        """
        if supplier_id is None:
            sql = """
                SELECT id FROM purchases
                WHERE supplier_id IS NULL AND invoice_number = ?
            """
            params: list[Any] = [invoice_number]
        else:
            sql = """
                SELECT id FROM purchases
                WHERE supplier_id = ? AND invoice_number = ?
            """
            params = [supplier_id, invoice_number]

        if exclude_purchase_id is not None:
            sql += " AND id != ?"
            params.append(exclude_purchase_id)

        existing = conn.execute(sql, params).fetchone()
        if existing is not None:
            raise ValueError(
                f"Nomor faktur '{invoice_number}' sudah digunakan pada supplier yang sama."
            )

    def _validate_and_normalize_lines(
        self,
        conn: sqlite3.Connection,
        details: list[PurchaseLinePayload],
    ) -> list[PurchaseLinePayload]:
        """Memvalidasi setiap baris detail terhadap master items dan item_units.

        Args:
            conn: Koneksi SQLite aktif di dalam transaksi.
            details: Daftar baris pembelian dari antarmuka pengguna.

        Returns:
            Daftar PurchaseLinePayload terverifikasi dengan konversi otoritatif DB.

        Raises:
            ValueError: Jika daftar barang kosong atau ada item/satuan/qty tidak valid.
        """
        if not details:
            raise ValueError("Keranjang kulakan kosong. Minimal 1 barang wajib diisi.")

        normalized_lines: list[PurchaseLinePayload] = []
        for idx, line in enumerate(details, start=1):
            item_id = int(line["item_id"])
            item_unit_id = int(line["item_unit_id"])
            quantity = float(line["quantity"])
            unit_cost = float(line["unit_cost"])

            if quantity <= 0:
                raise ValueError(f"Qty beli baris ke-{idx} harus lebih dari 0.")
            if unit_cost < 0:
                raise ValueError(f"Harga beli baris ke-{idx} tidak boleh negatif.")

            unit_row = conn.execute(
                """
                SELECT iu.id, iu.item_id, iu.conversion_qty
                FROM item_units iu
                INNER JOIN items i ON i.id = iu.item_id
                WHERE iu.id = ? AND iu.item_id = ?;
                """,
                (item_unit_id, item_id),
            ).fetchone()
            if unit_row is None:
                raise ValueError(
                    f"Satuan beli pada baris ke-{idx} tidak cocok dengan master barang."
                )

            conversion_qty = float(unit_row["conversion_qty"])
            if conversion_qty <= 0:
                raise ValueError(f"Faktor konversi baris ke-{idx} tidak valid.")

            base_quantity = quantity * conversion_qty
            subtotal = quantity * unit_cost

            normalized_lines.append(
                {
                    "item_id": item_id,
                    "item_unit_id": item_unit_id,
                    "quantity": quantity,
                    "conversion_qty": conversion_qty,
                    "base_quantity": base_quantity,
                    "unit_cost": unit_cost,
                    "subtotal": subtotal,
                }
            )
        return normalized_lines

    def record_purchase(
        self,
        payload: PurchasePayload,
        draft_purchase_id: int | None = None,
    ) -> PurchaseSaveResult:
        """Menyimpan nota kulakan final secara atomik beserta lapisan stok FIFO dan pembayaran.

        Metode ini menjalankan satu transaksi BEGIN IMMEDIATE yang menyisipkan atau
        memfinalisasi tabel purchases, menyimpan purchase_details, membentuk layer baru
        di inventory_layers (dengan unit_cost per satuan dasar yang memperhitungkan diskon
        nota secara proporsional), mencatat stock_movements, serta menyimpan pembayaran awal
        ke purchase_payments agar trigger SQLite menyinkronkan status hutang secara otomatis.

        Args:
            payload: Struktur data PurchasePayload lengkap dari antarmuka pengguna.
            draft_purchase_id: ID draft opsional apabila memfinalisasi draft sebelumnya.

        Returns:
            Objek PurchaseSaveResult berisi ringkasan hasil transaksi dan jumlah layer FIFO.

        Raises:
            ValueError: Jika data nota, supplier, faktur, atau rincian item tidak valid.
            RuntimeError: Jika database gagal mengembalikan ID baris baru.
        """
        invoice_number = payload["invoice_number"].strip()
        if not invoice_number:
            raise ValueError("Nomor faktur / nota pembelian wajib diisi.")

        supplier_id = payload["supplier_id"]
        purchase_date = payload["purchase_date"].strip() or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        payment_method = payload["payment_method"].strip() or "Tunai"
        notes = payload["notes"].strip()
        reference_number = payload["reference_number"]
        clean_ref = reference_number.strip() if reference_number else None

        with self._atomic_write() as conn:
            if supplier_id is not None:
                sup_exists = conn.execute(
                    "SELECT id FROM suppliers WHERE id = ?;",
                    (supplier_id,),
                ).fetchone()
                if sup_exists is None:
                    raise ValueError("Supplier yang dipilih tidak ditemukan di database.")

            self._check_duplicate_invoice(
                conn=conn,
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                exclude_purchase_id=draft_purchase_id,
            )

            lines = self._validate_and_normalize_lines(conn, payload["details"])
            raw_subtotal = sum(line["subtotal"] for line in lines)
            subtotal_int = int(round(raw_subtotal))
            discount_int = max(0, min(int(payload["discount"]), subtotal_int))
            total_int = max(0, subtotal_int - discount_int)

            requested_paid = max(0, int(payload["amount_paid"]))
            effective_paid = min(requested_paid, total_int)
            remaining_initial = max(0, total_int - effective_paid)

            if remaining_initial > 0 and supplier_id is None:
                raise ValueError(
                    "Transaksi cicilan atau tempo wajib memilih Supplier agar hutang tercatat."
                )

            due_date = payload["due_date"] if remaining_initial > 0 else None

            if draft_purchase_id is not None:
                draft_row = conn.execute(
                    "SELECT id, status FROM purchases WHERE id = ?;",
                    (draft_purchase_id,),
                ).fetchone()
                if draft_row is None or str(draft_row["status"]) != "DRAFT":
                    raise ValueError("Draft pembelian yang dimaksud sudah tidak tersedia.")

                conn.execute(
                    "DELETE FROM purchase_details WHERE purchase_id = ?;",
                    (draft_purchase_id,),
                )
                conn.execute(
                    """
                    UPDATE purchases
                    SET invoice_number = ?,
                        supplier_id = ?,
                        purchase_date = ?,
                        subtotal = ?,
                        discount = ?,
                        total = ?,
                        payment_method = ?,
                        amount_paid = 0,
                        remaining_amount = ?,
                        payment_status = ?,
                        due_date = ?,
                        status = 'COMPLETED',
                        notes = ?
                    WHERE id = ?;
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal_int,
                        discount_int,
                        total_int,
                        payment_method,
                        total_int,
                        "PAID" if total_int == 0 else "UNPAID",
                        due_date,
                        notes if notes else None,
                        draft_purchase_id,
                    ),
                )
                purchase_id = draft_purchase_id
            else:
                purchase_cursor = conn.execute(
                    """
                    INSERT INTO purchases (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal,
                        discount,
                        total,
                        payment_method,
                        amount_paid,
                        remaining_amount,
                        payment_status,
                        due_date,
                        status,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'COMPLETED', ?);
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal_int,
                        discount_int,
                        total_int,
                        payment_method,
                        total_int,
                        "PAID" if total_int == 0 else "UNPAID",
                        due_date,
                        notes if notes else None,
                    ),
                )
                inserted_id = purchase_cursor.lastrowid
                if inserted_id is None:
                    raise RuntimeError("Gagal memperoleh ID nota pembelian baru.")
                purchase_id = int(inserted_id)

            discount_ratio = (
                float(total_int) / raw_subtotal if raw_subtotal > 0 else 1.0
            )
            layers_created = 0

            for line in lines:
                detail_cursor = conn.execute(
                    """
                    INSERT INTO purchase_details (
                        purchase_id,
                        item_id,
                        item_unit_id,
                        quantity,
                        conversion_qty,
                        base_quantity,
                        unit_cost,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        purchase_id,
                        line["item_id"],
                        line["item_unit_id"],
                        line["quantity"],
                        line["conversion_qty"],
                        line["base_quantity"],
                        line["unit_cost"],
                        line["subtotal"],
                    ),
                )
                detail_id = detail_cursor.lastrowid
                if detail_id is None:
                    raise RuntimeError("Gagal memperoleh ID rincian pembelian baru.")

                net_line_cost = line["subtotal"] * discount_ratio
                base_unit_cost = (
                    net_line_cost / line["base_quantity"]
                    if line["base_quantity"] > 0
                    else 0.0
                )

                conn.execute(
                    """
                    INSERT INTO inventory_layers (
                        item_id,
                        source_type,
                        purchase_detail_id,
                        received_qty,
                        remaining_qty,
                        unit_cost,
                        received_at
                    )
                    VALUES (?, 'PURCHASE', ?, ?, ?, ?, ?);
                    """,
                    (
                        line["item_id"],
                        int(detail_id),
                        line["base_quantity"],
                        line["base_quantity"],
                        base_unit_cost,
                        purchase_date,
                    ),
                )
                layers_created += 1

                movement_note = f"Kulakan {invoice_number}"
                if notes:
                    movement_note = f"{movement_note} - {notes}"

                conn.execute(
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
                    VALUES (?, 'PURCHASE', ?, NULL, NULL, ?, 0, ?, ?);
                    """,
                    (
                        line["item_id"],
                        int(detail_id),
                        line["base_quantity"],
                        purchase_date,
                        movement_note,
                    ),
                )

            if effective_paid > 0:
                payment_note = (
                    "Pembayaran awal saat kulakan"
                    if effective_paid < total_int
                    else "Pembayaran lunas saat kulakan"
                )
                conn.execute(
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
                        purchase_id,
                        purchase_date,
                        effective_paid,
                        payment_method,
                        clean_ref,
                        payment_note,
                    ),
                )

            final_row = conn.execute(
                """
                SELECT
                    id,
                    invoice_number,
                    status,
                    total,
                    amount_paid,
                    remaining_amount,
                    payment_status
                FROM purchases
                WHERE id = ?;
                """,
                (purchase_id,),
            ).fetchone()
            if final_row is None:
                raise RuntimeError("Nota pembelian gagal diverifikasi setelah disimpan.")

            return {
                "purchase_id": int(final_row["id"]),
                "invoice_number": str(final_row["invoice_number"]),
                "status": str(final_row["status"]),
                "total": int(final_row["total"]),
                "amount_paid": int(final_row["amount_paid"]),
                "remaining_amount": int(final_row["remaining_amount"]),
                "payment_status": str(final_row["payment_status"]),
                "layers_created": layers_created,
            }

    def save_purchase_draft(
        self,
        payload: PurchasePayload,
        draft_purchase_id: int | None = None,
    ) -> PurchaseSaveResult:
        """Menyimpan rencana belanja sebagai DRAFT tanpa menambah stok FIFO atau pembayaran.

        Args:
            payload: Struktur data PurchasePayload dari antarmuka pengguna.
            draft_purchase_id: ID draft sebelumnya jika sedang menyunting draft yang ada.

        Returns:
            Objek PurchaseSaveResult dengan status DRAFT dan layers_created bernilai 0.

        Raises:
            ValueError: Jika nomor faktur atau daftar barang tidak valid.
            RuntimeError: Jika ID draft baru gagal diperoleh dari database.
        """
        invoice_number = payload["invoice_number"].strip()
        if not invoice_number:
            raise ValueError("Nomor faktur / nota draft wajib diisi.")

        supplier_id = payload["supplier_id"]
        purchase_date = payload["purchase_date"].strip() or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        payment_method = payload["payment_method"].strip() or "Tunai"
        notes = payload["notes"].strip()

        with self._atomic_write() as conn:
            self._check_duplicate_invoice(
                conn=conn,
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                exclude_purchase_id=draft_purchase_id,
            )
            lines = self._validate_and_normalize_lines(conn, payload["details"])
            subtotal_int = int(round(sum(line["subtotal"] for line in lines)))
            discount_int = max(0, min(int(payload["discount"]), subtotal_int))
            total_int = max(0, subtotal_int - discount_int)

            if draft_purchase_id is not None:
                conn.execute(
                    "DELETE FROM purchase_details WHERE purchase_id = ?;",
                    (draft_purchase_id,),
                )
                conn.execute(
                    """
                    UPDATE purchases
                    SET invoice_number = ?,
                        supplier_id = ?,
                        purchase_date = ?,
                        subtotal = ?,
                        discount = ?,
                        total = ?,
                        payment_method = ?,
                        amount_paid = 0,
                        remaining_amount = ?,
                        payment_status = 'UNPAID',
                        due_date = ?,
                        status = 'DRAFT',
                        notes = ?
                    WHERE id = ? AND status = 'DRAFT';
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal_int,
                        discount_int,
                        total_int,
                        payment_method,
                        total_int,
                        payload["due_date"],
                        notes if notes else None,
                        draft_purchase_id,
                    ),
                )
                purchase_id = draft_purchase_id
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO purchases (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal,
                        discount,
                        total,
                        payment_method,
                        amount_paid,
                        remaining_amount,
                        payment_status,
                        due_date,
                        status,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 'UNPAID', ?, 'DRAFT', ?);
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_date,
                        subtotal_int,
                        discount_int,
                        total_int,
                        payment_method,
                        total_int,
                        payload["due_date"],
                        notes if notes else None,
                    ),
                )
                inserted_id = cursor.lastrowid
                if inserted_id is None:
                    raise RuntimeError("Gagal memperoleh ID draft pembelian baru.")
                purchase_id = int(inserted_id)

            for line in lines:
                conn.execute(
                    """
                    INSERT INTO purchase_details (
                        purchase_id,
                        item_id,
                        item_unit_id,
                        quantity,
                        conversion_qty,
                        base_quantity,
                        unit_cost,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        purchase_id,
                        line["item_id"],
                        line["item_unit_id"],
                        line["quantity"],
                        line["conversion_qty"],
                        line["base_quantity"],
                        line["unit_cost"],
                        line["subtotal"],
                    ),
                )

        return {
            "purchase_id": purchase_id,
            "invoice_number": invoice_number,
            "status": "DRAFT",
            "total": total_int,
            "amount_paid": 0,
            "remaining_amount": total_int,
            "payment_status": "UNPAID",
            "layers_created": 0,
        }

    def record_purchase_payment(
        self,
        purchase_id: int,
        amount: int,
        payment_method: str,
        payment_date: str | None = None,
        reference_number: str | None = None,
        notes: str = "",
    ) -> PaymentRecordResult:
        """Mencatat pembayaran cicilan atau pelunasan hutang supplier secara atomik.

        Menyisipkan baris baru ke tabel purchase_payments sehingga trigger
        trg_purchase_payments_after_insert otomatis menghitung ulang amount_paid,
        remaining_amount, dan payment_status pada tabel purchases.

        Args:
            purchase_id: ID nota pembelian yang akan dibayarkan.
            amount: Nominal pembayaran dalam Rupiah bulat (harus > 0 dan <= sisa hutang).
            payment_method: Metode pembayaran, misalnya Tunai atau Transfer Bank.
            payment_date: Tanggal pembayaran format yyyy-MM-dd HH:mm:ss; default sekarang.
            reference_number: Nomor bukti transfer atau referensi opsional.
            notes: Catatan pembayaran opsional.

        Returns:
            Objek PaymentRecordResult berisi status pembayaran terbaru pasca-trigger.

        Raises:
            ValueError: Jika nota tidak ditemukan, masih DRAFT, sudah lunas, atau nominal salah.
            RuntimeError: Jika ID pembayaran baru gagal diperoleh.
        """
        if amount <= 0:
            raise ValueError("Nominal pembayaran harus lebih besar dari Rp 0.")

        clean_method = payment_method.strip() or "Tunai"
        clean_date = (
            payment_date.strip()
            if payment_date is not None and payment_date.strip()
            else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        clean_ref = reference_number.strip() if reference_number else None
        clean_notes = notes.strip()

        with self._atomic_write() as conn:
            purchase_row = conn.execute(
                """
                SELECT
                    id,
                    invoice_number,
                    total,
                    amount_paid,
                    remaining_amount,
                    payment_status,
                    status
                FROM purchases
                WHERE id = ?;
                """,
                (purchase_id,),
            ).fetchone()
            if purchase_row is None:
                raise ValueError("Nota pembelian tidak ditemukan di database.")

            if str(purchase_row["status"]) != "COMPLETED":
                raise ValueError(
                    "Nota masih berstatus DRAFT. Finalisasi kulakan terlebih dahulu."
                )

            current_remaining = int(purchase_row["remaining_amount"])
            if current_remaining <= 0 or str(purchase_row["payment_status"]) == "PAID":
                raise ValueError("Nota pembelian ini sudah berstatus LUNAS.")

            if amount > current_remaining:
                raise ValueError(
                    f"Nominal bayar ({format_rupiah(amount)}) melebihi sisa hutang "
                    f"({format_rupiah(current_remaining)})."
                )

            pay_cursor = conn.execute(
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
                    purchase_id,
                    clean_date,
                    amount,
                    clean_method,
                    clean_ref,
                    clean_notes if clean_notes else None,
                ),
            )
            payment_id = pay_cursor.lastrowid
            if payment_id is None:
                raise RuntimeError("Gagal memperoleh ID pembayaran pembelian baru.")

            updated_row = conn.execute(
                """
                SELECT
                    invoice_number,
                    amount_paid,
                    remaining_amount,
                    payment_status
                FROM purchases
                WHERE id = ?;
                """,
                (purchase_id,),
            ).fetchone()
            if updated_row is None:
                raise RuntimeError("Gagal membaca status nota setelah pelunasan.")

            return {
                "payment_id": int(payment_id),
                "purchase_id": purchase_id,
                "invoice_number": str(updated_row["invoice_number"]),
                "paid_this_time": amount,
                "amount_paid": int(updated_row["amount_paid"]),
                "remaining_amount": int(updated_row["remaining_amount"]),
                "payment_status": str(updated_row["payment_status"]),
            }

    def get_purchase_history(
        self,
        filter_payload: HistoryFilterPayload | None = None,
    ) -> list[PurchaseHistoryRow]:
        """Mengambil daftar riwayat pembelian supplier sesuai kriteria filter aktif.

        Args:
            filter_payload: Filter pencarian teks, status bayar, dan rentang tanggal.

        Returns:
            Daftar PurchaseHistoryRow yang diurutkan dari transaksi terbaru.
        """
        conditions: list[str] = ["1 = 1"]
        params: list[Any] = []

        if filter_payload is not None:
            search = filter_payload["search"].strip()
            if search:
                like_term = f"%{search}%"
                conditions.append(
                    "(p.invoice_number LIKE ? OR COALESCE(s.name, 'Belanja Umum') LIKE ?)"
                )
                params.extend([like_term, like_term])

            payment_status = filter_payload["payment_status"].strip().upper()
            if payment_status in ("PAID", "PARTIAL", "UNPAID"):
                conditions.append("p.payment_status = ?")
                params.append(payment_status)

            date_from = filter_payload["date_from"].strip()
            if date_from:
                conditions.append("substr(p.purchase_date, 1, 10) >= ?")
                params.append(date_from)

            date_to = filter_payload["date_to"].strip()
            if date_to:
                conditions.append("substr(p.purchase_date, 1, 10) <= ?")
                params.append(date_to)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT
                p.id,
                p.purchase_date,
                p.invoice_number,
                COALESCE(s.name, 'Belanja Umum') AS supplier_name,
                p.total,
                p.amount_paid,
                p.remaining_amount,
                p.payment_status,
                p.due_date,
                p.status
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE {where_clause}
            ORDER BY p.purchase_date DESC, p.id DESC;
        """

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        history: list[PurchaseHistoryRow] = []
        for row in rows:
            status_val = str(row["status"])
            invoice_text = str(row["invoice_number"])
            if status_val == "DRAFT":
                invoice_text = f"[DRAFT] {invoice_text}"
            display_remaining = 0 if status_val == "DRAFT" else int(row["remaining_amount"])
            history.append(
                {
                    "id": int(row["id"]),
                    "purchase_date": str(row["purchase_date"])[:16],
                    "invoice_number": invoice_text,
                    "supplier_name": str(row["supplier_name"]),
                    "total": int(row["total"]),
                    "amount_paid": int(row["amount_paid"]),
                    "remaining_amount": display_remaining,
                    "payment_status": str(row["payment_status"]),
                    "due_date": str(row["due_date"]) if row["due_date"] is not None else None,
                    "status": status_val,
                }
            )
        return history

    def get_purchase_detail_bundle(self, purchase_id: int) -> PurchaseDetailBundle:
        """Mengambil detail lengkap satu nota pembelian beserta daftar item dan cicilannya.

        Args:
            purchase_id: ID unik transaksi pada tabel purchases.

        Returns:
            Objek PurchaseDetailBundle siap ditampilkan di dialog detail atau pelunasan.

        Raises:
            ValueError: Jika nota pembelian dengan ID tersebut tidak ditemukan.
        """
        with self._connect() as conn:
            header = conn.execute(
                """
                SELECT
                    p.id,
                    p.invoice_number,
                    p.supplier_id,
                    COALESCE(s.name, 'Belanja Umum') AS supplier_name,
                    p.purchase_date,
                    p.subtotal,
                    p.discount,
                    p.total,
                    p.payment_method,
                    p.amount_paid,
                    p.remaining_amount,
                    p.payment_status,
                    p.due_date,
                    p.status,
                    COALESCE(p.notes, '') AS notes
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                WHERE p.id = ?;
                """,
                (purchase_id,),
            ).fetchone()
            if header is None:
                raise ValueError(f"Nota pembelian ID {purchase_id} tidak ditemukan.")

            detail_rows = conn.execute(
                """
                SELECT
                    i.sku,
                    i.name AS item_name,
                    iu.variant_name,
                    u.symbol AS base_unit_symbol,
                    pd.quantity,
                    pd.conversion_qty,
                    pd.base_quantity,
                    pd.unit_cost,
                    pd.subtotal
                FROM purchase_details pd
                INNER JOIN items i ON i.id = pd.item_id
                INNER JOIN item_units iu ON iu.id = pd.item_unit_id
                INNER JOIN units u ON u.id = i.base_unit_id
                WHERE pd.purchase_id = ?
                ORDER BY pd.id ASC;
                """,
                (purchase_id,),
            ).fetchall()

            payment_rows = conn.execute(
                """
                SELECT
                    id,
                    payment_date,
                    amount,
                    payment_method,
                    COALESCE(reference_number, '') AS reference_number,
                    COALESCE(notes, '') AS notes
                FROM purchase_payments
                WHERE purchase_id = ?
                ORDER BY payment_date ASC, id ASC;
                """,
                (purchase_id,),
            ).fetchall()

        lines: list[PurchaseDetailLineView] = [
            {
                "sku": str(row["sku"]),
                "item_name": str(row["item_name"]),
                "variant_name": str(row["variant_name"]),
                "base_unit_symbol": str(row["base_unit_symbol"]),
                "quantity": float(row["quantity"]),
                "conversion_qty": float(row["conversion_qty"]),
                "base_quantity": float(row["base_quantity"]),
                "unit_cost": float(row["unit_cost"]),
                "subtotal": float(row["subtotal"]),
            }
            for row in detail_rows
        ]
        payments: list[PurchasePaymentHistoryView] = [
            {
                "id": int(row["id"]),
                "payment_date": str(row["payment_date"]),
                "amount": int(row["amount"]),
                "payment_method": str(row["payment_method"]),
                "reference_number": str(row["reference_number"]),
                "notes": str(row["notes"]),
            }
            for row in payment_rows
        ]

        return {
            "id": int(header["id"]),
            "invoice_number": str(header["invoice_number"]),
            "supplier_id": (
                int(header["supplier_id"]) if header["supplier_id"] is not None else None
            ),
            "supplier_name": str(header["supplier_name"]),
            "purchase_date": str(header["purchase_date"]),
            "subtotal": int(header["subtotal"]),
            "discount": int(header["discount"]),
            "total": int(header["total"]),
            "payment_method": str(header["payment_method"]),
            "amount_paid": int(header["amount_paid"]),
            "remaining_amount": int(header["remaining_amount"]),
            "payment_status": str(header["payment_status"]),
            "due_date": str(header["due_date"]) if header["due_date"] is not None else None,
            "status": str(header["status"]),
            "notes": str(header["notes"]),
            "lines": lines,
            "payments": payments,
        }

    def build_purchase_payload_from_id(
        self,
        purchase_id: int,
        as_duplicate: bool = True,
    ) -> tuple[PurchasePayload, str]:
        """Menyusun PurchasePayload dari nota lama untuk fitur Ulang Nota atau muat Draft.

        Args:
            purchase_id: ID nota pembelian sumber.
            as_duplicate: Jika True, menghasilkan nomor faktur baru dan mengosongkan status lunas.

        Returns:
            Tuple (PurchasePayload, status_asli_nota).

        Raises:
            ValueError: Jika nota sumber tidak ditemukan.
        """
        with self._connect() as conn:
            header = conn.execute(
                """
                SELECT
                    invoice_number,
                    supplier_id,
                    purchase_date,
                    subtotal,
                    discount,
                    total,
                    payment_method,
                    amount_paid,
                    remaining_amount,
                    payment_status,
                    due_date,
                    status,
                    COALESCE(notes, '') AS notes
                FROM purchases
                WHERE id = ?;
                """,
                (purchase_id,),
            ).fetchone()
            if header is None:
                raise ValueError(f"Nota pembelian ID {purchase_id} tidak ditemukan.")

            detail_rows = conn.execute(
                """
                SELECT
                    item_id,
                    item_unit_id,
                    quantity,
                    conversion_qty,
                    base_quantity,
                    unit_cost,
                    subtotal
                FROM purchase_details
                WHERE purchase_id = ?
                ORDER BY id ASC;
                """,
                (purchase_id,),
            ).fetchall()

        original_status = str(header["status"])
        details: list[PurchaseLinePayload] = [
            {
                "item_id": int(row["item_id"]),
                "item_unit_id": int(row["item_unit_id"]),
                "quantity": float(row["quantity"]),
                "conversion_qty": float(row["conversion_qty"]),
                "base_quantity": float(row["base_quantity"]),
                "unit_cost": float(row["unit_cost"]),
                "subtotal": float(row["subtotal"]),
            }
            for row in detail_rows
        ]

        total_int = int(header["total"])
        use_new_invoice = as_duplicate and original_status != "DRAFT"
        invoice_number = (
            self.generate_next_invoice_number()
            if use_new_invoice
            else str(header["invoice_number"])
        )
        amount_paid = total_int if use_new_invoice else int(header["amount_paid"])
        remaining_amount = 0 if use_new_invoice else int(header["remaining_amount"])
        payment_status = "PAID" if use_new_invoice else str(header["payment_status"])

        payload: PurchasePayload = {
            "invoice_number": invoice_number,
            "supplier_id": (
                int(header["supplier_id"]) if header["supplier_id"] is not None else None
            ),
            "purchase_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subtotal": int(header["subtotal"]),
            "discount": int(header["discount"]),
            "total": total_int,
            "payment_method": str(header["payment_method"]),
            "amount_paid": amount_paid,
            "remaining_amount": remaining_amount,
            "payment_status": payment_status,
            "due_date": (
                None
                if use_new_invoice
                else (str(header["due_date"]) if header["due_date"] is not None else None)
            ),
            "status": original_status,
            "notes": str(header["notes"]),
            "reference_number": None,
            "details": details,
        }
        return payload, original_status

    def get_item_selling_units(self, item_id: int) -> tuple[str, list[ItemUnitOption]]:
        """Mengambil nama barang dan seluruh varian harga jualnya untuk dialog ubah harga.

        Args:
            item_id: ID unik barang pada tabel items.

        Returns:
            Tuple (nama_barang, daftar_ItemUnitOption).

        Raises:
            ValueError: Jika barang tidak ditemukan.
        """
        catalog = self.get_catalog_items()
        for item in catalog:
            if item["item_id"] == item_id:
                return item["name"], item["units"]
        raise ValueError(f"Barang ID {item_id} tidak ditemukan pada katalog aktif.")

    def update_selling_prices(self, price_updates: dict[int, int]) -> int:
        """Memperbarui harga jual satu atau lebih varian satuan di tabel item_units.

        Args:
            price_updates: Peta item_unit_id ke nilai selling_price baru (>= 0).

        Returns:
            Jumlah baris item_units yang berhasil diperbarui.

        Raises:
            ValueError: Jika terdapat nominal harga jual negatif.
        """
        if not price_updates:
            return 0

        for unit_id, price in price_updates.items():
            if price < 0:
                raise ValueError(f"Harga jual untuk satuan ID {unit_id} tidak boleh negatif.")

        updated_count = 0
        with self._atomic_write() as conn:
            for unit_id, price in price_updates.items():
                cursor = conn.execute(
                    """
                    UPDATE item_units
                    SET selling_price = ?
                    WHERE id = ?;
                    """,
                    (int(price), int(unit_id)),
                )
                updated_count += cursor.rowcount
        return updated_count

    def parse_csv_purchase_file(
        self,
        file_path: str | Path,
        catalog_items: list[CatalogItemData],
    ) -> CsvImportSummary:
        """Membaca file CSV kulakan dan mencocokkan SKU serta satuan dengan katalog aktif.

        Format kolom yang dikenali secara fleksibel (case-insensitive):
        sku, satuan/unit/variant_name (opsional), qty/quantity (default 1),
        harga_beli/unit_cost (opsional).

        Args:
            file_path: Lokasi file CSV yang dipilih pengguna.
            catalog_items: Daftar barang katalog aktif saat ini.

        Returns:
            Objek CsvImportSummary berisi daftar baris cocok dan alasan baris dilewati.
        """
        sku_map: dict[str, CatalogItemData] = {
            item["sku"].strip().lower(): item for item in catalog_items
        }
        matched_rows: list[tuple[CatalogItemData, float, int | None, float | None]] = []
        skipped_reasons: list[str] = []

        with Path(file_path).open("r", encoding="utf-8-sig", newline="") as csv_file:
            sample = csv_file.read(2048)
            csv_file.seek(0)
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            reader = csv.DictReader(csv_file, delimiter=delimiter)

            for line_num, raw_row in enumerate(reader, start=2):
                normalized_row = {
                    (key or "").strip().lower(): (val or "").strip()
                    for key, val in raw_row.items()
                }
                sku_text = normalized_row.get("sku", "")
                if not sku_text:
                    skipped_reasons.append(f"Baris {line_num}: kolom SKU kosong.")
                    continue

                catalog_item = sku_map.get(sku_text.lower())
                if catalog_item is None:
                    skipped_reasons.append(f"Baris {line_num}: SKU '{sku_text}' tidak ditemukan.")
                    continue

                unit_hint = (
                    normalized_row.get("satuan")
                    or normalized_row.get("variant_name")
                    or normalized_row.get("unit")
                    or ""
                ).lower()
                matched_unit_id: int | None = None
                if unit_hint:
                    for unit in catalog_item["units"]:
                        if (
                            unit["variant_name"].lower() == unit_hint
                            or unit["unit_symbol"].lower() == unit_hint
                        ):
                            matched_unit_id = unit["item_unit_id"]
                            break

                qty_raw = normalized_row.get("qty") or normalized_row.get("quantity") or "1"
                try:
                    qty_val = float(qty_raw.replace(",", "."))
                    if qty_val <= 0:
                        raise ValueError("Qty harus > 0")
                except ValueError:
                    skipped_reasons.append(f"Baris {line_num}: qty '{qty_raw}' tidak valid.")
                    continue

                cost_raw = (
                    normalized_row.get("harga_beli")
                    or normalized_row.get("unit_cost")
                    or normalized_row.get("harga")
                    or ""
                )
                unit_cost: float | None = None
                if cost_raw:
                    try:
                        cleaned_cost = cost_raw.replace("Rp", "").replace(".", "").replace(",", ".")
                        parsed_cost = float(cleaned_cost.strip())
                        if parsed_cost < 0:
                            raise ValueError("Harga negatif")
                        unit_cost = parsed_cost
                    except ValueError:
                        skipped_reasons.append(
                            f"Baris {line_num}: harga beli '{cost_raw}' tidak valid."
                        )
                        continue

                matched_rows.append((catalog_item, qty_val, matched_unit_id, unit_cost))

        return {
            "matched_rows": matched_rows,
            "skipped_reasons": skipped_reasons,
        }


class QuickSupplierDialog(QDialog):
    """Dialog cepat untuk menambahkan supplier baru langsung dari halaman kulakan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi QuickSupplierDialog.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setWindowTitle("Tambah Supplier Baru")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Tambah Supplier Baru", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Supplier baru langsung tersedia dan dipilih pada nota aktif.", self)
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.name_input = QLineEdit(card)
        self.name_input.setPlaceholderText("Contoh: CV Kertas Nusantara")
        self.phone_input = QLineEdit(card)
        self.phone_input.setPlaceholderText("Contoh: 0812-3456-7890 (opsional)")
        self.address_input = QLineEdit(card)
        self.address_input.setPlaceholderText("Alamat toko / distributor (opsional)")

        form.addRow("Nama Supplier *", self.name_input)
        form.addRow("No. Telepon", self.phone_input)
        form.addRow("Alamat", self.address_input)
        layout.addWidget(card)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Simpan Supplier", self)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _validate_and_accept(self) -> None:
        """Memvalidasi nama supplier wajib diisi sebelum menutup dialog."""
        if not self.name_input.text().strip():
            self.error_label.setText("Nama supplier wajib diisi.")
            self.error_label.setVisible(True)
            self.name_input.setFocus()
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str]:
        """Mengambil nilai input nama, telepon, dan alamat supplier.

        Returns:
            Tuple (name, phone, address).
        """
        return (
            self.name_input.text().strip(),
            self.phone_input.text().strip(),
            self.address_input.text().strip(),
        )


class PurchasePaymentDialog(QDialog):
    """Dialog pencatatan cicilan atau pelunasan hutang nota pembelian supplier."""

    def __init__(
        self,
        bundle: PurchaseDetailBundle,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi PurchasePaymentDialog dengan ringkasan hutang nota.

        Args:
            bundle: Paket detail nota pembelian yang akan dibayarkan.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._remaining = bundle["remaining_amount"]
        self.setWindowTitle(f"Pelunasan Hutang - {bundle['invoice_number']}")
        self.setMinimumWidth(460)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"Bayar Cicilan / Pelunasan ({bundle['invoice_number']})", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            f"Supplier: {bundle['supplier_name']}  •  "
            f"Total: {format_rupiah(bundle['total'])}  •  "
            f"Sisa Hutang: {format_rupiah(self._remaining)}",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        amount_row = QHBoxLayout()
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.setSpacing(6)

        self.amount_spin = CurrencySpinBox(maximum=max(1, self._remaining), parent=card)
        self.amount_spin.setValue(self._remaining)
        self.amount_spin.setFixedHeight(32)

        full_btn = QPushButton("Lunasi Semua", card)
        full_btn.setObjectName("accentBtn")
        full_btn.setFixedHeight(32)
        full_btn.clicked.connect(self._set_full_remaining)

        amount_row.addWidget(self.amount_spin, 1)
        amount_row.addWidget(full_btn)

        self.method_combo = QComboBox(card)
        self.method_combo.addItems(list(TambahStokPage.PAYMENT_METHODS))
        self.method_combo.setFixedHeight(32)

        self.date_edit = QDateTimeEdit(QDateTime.currentDateTime(), card)
        self.date_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedHeight(32)

        self.reference_input = QLineEdit(card)
        self.reference_input.setPlaceholderText("No. resi / bukti transfer (opsional)")

        self.notes_input = QLineEdit(card)
        self.notes_input.setPlaceholderText("Catatan pembayaran cicilan (opsional)")

        form.addRow("Nominal Bayar *", amount_row)
        form.addRow("Metode Bayar", self.method_combo)
        form.addRow("Tanggal Bayar", self.date_edit)
        form.addRow("No. Referensi", self.reference_input)
        form.addRow("Catatan", self.notes_input)
        layout.addWidget(card)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        submit_btn = QPushButton("Simpan Pembayaran", self)
        submit_btn.setObjectName("primaryBtn")
        submit_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(submit_btn)
        layout.addLayout(btn_row)

    def _set_full_remaining(self) -> None:
        """Mengisi nominal pembayaran penuh sesuai sisa hutang nota."""
        self.amount_spin.setValue(self._remaining)

    def _validate_and_accept(self) -> None:
        """Memastikan nominal pembayaran valid sebelum menyimpan."""
        amount = self.amount_spin.value()
        if amount <= 0:
            self.error_label.setText("Nominal pembayaran harus lebih besar dari Rp 0.")
            self.error_label.setVisible(True)
            return
        if amount > self._remaining:
            self.error_label.setText("Nominal pembayaran tidak boleh melebihi sisa hutang.")
            self.error_label.setVisible(True)
            return
        self.accept()

    def get_payment_data(self) -> tuple[int, str, str, str | None, str]:
        """Mengembalikan parameter pembayaran yang diisi pengguna.

        Returns:
            Tuple (amount, payment_method, payment_date, reference_number, notes).
        """
        ref = self.reference_input.text().strip()
        return (
            self.amount_spin.value(),
            self.method_combo.currentText(),
            self.date_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            ref if ref else None,
            self.notes_input.text().strip(),
        )


class PurchaseDetailDialog(QDialog):
    """Dialog tampilan rincian item pembelian dan riwayat pembayaran cicilan nota.

    Attributes:
        pay_requested: Menandakan pengguna menekan tombol lanjut ke pelunasan hutang.
    """

    def __init__(
        self,
        bundle: PurchaseDetailBundle,
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi PurchaseDetailDialog.

        Args:
            bundle: Paket lengkap nota pembelian dari TambahStokService.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.pay_requested: bool = False
        self.setWindowTitle(f"Detail Nota Kulakan - {bundle['invoice_number']}")
        self.setMinimumSize(780, 520)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_card = QFrame(self)
        header_card.setObjectName("dialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(4)

        title = QLabel(
            f"Nota {bundle['invoice_number']}  ({bundle['status']} - {bundle['payment_status']})",
            header_card,
        )
        title.setObjectName("dialogTitle")

        due_info = bundle["due_date"] if bundle["due_date"] else "-"
        meta = QLabel(
            f"Supplier: {bundle['supplier_name']}  •  Tanggal: {bundle['purchase_date']}  •  "
            f"Jatuh Tempo: {due_info}",
            header_card,
        )
        meta.setObjectName("dialogSubtitle")

        totals = QLabel(
            f"Subtotal: {format_rupiah(bundle['subtotal'])}  •  "
            f"Diskon: {format_rupiah(bundle['discount'])}  •  "
            f"Total: {format_rupiah(bundle['total'])}  •  "
            f"Dibayar: {format_rupiah(bundle['amount_paid'])}  •  "
            f"Sisa Hutang: {format_rupiah(bundle['remaining_amount'])}",
            header_card,
        )
        totals.setObjectName("fieldLabel")
        totals.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(meta)
        header_layout.addWidget(totals)
        if bundle["notes"]:
            note_lbl = QLabel(f"Catatan: {bundle['notes']}", header_card)
            note_lbl.setObjectName("dialogSubtitle")
            header_layout.addWidget(note_lbl)
        layout.addWidget(header_card)

        items_label = QLabel("Rincian Barang Masuk (FIFO)", self)
        items_label.setObjectName("fieldLabel")
        layout.addWidget(items_label)

        lines_table = QTableWidget(len(bundle["lines"]), 6, self)
        lines_table.setHorizontalHeaderLabels(
            ["SKU", "Barang", "Satuan", "Qty Beli", "Stok Masuk", "Subtotal"]
        )
        lines_table.setAlternatingRowColors(True)
        lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v_head = lines_table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = lines_table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for row_idx, line in enumerate(bundle["lines"]):
            lines_table.setItem(row_idx, 0, QTableWidgetItem(line["sku"]))
            lines_table.setItem(row_idx, 1, QTableWidgetItem(line["item_name"]))
            lines_table.setItem(row_idx, 2, QTableWidgetItem(line["variant_name"]))
            qty_item = QTableWidgetItem(format_quantity(line["quantity"]))
            qty_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            base_item = QTableWidgetItem(
                f"{format_quantity(line['base_quantity'])} {line['base_unit_symbol']}"
            )
            base_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            sub_item = QTableWidgetItem(format_rupiah(line["subtotal"]))
            sub_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lines_table.setItem(row_idx, 3, qty_item)
            lines_table.setItem(row_idx, 4, base_item)
            lines_table.setItem(row_idx, 5, sub_item)
        layout.addWidget(lines_table, 3)

        pay_label = QLabel("Riwayat Pembayaran & Cicilan", self)
        pay_label.setObjectName("fieldLabel")
        layout.addWidget(pay_label)

        pay_table = QTableWidget(len(bundle["payments"]), 5, self)
        pay_table.setHorizontalHeaderLabels(
            ["Tanggal Bayar", "Metode", "Nominal", "No. Referensi", "Catatan"]
        )
        pay_table.setAlternatingRowColors(True)
        pay_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pay_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        pv_head = pay_table.verticalHeader()
        if pv_head is not None:
            pv_head.setVisible(False)
        ph_head = pay_table.horizontalHeader()
        if ph_head is not None:
            ph_head.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for row_idx, payment in enumerate(bundle["payments"]):
            pay_table.setItem(row_idx, 0, QTableWidgetItem(payment["payment_date"]))
            pay_table.setItem(row_idx, 1, QTableWidgetItem(payment["payment_method"]))
            amt_item = QTableWidgetItem(format_rupiah(payment["amount"]))
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            pay_table.setItem(row_idx, 2, amt_item)
            pay_table.setItem(
                row_idx, 3, QTableWidgetItem(payment["reference_number"] or "-")
            )
            pay_table.setItem(row_idx, 4, QTableWidgetItem(payment["notes"] or "-"))
        layout.addWidget(pay_table, 2)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        can_pay = (
            bundle["status"] == "COMPLETED"
            and bundle["payment_status"] != "PAID"
            and bundle["remaining_amount"] > 0
        )
        if can_pay:
            pay_btn = QPushButton("Bayar Cicilan / Pelunasan", self)
            pay_btn.setObjectName("primaryBtn")
            pay_btn.clicked.connect(self._request_payment)
            btn_row.addWidget(pay_btn)

        close_btn = QPushButton("Tutup", self)
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _request_payment(self) -> None:
        """Menandai permintaan pelunasan hutang dan menutup dialog detail."""
        self.pay_requested = True
        self.accept()


class BulkItemPickerDialog(QDialog):
    """Dialog pemilihan banyak barang sekaligus dengan filter kategori dan stok menipis."""

    def __init__(
        self,
        items: list[BulkCatalogItemView],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi BulkItemPickerDialog.

        Args:
            items: Daftar barang katalog lengkap beserta nama kategorinya.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._all_items = items
        self._filtered_items: list[BulkCatalogItemView] = list(items)
        self._selected_ids: set[int] = set()

        self.setWindowTitle("Pilih Banyak Barang Sekaligus")
        self.setMinimumSize(760, 500)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Pilih Banyak Barang (Bulk Picker)", self)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Cari SKU atau nama barang...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.category_combo = QComboBox(self)
        self.category_combo.addItem("Semua Kategori", "")
        categories = sorted({entry["category_name"] for entry in items})
        for cat in categories:
            self.category_combo.addItem(cat, cat)
        self.category_combo.currentIndexChanged.connect(self._apply_filter)

        self.low_stock_check = QCheckBox("Hanya Stok <= 10", self)
        self.low_stock_check.toggled.connect(self._apply_filter)

        select_visible_btn = QPushButton("Centang Semua Tampil", self)
        select_visible_btn.setObjectName("secondaryBtn")
        select_visible_btn.clicked.connect(self._select_all_visible)

        filter_row.addWidget(self.search_input, 1)
        filter_row.addWidget(self.category_combo)
        filter_row.addWidget(self.low_stock_check)
        filter_row.addWidget(select_visible_btn)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Pilih", "SKU", "Nama Barang", "Kategori", "Sisa Stok"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v_head = self.table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = self.table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 56)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 120)
        self.table.itemChanged.connect(self._handle_item_checked)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.count_label = QLabel("0 barang dipilih", self)
        self.count_label.setObjectName("dialogSubtitle")
        btn_row.addWidget(self.count_label)
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Tambahkan ke Keranjang", self)
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

        self._render_table()

    def _apply_filter(self) -> None:
        """Menyaring daftar barang sesuai teks pencarian, kategori, dan batas stok."""
        query = self.search_input.text().strip().lower()
        selected_category = str(self.category_combo.currentData() or "")
        only_low = self.low_stock_check.isChecked()

        filtered: list[BulkCatalogItemView] = []
        for entry in self._all_items:
            item = entry["catalog_item"]
            if selected_category and entry["category_name"] != selected_category:
                continue
            if only_low and item["current_stock"] > 10.0:
                continue
            if query and (
                query not in item["sku"].lower() and query not in item["name"].lower()
            ):
                continue
            filtered.append(entry)

        self._filtered_items = filtered
        self._render_table()

    def _render_table(self) -> None:
        """Merender ulang isi tabel dialog tanpa memicu sinyal itemChanged palsu."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._filtered_items))
        for row_idx, entry in enumerate(self._filtered_items):
            item = entry["catalog_item"]
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setData(Qt.ItemDataRole.UserRole, item["item_id"])
            is_checked = item["item_id"] in self._selected_ids
            check_item.setCheckState(
                Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
            )
            self.table.setItem(row_idx, 0, check_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(item["sku"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item["name"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(entry["category_name"]))

            stock_item = QTableWidgetItem(
                f"{format_quantity(item['current_stock'])} {item['base_unit_symbol']}"
            )
            stock_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row_idx, 4, stock_item)
        self.table.blockSignals(False)
        self._update_selected_count()

    def _handle_item_checked(self, item: QTableWidgetItem) -> None:
        """Memperbarui himpunan ID barang terpilih saat checkbox berubah.

        Args:
            item: Objek sel tabel yang status centangnya berubah.
        """
        if item.column() != 0:
            return
        raw_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(raw_id, int):
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(raw_id)
        else:
            self._selected_ids.discard(raw_id)
        self._update_selected_count()

    def _select_all_visible(self) -> None:
        """Mencentang seluruh barang yang sedang tampil setelah filter."""
        for entry in self._filtered_items:
            self._selected_ids.add(entry["catalog_item"]["item_id"])
        self._render_table()

    def _update_selected_count(self) -> None:
        """Memperbarui teks jumlah barang terpilih pada footer dialog."""
        self.count_label.setText(f"{len(self._selected_ids)} barang dipilih")

    def get_selected_items(self) -> list[CatalogItemData]:
        """Mengembalikan daftar CatalogItemData yang dicentang pengguna.

        Returns:
            Daftar CatalogItemData siap ditambahkan ke keranjang belanja.
        """
        return [
            entry["catalog_item"]
            for entry in self._all_items
            if entry["catalog_item"]["item_id"] in self._selected_ids
        ]


class RepeatOrderDialog(QDialog):
    """Dialog pemilih nota kulakan lama atau draft untuk dimuat ulang ke keranjang."""

    def __init__(
        self,
        history_rows: list[PurchaseHistoryRow],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi RepeatOrderDialog.

        Args:
            history_rows: Daftar nota pembelian yang tersedia untuk disalin.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._rows = history_rows
        self._selected_purchase_id: int | None = None

        self.setWindowTitle("Muat Ulang Nota Lama / Draft")
        self.setMinimumSize(700, 420)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Pilih Nota untuk Dimuat ke Keranjang", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Nota COMPLETED akan disalin dengan nomor faktur baru; nota DRAFT dibuka untuk "
            "dilanjutkan.",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget(len(history_rows), 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Tanggal", "No. Faktur", "Supplier", "Total", "Status"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        v_head = self.table.verticalHeader()
        if v_head is not None:
            v_head.setVisible(False)
        h_head = self.table.horizontalHeader()
        if h_head is not None:
            h_head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for idx, row in enumerate(history_rows):
            date_item = QTableWidgetItem(row["purchase_date"])
            date_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(idx, 0, date_item)
            self.table.setItem(idx, 1, QTableWidgetItem(row["invoice_number"]))
            self.table.setItem(idx, 2, QTableWidgetItem(row["supplier_name"]))
            total_item = QTableWidgetItem(format_rupiah(row["total"]))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(idx, 3, total_item)
            self.table.setItem(idx, 4, QTableWidgetItem(row["status"]))

        self.table.itemDoubleClicked.connect(self._confirm_selection)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        load_btn = QPushButton("Muat ke Keranjang", self)
        load_btn.setObjectName("primaryBtn")
        load_btn.clicked.connect(self._confirm_selection)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

    def _confirm_selection(self) -> None:
        """Menyimpan ID nota yang dipilih baris aktif lalu menutup dialog."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
        first_item = self.table.item(current_row, 0)
        if first_item is None:
            return
        raw_id = first_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(raw_id, int):
            self._selected_purchase_id = raw_id
            self.accept()

    def get_selected_purchase_id(self) -> int | None:
        """Mengembalikan ID nota yang dipilih pengguna.

        Returns:
            ID pembelian atau None jika tidak ada yang dipilih.
        """
        return self._selected_purchase_id


class EditSellingPriceDialog(QDialog):
    """Dialog penyesuaian harga jual varian satuan barang langsung saat kulakan."""

    def __init__(
        self,
        item_name: str,
        units: list[ItemUnitOption],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi EditSellingPriceDialog.

        Args:
            item_name: Nama barang yang sedang diedit harga jualnya.
            units: Daftar varian satuan milik barang tersebut.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._spin_by_unit_id: dict[int, CurrencySpinBox] = {}
        self.setWindowTitle(f"Ubah Harga Jual - {item_name}")
        self.setMinimumWidth(460)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"Sesuaikan Harga Jual: {item_name}", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Perbarui harga jual apabila harga modal dari supplier mengalami perubahan.",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        for unit in units:
            spin = CurrencySpinBox(parent=card)
            spin.setValue(max(0, unit["selling_price"]))
            spin.setFixedHeight(32)
            label_text = (
                f"{unit['variant_name']} (x{format_quantity(unit['conversion_qty'])})  "
                f"[Modal akhir: {format_rupiah(unit['last_unit_cost'])}]"
            )
            form.addRow(label_text, spin)
            self._spin_by_unit_id[unit["item_unit_id"]] = spin

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Simpan Harga Jual", self)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def get_updated_prices(self) -> dict[int, int]:
        """Mengembalikan peta item_unit_id ke harga jual terbaru hasil input pengguna.

        Returns:
            Dictionary item_unit_id -> selling_price.
        """
        return {
            unit_id: spin.value() for unit_id, spin in self._spin_by_unit_id.items()
        }


class TambahStokController(QObject):
    """Controller yang menghubungkan seluruh sinyal TambahStokPage ke TambahStokService.

    Attributes:
        page: Instance TambahStokPage yang dikendalikan.
        service: Instance TambahStokService untuk operasi SQLite atomik.
    """

    def __init__(
        self,
        page: TambahStokPage,
        service: TambahStokService | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Menginisialisasi TambahStokController, memasang sinyal, dan memuat data awal.

        Args:
            page: Halaman UI TambahStokPage target.
            service: Instance layanan basis data; default membuat TambahStokService baru.
            parent: QObject induk opsional.
        """
        super().__init__(parent if parent is not None else page)
        self.page: TambahStokPage = page
        self.service: TambahStokService = (
            service if service is not None else TambahStokService()
        )
        self._active_draft_id: int | None = None
        self._last_history_filter: HistoryFilterPayload = {
            "search": "",
            "payment_status": "ALL",
            "date_from": QDate.currentDate().addMonths(-1).toString("yyyy-MM-dd"),
            "date_to": QDate.currentDate().toString("yyyy-MM-dd"),
        }

        self._connect_page_signals()
        self.load_initial_data()

    def _connect_page_signals(self) -> None:
        """Menghubungkan seluruh sinyal publik TambahStokPage ke slot controller."""
        self.page.submit_purchase_requested.connect(self._handle_submit_purchase)
        self.page.save_draft_requested.connect(self._handle_save_draft)
        self.page.add_supplier_requested.connect(self._handle_add_supplier)
        self.page.generate_invoice_requested.connect(self._handle_generate_invoice)
        self.page.bulk_picker_requested.connect(self._handle_bulk_picker)
        self.page.repeat_order_requested.connect(self._handle_repeat_order)
        self.page.import_csv_requested.connect(self._handle_import_csv)
        self.page.edit_selling_price_requested.connect(self._handle_edit_selling_price)
        self.page.history_filter_changed.connect(self._handle_history_filter_changed)
        self.page.history_refresh_requested.connect(self.refresh_history)
        self.page.history_detail_requested.connect(self._handle_history_detail)
        self.page.history_payment_requested.connect(self._handle_history_payment)
        self.page.history_duplicate_requested.connect(self._handle_history_duplicate)
        self.page.reset_form_btn.clicked.connect(self._clear_active_draft)

    def _clear_active_draft(self) -> None:
        """Menghapus penanda ID draft aktif saat formulir direset pengguna."""
        self._active_draft_id = None

    def load_initial_data(self) -> None:
        """Memuat supplier aktif, katalog barang, nomor faktur awal, dan riwayat kulakan."""
        try:
            self.refresh_suppliers()
            self.refresh_catalog()
            self.page.set_invoice_number(self.service.generate_next_invoice_number())
            self.refresh_history()
        except Exception as exc:
            logger.exception("Gagal memuat data awal halaman Tambah Stok")
            self.page.show_status_banner(
                f"Gagal memuat data database: {exc}",
                level="error",
                duration_ms=7000,
            )

    def refresh_suppliers(self, selected_id: int | None = None) -> None:
        """Memuat ulang daftar supplier aktif ke dropdown header nota.

        Args:
            selected_id: ID supplier yang ingin langsung dipilih opsional.
        """
        suppliers = self.service.get_active_suppliers()
        self.page.set_suppliers(suppliers, selected_id=selected_id)

    def refresh_catalog(self) -> None:
        """Memuat ulang katalog barang aktif, stok FIFO terkini, dan harga beli terakhir."""
        catalog = self.service.get_catalog_items()
        self.page.set_catalog_items(catalog)

    def refresh_history(self) -> None:
        """Memuat ulang tabel riwayat kulakan dan kartu KPI sesuai filter terakhir."""
        try:
            rows = self.service.get_purchase_history(self._last_history_filter)
            self.page.set_purchase_history(rows)
        except Exception as exc:
            logger.exception("Gagal memuat riwayat pembelian")
            self.page.show_status_banner(
                f"Gagal memuat riwayat pembelian: {exc}",
                level="error",
            )

    def _coerce_purchase_payload(self, raw: dict[str, Any]) -> PurchasePayload:
        """Mengonversi dictionary dari sinyal Qt menjadi PurchasePayload bertipe ketat.

        Args:
            raw: Dictionary mentah hasil pancaran sinyal submit atau draft.

        Returns:
            Objek PurchasePayload siap diteruskan ke TambahStokService.
        """
        raw_details = raw.get("details", [])
        details: list[PurchaseLinePayload] = []
        if isinstance(raw_details, list):
            for entry in raw_details:
                if not isinstance(entry, dict):
                    continue
                details.append(
                    {
                        "item_id": int(entry.get("item_id", 0)),
                        "item_unit_id": int(entry.get("item_unit_id", 0)),
                        "quantity": float(entry.get("quantity", 0.0)),
                        "conversion_qty": float(entry.get("conversion_qty", 1.0)),
                        "base_quantity": float(entry.get("base_quantity", 0.0)),
                        "unit_cost": float(entry.get("unit_cost", 0.0)),
                        "subtotal": float(entry.get("subtotal", 0.0)),
                    }
                )

        raw_supplier = raw.get("supplier_id")
        supplier_id = int(raw_supplier) if isinstance(raw_supplier, int) else None
        raw_due = raw.get("due_date")
        due_date = str(raw_due) if isinstance(raw_due, str) and raw_due else None
        raw_ref = raw.get("reference_number")
        reference_number = str(raw_ref) if isinstance(raw_ref, str) and raw_ref else None

        return {
            "invoice_number": str(raw.get("invoice_number", "")),
            "supplier_id": supplier_id,
            "purchase_date": str(raw.get("purchase_date", "")),
            "subtotal": int(raw.get("subtotal", 0)),
            "discount": int(raw.get("discount", 0)),
            "total": int(raw.get("total", 0)),
            "payment_method": str(raw.get("payment_method", "Tunai")),
            "amount_paid": int(raw.get("amount_paid", 0)),
            "remaining_amount": int(raw.get("remaining_amount", 0)),
            "payment_status": str(raw.get("payment_status", "PAID")),
            "due_date": due_date,
            "status": str(raw.get("status", "COMPLETED")),
            "notes": str(raw.get("notes", "")),
            "reference_number": reference_number,
            "details": details,
        }

    def _handle_submit_purchase(self, raw_payload: dict[str, Any]) -> None:
        """Menangani penyimpanan transaksi kulakan final dan pembaruan stok FIFO.

        Args:
            raw_payload: Dictionary data nota dari sinyal submit_purchase_requested.
        """
        try:
            payload = self._coerce_purchase_payload(raw_payload)
            result = self.service.record_purchase(
                payload=payload,
                draft_purchase_id=self._active_draft_id,
            )
            self._active_draft_id = None
            self.refresh_catalog()
            self.refresh_history()
            self.page.reset_form(keep_supplier=False)
            self.page.set_invoice_number(self.service.generate_next_invoice_number())

            status_desc = (
                "LUNAS"
                if result["payment_status"] == "PAID"
                else (
                    f"{result['payment_status']} "
                    f"(Sisa: {format_rupiah(result['remaining_amount'])})"
                )
            )
            self.page.show_status_banner(
                f"Kulakan {result['invoice_number']} berhasil disimpan! "
                f"{result['layers_created']} layer stok FIFO ditambahkan • Status: {status_desc}.",
                level="success",
                duration_ms=6000,
            )
        except (ValueError, sqlite3.Error, RuntimeError) as exc:
            logger.exception("Gagal menyimpan transaksi kulakan")
            self.page.show_status_banner(
                f"Gagal menyimpan kulakan: {exc}",
                level="error",
                duration_ms=7000,
            )

    def _handle_save_draft(self, raw_payload: dict[str, Any]) -> None:
        """Menangani penyimpanan daftar belanja sebagai DRAFT tanpa mengubah stok FIFO.

        Args:
            raw_payload: Dictionary data nota dari sinyal save_draft_requested.
        """
        try:
            payload = self._coerce_purchase_payload(raw_payload)
            result = self.service.save_purchase_draft(
                payload=payload,
                draft_purchase_id=self._active_draft_id,
            )
            self._active_draft_id = None
            self.refresh_history()
            self.page.reset_form(keep_supplier=False)
            self.page.set_invoice_number(self.service.generate_next_invoice_number())
            self.page.show_status_banner(
                f"Draft {result['invoice_number']} tersimpan (stok FIFO belum ditambahkan).",
                level="info",
                duration_ms=5000,
            )
        except (ValueError, sqlite3.Error, RuntimeError) as exc:
            logger.exception("Gagal menyimpan draft kulakan")
            self.page.show_status_banner(
                f"Gagal menyimpan draft: {exc}",
                level="error",
                duration_ms=6000,
            )

    def _handle_add_supplier(self) -> None:
        """Membuka dialog tambah supplier baru dan langsung memilihnya pada header nota."""
        dialog = QuickSupplierDialog(parent=self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, phone, address = dialog.get_values()
        try:
            created = self.service.create_supplier(name=name, phone=phone, address=address)
            self.refresh_suppliers(selected_id=created["id"])
            self.page.show_status_banner(
                f"Supplier '{created['name']}' berhasil ditambahkan.",
                level="success",
            )
        except (ValueError, sqlite3.Error, RuntimeError) as exc:
            logger.exception("Gagal menambah supplier baru")
            self.page.show_status_banner(f"Gagal menambah supplier: {exc}", level="error")

    def _handle_generate_invoice(self) -> None:
        """Mengisi nomor faktur berurutan terbaru dari database ke header nota."""
        try:
            next_inv = self.service.generate_next_invoice_number()
            self.page.set_invoice_number(next_inv)
        except sqlite3.Error as exc:
            logger.exception("Gagal menghasilkan nomor faktur otomatis")
            self.page.show_status_banner(
                f"Gagal membuat nomor faktur otomatis: {exc}",
                level="error",
            )

    def _handle_bulk_picker(self) -> None:
        """Membuka dialog Pilih Banyak Barang dan memasukkan item tercentang ke grid."""
        try:
            bulk_items = self.service.get_bulk_catalog_items()
        except sqlite3.Error as exc:
            logger.exception("Gagal memuat katalog untuk Bulk Picker")
            self.page.show_status_banner(f"Gagal memuat katalog: {exc}", level="error")
            return

        dialog = BulkItemPickerDialog(items=bulk_items, parent=self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_items = dialog.get_selected_items()
        if selected_items:
            self.page.add_items_bulk(selected_items)

    def _handle_repeat_order(self) -> None:
        """Membuka dialog pilih nota lama atau draft lalu memuatnya ke keranjang."""
        try:
            recent_rows = self.service.get_purchase_history(filter_payload=None)
        except sqlite3.Error as exc:
            logger.exception("Gagal memuat daftar nota untuk Ulang Nota")
            self.page.show_status_banner(f"Gagal memuat daftar nota: {exc}", level="error")
            return

        if not recent_rows:
            self.page.show_status_banner(
                "Belum ada riwayat nota pembelian yang dapat dimuat ulang.",
                level="warning",
            )
            return

        dialog = RepeatOrderDialog(history_rows=recent_rows, parent=self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        purchase_id = dialog.get_selected_purchase_id()
        if purchase_id is not None:
            self._handle_history_duplicate(purchase_id)

    def _handle_import_csv(self) -> None:
        """Membuka file chooser CSV dan memasukkan baris kulakan yang cocok ke grid."""
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self.page,
            "Import Daftar Kulakan (CSV)",
            "",
            "File CSV (*.csv);;Semua File (*.*)",
        )
        if not file_path:
            return

        try:
            catalog_items = self.service.get_catalog_items()
            summary = self.service.parse_csv_purchase_file(file_path, catalog_items)
        except Exception as exc:
            logger.exception("Gagal membaca file CSV kulakan")
            self.page.show_status_banner(f"Gagal membaca file CSV: {exc}", level="error")
            return

        matched = summary["matched_rows"]
        skipped = summary["skipped_reasons"]
        if not matched:
            reason_hint = skipped[0] if skipped else "Format kolom SKU tidak ditemukan."
            self.page.show_status_banner(
                f"Tidak ada baris yang dapat diimpor. {reason_hint}",
                level="warning",
                duration_ms=6000,
            )
            return

        first_row = -1
        for item, qty, unit_id, unit_cost in matched:
            row_idx = self.page.add_item_to_cart(
                item=item,
                quantity=qty,
                item_unit_id=unit_id,
                unit_cost=unit_cost,
                focus_qty=False,
            )
            if first_row < 0 and row_idx >= 0:
                first_row = row_idx

        if skipped:
            self.page.show_status_banner(
                f"{len(matched)} item diimpor, {len(skipped)} baris dilewati ({skipped[0]}).",
                level="warning",
                duration_ms=6000,
            )
        else:
            self.page.show_status_banner(
                f"{len(matched)} item berhasil diimpor dari CSV ke keranjang.",
                level="success",
            )
        self.page.focus_cart_grid()

    def _handle_edit_selling_price(self, item_id: int) -> None:
        """Membuka dialog ubah harga jual item_units dan memperbarui katalog.

        Args:
            item_id: ID barang yang tombol ubah harganya ditekan pada grid.
        """
        try:
            item_name, units = self.service.get_item_selling_units(item_id)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat varian harga jual barang")
            self.page.show_status_banner(f"Gagal memuat harga jual: {exc}", level="error")
            return

        dialog = EditSellingPriceDialog(item_name=item_name, units=units, parent=self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            updated = self.service.update_selling_prices(dialog.get_updated_prices())
            self.refresh_catalog()
            self.page.show_status_banner(
                f"Harga jual '{item_name}' diperbarui ({updated} varian satuan).",
                level="success",
            )
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Gagal memperbarui harga jual barang")
            self.page.show_status_banner(
                f"Gagal menyimpan harga jual: {exc}",
                level="error",
            )

    def _handle_history_filter_changed(self, raw_filter: dict[str, Any]) -> None:
        """Menyimpan kriteria filter riwayat terbaru dan menyegarkan tabel riwayat.

        Args:
            raw_filter: Dictionary kriteria filter dari Tab 2.
        """
        self._last_history_filter = {
            "search": str(raw_filter.get("search", "")),
            "payment_status": str(raw_filter.get("payment_status", "ALL")),
            "date_from": str(raw_filter.get("date_from", "")),
            "date_to": str(raw_filter.get("date_to", "")),
        }
        self.refresh_history()

    def _handle_history_detail(self, purchase_id: int) -> None:
        """Menampilkan dialog rincian barang dan riwayat cicilan untuk satu nota.

        Args:
            purchase_id: ID nota pembelian yang dipilih di Tab 2.
        """
        try:
            bundle = self.service.get_purchase_detail_bundle(purchase_id)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat detail nota pembelian")
            self.page.show_status_banner(f"Gagal memuat detail nota: {exc}", level="error")
            return

        dialog = PurchaseDetailDialog(bundle=bundle, parent=self.page)
        dialog.exec()
        if dialog.pay_requested:
            self._handle_history_payment(purchase_id)

    def _handle_history_payment(self, purchase_id: int) -> None:
        """Membuka dialog pelunasan hutang supplier dan mengeksekusi pembayaran atomik.

        Args:
            purchase_id: ID nota pembelian yang akan dibayarkan cicilan atau pelunasannya.
        """
        try:
            bundle = self.service.get_purchase_detail_bundle(purchase_id)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat data hutang nota")
            self.page.show_status_banner(f"Gagal memuat data hutang: {exc}", level="error")
            return

        if bundle["status"] != "COMPLETED":
            self.page.show_status_banner(
                "Nota masih berstatus DRAFT. Muat ulang dan simpan stok terlebih dahulu.",
                level="warning",
            )
            return

        if bundle["remaining_amount"] <= 0 or bundle["payment_status"] == "PAID":
            self.page.show_status_banner("Nota pembelian ini sudah berstatus LUNAS.", level="info")
            return

        dialog = PurchasePaymentDialog(bundle=bundle, parent=self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        amount, method, pay_date, ref_num, notes = dialog.get_payment_data()
        try:
            result = self.service.record_purchase_payment(
                purchase_id=purchase_id,
                amount=amount,
                payment_method=method,
                payment_date=pay_date,
                reference_number=ref_num,
                notes=notes,
            )
            self.refresh_history()
            status_msg = (
                "LUNAS"
                if result["payment_status"] == "PAID"
                else f"Sisa Hutang: {format_rupiah(result['remaining_amount'])}"
            )
            self.page.show_status_banner(
                f"Pembayaran {format_rupiah(result['paid_this_time'])} untuk "
                f"{result['invoice_number']} berhasil dicatat • {status_msg}.",
                level="success",
                duration_ms=6000,
            )
        except (ValueError, sqlite3.Error, RuntimeError) as exc:
            logger.exception("Gagal mencatat pelunasan hutang supplier")
            self.page.show_status_banner(
                f"Gagal mencatat pembayaran: {exc}",
                level="error",
                duration_ms=6500,
            )

    def _handle_history_duplicate(self, purchase_id: int) -> None:
        """Memuat ulang item dari nota lama atau membuka draft ke keranjang belanja.

        Args:
            purchase_id: ID nota pembelian yang akan disalin atau dilanjutkan.
        """
        try:
            payload, original_status = self.service.build_purchase_payload_from_id(
                purchase_id=purchase_id,
                as_duplicate=True,
            )
            catalog_items = self.service.get_catalog_items()
            catalog_map = {item["item_id"]: item for item in catalog_items}
            self.page.set_catalog_items(catalog_items)
            self._active_draft_id = purchase_id if original_status == "DRAFT" else None
            self.page.load_purchase_into_form(payload, catalog_map=catalog_map)
        except (ValueError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat ulang nota pembelian")
            self.page.show_status_banner(
                f"Gagal memuat ulang nota: {exc}",
                level="error",
            )
