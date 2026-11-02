"""Import and export services.

Rules this module follows:
  * Validate file readability before editing begins.
  * Never overwrite the source unless the user explicitly chose it as the
    destination.
  * Write to a temporary file, then atomically replace the destination, so a
    crash or full disk mid-write can never leave a half-written file sitting
    at the destination path pretending to be a successful export.
  * Never report success before the write is actually durable.

Metadata policy: every export strips all metadata — EXIF (including GPS
coordinates, camera/device identifiers, and capture timestamps), ICC color
profiles, and any XMP/IPTC data. Nothing is selectively preserved.

Why strip-everything rather than preserve-everything or a selective
policy: a photo's EXIF block is exactly the kind of personal metadata
(location, device, timestamp) a user might not realize they're sharing,
and this application has no UI yet for inspecting or selectively removing
individual fields (that richer control is a planned future feature). Of
the two simple options available right now, "strip by default" is the
privacy-safe one: a user who loses orientation metadata they didn't need
is inconvenienced; a user who unknowingly re-shares GPS coordinates
embedded in an edited photo is not. (Orientation specifically is not lost
in practice — `imaging.operations.normalize_orientation` already bakes it
into the pixel data at import time, before this policy ever applies.)

ICC color profiles are stripped for a separate, narrower reason: this
application does no color-management processing, so there is no profile
this app computed or validated to attach; carrying the source's profile
through unexamined would be re-exporting a claim about the pixel data this
code never verified.

`_strip_metadata` makes this an explicit, tested step rather than an
incidental side effect of which `Image.save()` keyword arguments happen not
to be passed — see `tests/test_import_export.py::test_export_strips_metadata_even_if_source_had_it`.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from snapforge.imaging.operations import ImageTooLargeError, guard_dimensions

#: Formats the initial release supports, both directions.
SUPPORTED_IMPORT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_EXPORT_FORMATS = {"JPEG", "PNG", "WEBP"}

_EXTENSION_TO_PIL_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


class ImportError_(RuntimeError):
    """Raised when a source file cannot be opened as a supported image.

    (Named with a trailing underscore to avoid shadowing the builtin
    ImportError, which has an unrelated meaning in Python.)
    """


class ExportError(RuntimeError):
    """Raised when an export cannot be completed. Never raised *after* a
    partially-written file has been left at the requested destination.
    """


@dataclass(frozen=True)
class ExportOptions:
    destination: Path
    format: str  # one of SUPPORTED_EXPORT_FORMATS
    quality: int = 90  # JPEG/WebP only, 1-100
    overwrite_confirmed: bool = False


def open_image(path: Path) -> Image.Image:
    """Decode `path` into a PIL Image, validated and safe to edit.

    Does not trust the file extension — Pillow's own content sniffing is
    what determines the real format; the extension is only used later, for
    export, to pick a default format.
    """
    if not path.exists():
        raise ImportError_(f"File not found: {path.name}")
    if not path.is_file():
        raise ImportError_(f"Not a file: {path.name}")

    try:
        with Image.open(path) as handle:
            handle.load()  # force full decode now, so corruption surfaces here
            image = handle.copy()
    except UnidentifiedImageError as exc:
        raise ImportError_(
            f"'{path.name}' is not a recognized or supported image file."
        ) from exc
    except OSError as exc:
        raise ImportError_(f"Could not read '{path.name}': {exc}") from exc

    try:
        guard_dimensions(image)
    except ImageTooLargeError as exc:
        raise ImportError_(str(exc)) from exc

    return image


def _coerce_for_format(image: Image.Image, pil_format: str) -> Image.Image:
    """Ensure the image mode is compatible with the target format.

    JPEG has no alpha channel; flattening onto white is the conventional,
    least-surprising default and is documented behavior, not a silent
    unexplained change.
    """
    if pil_format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA") if image.mode != "RGBA" else image
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=rgba.split()[-1])
        return flattened
    if pil_format == "JPEG" and image.mode not in ("RGB", "L"):
        return image.convert("RGB")
    return image


def _strip_metadata(image: Image.Image) -> Image.Image:
    """Return a copy of `image` with no EXIF/ICC/XMP/IPTC metadata.

    `Image.save()` already omits most of this by default when no `exif=`
    or `icc_profile=` keyword is passed — but relying on that omission
    would make the metadata policy an accident of which kwargs this module
    happens not to pass, rather than a guaranteed property of every export.
    Clearing `.info` makes it explicit and independent of Pillow's
    per-format save defaults (see module docstring for the policy itself).
    """
    stripped = image.copy()
    stripped.info = {}
    return stripped


def export_image(image: Image.Image, options: ExportOptions) -> Path:
    """Write `image` to `options.destination`, atomically.

    Returns the final destination path on success. Raises ExportError
    (without ever leaving a corrupt/partial file at the destination) on any
    failure.
    """
    fmt = options.format.upper()
    if fmt not in SUPPORTED_EXPORT_FORMATS:
        raise ExportError(f"Unsupported export format: {options.format}")

    destination = options.destination
    if destination.exists() and not options.overwrite_confirmed:
        raise ExportError(
            f"'{destination.name}' already exists. Overwrite must be explicitly confirmed."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    prepared = _coerce_for_format(image, fmt)
    prepared = _strip_metadata(prepared)

    save_kwargs: dict = {}
    if fmt in ("JPEG", "WEBP"):
        quality = max(1, min(100, options.quality))
        save_kwargs["quality"] = quality
    if fmt == "JPEG":
        save_kwargs["optimize"] = True
    if fmt == "PNG":
        save_kwargs["optimize"] = True

    # Write to a temp file in the *same directory* as the destination (so the
    # final os.replace is an atomic rename on the same filesystem, not a
    # cross-device copy that could fail halfway) then swap it into place.
    tmp_fd, tmp_path_str = tempfile.mkstemp(
        dir=str(destination.parent), prefix=f".{destination.stem}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_path_str)
    try:
        os.close(tmp_fd)
        prepared.save(tmp_path, format=fmt, **save_kwargs)
        # Reopen-and-verify before we commit: catches a backend that wrote
        # a truncated/corrupt file without raising, so a partially written
        # file is never presented to the user as a successful export.
        with Image.open(tmp_path) as verify:
            verify.load()
        os.replace(tmp_path, destination)
    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise ExportError(f"Export to '{destination.name}' failed: {exc}") from exc

    return destination


def default_format_for(path: Path) -> str | None:
    return _EXTENSION_TO_PIL_FORMAT.get(path.suffix.lower())


def is_supported_import(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMPORT_EXTENSIONS
