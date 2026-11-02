"""The central image canvas.

This widget only displays a QPixmap it is given and reports back selection
geometry in *source-image pixel coordinates*. It never decodes, encodes, or
transforms image pixels itself — all of that stays in the imaging layer.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    """Convert a PIL image to a QPixmap without going through a file.

    Centralized here so there is exactly one conversion path to audit for
    correctness (mode handling, byte order) rather than duplicating it.
    """
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    data = image.tobytes("raw", image.mode)
    qformat = QImage.Format.Format_RGBA8888 if image.mode == "RGBA" else QImage.Format.Format_RGB888
    qimage = QImage(data, image.width, image.height, qformat)
    # QImage does not copy the buffer by default; `data` must outlive it, so
    # force a deep copy before `data` (a local) goes out of scope.
    return QPixmap.fromImage(qimage.copy())


#: Discrete zoom steps. A fixed step list — rather than a continuous
#: multiply/divide — keeps "zoom in" / "zoom out" predictable and
#: trivially testable: the result of N clicks never depends on
#: floating-point drift.
ZOOM_STEPS: list[float] = [0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 4.00, 6.00, 8.00]
ZOOM_ACTUAL_SIZE = 1.00


class ImageCanvas(QWidget):
    """Displays the current preview and, in crop mode, lets the user drag a
    selection rectangle. Emits the finished selection in *image pixel*
    coordinates (not widget coordinates) so callers never need to know about
    scale factors.

    Two display modes:
      * **Fit** (`_zoom is None`, the default): the widget is expected to be
        hosted in a `QScrollArea` with `widgetResizable=True`, so this
        widget always matches the viewport size; the image is letterboxed
        within it, scaled down (never up) to fit.
      * **Zoom** (`_zoom` is a float): the widget sets its own fixed size to
        `image_size * zoom` and expects `widgetResizable=False` on its
        `QScrollArea`, so the scroll area shows scrollbars/panning when the
        zoomed image exceeds the viewport. `MainWindow` is responsible for
        toggling `widgetResizable` to match — see `zoom_changed`.
    """

    crop_selected = Signal(int, int, int, int)  # left, top, right, bottom
    zoom_changed = Signal(object)  # float (zoom factor) or None (fit mode)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._pixmap: QPixmap | None = None
        self._crop_mode = False
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._zoom: float | None = None  # None == fit-to-window
        self.setMouseTracking(True)
        # A plain QWidget announces nothing to a screen reader on its own;
        # set this explicitly and keep it current (see set_crop_mode)
        # rather than leaving it blank.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._update_accessible_text()

    def _update_accessible_text(self) -> None:
        self.setAccessibleName("Image canvas")
        if self._crop_mode:
            self.setAccessibleDescription(
                "Crop selection mode. Click and drag to select the area to "
                "keep; the rest will be discarded."
            )
        elif self._pixmap is None:
            self.setAccessibleDescription("No image is open.")
        else:
            self.setAccessibleDescription("Showing the current image preview.")

    # --- Public API ------------------------------------------------------

    def set_image(self, image: Image.Image) -> None:
        self._pixmap = pil_to_qpixmap(image)
        self._apply_zoom_sizing()
        self._update_accessible_text()
        self.update()

    def clear_image(self) -> None:
        self._pixmap = None
        self._zoom = None
        self._update_accessible_text()
        self.update()

    def set_crop_mode(self, enabled: bool) -> None:
        self._crop_mode = enabled
        self._drag_start = None
        self._drag_current = None
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        self._update_accessible_text()
        self.update()

    @property
    def zoom(self) -> float | None:
        """Current zoom factor, or None if in fit-to-window mode."""
        return self._zoom

    def set_zoom_fit(self) -> None:
        """Return to fit-to-window mode (never upscales, letterboxed)."""
        if self._zoom is None:
            return
        self._zoom = None
        self._apply_zoom_sizing()
        self.zoom_changed.emit(None)

    def set_zoom(self, factor: float) -> None:
        """Set an explicit zoom factor, clamped to the supported range."""
        clamped = min(max(factor, ZOOM_STEPS[0]), ZOOM_STEPS[-1])
        if self._zoom == clamped:
            return
        self._zoom = clamped
        self._apply_zoom_sizing()
        self.zoom_changed.emit(clamped)

    def zoom_in(self) -> None:
        self._step_zoom(1)

    def zoom_out(self) -> None:
        self._step_zoom(-1)

    def _step_zoom(self, direction: int) -> None:
        current = self._zoom if self._zoom is not None else ZOOM_ACTUAL_SIZE
        steps_above_or_below = [
            s for s in ZOOM_STEPS if (s > current if direction > 0 else s < current)
        ]
        if not steps_above_or_below:
            return
        next_step = min(steps_above_or_below) if direction > 0 else max(steps_above_or_below)
        self.set_zoom(next_step)

    def _apply_zoom_sizing(self) -> None:
        """Give the widget the fixed size zoom mode needs, or release it
        back to flexible sizing for fit mode. Called whenever the zoom
        factor or the image changes.
        """
        if self._pixmap is None:
            return
        if self._zoom is None:
            self.setMinimumSize(200, 200)
            self.setMaximumSize(16_777_215, 16_777_215)  # Qt's QWIDGETSIZE_MAX
        else:
            size = self._pixmap.size() * self._zoom
            fixed = QSize(max(1, round(size.width())), max(1, round(size.height())))
            self.setFixedSize(fixed)
        self.update()

    # --- Geometry helpers --------------------------------------------------

    def _draw_rect(self) -> QRect:
        """The rectangle, within this widget, that the pixmap is drawn into.

        In zoom mode the widget's own size already equals the zoomed image
        size (see `_apply_zoom_sizing`), so the pixmap fills the whole
        widget. In fit mode the image is letterboxed/centered and never
        upscaled beyond the widget.
        """
        if self._pixmap is None:
            return QRect()
        pm_size = self._pixmap.size()
        if pm_size.width() == 0 or pm_size.height() == 0:
            return QRect()

        if self._zoom is not None:
            return QRect(0, 0, self.width(), self.height())

        widget_size = self.size()
        scale = min(widget_size.width() / pm_size.width(), widget_size.height() / pm_size.height())
        scale = min(scale, 1.0) if scale > 1.0 else scale
        drawn_w = max(1, round(pm_size.width() * scale))
        drawn_h = max(1, round(pm_size.height() * scale))
        x = (widget_size.width() - drawn_w) // 2
        y = (widget_size.height() - drawn_h) // 2
        return QRect(x, y, drawn_w, drawn_h)

    def _widget_to_image_point(self, point: QPoint) -> QPoint | None:
        draw_rect = self._draw_rect()
        if draw_rect.isEmpty() or self._pixmap is None:
            return None
        clamped_x = min(max(point.x(), draw_rect.left()), draw_rect.right())
        clamped_y = min(max(point.y(), draw_rect.top()), draw_rect.bottom())
        rel_x = clamped_x - draw_rect.x()
        rel_y = clamped_y - draw_rect.y()
        scale_x = self._pixmap.width() / draw_rect.width()
        scale_y = self._pixmap.height() / draw_rect.height()
        return QPoint(round(rel_x * scale_x), round(rel_y * scale_y))

    # --- Qt events -----------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if self._pixmap is not None:
            draw_rect = self._draw_rect()
            painter.drawPixmap(draw_rect, self._pixmap)
        else:
            # Friendly first-run state instead of a blank gray rectangle —
            # tells a new user exactly what to do without reading docs.
            painter.setPen(QPen(Qt.GlobalColor.gray))
            empty_state_text = "Open an image to get started\n(File → Open, or Ctrl+O)"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, empty_state_text)

        if self._crop_mode and self._drag_start is not None and self._drag_current is not None:
            selection = QRect(self._drag_start, self._drag_current).normalized()
            pen = QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(selection)

    def mousePressEvent(self, event) -> None:
        if self._crop_mode and self._pixmap is not None:
            self._drag_start = event.position().toPoint()
            self._drag_current = self._drag_start
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._crop_mode and self._drag_start is not None:
            self._drag_current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if not self._crop_mode or self._drag_start is None or self._drag_current is None:
            return
        start_img = self._widget_to_image_point(self._drag_start)
        end_img = self._widget_to_image_point(self._drag_current)
        self._drag_start = None
        self._drag_current = None
        self.update()

        if start_img is None or end_img is None:
            return
        left, right = sorted((start_img.x(), end_img.x()))
        top, bottom = sorted((start_img.y(), end_img.y()))
        #: Ignore accidental clicks/micro-drags rather than emitting a
        #: degenerate near-zero-size crop.
        if right - left < 4 or bottom - top < 4:
            return
        self.crop_selected.emit(left, top, right, bottom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()
