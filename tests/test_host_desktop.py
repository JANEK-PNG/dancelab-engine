from dancelab.host import desktop_available, desktop_requirement_message
from dancelab.host.desktop_app import main


def test_desktop_host_reports_optional_dependency_contract():
    message = desktop_requirement_message()
    assert "PySide6" in message
    assert "desktop" in message

    if desktop_available():
        assert callable(main)
    else:
        try:
            main()
        except RuntimeError as exc:
            assert "PySide6" in str(exc)
        else:  # pragma: no cover - only if dependency unexpectedly appears mid-test
            assert False, "desktop host should require PySide6 when unavailable"
