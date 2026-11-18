"""Modul autentikasi login menggunakan sistem kunci global.

Modul ini menangani logika validasi kunci, pencatatan riwayat login,
serta implementasi hukuman penguncian sistem global secara bertingkat.
"""

import sqlite3
import time
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class AuthResponse:
    """Representasi data hasil dari proses autentikasi.

    Attributes:
        is_success (bool): Status keberhasilan login.
        message (str): Pesan evaluasi dari sistem.
        user_data (Optional[Dict[str, Any]]): Data pengguna jika login berhasil.
        locked_until (int): Waktu rilis penguncian dalam format epoch UNIX.
    """
    is_success: bool
    message: str
    user_data: Optional[Dict[str, Any]] = None
    locked_until: int = 0


class LoginAuthService:
    """Layanan bisnis untuk menangani autentikasi berbasis kunci.

    Attributes:
        db_path (str): Lokasi path file database SQLite.
    """

    def __init__(self, db_path: str = "user_data.db"):
        """Inisialisasi instance LoginAuthService.

        Args:
            db_path (str): Path file database target.
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Membuat dan mengembalikan koneksi ke database SQLite.

        Returns:
            sqlite3.Connection: Objek koneksi database yang siap digunakan.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_settings(self, conn: sqlite3.Connection) -> Dict[str, int]:
        """Mengambil konfigurasi sistem dari tabel settings.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.

        Returns:
            Dict[str, int]: Kamus berisi pengaturan dengan tipe integer.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        
        settings = {
            "max_failed_attempts": 5,
            "base_lockout_seconds": 60
        }
        
        for row in rows:
            if row["key"] in settings:
                settings[row["key"]] = int(row["value"])
                
        return settings

    def _check_system_lockout(self, conn: sqlite3.Connection) -> AuthResponse:
        """Memverifikasi apakah sistem saat ini sedang dalam status terkunci.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.

        Returns:
            AuthResponse: Status terkunci jika waktu belum berlalu, 
            atau status sukses dengan pesan aman jika tidak terkunci.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT locked_until FROM system_lockout WHERE id = 1")
        row = cursor.fetchone()
        
        current_time = int(time.time())
        locked_until = row["locked_until"] if row else 0
        
        if locked_until > current_time:
            remaining_time = locked_until - current_time
            logger.warning(
                "Sistem terkunci. Sisa waktu: %d detik", remaining_time
            )
            return AuthResponse(
                is_success=False,
                message=f"Sistem terkunci sementara. Coba lagi dalam {remaining_time} detik.",
                locked_until=locked_until
            )
            
        return AuthResponse(is_success=True, message="Sistem aman.")

    def _verify_key(self, provided_key: str, stored_hash: bytes, stored_salt: bytes) -> bool:
        """Melakukan komputasi hash kriptografi untuk mencocokkan kunci.

        Args:
            provided_key (str): Kunci murni yang dimasukkan pengguna.
            stored_hash (bytes): Hash murni dari database.
            stored_salt (bytes): Salt murni dari database.

        Returns:
            bool: True jika hash cocok, False jika tidak cocok.
        """
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            provided_key.encode('utf-8'),
            stored_salt,
            100000
        )
        return computed_hash == stored_hash

    def _log_attempt(self, conn: sqlite3.Connection, user_id: Optional[int], status: str) -> None:
        """Mencatat aktivitas percobaan login ke dalam database log.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.
            user_id (Optional[int]): ID pengguna jika berhasil, None jika gagal/tidak diketahui.
            status (str): Status string ('SUCCESS' atau 'FAILED').
        """
        cursor = conn.cursor()
        current_time = int(time.time())
        cursor.execute("""
            INSERT INTO login_logs (user_id, status, created_at)
            VALUES (?, ?, ?)
        """, (user_id, status, current_time))
        conn.commit()

    def _reset_lockout(self, conn: sqlite3.Connection) -> None:
        """Mereset parameter hukuman penguncian kembali ke nilai nol.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.
        """
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE system_lockout 
            SET failed_attempts = 0, lock_count = 0, locked_until = 0, last_failed_at = 0 
            WHERE id = 1
        """)
        conn.commit()

    def _process_failed_attempt(self, conn: sqlite3.Connection) -> AuthResponse:
        """Memproses logika eskalasi hukuman saat percobaan login gagal.

        Args:
            conn (sqlite3.Connection): Objek koneksi database aktif.

        Returns:
            AuthResponse: Hasil evaluasi yang mengindikasikan gagal dan status penguncian terkini.
        """
        settings = self._get_settings(conn)
        current_time = int(time.time())
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT failed_attempts, lock_count 
            FROM system_lockout 
            WHERE id = 1
        """)
        lock_data = cursor.fetchone()
        
        failed_attempts = (lock_data["failed_attempts"] if lock_data else 0) + 1
        lock_count = lock_data["lock_count"] if lock_data else 0
        locked_until = 0
        
        if failed_attempts >= settings["max_failed_attempts"]:
            lock_count += 1
            multiplier = 2 ** (lock_count - 1)
            penalty_seconds = settings["base_lockout_seconds"] * multiplier
            locked_until = current_time + penalty_seconds
            failed_attempts = 0 
            
        cursor.execute("""
            UPDATE system_lockout 
            SET failed_attempts = ?, lock_count = ?, locked_until = ?, last_failed_at = ? 
            WHERE id = 1
        """, (failed_attempts, lock_count, locked_until, current_time))
        
        conn.commit()
        
        if locked_until > 0:
            remaining_time = locked_until - current_time
            logger.warning(
                "Sistem terkunci selama %d detik setelah percobaan gagal berturut-turut",
                remaining_time,
            )
            return AuthResponse(
                is_success=False,
                message=f"Kunci salah berturut-turut. Sistem terkunci selama {remaining_time} detik.",
                locked_until=locked_until
            )
            
        remaining_attempts = settings['max_failed_attempts'] - failed_attempts
        logger.debug("Sisa percobaan login: %d", remaining_attempts)
        return AuthResponse(
            is_success=False,
            message=f"Kunci tidak valid. Sisa percobaan: {remaining_attempts}"
        )

    def authenticate(self, key: str) -> AuthResponse:
        """Fungsi orkestrasi utama untuk memproses permintaan login.

        Args:
            key (str): Kunci akses yang diberikan oleh antarmuka sistem.

        Returns:
            AuthResponse: Objek representasi hasil validasi autentikasi.
        """
        if not key or not key.strip():
            return AuthResponse(is_success=False, message="Kunci akses tidak boleh kosong.")

        try:
            with self._get_connection() as conn:
                lockout_check = self._check_system_lockout(conn)
                if not lockout_check.is_success:
                    return lockout_check

                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, role, key_hash, key_salt 
                    FROM users 
                    WHERE is_active = 1
                """)
                active_users = cursor.fetchall()

                authenticated_user = None

                for user in active_users:
                    if self._verify_key(key, user["key_hash"], user["key_salt"]):
                        authenticated_user = dict(user)
                        break

                if authenticated_user:
                    self._reset_lockout(conn)
                    self._log_attempt(conn, authenticated_user["id"], "SUCCESS")
                    
                    authenticated_user.pop("key_hash", None)
                    authenticated_user.pop("key_salt", None)
                    
                    logger.info(
                        "Otorisasi berhasil untuk User ID: %d",
                        authenticated_user['id'],
                    )
                    return AuthResponse(
                        is_success=True,
                        message="Login berhasil.",
                        user_data=authenticated_user
                    )
                else:
                    self._log_attempt(conn, None, "FAILED")
                    logger.warning("Upaya otorisasi ditolak. Kunci tidak valid.")
                    return self._process_failed_attempt(conn)
                    
        except sqlite3.Error:
            logger.exception("Kesalahan internal database")
            return AuthResponse(is_success=False, message="Terjadi kesalahan pada basis data sistem.")
        except Exception:
            logger.exception("Kesalahan sistem tidak terduga")
            return AuthResponse(is_success=False, message="Terjadi kegagalan proses internal.")
