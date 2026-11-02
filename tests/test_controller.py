from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from snapforge.controllers.editor_controller import EditorController
from snapforge.imaging.operations import Rotation90
from snapforge.services.import_export import ExportOptions


@pytest.fixture
def source_path(tmp_path, rgb_image) -> Path:
    path = tmp_path / "source.png"
    rgb_image.save(path, format="PNG")
    return path


@pytest.fixture
def controller() -> EditorController:
    return EditorController()


def test_open_image_emits_document_opened_and_preview(qtbot, controller, source_path):
    with qtbot.waitSignals([controller.document_opened, controller.preview_updated], timeout=2000):
        ok = controller.open_image(source_path)
    assert ok
    assert controller.has_document


def test_open_unsupported_extension_emits_error_and_no_document(qtbot, controller, tmp_path):
    bogus = tmp_path / "photo.tiff"
    bogus.write_bytes(b"not a real file, just needs an unsupported extension")
    with qtbot.waitSignal(controller.error_occurred, timeout=2000):
        ok = controller.open_image(bogus)
    assert not ok
    assert not controller.has_document


def test_open_corrupt_file_emits_error(qtbot, controller, tmp_path):
    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"\x89PNG\r\n not actually valid png data")
    with qtbot.waitSignal(controller.error_occurred, timeout=2000):
        ok = controller.open_image(corrupt)
    assert not ok


def test_opening_new_image_discards_previous_history(qtbot, controller, source_path, tmp_path):
    controller.open_image(source_path)
    controller.commit_adjustment(brightness=50.0)
    assert controller.document.params.brightness == 50.0

    second_path = tmp_path / "second.png"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(second_path)
    controller.open_image(second_path)

    assert controller.document.params.brightness == 0.0
    assert not controller.document.history.can_undo()


def test_preview_adjustment_does_not_commit_history(qtbot, controller, source_path):
    controller.open_image(source_path)
    with qtbot.waitSignal(controller.preview_updated, timeout=2000):
        controller.preview_adjustment(brightness=40.0)
    # Live preview must not have touched committed params or history.
    assert controller.document.params.brightness == 0.0
    assert not controller.document.history.can_undo()


def test_commit_adjustment_creates_exactly_one_undo_step(qtbot, controller, source_path):
    controller.open_image(source_path)
    # Simulate a slider drag: many live previews, one final commit.
    for v in (5.0, 10.0, 15.0, 20.0):
        controller.preview_adjustment(brightness=v)
    with qtbot.waitSignal(controller.history_changed, timeout=2000):
        controller.commit_adjustment(brightness=20.0)

    assert controller.document.params.brightness == 20.0
    controller.undo()
    assert controller.document.params.brightness == 0.0
    assert not controller.document.history.can_undo()


def test_rotate_and_flip_are_each_one_undo_step(qtbot, controller, source_path):
    controller.open_image(source_path)
    controller.rotate_clockwise()
    controller.flip_horizontal()
    assert controller.document.params.rotation == Rotation90.CW_90
    assert controller.document.params.flip_horizontal is True

    controller.undo()
    assert controller.document.params.flip_horizontal is False
    assert controller.document.params.rotation == Rotation90.CW_90

    controller.undo()
    assert controller.document.params.rotation == Rotation90.NONE


def test_rotation_after_crop_invalidates_the_crop(qtbot, controller, source_path):
    controller.open_image(source_path)
    controller.apply_crop(2, 2, 20, 15)
    assert controller.document.params.crop_box is not None

    with qtbot.waitSignal(controller.status_message, timeout=2000):
        controller.rotate_clockwise()

    assert controller.document.params.crop_box is None
    assert controller.document.params.rotation == Rotation90.CW_90


def test_apply_crop_out_of_bounds_emits_error_not_crash(qtbot, controller, source_path):
    controller.open_image(source_path)
    width, height = controller.document.source.size
    with qtbot.waitSignal(controller.error_occurred, timeout=2000):
        controller.apply_crop(0, 0, width + 100, height + 100)
    assert controller.document.params.crop_box is None


def test_undo_redo_with_no_document_does_not_raise(qtbot, controller):
    controller.undo()  # no document open at all
    controller.redo()


def test_reset_adjustments_only_preserves_geometry(qtbot, controller, source_path):
    controller.open_image(source_path)
    controller.rotate_clockwise()
    controller.commit_adjustment(brightness=30.0, contrast=10.0)

    controller.reset_adjustments_only()

    assert controller.document.params.brightness == 0.0
    assert controller.document.params.contrast == 0.0
    assert controller.document.params.rotation == Rotation90.CW_90


def test_export_success_emits_export_succeeded(qtbot, controller, source_path, tmp_path):
    controller.open_image(source_path)
    dest = tmp_path / "out.png"
    options = ExportOptions(destination=dest, format="PNG")
    with qtbot.waitSignal(controller.export_succeeded, timeout=5000) as blocker:
        controller.export(options)
    assert blocker.args == [str(dest)]
    assert dest.exists()


def test_export_without_document_emits_export_failed(qtbot, controller, tmp_path):
    dest = tmp_path / "out.png"
    options = ExportOptions(destination=dest, format="PNG")
    with qtbot.waitSignal(controller.export_failed, timeout=2000):
        controller.export(options)
    assert not dest.exists()


def test_export_overwrite_without_confirmation_emits_export_failed(
    qtbot, controller, source_path, tmp_path
):
    controller.open_image(source_path)
    dest = tmp_path / "out.png"
    dest.write_bytes(b"existing")
    options = ExportOptions(destination=dest, format="PNG", overwrite_confirmed=False)
    with qtbot.waitSignal(controller.export_failed, timeout=2000):
        controller.export(options)
    assert dest.read_bytes() == b"existing"


def test_compare_original_shows_unedited_preview(qtbot, controller, source_path):
    controller.open_image(source_path)
    controller.commit_adjustment(brightness=80.0)

    captured: list = []
    controller.preview_updated.connect(captured.append)
    controller.set_compare_original(True)

    assert len(captured) == 1
    original_preview_pixels = list(captured[0].convert("RGB").getdata())
    source_pixels = list(controller.document.source.convert("RGB").getdata())
    # The compare-original preview must match the untouched source, not the
    # brightened working image (allow for preview downscaling: same size
    # here since the source is small enough not to be scaled).
    assert original_preview_pixels == source_pixels
