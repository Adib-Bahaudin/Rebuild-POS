"""Modul orkestrator untuk inisialisasi database secara menyeluruh.

Modul ini bertugas memeriksa dan menjalankan seluruh tugas inisialisasi
yang berhubungan dengan database, termasuk pembuatan tabel (inituserdatabase),
pembuatan super user pertama (initsuperuser), serta inisialisasi database
transaksi FIFO (inittransaksidatabase), dengan melakukan pengecekan kondisi
database terlebih dahulu sebelum menjalankan setiap langkah.
"""

from __future__ import annotations

from contextlib import closing
import logging
from pathlib import Path
from typing import Optional

from sqlcipher3 import dbapi2 as sqlite3

from config import DEFAULT_DB_PATH
from util.helper.database.db_connection import create_sqlite_connection
from util.helper.database.init.inituserdatabase import DatabaseInitializer
from util.helper.database.init.initsuperuser import run_superuser_in_cmd
from util.helper.database.init.inittransaksidatabase import init_transaksi_database

logger = logging.getLogger(__name__)


class InitDatabase:
    """Orkestrator utama untuk seluruh proses inisialisasi database.

    Kelas ini mengkoordinasikan jalannya DatabaseInitializer,
    SuperUserInitializer, dan TransaksiDatabaseInitializer secara berurutan,
    dengan pengecekan kondisi database di setiap tahap untuk menentukan apakah
    suatu langkah perlu dijalankan atau bisa dilewati.

    Attributes:
        db_path (Path): Lokasi path file database SQLite user.
    """

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
    ) -> None:
        """Inisialisasi instance InitDatabase.

        Args:
            db_path: Path file database. Default menggunakan DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def _is_database_exists(self) -> bool:
        """Memeriksa apakah file database sudah ada di sistem file.

        Returns:
            bool: True jika file database ada, False jika belum.
        """
        return self.db_path.exists()

    def _is_tables_ready(self) -> bool:
        """Memeriksa apakah semua tabel yang diperlukan sudah ada.

        Returns:
            bool: True jika semua tabel sudah lengkap, False jika belum.
        """
        required_tables = {"users", "system_lockout", "login_logs", "settings"}
        try:
            with closing(
                create_sqlite_connection(
                    self.db_path,
                    require_exists=True,
                    row_factory=False,
                    foreign_keys=False,
                )
            ) as conn:
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
            with closing(
                create_sqlite_connection(
                    self.db_path,
                    require_exists=True,
                    row_factory=False,
                    foreign_keys=False,
                )
            ) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error:
            return False

    def run(self) -> None:
        """Menjalankan seluruh proses inisialisasi database secara berurutan.

        Alur eksekusi:
            1. Periksa apakah database dan tabel user sudah ada.
               - Jika belum → jalankan DatabaseInitializer.initialize()
            2. Periksa apakah super user sudah ada.
               - Jika belum → jalankan SuperUserInitializer.create_superuser()
            3. Jalankan inisialisasi database transaksi (inittransaksidatabase).
            4. Jika semua sudah siap → lanjut ke aplikasi.
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

        logger.info("Menjalankan inisialisasi database transaksi...")
        init_transaksi_database(self.db_path)
        logger.info("Inisialisasi database transaksi selesai")

        logger.info("Pemeriksaan inisialisasi database selesai")
