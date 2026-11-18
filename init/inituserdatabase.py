"""Modul untuk inisialisasi database pengguna SQLite.

Modul ini bertanggung jawab untuk membuat dan memverifikasi eksistensi
database serta tabel-tabel yang diperlukan untuk sistem autentikasi.
"""

import sqlite3
import os
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class DatabaseInitializer:
    """Kelas untuk mengelola inisialisasi database pengguna.

    Attributes:
        db_path (str): Lokasi path file database SQLite.
    """

    def __init__(self, db_path: str = "user_data.db"):
        """Inisialisasi instance DatabaseInitializer.

        Args:
            db_path (str): Path file database. Default ke 'user_data.db'.
        """
        self.db_path = db_path

    def _check_db_exists(self) -> bool:
        """Memeriksa apakah file database sudah ada di sistem file.

        Returns:
            bool: True jika database sudah ada, False jika belum.
        """
        exists = os.path.exists(self.db_path)
        if exists:
            logging.info(f"Database ditemukan di: {self.db_path}")
        else:
            logging.info(f"Database belum ada. Akan membuat baru di: {self.db_path}")
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
        logging.info("Verifikasi dan pembuatan tabel selesai.")

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
        logging.info("Inisialisasi data default selesai.")

    def initialize(self) -> None:
        """Mengeksekusi seluruh proses inisialisasi database.
        
        Meliputi verifikasi file, pembuatan tabel, dan pengisian data default.
        """
        self._check_db_exists()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                self._create_tables(conn)
                self._initialize_default_data(conn)
                
            logging.info("Proses inisialisasi database berhasil secara keseluruhan.")
            
        except sqlite3.Error as e:
            logging.error(f"Terjadi kesalahan pada database SQLite: {e}")
        except Exception as e:
            logging.error(f"Terjadi kesalahan sistem: {e}")
