from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QMessageBox

from snapforge.ui.main_window import MainWindow


@pytest.fixture
def no_blocking_dialogs(monkeypatch):
    """Replace modal QMessageBox calls with no-ops so tests that trigger
    them (Getting Started, About, export success/failure) don't hang
    waiting for a click that will never come.
    """
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "about", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )


def test_window_constructs_with_no_document(qtbot, no_blocking_dialogs):
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.controller.has_document
    assert not window.export_action.isEnabled()


def test_help_menu_actions_exist_and_dont_crash(qtbot, no_blocking_dialogs):
    window = MainWindow()
    qtbot.addWidget(window)

    window._on_getting_started()
    window._on_about()  # must not raise


def test_toolbar_actions_have_tooltips(qtbot, no_blocking_dialogs):
    window = MainWindow()
    qtbot.addWidget(window)

    for action in (
        window.rotate_ccw_action,
        window.rotate_cw_action,
        window.flip_h_action,
        window.flip_v_action,
        window.crop_action,
    ):
        assert action.toolTip(), f"{action.text()} has no tooltip"


def test_toolbar_disabled_until_document_opened(qtbot, no_blocking_dialogs):
    window = MainWindow()
    qtbot.addWidget(window)
    for action in window._toolbar_actions:
        assert not action.isEnabled()


def test_opening_image_enables_toolbar_and_zoom_menu(qtbot, no_blocking_dialogs, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)

    path = tmp_path / "source.png"
    Image.new("RGB", (40, 40), (10, 20, 30)).save(path)
    window.controller.open_image(Path(path))

    for action in window._toolbar_actions:
        assert action.isEnabled()
    assert window.zoom_fit_action.isEnabled()


def test_canvas_shows_empty_state_before_any_image(qtbot, no_blocking_dialogs):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(400, 300)

    # Smoke test: forcing a repaint with no image must not raise. This is
    # what exercises the "Open an image to get started" empty-state text.
    window.canvas.grab()
