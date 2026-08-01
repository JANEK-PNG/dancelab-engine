#!/usr/bin/env python3
"""Install a built DanceLab wheel in isolation and verify its headless surface."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import venv


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Wheel extra to install and probe (repeatable).",
    )
    parser.add_argument("wheel", type=Path, help="Path to one built DanceLab wheel")
    return parser


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _create_environment(env_dir: Path, *, cwd: Path) -> None:
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        return
    except (OSError, subprocess.CalledProcessError):
        shutil.rmtree(env_dir, ignore_errors=True)

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("stdlib venv failed and uv is unavailable")
    _run(
        [uv, "venv", "--seed", "--python", sys.executable, str(env_dir)],
        cwd=cwd,
    )


def main() -> int:
    args = _parser().parse_args()
    wheel = args.wheel.expanduser().resolve(strict=True)
    if wheel.suffix != ".whl":
        raise ValueError(f"expected a wheel, got: {wheel}")
    extras = sorted(set(args.extra))
    install_target = str(wheel)
    if extras:
        install_target = f"{wheel}[{','.join(extras)}]"

    with tempfile.TemporaryDirectory(prefix="dancelab-clean-install-") as raw_temp:
        temp_dir = Path(raw_temp)
        env_dir = temp_dir / "venv"
        _create_environment(env_dir, cwd=temp_dir)
        executable_dir = "Scripts" if os.name == "nt" else "bin"
        python = env_dir / executable_dir / ("python.exe" if os.name == "nt" else "python")
        dancelab = env_dir / executable_dir / ("dancelab.exe" if os.name == "nt" else "dancelab")

        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                install_target,
            ],
            cwd=temp_dir,
        )
        _run([str(python), "-m", "pip", "check"], cwd=temp_dir)

        probe = textwrap.dedent(
            f"""
            from pathlib import Path
            import sys

            import dancelab
            import dancelab.api.main
            import dancelab.core.pipeline
            import dancelab.preview.transition_simulation

            package_path = Path(dancelab.__file__).resolve()
            environment = Path({str(env_dir)!r}).resolve()
            assert environment in package_path.parents, package_path
            print(f"clean headless import: {{package_path}}")
            """
        )
        if "rekordbox" in extras:
            probe += textwrap.dedent(
                """

                import pyrekordbox
                import dancelab.ingestion.rb_backup
                import dancelab.ingestion.rekordbox_cue_writer
                print("clean Rekordbox writer import: ok")
                """
            )
        _run([str(python), "-I", "-c", probe], cwd=temp_dir)
        _run([str(dancelab), "--help"], cwd=temp_dir)

    profile = ",".join(extras) if extras else "base"
    print(f"clean wheel verification passed: {wheel.name} ({profile})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
