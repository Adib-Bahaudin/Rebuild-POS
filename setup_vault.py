"""Skrip kompilasi Cython untuk membangun modul biner util.helper.database.db_vault."""

from Cython.Build import cythonize
from setuptools import Extension, setup

extensions = [
    Extension(
        name="util.helper.database.db_vault",
        sources=["util/helper/database/db_vault.pyx"],
    )
]

setup(
    name="db_vault_builder",
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    ),
)