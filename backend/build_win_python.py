#!/usr/bin/env python3
"""Build a self-contained Windows Python runtime for the packaged Electron app.

Produces two folders next to this script, both shipped via electron-builder.yml:
  python-embed/  -> standalone embeddable CPython (no install needed on the PC)
  pylibs/        -> Django + deps as Windows wheels (added to sys.path via ._pth)

A venv is deliberately NOT used: it is not portable (it only references a base
Python by absolute path), and a Linux venv cannot run on Windows at all -- that
was the original "connection to server" bug (backend never started on Windows).

Cross-platform: the wheels are downloaded for the win_amd64 target, so the host
OS / Python version do not matter. Runs the same locally and in GitHub Actions.
"""
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PY_VERSION = "3.13.1"  # embeddable CPython version
PY_TAG = "313"  # cp tag for wheel selection + ._pth filename
EMBED_URL = (
    f"https://www.python.org/ftp/python/{PY_VERSION}/"
    f"python-{PY_VERSION}-embed-amd64.zip"
)

HERE = Path(__file__).resolve().parent
PYLIBS = HERE / "pylibs"
EMBED = HERE / "python-embed"
REQS = HERE / "requirements.txt"


def build_pylibs() -> None:
    print(">> Installing Windows wheels into pylibs/")
    if PYLIBS.exists():
        shutil.rmtree(PYLIBS)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(PYLIBS),
            "--platform", "win_amd64",
            "--python-version", PY_TAG,
            "--implementation", "cp",
            "--abi", f"cp{PY_TAG}",
            "--only-binary=:all:",
            "-r", str(REQS),
        ],
        check=True,
    )


def build_embed() -> None:
    print(f">> Downloading embeddable Python {PY_VERSION}")
    if EMBED.exists():
        shutil.rmtree(EMBED)
    EMBED.mkdir()
    zip_path = EMBED / "py.zip"
    urllib.request.urlretrieve(EMBED_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(EMBED)
    zip_path.unlink()

    print(f">> Writing python{PY_TAG}._pth (adds backend + pylibs to sys.path)")
    pth = EMBED / f"python{PY_TAG}._pth"
    pth.write_text(
        f"python{PY_TAG}.zip\n"
        ".\n"
        "..\\backend\n"
        "..\\backend\\pylibs\n"
        "\n"
        "# Run site.main() so the paths above are added to sys.path\n"
        "import site\n"
    )


if __name__ == "__main__":
    build_pylibs()
    build_embed()
    print(">> Done. python-embed/ and pylibs/ ready for electron-builder.")
