from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from snapforge.controllers.editor_controller import EditorController
from snapforge.imaging.operations import EditParams
from snapforge.ui.adjustments_panel import _SLIDERS, AdjustmentsPanel


@pytest.fixture
def controller_with_document(tmp_path, rgb_image) -> EditorController:
    path = tmp_path / "source.png"
    rgb_image.save(path, format="PNG")
    c = EditorController()
    c.open_image(path)
    return c


def test_panel_disabled_with_no_document(qtbot):
    controller = EditorController()
    panel = AdjustmentsPanel(controller)
    qtbot.addWidget(panel)
    assert not panel.isEnabled()


def test_dragging_a_slider_updates_live_preview_not_history(qtbot, controller_with_document):
    panel = AdjustmentsPanel(controller_with_document)
    qtbot.addWidget(panel)
    panel.setEnabled(True)

    brightness_row = panel._rows["brightness"]
    brightness_row.slider.setValue(30)  # simulates dragging, not releasing

    assert controller_with_document.document.params.brightness == 0.0
    assert not controller_with_document.document.history.can_undo()


def test_releasing_a_slider_commits_one_history_entry(qtbot, controller_with_document):
    panel = AdjustmentsPanel(controller_with_document)
    qtbot.addWidget(panel)
    panel.setEnabled(True)

    brightness_row = panel._rows["brightness"]
    brightness_row.slider.setValue(30)
    brightness_row._on_released()  # simulate mouse release directly

    assert controller_with_document.document.params.brightness == 30.0
    assert controller_with_document.document.history.can_undo()
    controller_with_document.undo()
    assert controller_with_document.document.params.brightness == 0.0


def test_sync_from_params_updates_all_sliders_without_emitting(qtbot, controller_with_document):
    panel = AdjustmentsPanel(controller_with_document)
    qtbot.addWidget(panel)

    received = []
    for row in panel._rows.values():
        row.live_changed.connect(lambda *a: received.append(a))

    panel.sync_from_params(
        EditParams(brightness=10, contrast=-20, saturation=5, warmth=15, sharpness=-5)
    )

    assert panel._rows["brightness"].slider.value() == 10
    assert panel._rows["contrast"].slider.value() == -20
    assert panel._rows["saturation"].slider.value() == 5
    assert panel._rows["warmth"].slider.value() == 15
    assert panel._rows["sharpness"].slider.value() == -5
    assert received == []  # programmatic sync must not look like user input


def test_reset_button_zeroes_adjustments_but_preserves_geometry(qtbot, controller_with_document):
    from snapforge.imaging.operations import Rotation90

    controller_with_document.rotate_clockwise()
    controller_with_document.commit_adjustment(brightness=40.0, contrast=20.0)

    panel = AdjustmentsPanel(controller_with_document)
    qtbot.addWidget(panel)
    panel.setEnabled(True)
    panel.sync_from_params(controller_with_document.document.params)

    panel.reset_button.click()

    params = controller_with_document.document.params
    assert params.brightness == 0.0
    assert params.contrast == 0.0
    assert params.rotation == Rotation90.CW_90
    assert panel._rows["brightness"].slider.value() == 0


# --- Accessibility -----------------------------------------


def test_every_slider_has_an_accessible_name(qtbot):
    controller = EditorController()
    panel = AdjustmentsPanel(controller)
    qtbot.addWidget(panel)

    for field, label in _SLIDERS:
        row = panel._rows[field]
        assert row.slider.accessibleName(), f"{field} slider has no accessible name"
        assert label.lower() in row.slider.accessibleName().lower()
        assert row.slider.accessibleDescription()


def test_sliders_are_keyboard_focusable(qtbot):
    controller = EditorController()
    panel = AdjustmentsPanel(controller)
    qtbot.addWidget(panel)

    for field, _label in _SLIDERS:
        assert panel._rows[field].slider.focusPolicy() != Qt.FocusPolicy.NoFocus
