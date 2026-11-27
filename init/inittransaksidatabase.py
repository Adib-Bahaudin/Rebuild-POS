"""Modul inisialisasi database transaksi dan inventaris FIFO berbasis SQLite.

Modul ini bertanggung jawab untuk memverifikasi keberadaan file database,
memeriksa kelengkapan tabel, melakukan migrasi skema secara aman, serta membuat
struktur tabel, indeks, dan trigger yang diperlukan untuk operasional transaksi
(pembelian, penjualan lunas/cicilan/tempo, jasa) dan pelacakan stok FIFO.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

from config import DEFAULT_DB_PATH
from util.helper.db_connection import create_sqlite_connection

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
                payment_method TEXT NOT NULL DEFAULT 'Tunai',
                amount_paid INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
                remaining_amount INTEGER NOT NULL DEFAULT 0 CHECK (remaining_amount >= 0),
                payment_status TEXT NOT NULL DEFAULT 'PAID'
                    CHECK (payment_status IN ('PAID', 'PARTIAL', 'UNPAID')),
                due_date TEXT NULL,
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
        "purchase_payments": """
            CREATE TABLE IF NOT EXISTS purchase_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                amount INTEGER NOT NULL CHECK (amount > 0),
                payment_method TEXT NOT NULL DEFAULT 'Tunai',
                reference_number TEXT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (purchase_id) REFERENCES purchases(id)
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
                rounding INTEGER NOT NULL DEFAULT 0,
                tip INTEGER NOT NULL DEFAULT 0 CHECK (tip >= 0),
                total INTEGER NOT NULL DEFAULT 0 CHECK (total >= 0),
                payment_method TEXT NOT NULL DEFAULT 'Tunai',
                amount_paid INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
                remaining_amount INTEGER NOT NULL DEFAULT 0 CHECK (remaining_amount >= 0),
                change_amount INTEGER NOT NULL DEFAULT 0 CHECK (change_amount >= 0),
                payment_status TEXT NOT NULL DEFAULT 'PAID'
                    CHECK (payment_status IN ('PAID', 'PARTIAL', 'UNPAID')),
                due_date TEXT NULL,
                cashier_name TEXT NOT NULL DEFAULT 'KASIR',
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
        "sale_payments": """
            CREATE TABLE IF NOT EXISTS sale_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                amount INTEGER NOT NULL CHECK (amount > 0),
                tendered_amount INTEGER NOT NULL DEFAULT 0 CHECK (tendered_amount >= 0),
                change_given INTEGER NOT NULL DEFAULT 0 CHECK (change_given >= 0),
                payment_method TEXT NOT NULL DEFAULT 'Tunai',
                reference_number TEXT NULL,
                cashier_name TEXT NOT NULL DEFAULT 'KASIR',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (sale_id) REFERENCES sales(id)
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
        CREATE INDEX IF NOT EXISTS idx_purchase_payments_purchase_id
        ON purchase_payments (purchase_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_purchases_payment_status
        ON purchases (payment_status, due_date)
        WHERE payment_status IN ('UNPAID', 'PARTIAL');
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sale_details_sale_id
        ON sale_details (sale_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sale_detail_materials_sale_detail_id
        ON sale_detail_materials (sale_detail_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sale_payments_sale_id
        ON sale_payments (sale_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sales_payment_status
        ON sales (payment_status, due_date)
        WHERE payment_status IN ('UNPAID', 'PARTIAL');
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sales_customer_payment_status
        ON sales (customer_id, payment_status);
        """,
    ]

    TRIGGER_STATEMENTS: list[str] = [
        """
        CREATE TRIGGER IF NOT EXISTS trg_sales_after_insert_sync_payment
        AFTER INSERT ON sales
        BEGIN
            UPDATE sales
            SET remaining_amount = MAX(0, NEW.total - NEW.amount_paid),
                payment_status = CASE
                    WHEN NEW.amount_paid >= NEW.total THEN 'PAID'
                    WHEN NEW.amount_paid > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_sales_after_update_sync_payment
        AFTER UPDATE OF total, amount_paid ON sales
        BEGIN
            UPDATE sales
            SET remaining_amount = MAX(0, NEW.total - NEW.amount_paid),
                payment_status = CASE
                    WHEN NEW.amount_paid >= NEW.total THEN 'PAID'
                    WHEN NEW.amount_paid > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_sale_payments_after_insert
        AFTER INSERT ON sale_payments
        BEGIN
            UPDATE sales
            SET amount_paid = COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id
                ), 0),
                remaining_amount = MAX(0, total - COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id
                ), 0)),
                payment_status = CASE
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id), 0) >= total THEN 'PAID'
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id), 0) > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.sale_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_sale_payments_after_update
        AFTER UPDATE OF amount ON sale_payments
        BEGIN
            UPDATE sales
            SET amount_paid = COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id
                ), 0),
                remaining_amount = MAX(0, total - COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id
                ), 0)),
                payment_status = CASE
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id), 0) >= total THEN 'PAID'
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = NEW.sale_id), 0) > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.sale_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_sale_payments_after_delete
        AFTER DELETE ON sale_payments
        BEGIN
            UPDATE sales
            SET amount_paid = COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = OLD.sale_id
                ), 0),
                remaining_amount = MAX(0, total - COALESCE((
                    SELECT SUM(amount) FROM sale_payments WHERE sale_id = OLD.sale_id
                ), 0)),
                payment_status = CASE
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = OLD.sale_id), 0) >= total THEN 'PAID'
                    WHEN COALESCE((SELECT SUM(amount) FROM sale_payments WHERE sale_id = OLD.sale_id), 0) > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = OLD.sale_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_purchases_after_insert_sync_payment
        AFTER INSERT ON purchases
        BEGIN
            UPDATE purchases
            SET remaining_amount = MAX(0, NEW.total - NEW.amount_paid),
                payment_status = CASE
                    WHEN NEW.amount_paid >= NEW.total THEN 'PAID'
                    WHEN NEW.amount_paid > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_purchases_after_update_sync_payment
        AFTER UPDATE OF total, amount_paid ON purchases
        BEGIN
            UPDATE purchases
            SET remaining_amount = MAX(0, NEW.total - NEW.amount_paid),
                payment_status = CASE
                    WHEN NEW.amount_paid >= NEW.total THEN 'PAID'
                    WHEN NEW.amount_paid > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_purchase_payments_after_insert
        AFTER INSERT ON purchase_payments
        BEGIN
            UPDATE purchases
            SET amount_paid = COALESCE((
                    SELECT SUM(amount) FROM purchase_payments WHERE purchase_id = NEW.purchase_id
                ), 0),
                remaining_amount = MAX(0, total - COALESCE((
                    SELECT SUM(amount) FROM purchase_payments WHERE purchase_id = NEW.purchase_id
                ), 0)),
                payment_status = CASE
                    WHEN COALESCE((SELECT SUM(amount) FROM purchase_payments WHERE purchase_id = NEW.purchase_id), 0) >= total THEN 'PAID'
                    WHEN COALESCE((SELECT SUM(amount) FROM purchase_payments WHERE purchase_id = NEW.purchase_id), 0) > 0 THEN 'PARTIAL'
                    ELSE 'UNPAID'
                END
            WHERE id = NEW.purchase_id;
        END;
        """,
    ]

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Menginisialisasi instance TransaksiDatabaseInitializer.

        Args:
            db_path: Path file database SQLite. Default menggunakan DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def check_database_exists(self) -> bool:
        """Memeriksa apakah file database sudah tersedia pada path target.

        Returns:
            True jika file database sudah ada, False jika belum.
        """
        exists = self.db_path.exists() and self.db_path.is_file()
        if exists:
            logger.debug("Database ditemukan di: %s", self.db_path)
        else:
            logger.info("Database belum ada. Akan membuat baru di: %s", self.db_path)
        return exists

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite dengan dukungan foreign keys dan mode WAL.

        Returns:
            Objek koneksi sqlite3.Connection siap pakai.
        """
        return create_sqlite_connection(
            self.db_path,
            require_exists=False,
            row_factory=False,
            foreign_keys=True,
            wal_mode=True,
        )

    def get_existing_tables(self, conn: sqlite3.Connection) -> set[str]:
        """Mengambil seluruh nama tabel pengguna yang sudah ada di database.

        Args:
            conn: Koneksi sqlite3 aktif.

        Returns:
            Himpunan nama tabel yang tersedia.
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
        """Membandingkan tabel yang ada dengan daftar tabel skema yang diharapkan.

        Args:
            conn: Koneksi sqlite3 aktif.

        Returns:
            Dictionary berisi daftar tabel 'existing' dan 'missing'.
        """
        existing_set = self.get_existing_tables(conn)
        expected_order = list(self.TABLE_SCHEMAS.keys())

        existing = [name for name in expected_order if name in existing_set]
        missing = [name for name in expected_order if name not in existing_set]

        return {"existing": existing, "missing": missing}

    def _migrate_sales_columns(self, conn: sqlite3.Connection) -> None:
        """Memastikan kolom lama & baru pada tabel sales lengkap serta melakukan backfill data lama."""
        cursor = conn.execute("PRAGMA table_info(sales);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if not existing_cols:
            return

        added_cols: set[str] = set()
        column_defs = [
            ("rounding", "INTEGER NOT NULL DEFAULT 0"),
            ("tip", "INTEGER NOT NULL DEFAULT 0 CHECK (tip >= 0)"),
            ("payment_method", "TEXT NOT NULL DEFAULT 'Tunai'"),
            ("amount_paid", "INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid >= 0)"),
            ("remaining_amount", "INTEGER NOT NULL DEFAULT 0 CHECK (remaining_amount >= 0)"),
            ("change_amount", "INTEGER NOT NULL DEFAULT 0 CHECK (change_amount >= 0)"),
            (
                "payment_status",
                "TEXT NOT NULL DEFAULT 'PAID' CHECK (payment_status IN ('PAID', 'PARTIAL', 'UNPAID'))",
            ),
            ("due_date", "TEXT NULL"),
            ("cashier_name", "TEXT NOT NULL DEFAULT 'KASIR'"),
        ]
        for col_name, col_type in column_defs:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE sales ADD COLUMN {col_name} {col_type};")
                added_cols.add(col_name)
                logger.info("Kolom '%s' berhasil ditambahkan ke tabel sales", col_name)

        if {"remaining_amount", "payment_status"} & added_cols:
            conn.execute(
                """
                UPDATE sales
                SET remaining_amount = CASE
                        WHEN total > amount_paid THEN total - amount_paid
                        ELSE 0
                    END,
                    payment_status = CASE
                        WHEN amount_paid >= total THEN 'PAID'
                        WHEN amount_paid > 0 THEN 'PARTIAL'
                        ELSE 'UNPAID'
                    END;
                """
            )
            logger.info("Sinkronisasi data pelunasan transaksi lama pada tabel sales selesai")

    def _migrate_purchases_columns(self, conn: sqlite3.Connection) -> None:
        """Memastikan kolom pembayaran pada tabel purchases lengkap tanpa merusak data lama."""
        cursor = conn.execute("PRAGMA table_info(purchases);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if not existing_cols:
            return

        added_cols: set[str] = set()
        column_defs = [
            ("payment_method", "TEXT NOT NULL DEFAULT 'Tunai'"),
            ("amount_paid", "INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid >= 0)"),
            ("remaining_amount", "INTEGER NOT NULL DEFAULT 0 CHECK (remaining_amount >= 0)"),
            (
                "payment_status",
                "TEXT NOT NULL DEFAULT 'PAID' CHECK (payment_status IN ('PAID', 'PARTIAL', 'UNPAID'))",
            ),
            ("due_date", "TEXT NULL"),
        ]
        for col_name, col_type in column_defs:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE purchases ADD COLUMN {col_name} {col_type};")
                added_cols.add(col_name)
                logger.info("Kolom '%s' berhasil ditambahkan ke tabel purchases", col_name)

        if "amount_paid" in added_cols:
            conn.execute(
                """
                UPDATE purchases
                SET amount_paid = total,
                    remaining_amount = 0,
                    payment_status = 'PAID';
                """
            )
            logger.info("Sinkronisasi data pembayaran lama pada tabel purchases selesai")

    def initialize(self) -> dict[str, Any]:
        """Menjalankan verifikasi awal, migrasi kolom, dan pembuatan tabel/indeks/trigger."""
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

                self._migrate_sales_columns(conn)
                self._migrate_purchases_columns(conn)

                for index_sql in self.INDEX_STATEMENTS:
                    conn.execute(index_sql)

                for trigger_sql in self.TRIGGER_STATEMENTS:
                    conn.execute(trigger_sql)

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


def init_transaksi_database(
    db_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Menjalankan inisialisasi dan verifikasi skema database transaksi.

    Args:
        db_path: Path file database SQLite opsional.

    Returns:
        Dictionary ringkasan hasil inisialisasi dan verifikasi tabel.
    """
    initializer = TransaksiDatabaseInitializer(db_path=db_path)
    return initializer.initialize()