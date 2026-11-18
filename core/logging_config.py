"""Konfigurasi logging terpusat untuk seluruh aplikasi POS.

Modul ini menyediakan fungsi setup_logging() yang harus dipanggil
sekali saja pada saat startup aplikasi (di main.py) sebelum modul
lain melakukan logging.  Seluruh modul lain cukup menggunakan:

    import logging
    logger = logging.getLogger(__name__)

Konfigurasi mendukung:
    - LOG_LEVEL : level logging via environment variable (default: INFO)
    - LOG_FORMAT: 'text' (default) atau 'json'
    - LOG_FILE  : path file log opsional (e.g. 'logs/app.log')
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional


_SENSITIVE_PATTERNS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "key_hash", "key_salt", "authorization", "credential",
})


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
            Selalu True agar record tetap diteruskan setelah redaksi.
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
            String JSON satu baris yang merepresentasikan record log.
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


_TEXT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Menginisialisasi sistem logging terpusat untuk seluruh aplikasi.

    Fungsi ini hanya boleh dipanggil **sekali** pada saat startup.
    Konfigurasi dikendalikan melalui environment variable:

        LOG_LEVEL  : DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
        LOG_FORMAT : 'text' atau 'json' (default: text)
        LOG_FILE   : path file log, e.g. 'logs/app.log' (default: None)

    Handler yang terpasang:
        - Console handler (stderr) — selalu aktif.
        - File handler (RotatingFileHandler) — aktif jika LOG_FILE diset.
    """
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    log_file: Optional[str] = os.environ.get("LOG_FILE")

    log_level = getattr(logging, log_level_name, logging.INFO)

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    root_logger.setLevel(log_level)

    if log_format == "json":
        formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT)

    sensitive_filter = _SensitiveDataFilter()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    logging.getLogger("PySide6").setLevel(logging.WARNING)
    logging.getLogger("sqlite3").setLevel(logging.WARNING)
