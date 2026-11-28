"""Modul untuk inisialisasi database pengguna SQLite.

Modul ini bertanggung jawab untuk membuat dan memverifikasi eksistensi
database serta tabel-tabel yang diperlukan untuk sistem autentikasi.
"""

from contextlib import closing
import logging
from pathlib import Path
from typing import Optional

from sqlcipher3 import dbapi2 as sqlite3

from config import DEFAULT_DB_PATH
from util.helper.database.db_connection import create_sqlite_connection

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Kelas untuk mengelola inisialisasi database pengguna.

    Attributes:
        db_path (Path): Lokasi path file database SQLite.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Inisialisasi instance DatabaseInitializer.

        Args:
            db_path: Path file database. Default menggunakan DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def _check_db_exists(self) -> bool:
        """Memeriksa apakah file database sudah ada di sistem file.

        Returns:
            bool: True jika database sudah ada, False jika belum.
        """
        exists = self.db_path.exists()
        if exists:
            logger.debug("Database ditemukan di: %s", self.db_path)
        else:
            logger.info("Database belum ada. Akan membuat baru di: %s", self.db_path)
        return exists

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Membuat tabel-tabel yang diperlukan jika belum ada.

        Args:
            conn (sqlite3.Connection): Objek koneksi ke database SQLite.
        """
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                key_hash BLOB NOT NULL,
                key_salt BLOB NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_lockout (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                failed_attempts INTEGER DEFAULT 0,
                lock_count INTEGER DEFAULT 0,
                locked_until INTEGER DEFAULT 0,
                last_failed_at INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        conn.commit()
        logger.info("Verifikasi dan pembuatan tabel selesai")

    def _initialize_default_data(self, conn: sqlite3.Connection) -> None:
        """Mengisi data default (seeder) yang diperlukan oleh sistem.

        Args:
            conn (sqlite3.Connection): Objek koneksi ke database SQLite.
        """
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO system_lockout 
            (id, failed_attempts, lock_count, locked_until, last_failed_at)
            VALUES (1, 0, 0, 0, 0)
        """)

        default_settings = [
            ("max_failed_attempts", "3"),
            ("base_lockout_seconds", "60")
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        """, default_settings)

        conn.commit()
        logger.info("Inisialisasi data default selesai")

    def _tables_exist(self, conn: sqlite3.Connection) -> bool:
        """Memeriksa apakah semua tabel yang diperlukan sudah ada di database.

        Args:
            conn (sqlite3.Connection): Objek koneksi ke database SQLite.

        Returns:
            bool: True jika semua tabel sudah ada, False jika ada yang belum.
        """
        required_tables = {"users", "system_lockout", "login_logs", "settings"}
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
        missing = required_tables - existing_tables

        if missing:
            logger.info("Tabel belum lengkap. Tabel yang belum ada: %s", missing)
            return False

        logger.debug("Semua tabel sudah ada di database")
        return True

    def _default_data_exists(self, conn: sqlite3.Connection) -> bool:
        """Memeriksa apakah data default (seeder) sudah ada di database.

        Args:
            conn (sqlite3.Connection): Objek koneksi ke database SQLite.

        Returns:
            bool: True jika semua data default sudah ada, False jika belum.
        """
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM system_lockout WHERE id = 1"
        )
        if cursor.fetchone()[0] == 0:
            logger.debug("Data default system_lockout belum ada")
            return False

        required_keys = {"max_failed_attempts", "base_lockout_seconds"}
        cursor.execute("SELECT key FROM settings")
        existing_keys = {row[0] for row in cursor.fetchall()}
        missing_keys = required_keys - existing_keys

        if missing_keys:
            logger.debug("Data default settings belum lengkap. Key belum ada: %s", missing_keys)
            return False

        logger.debug("Semua data default sudah ada di database")
        return True

    def initialize(self) -> None:
        """Mengeksekusi seluruh proses inisialisasi database.
        
        Meliputi verifikasi file, pembuatan tabel, dan pengisian data default.
        Jika tabel sudah ada, pembuatan tabel dilewati.
        Jika data default sudah ada, pengisian data default dilewati.
        """
        self._check_db_exists()
        
        try:
            with closing(
                create_sqlite_connection(
                    self.db_path,
                    require_exists=False,
                    row_factory=False,
                    foreign_keys=True,
                )
            ) as conn:
                
                if not self._tables_exist(conn):
                    self._create_tables(conn)
                else:
                    logger.debug("Pembuatan tabel dilewati — semua tabel sudah ada")

                if not self._default_data_exists(conn):
                    self._initialize_default_data(conn)
                else:
                    logger.debug("Pengisian data default dilewati — semua data sudah ada")
                
            logger.info("Proses inisialisasi database berhasil secara keseluruhan")
            
        except sqlite3.Error:
            logger.exception("Terjadi kesalahan pada database SQLite")
        except Exception:
            logger.exception("Terjadi kesalahan sistem")
