"""Modul orkestrator untuk inisialisasi database secara menyeluruh.

Modul ini bertugas memeriksa dan menjalankan seluruh tugas inisialisasi
yang berhubungan dengan database, termasuk pembuatan tabel (inituserdatabase)
dan pembuatan super user pertama (initsuperuser), dengan melakukan
pengecekan kondisi database terlebih dahulu sebelum menjalankan setiap langkah.
"""

import sqlite3
import os
import logging

from init.inituserdatabase import DatabaseInitializer
from init.initsuperuser import run_superuser_in_cmd

logger = logging.getLogger(__name__)


class InitDatabase:
    """Orkestrator utama untuk seluruh proses inisialisasi database.

    Kelas ini mengkoordinasikan jalannya DatabaseInitializer dan
    SuperUserInitializer secara berurutan, dengan pengecekan kondisi
    database di setiap tahap untuk menentukan apakah suatu langkah
    perlu dijalankan atau bisa dilewati.

    Attributes:
        db_path (str): Lokasi path file database SQLite.
    """

    def __init__(self, db_path: str = "user_data.db"):
        """Inisialisasi instance InitDatabase.

        Args:
            db_path (str): Path file database. Default ke 'user_data.db'.
        """
        self.db_path = db_path

    def _is_database_exists(self) -> bool:
        """Memeriksa apakah file database sudah ada di sistem file.

        Returns:
            bool: True jika file database ada, False jika belum.
        """
        return os.path.exists(self.db_path)

    def _is_tables_ready(self) -> bool:
        """Memeriksa apakah semua tabel yang diperlukan sudah ada.

        Returns:
            bool: True jika semua tabel sudah lengkap, False jika belum.
        """
        required_tables = {"users", "system_lockout", "login_logs", "settings"}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = {row[0] for row in cursor.fetchall()}
                return required_tables.issubset(existing_tables)
        except sqlite3.Error:
            return False

    def _is_superuser_exists(self) -> bool:
        """Memeriksa apakah sudah ada super user di dalam database.

        Returns:
            bool: True jika sudah ada minimal satu pengguna, False jika kosong.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error:
            return False

    def run(self) -> None:
        """Menjalankan seluruh proses inisialisasi database secara berurutan.

        Alur eksekusi:
            1. Periksa apakah database dan tabel sudah ada.
               - Jika belum → jalankan DatabaseInitializer.initialize()
            2. Periksa apakah super user sudah ada.
               - Jika belum → jalankan SuperUserInitializer.create_superuser()
            3. Jika semua sudah siap → lewati, lanjut ke aplikasi.
        """
        logger.info("Memulai pemeriksaan inisialisasi database")

        if not self._is_database_exists() or not self._is_tables_ready():
            logger.info("Database atau tabel belum lengkap. Menjalankan inisialisasi struktur...")
            db_initializer = DatabaseInitializer(self.db_path)
            db_initializer.initialize()
            logger.info("Inisialisasi struktur database selesai")
        else:
            logger.debug("Struktur database sudah lengkap. Tahap ini dilewati")

        if not self._is_superuser_exists():
            logger.info("Super user belum ditemukan. Menjalankan inisialisasi super user...")
            run_superuser_in_cmd(self.db_path)
            logger.info("Inisialisasi super user selesai")
        else:
            logger.debug("Super user sudah ada. Tahap ini dilewati")

        logger.info("Pemeriksaan inisialisasi database selesai")
