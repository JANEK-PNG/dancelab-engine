from pathlib import Path
from types import SimpleNamespace

from dancelab.host import desktop_bundle
from dancelab.host.desktop_bundle import (
    app_bundle_path,
    builder_python_path,
    build_command,
    build_desktop_bundle,
    build_environment,
    extended_attribute_names,
    is_project_root,
    launcher_path,
    mirror_verified_app_bundle_to_fallback,
    spec_path,
    strip_root_bundle_metadata,
    xattr_cleanup_targets,
    xattr_sentinel_paths,
)


def test_desktop_bundle_paths_and_command_are_repo_stable():
    assert is_project_root(desktop_bundle.repo_root())
    assert spec_path().name == "pysidedeploy.spec"
    assert launcher_path().name == "dancelab_host_app.py"
    assert app_bundle_path().name == "DanceLab Host.app"
    assert builder_python_path().name.startswith("python")

    command = build_command(dry_run=True, verbose=True)
    assert command[0].endswith("pyside6-deploy")
    assert command[1:3] == ["-c", str(spec_path())]
    assert command[3] == str(launcher_path())
    assert "-f" in command
    assert "--dry-run" in command
    assert "-v" in command
    assert "--extra-ignore-dirs" in command


def test_desktop_bundle_exposes_cleanup_targets_and_build_env():
    targets = xattr_cleanup_targets()
    assert any(path.name == "src" for path in targets)
    assert any(path.name == "scripts" for path in targets)
    assert any(path.name == "site-packages" for path in targets)

    sentinels = xattr_sentinel_paths()
    assert any(path.name == "pyproject.toml" for path in sentinels)
    assert any(path.name == "pysidedeploy.spec" for path in sentinels)
    assert any(path == builder_python_path() for path in sentinels)

    env = build_environment()
    assert "COPYFILE_DISABLE" in env

    assert isinstance(extended_attribute_names(spec_path()), list)


def test_desktop_bundle_dry_run_skips_macos_signability_preflight(monkeypatch):
    def fail_preflight() -> None:
        raise AssertionError("dry-run should not trigger macOS signability preflight")

    captured: dict[str, object] = {}

    def fake_run(command, cwd, env, text, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(desktop_bundle, "ensure_signable_macos_environment", fail_preflight)
    monkeypatch.setattr(desktop_bundle.subprocess, "run", fake_run)

    result = build_desktop_bundle(dry_run=True)

    assert result.returncode == 0
    assert "--dry-run" in captured["command"]
    assert captured["cwd"] == desktop_bundle.repo_root()


def test_macos_probe_only_case_warns_but_does_not_block(monkeypatch, capsys):
    monkeypatch.setattr(desktop_bundle.sys, "platform", "darwin")
    monkeypatch.setattr(desktop_bundle.sys, "executable", "/tmp/python3.12")
    monkeypatch.setattr(desktop_bundle, "xattr_cleanup_targets", lambda: [])
    monkeypatch.setattr(desktop_bundle, "strip_extended_attributes", lambda paths: None)
    monkeypatch.setattr(desktop_bundle, "xattr_sentinel_paths", lambda: [])
    monkeypatch.setattr(desktop_bundle, "blocked_extended_attributes", lambda paths: [])
    monkeypatch.setattr(
        desktop_bundle,
        "probe_fresh_extended_attributes",
        lambda: (
            Path("/tmp/dancelab-host-xattr.probe"),
            ["com.apple.provenance"],
            ["com.apple.provenance"],
        ),
    )
    monkeypatch.setattr(desktop_bundle, "builder_python_path", lambda: Path("/opt/homebrew/bin/python3.12"))

    desktop_bundle.ensure_signable_macos_environment()

    captured = capsys.readouterr()
    assert "preflight warning" in captured.err
    assert "Continuing with the bundle build" in captured.err


def test_build_desktop_bundle_recovers_from_post_build_sanitize_pass(monkeypatch):
    monkeypatch.setattr(desktop_bundle, "ensure_signable_macos_environment", lambda: None)
    monkeypatch.setattr(desktop_bundle, "salvage_macos_signed_app_bundle", lambda path: True)
    monkeypatch.setattr(
        desktop_bundle.subprocess,
        "run",
        lambda command, cwd, env, text, check: SimpleNamespace(args=command, returncode=1),
    )

    result = build_desktop_bundle(dry_run=False)

    assert result.returncode == 0


def test_build_desktop_bundle_recovers_when_successful_build_is_not_verifiable(monkeypatch):
    monkeypatch.setattr(desktop_bundle, "ensure_signable_macos_environment", lambda: None)
    monkeypatch.setattr(
        desktop_bundle.subprocess,
        "run",
        lambda command, cwd, env, text, check: SimpleNamespace(args=command, returncode=0),
    )
    monkeypatch.setattr(
        desktop_bundle,
        "verify_codesigned_app_bundle",
        lambda path: (_ for _ in ()).throw(
            desktop_bundle.subprocess.CalledProcessError(1, ["codesign"])
        ),
    )
    monkeypatch.setattr(desktop_bundle, "salvage_macos_signed_app_bundle", lambda path: True)

    result = build_desktop_bundle(dry_run=False)

    assert result.returncode == 0


def test_strip_root_bundle_metadata_attempts_known_xattrs(monkeypatch, tmp_path):
    bundle = tmp_path / "DanceLab Host.app"
    bundle.mkdir()
    calls: list[list[str]] = []

    def fake_run(command, check, text, capture_output):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(desktop_bundle.sys, "platform", "darwin")
    monkeypatch.setattr(desktop_bundle.subprocess, "run", fake_run)

    strip_root_bundle_metadata(bundle)

    assert [command[2] for command in calls] == [
        "com.apple.FinderInfo",
        "com.apple.fileprovider.fpfs#P",
        "com.apple.provenance",
    ]


def test_mirror_verified_app_bundle_to_fallback_returns_installed_target(monkeypatch, tmp_path):
    source_bundle = tmp_path / "DanceLab Host.app"
    source_bundle.mkdir()
    fallback_bundle = tmp_path / "Applications" / "DanceLab Host.app"

    monkeypatch.setattr(desktop_bundle, "fallback_app_bundle_path", lambda _name: fallback_bundle)
    monkeypatch.setattr(desktop_bundle, "install_verified_app_bundle", lambda source, target: True)

    mirrored = mirror_verified_app_bundle_to_fallback(source_bundle)

    assert mirrored == fallback_bundle
