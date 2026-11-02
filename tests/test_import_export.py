from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from snapforge.services import import_export as io_service

# --- Import ------------------------------------------------------------


def test_open_image_round_trips_a_valid_png(tmp_path, rgb_image):
    path = tmp_path / "source.png"
    rgb_image.save(path, format="PNG")

    decoded = io_service.open_image(path)
    assert decoded.size == rgb_image.size


def test_open_image_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(io_service.ImportError_):
        io_service.open_image(tmp_path / "does-not-exist.png")


def test_open_image_rejects_non_image_file(tmp_path):
    path = tmp_path / "not-an-image.jpg"
    path.write_bytes(b"this is definitely not image data, just plain text")
    with pytest.raises(io_service.ImportError_):
        io_service.open_image(path)


def test_open_image_rejects_truncated_jpeg(tmp_path, truncated_jpeg_bytes):
    path = tmp_path / "broken.jpg"
    path.write_bytes(truncated_jpeg_bytes)
    with pytest.raises(io_service.ImportError_):
        io_service.open_image(path)


def test_open_image_does_not_trust_extension(tmp_path, rgb_image):
    # A PNG saved with a .jpg extension should still decode correctly,
    # because Pillow sniffs content rather than trusting the extension.
    path = tmp_path / "mislabeled.jpg"
    rgb_image.save(path, format="PNG")
    decoded = io_service.open_image(path)
    assert decoded.size == rgb_image.size


def test_is_supported_import():
    assert io_service.is_supported_import(Path("photo.jpg"))
    assert io_service.is_supported_import(Path("photo.JPEG"))
    assert io_service.is_supported_import(Path("photo.png"))
    assert io_service.is_supported_import(Path("photo.webp"))
    assert not io_service.is_supported_import(Path("photo.tiff"))
    assert not io_service.is_supported_import(Path("photo.raw"))


# --- Export --------------------------------------------------------------


@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")])
def test_export_writes_a_reopenable_file(tmp_path, rgb_image, fmt, ext):
    dest = tmp_path / f"out.{ext}"
    options = io_service.ExportOptions(destination=dest, format=fmt)
    result_path = io_service.export_image(rgb_image, options)

    assert result_path == dest
    assert dest.exists()
    with Image.open(dest) as reopened:
        reopened.load()
        assert reopened.size == rgb_image.size


def test_export_refuses_to_overwrite_without_confirmation(tmp_path, rgb_image):
    dest = tmp_path / "out.png"
    dest.write_bytes(b"pre-existing content")

    options = io_service.ExportOptions(destination=dest, format="PNG", overwrite_confirmed=False)
    with pytest.raises(io_service.ExportError):
        io_service.export_image(rgb_image, options)

    # The pre-existing file must be untouched by the failed attempt.
    assert dest.read_bytes() == b"pre-existing content"


def test_export_overwrites_when_confirmed(tmp_path, rgb_image):
    dest = tmp_path / "out.png"
    dest.write_bytes(b"pre-existing content")

    options = io_service.ExportOptions(destination=dest, format="PNG", overwrite_confirmed=True)
    io_service.export_image(rgb_image, options)

    with Image.open(dest) as reopened:
        reopened.load()
        assert reopened.size == rgb_image.size


def test_export_never_leaves_source_file_as_destination(tmp_path, rgb_image):
    """Exporting must never implicitly target the source path; the service
    only ever writes to `options.destination`, and the controller is
    responsible for requiring the user to choose it explicitly. This test
    pins that `export_image` has no special-case path back to any 'source'.
    """
    source_path = tmp_path / "source.png"
    rgb_image.save(source_path, format="PNG")
    original_bytes = source_path.read_bytes()

    other_dest = tmp_path / "export.png"
    options = io_service.ExportOptions(destination=other_dest, format="PNG")
    io_service.export_image(rgb_image, options)

    assert source_path.read_bytes() == original_bytes


def test_export_rejects_unsupported_format(tmp_path, rgb_image):
    options = io_service.ExportOptions(destination=tmp_path / "out.tiff", format="TIFF")
    with pytest.raises(io_service.ExportError):
        io_service.export_image(rgb_image, options)


def test_export_jpeg_flattens_alpha_onto_white(tmp_path, rgba_image):
    dest = tmp_path / "out.jpg"
    options = io_service.ExportOptions(destination=dest, format="JPEG")
    io_service.export_image(rgba_image, options)

    with Image.open(dest) as reopened:
        reopened.load()
        assert reopened.mode == "RGB"
        # A fully-transparent source pixel should resolve to white, not black
        # or left undefined.
        transparent_region_color = reopened.getpixel((15, 0))
        assert transparent_region_color[0] > 200  # close to white


def test_export_does_not_leave_tmp_files_behind_on_success(tmp_path, rgb_image):
    dest = tmp_path / "out.png"
    options = io_service.ExportOptions(destination=dest, format="PNG")
    io_service.export_image(rgb_image, options)

    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".out.")]
    assert leftovers == []


@pytest.mark.parametrize("fmt,ext", [("JPEG", "jpg"), ("PNG", "png")])
def test_export_strips_metadata_even_if_source_had_it(
    tmp_path, portrait_with_orientation_bytes, fmt, ext
):
    """Pins the documented metadata policy (see import_export.py's module
    docstring): every export is stripped of EXIF/ICC/XMP metadata,
    regardless of what the source carried. This must hold for every
    supported export format, not just the one the source happened to use.
    """
    source_path = tmp_path / "with_exif.jpg"
    source_path.write_bytes(portrait_with_orientation_bytes)
    decoded = io_service.open_image(source_path)
    assert len(decoded.getexif()) > 0, "fixture must actually carry EXIF data for this test"

    dest = tmp_path / f"stripped.{ext}"
    io_service.export_image(decoded, io_service.ExportOptions(destination=dest, format=fmt))

    with Image.open(dest) as reopened:
        reopened.load()
        assert len(reopened.getexif()) == 0
        assert "icc_profile" not in reopened.info


def test_default_format_for_known_extensions():
    assert io_service.default_format_for(Path("a.jpg")) == "JPEG"
    assert io_service.default_format_for(Path("a.jpeg")) == "JPEG"
    assert io_service.default_format_for(Path("a.png")) == "PNG"
    assert io_service.default_format_for(Path("a.webp")) == "WEBP"
    assert io_service.default_format_for(Path("a.tiff")) is None
