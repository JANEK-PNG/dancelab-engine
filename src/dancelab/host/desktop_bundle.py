"""Build and inspect the packaged macOS desktop host bundle."""

from __future__ import annotations

import argparse
import os
import shutil
import site
import subprocess
import sys
import tempfile
from pathlib import Path


def is_project_root(path: Path) -> bool:
    return (
        (path / "pyproject.toml").exists()
        and (path / "pysidedeploy.spec").exists()
        and (path / "dancelab_host.pyproject").exists()
        and (path / "scripts" / "dancelab_host_app.py").exists()
        and (path / "src" / "dancelab").exists()
    )


def repo_root() -> Path:
    env_root = os.environ.get("DANCELAB_PROJECT_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if is_project_root(candidate):
            return candidate

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if is_project_root(candidate):
            return candidate

    package_path = Path(__file__).resolve()
    for candidate in package_path.parents:
        if is_project_root(candidate):
            return candidate

    return package_path.parents[3]


def spec_path() -> Path:
    return repo_root() / "pysidedeploy.spec"


def project_manifest_path() -> Path:
    return repo_root() / "dancelab_host.pyproject"


def launcher_path() -> Path:
    return repo_root() / "scripts" / "dancelab_host_app.py"


def dist_dir() -> Path:
    return repo_root() / "dist" / "desktop"


def app_bundle_path(app_name: str = "DanceLab Host") -> Path:
    return dist_dir() / f"{app_name}.app"


def fallback_app_bundle_path(app_name: str = "DanceLab Host") -> Path:
    return Path.home() / "Applications" / f"{app_name}.app"


def site_packages_dir() -> Path:
    return Path(site.getsitepackages()[0])


def deployment_dir() -> Path:
    return repo_root() / "scripts" / "deployment"


def builder_python_path() -> Path:
    return Path(sys.executable).resolve()


def deploy_executable() -> str:
    sibling = Path(sys.executable).parent / "pyside6-deploy"
    if sibling.exists():
        return str(sibling)
    resolved = shutil.which("pyside6-deploy")
    if resolved:
        return resolved
    return "pyside6-deploy"


def xattr_cleanup_targets() -> list[Path]:
    candidates = [
        repo_root() / "src",
        repo_root() / "scripts",
        spec_path(),
        project_manifest_path(),
        repo_root() / "pyproject.toml",
        site_packages_dir(),
        dist_dir(),
        deployment_dir(),
    ]
    seen: set[Path] = set()
    result: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def xattr_sentinel_paths() -> list[Path]:
    candidates = [
        repo_root() / "pyproject.toml",
        spec_path(),
        project_manifest_path(),
        Path(sys.executable),
        builder_python_path(),
        repo_root() / "src" / "dancelab" / "host" / "desktop_app.py",
        site_packages_dir() / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A" / "QtCore",
    ]
    return [candidate for candidate in candidates if candidate.exists()]


def extended_attribute_names(path: Path) -> list[str]:
    result = subprocess.run(
        ["xattr", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def strip_extended_attributes(paths: list[Path]) -> None:
    if sys.platform != "darwin":
        return
    for path in paths:
        subprocess.run(
            ["xattr", "-cr", str(path)],
            check=True,
            text=True,
        )


def blocked_extended_attributes(paths: list[Path]) -> list[tuple[Path, list[str]]]:
    blocked: list[tuple[Path, list[str]]] = []
    for path in paths:
        attrs = extended_attribute_names(path)
        if attrs:
            blocked.append((path, attrs))
    return blocked


def is_hard_blocked_signing_input(path: Path) -> bool:
    hard_paths = {
        Path(sys.executable).resolve(),
        builder_python_path(),
    }
    return path.resolve() in hard_paths


def probe_fresh_extended_attributes() -> tuple[Path, list[str], list[str]] | None:
    if sys.platform != "darwin":
        return None

    with tempfile.NamedTemporaryFile(
        prefix="dancelab-host-xattr-",
        suffix=".probe",
        delete=False,
    ) as handle:
        handle.write(b"dancelab host xattr probe\n")
        probe_path = Path(handle.name)

    try:
        attrs_before_clear = extended_attribute_names(probe_path)
        strip_extended_attributes([probe_path])
        attrs_after_clear = extended_attribute_names(probe_path)
        return probe_path, attrs_before_clear, attrs_after_clear
    finally:
        probe_path.unlink(missing_ok=True)


def ensure_signable_macos_environment() -> None:
    if sys.platform != "darwin":
        return

    strip_extended_attributes(xattr_cleanup_targets())
    blocked = blocked_extended_attributes(xattr_sentinel_paths())
    probe = probe_fresh_extended_attributes()
    hard_blocked = [(path, attrs) for path, attrs in blocked if is_hard_blocked_signing_input(path)]

    probe_is_blocked = probe is not None and bool(probe[2])
    if not blocked and not probe_is_blocked:
        return

    details: list[str] = []
    if blocked:
        blocked_details = "; ".join(
            f"{path}: {', '.join(attrs)}"
            for path, attrs in blocked
        )
        details.append(f"Build inputs still retain attrs after cleanup: {blocked_details}.")
    if probe is not None:
        probe_path, attrs_before_clear, attrs_after_clear = probe
        details.append(
            "Fresh-file probe "
            f"{probe_path} attrs before cleanup: {', '.join(attrs_before_clear) or 'none'}; "
            f"after cleanup: {', '.join(attrs_after_clear) or 'none'}."
        )
    details.append(
        "Builder interpreter "
        f"{Path(sys.executable)} resolves to {builder_python_path()}."
    )

    if not hard_blocked:
        print(
            "dancelab-host-build preflight warning: some macOS extended-attribute checks are still "
            "dirty, but no hard-blocking builder interpreter inputs are affected. Continuing with "
            "the bundle build so codesign can validate the actual app outputs. "
            + " ".join(details),
            file=sys.stderr,
        )
        return

    raise RuntimeError(
        "macOS build preflight failed: the current session cannot produce a signable app bundle. "
        "Protected extended attributes such as `com.apple.provenance` are surviving cleanup. "
        + " ".join(details)
        + " Verify the build from Apple's Terminal.app with Full Disk Access, and confirm a fresh "
        "temp file can be cleared with `xattr -d com.apple.provenance <file>` before rerunning "
        "`dancelab-host-build`."
    )


def build_environment() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform == "darwin":
        # Prevent copyfile(3)-style propagation of Finder/xattr metadata into the app bundle.
        env.setdefault("COPYFILE_DISABLE", "1")
    return env


def strip_root_bundle_metadata(app_bundle: Path) -> None:
    if sys.platform != "darwin" or not app_bundle.exists():
        return
    for attribute_name in (
        "com.apple.FinderInfo",
        "com.apple.fileprovider.fpfs#P",
        "com.apple.provenance",
    ):
        subprocess.run(
            ["xattr", "-d", attribute_name, str(app_bundle)],
            check=False,
            text=True,
            capture_output=True,
        )


def verify_codesigned_app_bundle(app_bundle: Path) -> None:
    strip_root_bundle_metadata(app_bundle)
    subprocess.run(
        [
            "codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=1",
            str(app_bundle),
        ],
        check=True,
        text=True,
    )


def install_verified_app_bundle(source_bundle: Path, target_bundle: Path) -> bool:
    try:
        target_bundle.parent.mkdir(parents=True, exist_ok=True)
        if target_bundle.exists():
            shutil.rmtree(target_bundle)
        if sys.platform == "darwin":
            subprocess.run(
                ["ditto", "--noextattr", "--noqtn", str(source_bundle), str(target_bundle)],
                check=True,
                text=True,
            )
        else:
            subprocess.run(
                ["cp", "-R", str(source_bundle), str(target_bundle)],
                check=True,
                text=True,
            )
        verify_codesigned_app_bundle(target_bundle)
    except (OSError, subprocess.CalledProcessError):
        if target_bundle.exists():
            shutil.rmtree(target_bundle, ignore_errors=True)
        return False

    return True


def mirror_verified_app_bundle_to_fallback(source_bundle: Path) -> Path | None:
    fallback_bundle = fallback_app_bundle_path(source_bundle.stem)
    if fallback_bundle == source_bundle:
        return None
    if install_verified_app_bundle(source_bundle, fallback_bundle):
        print(
            "dancelab-host-build installed a verified app bundle copy at "
            f"{fallback_bundle}.",
            file=sys.stderr,
        )
        return fallback_bundle
    return None


def salvage_macos_signed_app_bundle(app_bundle: Path) -> bool:
    if sys.platform != "darwin" or not app_bundle.exists():
        return False

    temporary_root = Path(tempfile.mkdtemp(prefix="dancelab-host-sanitized-"))
    sanitized_bundle = temporary_root / f"{app_bundle.stem}.__sanitized__.app"
    try:
        try:
            subprocess.run(
                ["ditto", "--noextattr", "--noqtn", str(app_bundle), str(sanitized_bundle)],
                check=True,
                text=True,
            )
            for attribute_name in (
                "com.apple.FinderInfo",
                "com.apple.fileprovider.fpfs#P",
            ):
                subprocess.run(
                    ["xattr", "-d", attribute_name, str(sanitized_bundle)],
                    check=False,
                    text=True,
                    capture_output=True,
                )
            subprocess.run(
                [
                    "codesign",
                    "-s",
                    "-",
                    "--force",
                    "--deep",
                    "--preserve-metadata=entitlements",
                    str(sanitized_bundle),
                ],
                check=True,
                text=True,
            )
            verify_codesigned_app_bundle(sanitized_bundle)
        except (OSError, subprocess.CalledProcessError):
            return False

        install_targets = [
            app_bundle,
            fallback_app_bundle_path(app_bundle.stem),
        ]
        final_target: Path | None = None
        for target_bundle in install_targets:
            if install_verified_app_bundle(sanitized_bundle, target_bundle):
                final_target = target_bundle
                break

        if final_target is None:
            return False

        print(
            "dancelab-host-build recovered the generated app bundle with a post-build macOS "
            f"sanitize+codesign pass at {final_target}.",
            file=sys.stderr,
        )
        return True
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def build_command(
    *,
    force: bool = True,
    dry_run: bool = False,
    keep_deployment_files: bool = False,
    verbose: bool = False,
) -> list[str]:
    command = [
        deploy_executable(),
        "-c",
        str(spec_path()),
        str(launcher_path()),
    ]
    if force:
        command.append("-f")
    if dry_run:
        command.append("--dry-run")
    if keep_deployment_files:
        command.append("--keep-deployment-files")
    if verbose:
        command.append("-v")
    return command


def build_desktop_bundle(
    *,
    force: bool = True,
    dry_run: bool = False,
    keep_deployment_files: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not dry_run:
        ensure_signable_macos_environment()
    command = build_command(
        force=force,
        dry_run=dry_run,
        keep_deployment_files=keep_deployment_files,
        verbose=verbose,
    )
    try:
        result = subprocess.run(
            command,
            cwd=repo_root(),
            env=build_environment(),
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Could not find `pyside6-deploy`. Install desktop tooling with "
            "`pip install .[desktop-build]`."
        ) from exc
    if dry_run:
        return result

    built_bundle = app_bundle_path()
    if result.returncode == 0:
        try:
            verify_codesigned_app_bundle(built_bundle)
        except (OSError, subprocess.CalledProcessError):
            if salvage_macos_signed_app_bundle(built_bundle):
                return subprocess.CompletedProcess(result.args, 0)
            return result
        mirror_verified_app_bundle_to_fallback(built_bundle)
        return result

    if salvage_macos_signed_app_bundle(built_bundle):
        return subprocess.CompletedProcess(result.args, 0)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dancelab-host-build",
        description="Build the packaged DanceLab Host macOS app bundle via pyside6-deploy.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the generated Nuitka command.")
    parser.add_argument(
        "--keep-deployment-files",
        action="store_true",
        help="Keep intermediate deployment/build files.",
    )
    parser.add_argument("--verbose", action="store_true", help="Run pyside6-deploy in verbose mode.")
    args = parser.parse_args(argv)

    result = build_desktop_bundle(
        dry_run=args.dry_run,
        keep_deployment_files=args.keep_deployment_files,
        verbose=args.verbose,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
