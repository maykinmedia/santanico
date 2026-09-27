#!/usr/bin/env python3
"""Build the pure-Python (py3-none-any) fallback wheel.

maturin always compiles the Rust extension (it detects the pyo3 bindings
regardless of crate-type/module-name), so the fallback wheel is built
separately with flit_core, the minimal PEP 517 backend (single pure-Python
module, no dependencies, no Rust toolchain required).

The [project] table is reused verbatim from pyproject.toml, so the metadata
cannot drift from the platform wheels; only the version is injected from
Cargo.toml (the single source of truth).
"""

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".pure-build"
PACKAGE = "santanico"


def main() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    cargo = (ROOT / "Cargo.toml").read_text()
    version = re.search(
        r'(?<=name = "santanico"\nversion = ")[0-9]+\.[0-9]+\.[0-9]+', cargo
    ).group(0)

    # Slice the [project] table out of the real pyproject, verbatim.
    project = re.search(r"\[project\]\n(.*?)(?=\n\[)", pyproject, re.DOTALL).group(1)
    project = re.sub(r'dynamic = \["version"\]\n', f'version = "{version}"\n', project)
    # flit_core rejects the deprecated license table next to license-files;
    # convert to the PEP 639 SPDX expression form.
    project = re.sub(
        r'license = \{ text = "([^"]+)" \}\n', r'license = "\1"\n', project
    )

    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    pkg_dir = SCRATCH / PACKAGE
    pkg_dir.mkdir(parents=True)
    # .py/.pyi/py.typed only: this naturally excludes the .so extension
    # left behind by `maturin develop` in local checkouts.
    for f in (ROOT / PACKAGE).iterdir():
        if f.is_file() and (f.suffix in {".py", ".pyi"} or f.name == "py.typed"):
            shutil.copy2(f, pkg_dir / f.name)
    for name in ("README.rst", "LICENSE"):
        shutil.copy2(ROOT / name, SCRATCH / name)

    (SCRATCH / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["flit_core>=3.12"]\n'
        'build-backend = "flit_core.buildapi"\n'
        "\n"
        "[project]\n"
        f"{project}\n"
    )

    try:
        subprocess.run(
            [
                "uv",
                "build",
                "--wheel",
                str(SCRATCH),
                "-o",
                str(ROOT / "dist"),
            ],
            check=True,
        )
    finally:
        shutil.rmtree(SCRATCH)


if __name__ == "__main__":
    main()
