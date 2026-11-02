"""Application / editing controller.

Coordinates user actions, editing commands, undo/redo, previews, and
export, and validates operations before they reach the image-processing
layer.

This class is the *only* thing the UI layer talks to for editing logic. It
owns no Qt widgets and does no painting — it exposes Qt signals so the UI
can react, which keeps `ui/` a thin presentation layer: it never touches
image-processing code and never writes image files directly.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Signal

from snapforge.imaging.operations import (
    CropBox,
    EditParams,
    InvalidCropError,
    Rotation90,
    crop,
    flip,
    rotate90,
)
from snapforge.models.document import ImageDocument
from snapforge.services import import_export as io_service

#: Preview renders are capped to this longer-side dimension, so the live
#: preview stays responsive. Export always uses the full-resolution source.
PREVIEW_MAX_DIMENSION = 1600


class EditorController(QObject):
    # --- Signals the UI subscribes to -------------------------------------
    document_opened = Signal()
    document_closed = Signal()
    preview_updated = Signal(object)  # PIL.Image.Image
    history_changed = Signal(bool, bool)  # can_undo, can_redo
    error_occurred = Signal(str, str)  # title, message
    status_message = Signal(str)
    export_succeeded = Signal(str)  # destination path as str
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._document: ImageDocument | None = None
        self._compare_original = False

    # --- Document lifecycle --------------------------------------------

    @property
    def document(self) -> ImageDocument | None:
        return self._document

    @property
    def has_document(self) -> bool:
        return self._document is not None

    def open_image(self, path: Path) -> bool:
        """Load `path` as the active document. Returns True on success.

        Any previous document (and its undo/redo history) is fully
        discarded, so opening a new image never accidentally carries over
        the previous image's edits.
        """
        path = Path(path)
        if not io_service.is_supported_import(path):
            self.error_occurred.emit(
                "Unsupported file",
                f"'{path.suffix or path.name}' is not a supported image format. "
                "SnapForge supports JPEG, PNG, and WebP.",
            )
            return False

        try:
            decoded = io_service.open_image(path)
        except io_service.ImportError_ as exc:
            self.error_occurred.emit("Couldn't open image", str(exc))
            return False

        try:
            self._document = ImageDocument.from_source(path, decoded)
        except Exception as exc:
            self.error_occurred.emit("Couldn't open image", str(exc))
            self._document = None
            return False

        self._compare_original = False
        self.document_opened.emit()
        self._emit_history_state()
        self._refresh_preview()
        self.status_message.emit(f"Opened {path.name}")
        return True

    def close_document(self) -> None:
        self._document = None
        self.document_closed.emit()

    # --- Adjustments (continuous sliders) --------------------------------

    def preview_adjustment(self, **changes: float) -> None:
        """Live-preview a slider in motion. Does NOT touch history.

        The controller tracks nothing special here: it renders a hypothetical
        EditParams (current committed params + `changes`) without pushing it
        anywhere. The caller is responsible for calling `commit_adjustment`
        with the final value once the user releases the control — that is
        what turns continuous dragging into exactly one undo step.
        """
        if self._document is None:
            return
        trial_params = self._document.params.with_changes(**changes)
        self._render_and_emit(trial_params)

    def commit_adjustment(self, **changes: float) -> None:
        if self._document is None:
            return
        new_params = self._document.params.with_changes(**changes)
        self._document.commit(new_params)
        self._emit_history_state()
        self._refresh_preview()

    # --- Geometry (discrete actions, each is its own undo step) ----------

    def rotate_clockwise(self) -> None:
        self._apply_discrete(
            lambda p: self._invalidate_crop_on_geometry_change(p).with_changes(
                rotation=Rotation90((int(p.rotation) + 1) % 4)
            )
        )

    def rotate_counterclockwise(self) -> None:
        self._apply_discrete(
            lambda p: self._invalidate_crop_on_geometry_change(p).with_changes(
                rotation=Rotation90((int(p.rotation) - 1) % 4)
            )
        )

    def flip_horizontal(self) -> None:
        self._apply_discrete(
            lambda p: self._invalidate_crop_on_geometry_change(p).with_changes(
                flip_horizontal=not p.flip_horizontal
            )
        )

    def flip_vertical(self) -> None:
        self._apply_discrete(
            lambda p: self._invalidate_crop_on_geometry_change(p).with_changes(
                flip_vertical=not p.flip_vertical
            )
        )

    def _invalidate_crop_on_geometry_change(self, params: EditParams) -> EditParams:
        """A crop box is defined relative to the rotate+flip output at the
        moment it was drawn (see ui/canvas.py + apply_crop). Changing
        rotation or flip after a crop exists would silently re-interpret
        those coordinates against a different image, producing a wrong crop
        — so instead we explicitly drop the stale crop and tell the user,
        rather than silently producing incorrect geometry.
        """
        if params.crop_box is not None:
            self.status_message.emit("Crop was reset because rotation/flip changed.")
            return params.with_changes(crop_box=None)
        return params

    def apply_crop(self, left: int, top: int, right: int, bottom: int) -> None:
        if self._document is None:
            return
        box = CropBox(left, top, right, bottom)

        # Validate BEFORE committing anything to history. An invalid crop
        # must never reach EditHistory: history.push() has already
        # happened by the time a lazy render would discover the problem,
        # which would leave the document permanently stuck on a crop_box
        # that fails every subsequent render.
        try:
            crop(self._geometry_reference_image(), box.as_tuple())
        except InvalidCropError as exc:
            self.error_occurred.emit("Invalid crop", str(exc))
            return

        self._apply_discrete(lambda p: p.with_changes(crop_box=box))

    def _geometry_reference_image(self):
        """The source after rotate/flip but before crop/color — the exact
        coordinate space ui/canvas.py draws crop selections against (see
        operations.render's docstring for why rotate/flip precede crop).
        """
        assert self._document is not None
        params = self._document.params
        image = self._document.source
        if params.rotation != Rotation90.NONE:
            image = rotate90(image, params.rotation)
        if params.flip_horizontal or params.flip_vertical:
            image = flip(image, horizontal=params.flip_horizontal, vertical=params.flip_vertical)
        return image

    def clear_crop(self) -> None:
        self._apply_discrete(lambda p: p.with_changes(crop_box=None))

    def reset_all_edits(self) -> None:
        self._apply_discrete(lambda _p: EditParams())

    def reset_adjustments_only(self) -> None:
        """Zero brightness/contrast/saturation/warmth/sharpness but leave
        crop, rotation, and flip untouched — the UI label and tooltip for
        this action are explicit about that scope.
        """
        self._apply_discrete(
            lambda p: p.with_changes(
                brightness=0.0, contrast=0.0, saturation=0.0, warmth=0.0, sharpness=0.0
            )
        )

    # --- Undo / redo -------------------------------------------------------

    def undo(self) -> None:
        if self._document is None:
            return
        self._document.undo()
        self._emit_history_state()
        self._refresh_preview()

    def redo(self) -> None:
        if self._document is None:
            return
        self._document.redo()
        self._emit_history_state()
        self._refresh_preview()

    # --- Before / after ------------------------------------------------

    def set_compare_original(self, enabled: bool) -> None:
        self._compare_original = enabled
        self._refresh_preview()

    # --- Export ----------------------------------------------------------

    def export(self, options: io_service.ExportOptions) -> None:
        if self._document is None:
            self.export_failed.emit("No image is open.")
            return
        try:
            full = self._document.render_full()
            final_path = io_service.export_image(full, options)
        except io_service.ExportError as exc:
            self.export_failed.emit(str(exc))
            return
        except Exception as exc:
            self.export_failed.emit(f"Unexpected export failure: {exc}")
            return
        self.export_succeeded.emit(str(final_path))

    # --- Internal helpers --------------------------------------------------

    def _apply_discrete(self, transform) -> None:
        if self._document is None:
            return
        new_params = transform(self._document.params)
        self._document.commit(new_params)
        self._emit_history_state()
        self._refresh_preview()

    def _emit_history_state(self) -> None:
        if self._document is None:
            self.history_changed.emit(False, False)
            return
        history = self._document.history
        self.history_changed.emit(history.can_undo(), history.can_redo())

    def _refresh_preview(self) -> None:
        if self._document is None:
            return
        if self._compare_original:
            preview = self._render_source_preview()
        else:
            preview = self._document.render_preview(PREVIEW_MAX_DIMENSION)
        self.preview_updated.emit(preview)

    def _render_source_preview(self) -> Image.Image:
        from snapforge.imaging.operations import resize_to_fit

        assert self._document is not None
        return resize_to_fit(self._document.source, PREVIEW_MAX_DIMENSION)

    def _render_and_emit(self, params: EditParams) -> None:
        if self._document is None:
            return
        from snapforge.imaging.operations import render, resize_to_fit

        full = render(self._document.source, params)
        preview = resize_to_fit(full, PREVIEW_MAX_DIMENSION)
        self.preview_updated.emit(preview)
