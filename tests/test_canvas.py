from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint

from snapforge.ui.canvas import ZOOM_STEPS, ImageCanvas, pil_to_qpixmap


def test_pil_to_qpixmap_preserves_dimensions(qapp, rgb_image):
    # QPixmap requires a live QApplication/QGuiApplication even for a pure
    # conversion with no widgets involved — `qapp` (from pytest-qt) ensures
    # one exists for the duration of this test.
    pixmap = pil_to_qpixmap(rgb_image)
    assert pixmap.width() == rgb_image.width
    assert pixmap.height() == rgb_image.height


def test_pil_to_qpixmap_handles_rgba(qapp, rgba_image):
    pixmap = pil_to_qpixmap(rgba_image)
    assert pixmap.width() == rgba_image.width
    assert pixmap.height() == rgba_image.height
    assert not pixmap.isNull()


def test_pil_to_qpixmap_handles_grayscale(qapp, grayscale_image):
    pixmap = pil_to_qpixmap(grayscale_image)
    assert not pixmap.isNull()
    assert pixmap.width() == grayscale_image.width


def test_canvas_crop_mode_defaults_off(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    assert canvas._crop_mode is False


def test_canvas_set_image_then_resize_has_centered_draw_rect(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.set_image(Image.new("RGB", (100, 50), (255, 0, 0)))

    draw_rect = canvas._draw_rect()
    assert not draw_rect.isEmpty()
    # Image is wider than tall (2:1); the widget is also wider than tall but
    # more so (4:3), so height should be the limiting dimension and the
    # drawn image should be horizontally centered with margins on each side.
    assert draw_rect.width() < 400
    assert draw_rect.x() > 0


def test_canvas_never_upscales_a_small_image(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.set_image(Image.new("RGB", (20, 20), (0, 255, 0)))

    draw_rect = canvas._draw_rect()
    assert draw_rect.width() == 20
    assert draw_rect.height() == 20


def test_widget_to_image_point_maps_corners_correctly(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.set_image(Image.new("RGB", (100, 100), (0, 0, 255)))

    draw_rect = canvas._draw_rect()
    top_left_image_point = canvas._widget_to_image_point(QPoint(draw_rect.x(), draw_rect.y()))
    assert top_left_image_point == QPoint(0, 0)

    bottom_right_widget_point = QPoint(draw_rect.right(), draw_rect.bottom())
    bottom_right_image_point = canvas._widget_to_image_point(bottom_right_widget_point)
    # Allow +/-1px rounding at the boundary.
    assert abs(bottom_right_image_point.x() - 99) <= 1
    assert abs(bottom_right_image_point.y() - 99) <= 1


def test_widget_to_image_point_clamps_outside_draw_rect(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.set_image(Image.new("RGB", (100, 100), (0, 0, 255)))

    # A point far outside the widget entirely should still clamp to a valid
    # in-bounds image coordinate rather than returning something negative or
    # out of range.
    result = canvas._widget_to_image_point(QPoint(-500, -500))
    assert result is not None
    assert 0 <= result.x() <= 100
    assert 0 <= result.y() <= 100


def test_widget_to_image_point_none_without_image(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    assert canvas._widget_to_image_point(QPoint(10, 10)) is None


def test_crop_selected_emits_sorted_bounds(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.set_image(Image.new("RGB", (100, 100), (0, 0, 255)))
    canvas.set_crop_mode(True)

    draw_rect = canvas._draw_rect()
    # Drag from bottom-right to top-left — the emitted box must still come
    # out with left<right and top<bottom (sorted), not raw drag order.
    start = QPoint(draw_rect.right() - 10, draw_rect.bottom() - 10)
    end = QPoint(draw_rect.x() + 10, draw_rect.y() + 10)

    with qtbot.waitSignal(canvas.crop_selected, timeout=1000) as blocker:
        _simulate_release(canvas, start, end)

    emitted_left, emitted_top, emitted_right, emitted_bottom = blocker.args
    assert emitted_left < emitted_right
    assert emitted_top < emitted_bottom


def _simulate_release(canvas: ImageCanvas, start: QPoint, end: QPoint):
    canvas._drag_start = start
    canvas._drag_current = end

    class _FakeEvent:
        pass

    canvas.mouseReleaseEvent(_FakeEvent())
    return start.x(), start.y(), end.x(), end.y()


def test_tiny_drag_does_not_emit_crop_selected(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 400)
    canvas.set_image(Image.new("RGB", (100, 100), (0, 0, 255)))
    canvas.set_crop_mode(True)

    draw_rect = canvas._draw_rect()
    start = QPoint(draw_rect.x() + 10, draw_rect.y() + 10)
    end = QPoint(draw_rect.x() + 11, draw_rect.y() + 11)  # 1px drag

    received = []
    canvas.crop_selected.connect(lambda *args: received.append(args))
    _simulate_release(canvas, start, end)
    assert received == []


# --- Zoom (fit-to-window, zoom, and image refresh) -------------------------


def test_zoom_defaults_to_fit(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    assert canvas.zoom is None


def test_set_zoom_clamps_to_supported_range(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (50, 50)))

    canvas.set_zoom(1000.0)
    assert canvas.zoom == ZOOM_STEPS[-1]

    canvas.set_zoom(-5.0)
    assert canvas.zoom == ZOOM_STEPS[0]


def test_set_zoom_resizes_canvas_to_zoomed_image_size(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (100, 50)))

    canvas.set_zoom(2.0)
    assert canvas.width() == 200
    assert canvas.height() == 100


def test_zoom_in_steps_through_fixed_levels(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))

    assert canvas.zoom is None  # starts at fit
    canvas.zoom_in()
    assert canvas.zoom == 1.50  # next step above the 1.0 "fit" baseline
    canvas.zoom_in()
    assert canvas.zoom == 2.00


def test_zoom_out_steps_down_and_stops_at_minimum(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))

    canvas.set_zoom(ZOOM_STEPS[1])
    canvas.zoom_out()
    assert canvas.zoom == ZOOM_STEPS[0]
    canvas.zoom_out()  # already at minimum — must not raise or go lower
    assert canvas.zoom == ZOOM_STEPS[0]


def test_zoom_in_stops_at_maximum(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))

    canvas.set_zoom(ZOOM_STEPS[-1])
    canvas.zoom_in()
    assert canvas.zoom == ZOOM_STEPS[-1]


def test_set_zoom_fit_returns_to_fit_mode(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))
    canvas.set_zoom(2.0)
    assert canvas.zoom is not None

    canvas.set_zoom_fit()
    assert canvas.zoom is None


def test_zoom_changed_signal_emits_on_every_change(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))

    with qtbot.waitSignal(canvas.zoom_changed, timeout=1000) as blocker:
        canvas.set_zoom(1.5)
    assert blocker.args == [1.5]

    with qtbot.waitSignal(canvas.zoom_changed, timeout=1000) as blocker:
        canvas.set_zoom_fit()
    assert blocker.args == [None]


def test_draw_rect_fills_whole_widget_in_zoom_mode(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (50, 30)))
    canvas.set_zoom(2.0)

    draw_rect = canvas._draw_rect()
    assert draw_rect.width() == canvas.width()
    assert draw_rect.height() == canvas.height()
    assert draw_rect.x() == 0
    assert draw_rect.y() == 0


