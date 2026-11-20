"""Modul inisialisasi database transaksi dan inventaris FIFO berbasis SQLite.

Modul ini bertanggung jawab untuk memverifikasi keberadaan file database,
memeriksa kelengkapan tabel, serta membuat struktur tabel dan indeks yang
diperlukan untuk operasional transaksi (pembelian, penjualan, jasa) dan
pelacakan stok menggunakan metode FIFO (First-In, First-Out).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class TransaksiDatabaseInitializer:
    """Mengelola verifikasi awal dan inisialisasi skema database transaksi FIFO.

    Attributes:
        db_path (Path): Lokasi path file database SQLite.
    """

    TABLE_SCHEMAS: dict[str, str] = {
        "categories": """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                parent_id INTEGER NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                FOREIGN KEY (parent_id) REFERENCES categories(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "units": """
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL UNIQUE
            );
        """,
        "items": """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                base_unit_id INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (category_id) REFERENCES categories(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (base_unit_id) REFERENCES units(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "item_units": """
            CREATE TABLE IF NOT EXISTS item_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                variant_name TEXT NOT NULL,
                conversion_qty REAL NOT NULL CHECK (conversion_qty > 0),
                selling_price INTEGER NOT NULL DEFAULT 0 CHECK (selling_price >= 0),
                is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                UNIQUE (item_id, variant_name),
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (unit_id) REFERENCES units(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "services": """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                selling_price INTEGER NOT NULL DEFAULT 0 CHECK (selling_price >= 0),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        """,
        "service_materials": """
            CREATE TABLE IF NOT EXISTS service_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                UNIQUE (service_id, item_id),
                FOREIGN KEY (service_id) REFERENCES services(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "suppliers": """
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            );
        """,
        "purchases": """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                supplier_id INTEGER NULL,
                purchase_date TEXT NOT NULL,
                subtotal INTEGER NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
                discount INTEGER NOT NULL DEFAULT 0 CHECK (discount >= 0),
                total INTEGER NOT NULL DEFAULT 0 CHECK (total >= 0),
                status TEXT NOT NULL DEFAULT 'COMPLETED',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                UNIQUE (supplier_id, invoice_number),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "purchase_details": """
            CREATE TABLE IF NOT EXISTS purchase_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_unit_id INTEGER NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                conversion_qty REAL NOT NULL CHECK (conversion_qty > 0),
                base_quantity REAL NOT NULL CHECK (base_quantity > 0),
                -- Harga beli per satuan beli (item_unit_id).
                unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                subtotal REAL NOT NULL CHECK (subtotal >= 0),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (purchase_id) REFERENCES purchases(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_unit_id) REFERENCES item_units(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "customers": """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            );
        """,
        "sales": """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                customer_id INTEGER NULL,
                sale_date TEXT NOT NULL,
                subtotal INTEGER NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
                discount INTEGER NOT NULL DEFAULT 0 CHECK (discount >= 0),
                total INTEGER NOT NULL DEFAULT 0 CHECK (total >= 0),
                status TEXT NOT NULL DEFAULT 'COMPLETED',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "sale_details": """
            CREATE TABLE IF NOT EXISTS sale_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                line_type TEXT NOT NULL CHECK (line_type IN ('ITEM', 'SERVICE')),
                item_id INTEGER NULL,
                service_id INTEGER NULL,
                item_unit_id INTEGER NULL,
                description TEXT NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                conversion_qty REAL NULL,
                base_quantity REAL NULL,
                unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
                subtotal INTEGER NOT NULL CHECK (subtotal >= 0),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (sale_id) REFERENCES sales(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (service_id) REFERENCES services(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_unit_id) REFERENCES item_units(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "sale_detail_materials": """
            CREATE TABLE IF NOT EXISTS sale_detail_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_detail_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity_per_service REAL NOT NULL CHECK (quantity_per_service > 0),
                service_quantity REAL NOT NULL CHECK (service_quantity > 0),
                total_quantity REAL NOT NULL CHECK (total_quantity > 0),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (sale_detail_id) REFERENCES sale_details(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "inventory_layers": """
            CREATE TABLE IF NOT EXISTS inventory_layers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'PURCHASE'
                    CHECK (source_type IN (
                        'PURCHASE', 'OPENING_STOCK', 'ADJUSTMENT_IN', 'SALES_RETURN'
                    )),
                purchase_detail_id INTEGER NULL,
                received_qty REAL NOT NULL CHECK (received_qty > 0),
                remaining_qty REAL NOT NULL
                    CHECK (remaining_qty >= 0 AND remaining_qty <= received_qty),
                -- Harga modal per satuan dasar (base_unit) dalam presisi desimal.
                unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                received_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (purchase_detail_id) REFERENCES purchase_details(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "stock_movements": """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                purchase_detail_id INTEGER NULL,
                sale_detail_id INTEGER NULL,
                sale_detail_material_id INTEGER NULL,
                quantity_in REAL NOT NULL DEFAULT 0 CHECK (quantity_in >= 0),
                quantity_out REAL NOT NULL DEFAULT 0 CHECK (quantity_out >= 0),
                movement_date TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (item_id) REFERENCES items(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (purchase_detail_id) REFERENCES purchase_details(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (sale_detail_id) REFERENCES sale_details(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (sale_detail_material_id) REFERENCES sale_detail_materials(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
        "stock_issue_allocations": """
            CREATE TABLE IF NOT EXISTS stock_issue_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_movement_id INTEGER NOT NULL,
                inventory_layer_id INTEGER NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                subtotal_cost REAL NOT NULL CHECK (subtotal_cost >= 0),
                FOREIGN KEY (stock_movement_id) REFERENCES stock_movements(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION,
                FOREIGN KEY (inventory_layer_id) REFERENCES inventory_layers(id)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
            );
        """,
    }

    INDEX_STATEMENTS: list[str] = [
        """
        CREATE INDEX IF NOT EXISTS idx_inventory_layers_fifo
        ON inventory_layers (item_id, received_at, id)
        WHERE remaining_qty > 0;
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_stock_movements_item_date
        ON stock_movements (item_id, movement_date, id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_stock_issue_allocations_movement
        ON stock_issue_allocations (stock_movement_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_stock_issue_allocations_layer
        ON stock_issue_allocations (inventory_layer_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_purchase_details_purchase_id
        ON purchase_details (purchase_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sale_details_sale_id
        ON sale_details (sale_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sale_detail_materials_sale_detail_id
        ON sale_detail_materials (sale_detail_id);
        """,
    ]

    def __init__(self, db_path: str | Path = "data/transaksi.db") -> None:
        """Menginisialisasi instance dengan lokasi file database.

        Args:
            db_path: Path menuju file database SQLite. Default 'data/transaksi.db'.
        """
        self.db_path: Path = Path(db_path)

    def check_database_exists(self) -> bool:
        """Memverifikasi apakah file database sudah ada di penyimpanan.

        Returns:
            True jika file database sudah ada dan berupa file valid, False jika belum.
        """
        exists = self.db_path.exists() and self.db_path.is_file()
        if exists:
            logger.debug("Database ditemukan di: %s", self.db_path)
        else:
            logger.info("Database belum ada. Akan membuat baru di: %s", self.db_path)
        return exists

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi ke database SQLite dengan pengaturan integritas aktif.

        Returns:
            Objek koneksi sqlite3 dengan foreign_keys dan WAL mode aktif.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def get_existing_tables(self, conn: sqlite3.Connection) -> set[str]:
        """Mengambil daftar nama tabel yang saat ini sudah ada di database.

        Args:
            conn: Koneksi aktif ke database SQLite.

        Returns:
            Himpunan (set) nama tabel yang sudah terbentuk di database.
        """
        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%';
            """
        )
        return {row[0] for row in cursor.fetchall()}

    def verify_tables(self, conn: sqlite3.Connection) -> dict[str, list[str]]:
        """Memverifikasi tabel mana saja yang sudah ada dan mana yang belum.

        Args:
            conn: Koneksi aktif ke database SQLite.

        Returns:
            Dictionary berisi dua list:
                - 'existing': daftar tabel yang sudah ada.
                - 'missing': daftar tabel yang belum ada sesuai urutan pembuatan.
        """
        existing_set = self.get_existing_tables(conn)
        expected_order = list(self.TABLE_SCHEMAS.keys())

        existing = [name for name in expected_order if name in existing_set]
        missing = [name for name in expected_order if name not in existing_set]

        return {"existing": existing, "missing": missing}

    def initialize(self) -> dict[str, Any]:
        """Menjalankan verifikasi awal dan membuat database/tabel yang belum ada.

        Alur kerja:
            1. Memeriksa apakah file database sudah ada atau belum.
            2. Membuat direktori induk jika belum tersedia.
            3. Memeriksa kelengkapan tabel yang sudah ada di dalam database.
            4. Membuat tabel yang masih kurang serta seluruh indeks FIFO.
            5. Memverifikasi ulang kelengkapan seluruh tabel setelah eksekusi.

        Returns:
            Dictionary berisi ringkasan hasil verifikasi dan inisialisasi.

        Raises:
            sqlite3.Error: Jika terjadi kegagalan saat eksekusi DDL SQLite.
        """
        try:
            db_existed = self.check_database_exists()
            if not db_existed:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

            created_tables: list[str] = []

            with self._connect() as conn:
                table_check_before = self.verify_tables(conn)
                existing_before = table_check_before["existing"]
                missing_before = table_check_before["missing"]

                if not missing_before:
                    logger.debug(
                        "Semua %d tabel sudah ada di database",
                        len(existing_before),
                    )
                else:
                    logger.info(
                        "Tabel belum lengkap. %d tabel sudah ada, %d tabel belum ada: %s",
                        len(existing_before),
                        len(missing_before),
                        ", ".join(missing_before),
                    )
                    for table_name in missing_before:
                        conn.execute(self.TABLE_SCHEMAS[table_name])
                        created_tables.append(table_name)
                        logger.info("Tabel '%s' berhasil dibuat", table_name)

                for index_sql in self.INDEX_STATEMENTS:
                    conn.execute(index_sql)

                conn.commit()

                if created_tables:
                    logger.info("Verifikasi dan pembuatan tabel selesai")

                table_check_after = self.verify_tables(conn)
                is_ready = len(table_check_after["missing"]) == 0

            logger.info("Proses inisialisasi database transaksi berhasil secara keseluruhan")

            return {
                "db_path": str(self.db_path.resolve()),
                "db_existed": db_existed,
                "existing_tables_before": existing_before,
                "created_tables": created_tables,
                "missing_tables_after": table_check_after["missing"],
                "total_tables": len(table_check_after["existing"]),
                "is_ready": is_ready,
            }
        except sqlite3.Error:
            logger.exception("Terjadi kesalahan pada database SQLite")
            raise
        except Exception:
            logger.exception("Terjadi kesalahan sistem")
            raise


def init_transaksi_database(db_path: str | Path = "data/transaksi.db") -> dict[str, Any]:
    """Fungsi helper untuk menjalankan inisialisasi database transaksi.

    Args:
        db_path: Path menuju file database SQLite. Default 'data/transaksi.db'.

    Returns:
        Ringkasan hasil verifikasi dan inisialisasi database.
    """
    initializer = TransaksiDatabaseInitializer(db_path=db_path)
    return initializer.initialize()


if __name__ == "__main__":
    import sys

    # Memastikan root proyek berada di sys.path saat dieksekusi langsung
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.logging_config import setup_logging

    setup_logging()
    target_db = sys.argv[1] if len(sys.argv) > 1 else "data/transaksi.db"
    init_transaksi_database(db_path=target_db)

