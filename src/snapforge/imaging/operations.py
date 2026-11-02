"""Pure image operations for SnapForge.

Design rules:
  * Every function here accepts an explicit `PIL.Image.Image` and explicit
    parameters, and returns a *new* image. None of them mutate their input.
  * No function in this module touches Qt, the filesystem, or global state.
    That keeps the operations independently unit-testable and reusable from
    both the live preview renderer and the final export path, which is what
    guarantees preview/export consistency.
  * Adjustment parameters are expressed on a human-friendly -100..100 scale
    (0 == no change) rather than raw PIL enhancement factors, so the UI and
    the tests share one unambiguous contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

# ---------------------------------------------------------------------------
# Constants / limits
# ---------------------------------------------------------------------------

#: Adjustment sliders are clamped to this symmetric range. Clamping happens
#: explicitly and only here — it's how a slider UI is expected to work.
ADJUSTMENT_MIN = -100.0
ADJUSTMENT_MAX = 100.0

#: Defensive ceiling against decompression-bomb style inputs. A
#: 12,000 x 12,000 image is already far beyond typical camera output.
MAX_IMAGE_DIMENSION = 12000


class ImageTooLargeError(ValueError):
    """Raised when a source image exceeds MAX_IMAGE_DIMENSION in either axis."""


class InvalidCropError(ValueError):
    """Raised when a requested crop box is out of bounds or degenerate."""


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def guard_dimensions(image: Image.Image) -> None:
    """Raise ImageTooLargeError if the image exceeds the safety ceiling.

    Called on import (services/import_export.py) before any processing, so
    a hostile or corrupt file with an absurd declared size cannot be used to
    exhaust memory.
    """
    w, h = image.size
    if w <= 0 or h <= 0:
        raise ImageTooLargeError(f"Image has non-positive dimensions: {w}x{h}")
    if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
        raise ImageTooLargeError(
            f"Image dimensions {w}x{h} exceed the supported maximum "
            f"({MAX_IMAGE_DIMENSION}px per side)."
        )


# ---------------------------------------------------------------------------
# Adjustments (color / tone)
# ---------------------------------------------------------------------------


def apply_brightness(image: Image.Image, amount: float) -> Image.Image:
    """amount in [-100, 100]; 0 = unchanged. Maps to a PIL enhance factor."""
    amount = _clamp(amount, ADJUSTMENT_MIN, ADJUSTMENT_MAX)
    factor = 1.0 + (amount / 100.0)
    if factor == 1.0:
        return image.copy()
    return ImageEnhance.Brightness(image).enhance(factor)


def apply_contrast(image: Image.Image, amount: float) -> Image.Image:
    amount = _clamp(amount, ADJUSTMENT_MIN, ADJUSTMENT_MAX)
    factor = 1.0 + (amount / 100.0)
    if factor == 1.0:
        return image.copy()
    return ImageEnhance.Contrast(image).enhance(factor)


def apply_saturation(image: Image.Image, amount: float) -> Image.Image:
    amount = _clamp(amount, ADJUSTMENT_MIN, ADJUSTMENT_MAX)
    factor = 1.0 + (amount / 100.0)
    if factor == 1.0:
        return image.copy()
    # ImageEnhance.Color requires a mode it can decompose into luminance;
    # convert-and-restore keeps callers free of mode bookkeeping.
    if image.mode in ("P",):
        rgb = image.convert("RGBA" if "transparency" in image.info else "RGB")
        return ImageEnhance.Color(rgb).enhance(factor)
    return ImageEnhance.Color(image).enhance(factor)


def apply_warmth(image: Image.Image, amount: float) -> Image.Image:
    """Shift the white balance toward orange (+) or blue (-).

    amount in [-100, 100]; 0 = unchanged. Implemented as a linear per-channel
    gain on R and B — a simple, deterministic approximation of a proper
    white-balance "temperature/tint" control. A true curve-based version is
    planned (see docs/ROADMAP.md); this is the documented v0.1 stand-in.
    """
    amount = _clamp(amount, ADJUSTMENT_MIN, ADJUSTMENT_MAX)
    if amount == 0.0:
        return image.copy()

    working_mode = image.mode
    has_alpha = working_mode in ("RGBA", "LA") or "transparency" in image.info
    rgb_image = image.convert("RGBA" if has_alpha else "RGB")

    arr = np.asarray(rgb_image).astype(np.float32)
    strength = amount / 100.0  # -1.0 .. 1.0
    r_gain = 1.0 + (0.30 * strength)
    b_gain = 1.0 - (0.30 * strength)

    arr[..., 0] = np.clip(arr[..., 0] * r_gain, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * b_gain, 0, 255)

    result = Image.fromarray(arr.astype(np.uint8), mode=rgb_image.mode)
    if result.mode != working_mode:
        result = result.convert(working_mode)
    return result


def apply_sharpness(image: Image.Image, amount: float) -> Image.Image:
    """amount in [-100, 100]; 0 = unchanged, negative = soften."""
    amount = _clamp(amount, ADJUSTMENT_MIN, ADJUSTMENT_MAX)
    factor = 1.0 + (amount / 100.0)
    if factor == 1.0:
        return image.copy()
    return ImageEnhance.Sharpness(image).enhance(factor)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class Rotation90(IntEnum):
    """Quarter-turn rotation steps.

    v0.1 supports only 90-degree-increment rotation. Free-angle rotation
    requires canvas-size/bounding-box decisions (fill color, resampling,
    crop-to-fit) that are explicitly out of the 10-hour scope —
    this is a deliberate, documented boundary, not an oversight.
    """

    NONE = 0
    CW_90 = 1
    CW_180 = 2
    CW_270 = 3


def rotate90(image: Image.Image, steps: Rotation90) -> Image.Image:
    steps = Rotation90(int(steps) % 4)
    if steps == Rotation90.NONE:
        return image.copy()
    # PIL's Image.rotate(angle) rotates counter-clockwise for positive angles;
    # negate to present a clockwise-stepping API to callers (matches the
    # conventional "rotate right" UI button).
    angle = -90 * int(steps)
    return image.rotate(angle, expand=True)


def flip(image: Image.Image, horizontal: bool = False, vertical: bool = False) -> Image.Image:
    result = image
    if horizontal:
        result = ImageOps.mirror(result)
    if vertical:
        result = ImageOps.flip(result)
    if not horizontal and not vertical:
        result = result.copy()
    return result


def crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """box = (left, top, right, bottom) in source-pixel coordinates."""
    left, top, right, bottom = box
    width, height = image.size

    if left < 0 or top < 0 or right > width or bottom > height:
        raise InvalidCropError(
            f"Crop box {box} is outside the image bounds (0, 0, {width}, {height})."
        )
    if right <= left or bottom <= top:
        raise InvalidCropError(f"Crop box {box} has non-positive width/height.")

    return image.crop((left, top, right, bottom))


def resize_to_fit(image: Image.Image, max_dimension: int) -> Image.Image:
    """Downscale (never upscale) so the longer side is <= max_dimension.

    Used by the preview renderer — never used on the export path,
    so exported pixels always come from full-resolution processing.
    """
    width, height = image.size
    longer_side = max(width, height)
    if longer_side <= max_dimension or max_dimension <= 0:
        return image.copy()
    scale = max_dimension / float(longer_side)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def normalize_orientation(image: Image.Image) -> Image.Image:
    """Bake EXIF orientation into pixel data and strip the tag.

    Doing this once at import time means every downstream consumer (preview,
    crop math, export) can treat image.size as the visually-correct size.
    """
    return ImageOps.exif_transpose(image) or image.copy()


# ---------------------------------------------------------------------------
# Edit parameters — the full, explicit, ordered pipeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True)
class EditParams:
    """The complete, serializable set of parameters for one edit state.

    Frozen + immutable by design: every edit command produces a *new*
    EditParams via `replace()` rather than mutating a shared instance. That
    is what makes undo/redo a simple stack of EditParams snapshots
    instead of a diffing problem.
    """

    crop_box: CropBox | None = None
    rotation: Rotation90 = Rotation90.NONE
    flip_horizontal: bool = False
    flip_vertical: bool = False
    brightness: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    warmth: float = 0.0
    sharpness: float = 0.0

    def with_changes(self, **kwargs) -> EditParams:
        return replace(self, **kwargs)

    def is_identity(self) -> bool:
        return self == EditParams()


#: Canonical, fixed operation order — this is the one place the order is
#: defined, and it never changes based on how many times a preview is
#: refreshed. Rotate/flip happen first, then crop, then color adjustments,
#: then sharpness last.
#:
#: Why rotate/flip before crop (a deliberate, documented decision — not an
#: arbitrary order): the crop UI (ui/canvas.py) lets the user draw a
#: selection rectangle on what is currently displayed. The only way that
#: rectangle's pixel coordinates stay meaningful is if `render()` applies
#: the *same* rotation/flip the user was looking at before it applies the
#: crop. The controller enforces the other half of this contract: changing
#: rotation or flip after a crop exists invalidates (clears) that crop
#: rather than silently reinterpreting its coordinates against a different
#: image (see EditorController._invalidate_crop_on_geometry_change).
#:
#: Sharpening is applied last so it acts on the final pixel data rather than
#: being amplified or muted by adjustments applied after it.
def render(source: Image.Image, params: EditParams) -> Image.Image:
    """Apply `params` to `source` in the one canonical order and return the
    result. `source` is never mutated. This single function is used by both
    the preview renderer and the export service, which is what guarantees
    they never disagree.
    """
    result = source

    if params.rotation != Rotation90.NONE:
        result = rotate90(result, params.rotation)

    if params.flip_horizontal or params.flip_vertical:
        result = flip(result, horizontal=params.flip_horizontal, vertical=params.flip_vertical)

    if params.crop_box is not None:
        result = crop(result, params.crop_box.as_tuple())

    if params.brightness != 0.0:
        result = apply_brightness(result, params.brightness)
    if params.contrast != 0.0:
        result = apply_contrast(result, params.contrast)
    if params.saturation != 0.0:
        result = apply_saturation(result, params.saturation)
    if params.warmth != 0.0:
        result = apply_warmth(result, params.warmth)
    if params.sharpness != 0.0:
        result = apply_sharpness(result, params.sharpness)

    if result is source:
        result = source.copy()
    return result
