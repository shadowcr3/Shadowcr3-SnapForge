"""The in-memory document model: a protected source image plus edit state.

Non-destructive by design:
  * Keeps the original source separate from the current rendered result.
  * The source is never mutated by any operation in this codebase — callers
    that need the edited pixels call `document.render_full()`, which always
    re-derives the result from `source` + `params` via
    `imaging.operations.render`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from snapforge.imaging import operations
from snapforge.models.history import EditHistory


@dataclass
class ImageDocument:
    """One open image and everything needed to edit and undo/redo it."""

    source_path: Path
    #: The decoded, orientation-normalized source. Treated as read-only
    #: everywhere outside this class's constructor.
    source: Image.Image
    history: EditHistory

    @classmethod
    def from_source(cls, source_path: Path, source_image: Image.Image) -> ImageDocument:
        operations.guard_dimensions(source_image)
        normalized = operations.normalize_orientation(source_image)
        # Defensive copy: whatever decoded `source_image` came from (e.g. a
        # file handle PIL keeps lazily open) should not be able to mutate
        # our protected copy out from under us.
        protected_source = normalized.copy()
        return cls(source_path=source_path, source=protected_source, history=EditHistory())

    @property
    def params(self) -> operations.EditParams:
        return self.history.current

    @property
    def has_unsaved_edits(self) -> bool:
        return not self.params.is_identity()

    def render_full(self) -> Image.Image:
        """Full-resolution render for export. Always derived fresh from the
        protected source — never cached in a way that could go stale, so
        preview and export can never silently diverge.
        """
        return operations.render(self.source, self.params)

    def render_preview(self, max_dimension: int) -> Image.Image:
        """Downscaled render for the on-screen canvas.

        Downscaling happens *after* the full edit pipeline so the preview is
        pixel-equivalent (modulo resampling) to a scaled-down export, not a
        different code path that could drift from it.
        """
        full = self.render_full()
        return operations.resize_to_fit(full, max_dimension)

    def commit(self, new_params: operations.EditParams) -> None:
        self.history.push(new_params)

    def undo(self) -> operations.EditParams:
        return self.history.undo()

    def redo(self) -> operations.EditParams:
        return self.history.redo()
