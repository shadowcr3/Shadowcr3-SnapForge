"""Shared fixtures.

Every fixture here is generated procedurally at test time — no real
personal photographs are used as test fixtures, so the repository never
ships binary image files at all.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image


@pytest.fixture
def rgb_image() -> Image.Image:
    """A standard 40x30 RGB image with a visible gradient (not a flat color,
    so adjustment operations have something non-trivial to act on).
    """
    img = Image.new("RGB", (40, 30))
    pixels = img.load()
    for x in range(40):
        for y in range(30):
            pixels[x, y] = (x * 6 % 256, y * 8 % 256, 128)
    return img


@pytest.fixture
def grayscale_image() -> Image.Image:
    img = Image.new("L", (32, 24))
    pixels = img.load()
    for x in range(32):
        for y in range(24):
            pixels[x, y] = (x * 8) % 256
    return img


@pytest.fixture
def rgba_image() -> Image.Image:
    img = Image.new("RGBA", (20, 20))
    pixels = img.load()
    for x in range(20):
        for y in range(20):
            alpha = 255 if x < 10 else 0
            pixels[x, y] = (200, 50, 50, alpha)
    return img


@pytest.fixture
def portrait_with_orientation_bytes() -> bytes:
    """A JPEG with EXIF orientation=6 (rotated 90 CW) so import-time
    normalization (operations.normalize_orientation) has something to do.
    """
    img = Image.new("RGB", (60, 40), color=(10, 120, 200))
    buffer = io.BytesIO()
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation tag
    img.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


@pytest.fixture
def truncated_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (50, 50), color=(255, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    full = buffer.getvalue()
    return full[: len(full) // 2]
