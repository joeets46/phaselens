"""Smoke tests: the project package is installed and importable."""

from importlib.metadata import version
from pathlib import Path

import phaselens


def test_package_is_importable():
    assert phaselens.__name__ == "phaselens"


def test_package_is_imported_from_src_layout():
    package_dir = Path(phaselens.__file__).resolve().parent
    assert package_dir.name == "phaselens"
    assert package_dir.parent.name == "src"


def test_package_is_installed_in_environment():
    # Fails if the package is merely on sys.path rather than installed.
    assert version("phaselens")
