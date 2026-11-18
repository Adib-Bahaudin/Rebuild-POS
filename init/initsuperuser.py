"""Modul untuk inisialisasi akun super user pertama.

Modul ini digunakan secara eksklusif untuk membuat akun master
pada saat pengaturan awal sistem. Skrip akan menolak eksekusi
jika sudah terdapat pengguna di dalam basis data.
"""

import sqlite3
import os
import hashlib
import getpass
import logging
import sys
from typing import Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class SuperUserInitializer:
    """Kelas untuk menangani pembuatan akun super user secara aman.

    Attributes:
        db_path (str): Lokasi path file database SQLite.
    """

    def __init__(self, db_path: str = "user_data.db"):
        """Inisialisasi instance SuperUserInitializer.

        Args:
            db_path (str): Path file database. Default ke 'user_data.db'.
        """
        self.db_path = db_path

    def _generate_crypto_materials(self, raw_key: str) -> Tuple[bytes, bytes]:
        """Menghasilkan salt acak dan hash aman dari kunci yang diberikan.

        Args:
            raw_key (str): Kunci akses murni (plaintext).

        Returns:
            Tuple[bytes, bytes]: Tuple yang berisi (key_hash, key_salt).
        """
        salt = os.urandom(32)
        key_hash = hashlib.pbkdf2_hmac(
            'sha256',
            raw_key.encode('utf-8'),
            salt,
            100000
        )
        return key_hash, salt

    def _is_database_empty(self, conn: sqlite3.Connection) -> bool:
        """Memeriksa apakah tabel users masih kosong.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.

        Returns:
            bool: True jika tabel kosong, False jika sudah ada data.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        return count == 0

    def create_superuser(self) -> None:
        """Menjalankan alur interaktif untuk membuat super user.
        
        Memvalidasi eksistensi database, mengecek apakah tabel pengguna
        kosong, dan meminta input kunci secara aman tersembunyi.
        """
        if not os.path.exists(self.db_path):
            logging.error(f"Database {self.db_path} tidak ditemukan. Jalankan inituserdatabase.py terlebih dahulu.")
            sys.exit(1)

        try:
            with sqlite3.connect(self.db_path) as conn:
                if not self._is_database_empty(conn):
                    logging.warning("Tindakan ditolak. Basis data sudah memiliki pengguna (Tidak kosong).")
                    sys.exit(1)

                print("\n=== INISIALISASI SUPER USER (MASTER AKUN) ===")
                print("Peringatan: Input kunci menggunakan mode rahasia (teks tidak akan muncul di layar saat diketik).\n")
                
                name = input("Masukkan Nama Super User: ").strip()
                if not name:
                    logging.error("Nama tidak boleh kosong.")
                    sys.exit(1)

                key = getpass.getpass("Masukkan Kunci Akses Baru: ").strip()
                if len(key) < 6:
                    logging.error("Kunci akses terlalu pendek (Minimal 6 karakter).")
                    sys.exit(1)

                key_confirm = getpass.getpass("Konfirmasi Kunci Akses: ").strip()
                if key != key_confirm:
                    logging.error("Konfirmasi kunci gagal. Kunci tidak cocok.")
                    sys.exit(1)

                key_hash, key_salt = self._generate_crypto_materials(key)

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (name, role, key_hash, key_salt, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, 'SUPERUSER', key_hash, key_salt, 1))
                
                conn.commit()
                logging.info(f"Super User '{name}' berhasil dibuat dan disimpan dengan aman.")
                print("=============================================\n")

        except sqlite3.Error as e:
            logging.error(f"Kesalahan pada basis data: {e}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Kesalahan sistem tidak terduga: {e}")
            sys.exit(1)
