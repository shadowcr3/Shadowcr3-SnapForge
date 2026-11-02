from __future__ import annotations

from pathlib import Path

import pytest

from snapforge.imaging.operations import EditParams, Rotation90
from snapforge.models.document import ImageDocument


def test_from_source_protects_against_external_mutation(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    original_pixels = list(doc.source.getdata())

    # Mutate the caller's original image after construction...
    rgb_image.putpixel((0, 0), (255, 255, 255))

    # ...the document's protected copy must be unaffected.
    assert list(doc.source.getdata()) == original_pixels


def test_has_unsaved_edits_false_for_fresh_document(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    assert not doc.has_unsaved_edits


def test_has_unsaved_edits_true_after_commit(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    doc.commit(EditParams(brightness=20))
    assert doc.has_unsaved_edits


def test_render_full_reflects_current_params(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    identity_render = list(doc.render_full().getdata())

    doc.commit(EditParams(rotation=Rotation90.CW_90))
    rotated_render = doc.render_full()
    assert rotated_render.size == (rgb_image.height, rgb_image.width)
    assert (
        list(doc.render_full().getdata()) != identity_render
        or rotated_render.size != rgb_image.size
    )


def test_render_preview_is_never_larger_than_full(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    preview = doc.render_preview(max_dimension=10)
    full = doc.render_full()
    assert max(preview.size) <= max(full.size)


def test_undo_redo_round_trip_through_document(rgb_image):
    doc = ImageDocument.from_source(Path("test.jpg"), rgb_image)
    doc.commit(EditParams(brightness=10))
    doc.commit(EditParams(brightness=20))

    doc.undo()
    assert doc.params == EditParams(brightness=10)
    doc.redo()
    assert doc.params == EditParams(brightness=20)


def test_oversized_source_is_rejected():
    from snapforge.imaging.operations import ImageTooLargeError

    class OversizedStandIn:
        size = (99999, 10)

        def copy(self):
            return self

    with pytest.raises(ImageTooLargeError):
        ImageDocument.from_source(Path("huge.jpg"), OversizedStandIn())  # type: ignore[arg-type]
