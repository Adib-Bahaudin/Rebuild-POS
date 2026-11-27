"""Modul konfigurasi terpusat dan manajemen path untuk aplikasi POS.

Modul ini bertanggung jawab menyediakan metadata aplikasi, deteksi lingkungan
eksekusi (Development vs Production), serta resolusi path terpusat untuk seluruh
aset statis dan data dinamis aplikasi berbasis PyQt/PySide6.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Final

from PySide6.QtCore import QCoreApplication, QStandardPaths

APP_NAME: Final[str] = "BarokahPOS"
ORGANIZATION_NAME: Final[str] = "Barokah"
APP_VERSION: Final[str] = "2.0.0"


def detect_production_mode() -> bool:
    """Mendeteksi apakah aplikasi berjalan di lingkungan produksi atau pengembangan.

    Pemeriksaan dilakukan secara berurutan:
        1. Override opsional dari environment variable APP_ENV ('production' / 'development').
        2. Atribut sys.frozen untuk runtime PyInstaller atau cx_Freeze.
        3. Variabel global '__compiled__' untuk distribusi terkompilasi Nuitka.
        4. Ekstensi file modul saat ini ('.pyd' atau '.so') dan pengecekan cython.compiled.

    Returns:
        bool: True jika aplikasi berjalan dalam mode produksi, False jika mode pengembangan.
    """
    env_override = os.environ.get("APP_ENV", "").strip().lower()
    if env_override == "production":
        return True
    if env_override == "development":
        return False

    if getattr(sys, "frozen", False):
        return True

    if "__compiled__" in globals():
        return True

    current_suffix = Path(__file__).suffix.lower()
    if current_suffix in {".pyd", ".so"}:
        return True

    try:
        cython_mod = importlib.import_module("cython")

        if getattr(cython_mod, "compiled", False):
            return True
    except (ImportError, AttributeError):
        pass

    return False


def _resolve_project_root() -> Path:
    """Menentukan root direktori proyek atau bundle ekstraksi aplikasi.

    Returns:
        Path: Lokasi direktori root bundle jika terdistribusi atau direktori proyek lokal.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return Path(meipass).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def _resolve_app_data_dir(project_root: Path, is_production: bool) -> Path:
    """Menentukan direktori penampung data dinamis aplikasi.

    Args:
        project_root: Direktori root aplikasi.
        is_production: Status apakah aplikasi berada pada mode produksi.

    Returns:
        Path: Direktori penyimpanan data yang dapat ditulis oleh aplikasi.
    """
    if not is_production:
        return project_root

    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    writable_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    if writable_dir:
        return Path(writable_dir).resolve()

    return project_root


IS_PRODUCTION: Final[bool] = detect_production_mode()
IS_DEV: Final[bool] = not IS_PRODUCTION

PROJECT_ROOT: Final[Path] = _resolve_project_root()
APP_DATA_DIR: Final[Path] = _resolve_app_data_dir(PROJECT_ROOT, IS_PRODUCTION)

ASSETS_DIR: Final[Path] = PROJECT_ROOT / "assets"
ICONS_DIR: Final[Path] = ASSETS_DIR / "icons"

DATABASE_DIR: Final[Path] = APP_DATA_DIR / "database" if IS_PRODUCTION else APP_DATA_DIR
LOGS_DIR: Final[Path] = APP_DATA_DIR / "logs"

DATABASE_NAME: Final[str] = "barokah_database.db"
DEFAULT_DB_PATH: Final[Path] = (
    DATABASE_DIR / DATABASE_NAME if IS_PRODUCTION else APP_DATA_DIR / DATABASE_NAME
)

DATABASE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_asset_path(relative_path: str | Path) -> Path:
    """Mendapatkan path absolut ke aset statis atau file read-only aplikasi.

    Args:
        relative_path: Path relatif dari folder proyek atau folder aset.

    Returns:
        Path: Objek Path absolut menuju lokasi aset target.
    """
    target = Path(relative_path)
    if target.is_absolute():
        return target

    direct_path = PROJECT_ROOT / target
    if direct_path.exists():
        return direct_path.resolve()

    asset_path = ASSETS_DIR / target
    if asset_path.exists():
        return asset_path.resolve()

    return direct_path.resolve()


def get_data_path(relative_path: str | Path) -> Path:
    """Mendapatkan path absolut ke file atau folder data dinamis aplikasi.

    Args:
        relative_path: Path relatif terhadap APP_DATA_DIR.

    Returns:
        Path: Objek Path absolut di dalam direktori penyimpanan data aplikasi.
    """
    target = Path(relative_path)
    if target.is_absolute():
        return target

    full_path = APP_DATA_DIR / target
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path.resolve()
