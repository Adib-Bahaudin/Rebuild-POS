"""Konfigurasi logging terpusat untuk seluruh aplikasi POS.

Modul ini menyediakan fungsi setup_logging() yang diinisialisasi
pada saat startup aplikasi di main.py sebelum modul lain melakukan logging.
Seluruh modul lain cukup menggunakan:

    import logging
    logger = logging.getLogger(__name__)

Konfigurasi mendukung mode Development dan Production, penulisan log berputar
(RotatingFileHandler), filter informasi sensitif, serta format teks atau JSON.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from config import IS_DEV, LOGS_DIR

_SENSITIVE_PATTERNS: Final[frozenset[str]] = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "key_hash", "key_salt", "authorization", "credential",
})

_TEXT_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


class _SensitiveDataFilter(logging.Filter):
    """Filter yang mencegah data sensitif bocor ke log.

    Memeriksa pesan log terhadap pola-pola kunci sensitif dan
    melakukan redaksi jika ditemukan kecocokan.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Menyaring dan meredaksi informasi sensitif dari record log.

        Args:
            record: Objek LogRecord yang akan diperiksa.

        Returns:
            bool: Selalu True agar record tetap diteruskan setelah redaksi.
        """
        msg = str(record.msg)
        msg_lower = msg.lower()
        for pattern in _SENSITIVE_PATTERNS:
            if pattern in msg_lower:
                record.msg = "[REDACTED - sensitive data removed]"
                record.args = None
                break
        return True


class _JSONFormatter(logging.Formatter):
    """Formatter yang menghasilkan output log dalam format JSON satu baris."""

    def format(self, record: logging.LogRecord) -> str:
        """Memformat record log menjadi string JSON.

        Args:
            record: Objek LogRecord yang akan diformat.

        Returns:
            str: String JSON satu baris yang merepresentasikan record log.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    log_level_override: Optional[str] = None,
    log_file_path: Optional[str | Path] = None,
) -> None:
    """Menginisialisasi sistem logging terpusat untuk seluruh aplikasi.

    Fungsi ini dipanggil pada startup aplikasi dan mengatur konfigurasi
    berdasarkan lingkungan eksekusi (Development vs Production).

    Args:
        log_level_override: Level log eksplisit (DEBUG, INFO, ERROR).
        log_file_path: Path file tujuan penyimpanan log.
    """
    default_level = "DEBUG" if IS_DEV else "INFO"
    env_level = os.environ.get("LOG_LEVEL", default_level).upper()
    active_level_name = log_level_override.upper() if log_level_override else env_level
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    log_level = getattr(logging, active_level_name, logging.INFO)

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    root_logger.setLevel(log_level)

    if log_format == "json":
        formatter: logging.Formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT)

    sensitive_filter = _SensitiveDataFilter()

    if IS_DEV:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)

    target_log_file: Optional[Path] = None
    if log_file_path:
        target_log_file = Path(log_file_path)
    elif not IS_DEV:
        target_log_file = LOGS_DIR / "app.log"
    elif os.environ.get("LOG_FILE"):
        target_log_file = Path(os.environ["LOG_FILE"])

    if target_log_file:
        target_log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            str(target_log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    logging.getLogger("PySide6").setLevel(logging.WARNING)
    logging.getLogger("sqlite3").setLevel(logging.WARNING)
