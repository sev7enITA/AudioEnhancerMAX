from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("AppKit")
pytest.importorskip("WebKit")

from desktop import native_window
from Foundation import NSURL


def file_url(path, *, directory=False):
    return NSURL.fileURLWithPath_isDirectory_(str(path), directory)


def test_workspace_picker_uses_backend_suffixes_and_preserves_folders(tmp_path):
    delegate = native_window.WorkspaceFilePanelDelegate.alloc().init()
    for extension in native_window.ALLOWED_EXTENSIONS:
        assert delegate.panel_shouldEnableURL_(None, file_url(tmp_path / f"clip{extension.upper()}"))
    for name in ("text.txt", "audio.oga", "audio.aiff", "video.mov", "clip.wav.txt", ".wav"):
        assert not delegate.panel_shouldEnableURL_(None, file_url(tmp_path / name))
    directory = file_url(tmp_path / "recordings", directory=True)
    assert delegate.panel_shouldEnableURL_(None, directory)
    assert not native_window._workspace_file_url(directory)


def test_native_dialog_enforces_workspace_only(tmp_path, monkeypatch):
    other_format = file_url(tmp_path / "verification.mov")
    panel = Mock()
    panel.runModal.return_value = native_window.NSModalResponseOK
    panel.URLs.return_value = [other_format]
    wrapper = SimpleNamespace(alloc=lambda: SimpleNamespace(init=lambda: panel))
    monkeypatch.setattr(native_window, "NSOpenPanel", wrapper)
    app = native_window.NativeAppDelegate.alloc().init()
    selected = []

    app._open_file_panel(True, False, True, selected.append)
    assert selected == [None]
    panel.setAllowedFileTypes_.assert_called_once_with(
        sorted(extension[1:] for extension in native_window.ALLOWED_EXTENSIONS)
    )
    panel.setCanChooseDirectories_.assert_called_with(False)

    selected.clear()
    panel.reset_mock()
    app._open_file_panel(True, True, False, selected.append)
    assert selected == [[other_format]]
    panel.setAllowedFileTypes_.assert_not_called()
    panel.setCanChooseDirectories_.assert_called_with(True)
    panel.setAllowsMultipleSelection_.assert_called_with(True)