def test_crop_coordinate_mapping_correct_at_2x_zoom(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (100, 100)))
    canvas.set_zoom(2.0)  # canvas is now exactly 200x200

    # At 2x zoom, widget point (50, 50) should map to image point (25, 25).
    result = canvas._widget_to_image_point(QPoint(50, 50))
    assert result == QPoint(25, 25)


def test_setting_new_image_preserves_current_zoom(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))
    canvas.set_zoom(2.0)

    canvas.set_image(Image.new("RGB", (60, 20)))
    assert canvas.zoom == 2.0
    assert canvas.width() == 120
    assert canvas.height() == 40


# --- Accessibility -----------------------------------------


def test_canvas_has_accessible_name_before_any_image(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    assert canvas.accessibleName() == "Image canvas"
    assert "no image" in canvas.accessibleDescription().lower()


def test_canvas_accessible_description_updates_with_image(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))
    assert "no image" not in canvas.accessibleDescription().lower()


def test_canvas_accessible_description_reflects_crop_mode(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.set_image(Image.new("RGB", (40, 40)))

    canvas.set_crop_mode(True)
    assert "crop" in canvas.accessibleDescription().lower()

    canvas.set_crop_mode(False)
    assert "crop" not in canvas.accessibleDescription().lower()


def test_canvas_is_keyboard_focusable(qtbot):
    canvas = ImageCanvas()
    qtbot.addWidget(canvas)
    from PySide6.QtCore import Qt

    assert canvas.focusPolicy() != Qt.FocusPolicy.NoFocus
