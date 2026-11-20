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
import subprocess
from typing import Tuple

logger = logging.getLogger(__name__)


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
            logger.error(
                "Database %s tidak ditemukan. Jalankan inituserdatabase.py terlebih dahulu.",
                self.db_path,
            )
            sys.exit(1)

        try:
            with sqlite3.connect(self.db_path) as conn:
                if not self._is_database_empty(conn):
                    logger.warning("Tindakan ditolak. Basis data sudah memiliki pengguna (Tidak kosong).")
                    sys.exit(1)

                print("\n=== INISIALISASI SUPER USER (MASTER AKUN) ===")
                print("Peringatan: Input kunci menggunakan mode rahasia (teks tidak akan muncul di layar saat diketik).\n")
                
                name = input("Masukkan Nama Super User: ").strip()
                if not name:
                    logger.error("Nama tidak boleh kosong.")
                    sys.exit(1)

                key = getpass.getpass("Masukkan Kunci Akses Baru: ").strip()
                if len(key) < 6:
                    logger.error("Kunci akses terlalu pendek (Minimal 6 karakter).")
                    sys.exit(1)

                key_confirm = getpass.getpass("Konfirmasi Kunci Akses: ").strip()
                if key != key_confirm:
                    logger.error("Konfirmasi kunci gagal. Kunci tidak cocok.")
                    sys.exit(1)

                key_hash, key_salt = self._generate_crypto_materials(key)

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (name, role, key_hash, key_salt, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, 'SUPERUSER', key_hash, key_salt, 1))
                
                conn.commit()
                logger.info("Super User '%s' berhasil dibuat dan disimpan dengan aman.", name)
                print("=============================================\n")

        except sqlite3.Error:
            logger.exception("Kesalahan pada basis data")
            sys.exit(1)
        except Exception:
            logger.exception("Kesalahan sistem tidak terduga")
            sys.exit(1)

def run_superuser_in_cmd(db_path: str = "user_data.db") -> None:
    """Membuka jendela CMD terpisah untuk inisialisasi Super User.
    
    Menjalankan alur pendaftaran dalam konsol terpisah agar input 'getpass'
    berfungsi dengan baik. Jika jendela ditutup secara paksa (X) atau
    proses gagal, aplikasi utama yang memanggil fungsi ini akan dihentikan.
    
    Args:
        db_path (str): Path absolut atau relatif dari file database.
    """
    try:
        script_path = os.path.abspath(__file__)
        logger.info("Membuka jendela CMD untuk inisialisasi Super User")
        
        result = subprocess.run(
            [sys.executable, script_path, db_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        if result.returncode != 0:
            logger.error(
                "Pendaftaran Super User gagal dengan kode keluar: %d",
                result.returncode,
            )
            sys.exit(1)

        logger.info("Proses inisialisasi Super User di CMD selesai")
            
    except Exception:
        logger.exception("Gagal menjalankan jendela CMD untuk Super User")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    target_db = sys.argv[1] if len(sys.argv) > 1 else "user_data.db"
    
    try:
        su_initializer = SuperUserInitializer(target_db)
        su_initializer.create_superuser()
        
        print("\nProses pendaftaran berhasil. Jendela akan menutup secara otomatis...")
        import time
        time.sleep(2)
        
    except SystemExit as e:
        if e.code != 0:
            print("\n[!] PROSES GAGAL ATAU DIBATALKAN.")
            input("Tekan Enter untuk menutup jendela ini dan kembali ke aplikasi...")
        sys.exit(e.code)
        
    except Exception:
        logger.exception("Kesalahan sistem tidak terduga saat inisialisasi Super User")
        print("\n[ERROR] Terjadi kesalahan sistem yang tidak terduga.")
        input("Tekan Enter untuk menutup jendela ini dan kembali ke aplikasi...")
        sys.exit(1)
