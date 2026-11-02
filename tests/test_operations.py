from __future__ import annotations

import pytest

from snapforge.imaging import operations as ops

# --- Adjustments: identity, determinism, no source mutation -----------------


@pytest.mark.parametrize(
    "func",
    [ops.apply_brightness, ops.apply_contrast, ops.apply_saturation, ops.apply_sharpness],
)
def test_zero_amount_is_identity_in_pixels(rgb_image, func):
    result = func(rgb_image, 0.0)
    assert result.size == rgb_image.size
    assert list(result.getdata()) == list(rgb_image.getdata())


def test_warmth_zero_is_identity(rgb_image):
    result = ops.apply_warmth(rgb_image, 0.0)
    assert list(result.getdata()) == list(rgb_image.getdata())


@pytest.mark.parametrize(
    "func,amount",
    [
        (ops.apply_brightness, 40),
        (ops.apply_contrast, -30),
        (ops.apply_saturation, 50),
        (ops.apply_warmth, 60),
        (ops.apply_sharpness, 25),
    ],
)
def test_adjustment_does_not_mutate_source(rgb_image, func, amount):
    original_pixels = list(rgb_image.getdata())
    func(rgb_image, amount)
    assert list(rgb_image.getdata()) == original_pixels


def test_adjustment_is_deterministic(rgb_image):
    a = ops.apply_brightness(rgb_image, 30)
    b = ops.apply_brightness(rgb_image, 30)
    assert list(a.getdata()) == list(b.getdata())


def test_warmth_increases_red_decreases_blue(rgb_image):
    warmed = ops.apply_warmth(rgb_image, 100)
    src_pixels = list(rgb_image.convert("RGB").getdata())
    warm_pixels = list(warmed.getdata())
    reds_increased = sum(1 for s, w in zip(src_pixels, warm_pixels, strict=True) if w[0] >= s[0])
    blues_decreased = sum(1 for s, w in zip(src_pixels, warm_pixels, strict=True) if w[2] <= s[2])
    assert reds_increased == len(src_pixels)
    assert blues_decreased == len(src_pixels)


def test_adjustments_clamp_out_of_range_values(rgb_image):
    # Values outside [-100, 100] must not raise; they are clamped.
    result = ops.apply_brightness(rgb_image, 10_000)
    assert result.size == rgb_image.size


def test_grayscale_image_survives_all_adjustments(grayscale_image):
    result = grayscale_image
    for func, amount in [
        (ops.apply_brightness, 20),
        (ops.apply_contrast, 20),
        (ops.apply_sharpness, 20),
    ]:
        result = func(result, amount)
    assert result.size == grayscale_image.size


def test_saturation_on_rgba_preserves_alpha(rgba_image):
    result = ops.apply_saturation(rgba_image, 50)
    assert result.mode in ("RGBA",)
    original_alpha = [p[3] for p in rgba_image.getdata()]
    result_alpha = [p[3] for p in result.getdata()]
    assert original_alpha == result_alpha


def test_warmth_preserves_alpha_channel(rgba_image):
    result = ops.apply_warmth(rgba_image, 70)
    original_alpha = [p[3] for p in rgba_image.getdata()]
    result_alpha = [p[3] for p in result.getdata()]
    assert original_alpha == result_alpha


# --- Geometry --------------------------------------------------------------


def test_rotate_90_swaps_dimensions(rgb_image):
    rotated = ops.rotate90(rgb_image, ops.Rotation90.CW_90)
    assert rotated.size == (rgb_image.height, rgb_image.width)


def test_rotate_180_keeps_dimensions(rgb_image):
    rotated = ops.rotate90(rgb_image, ops.Rotation90.CW_180)
    assert rotated.size == rgb_image.size


def test_rotate_four_times_returns_to_original(rgb_image):
    result = rgb_image
    for _ in range(4):
        result = ops.rotate90(result, ops.Rotation90.CW_90)
    assert result.size == rgb_image.size
    assert list(result.getdata()) == list(rgb_image.getdata())


def test_rotate_none_is_identity(rgb_image):
    result = ops.rotate90(rgb_image, ops.Rotation90.NONE)
    assert list(result.getdata()) == list(rgb_image.getdata())


def test_flip_horizontal_reverses_rows(rgb_image):
    flipped = ops.flip(rgb_image, horizontal=True)
    assert flipped.size == rgb_image.size
    assert flipped.getpixel((0, 0)) == rgb_image.getpixel((rgb_image.width - 1, 0))


def test_flip_vertical_reverses_columns(rgb_image):
    flipped = ops.flip(rgb_image, vertical=True)
    assert flipped.getpixel((0, 0)) == rgb_image.getpixel((0, rgb_image.height - 1))


def test_double_flip_returns_to_original(rgb_image):
    result = ops.flip(rgb_image, horizontal=True)
    result = ops.flip(result, horizontal=True)
    assert list(result.getdata()) == list(rgb_image.getdata())


def test_crop_produces_correct_dimensions(rgb_image):
    cropped = ops.crop(rgb_image, (5, 5, 25, 20))
    assert cropped.size == (20, 15)


def test_crop_out_of_bounds_raises(rgb_image):
    with pytest.raises(ops.InvalidCropError):
        ops.crop(rgb_image, (-1, 0, 10, 10))
    with pytest.raises(ops.InvalidCropError):
        ops.crop(rgb_image, (0, 0, rgb_image.width + 1, 10))


def test_crop_degenerate_box_raises(rgb_image):
    with pytest.raises(ops.InvalidCropError):
        ops.crop(rgb_image, (10, 10, 10, 20))  # zero width
    with pytest.raises(ops.InvalidCropError):
        ops.crop(rgb_image, (10, 20, 20, 10))  # bottom above top


def test_resize_to_fit_never_upscales(rgb_image):
    result = ops.resize_to_fit(rgb_image, 1000)
    assert result.size == rgb_image.size


def test_resize_to_fit_downscales_proportionally(rgb_image):
    result = ops.resize_to_fit(rgb_image, 20)
    assert max(result.size) == 20
    original_ratio = rgb_image.width / rgb_image.height
    new_ratio = result.width / result.height
    assert abs(original_ratio - new_ratio) < 0.05


def test_guard_dimensions_rejects_oversized_image():
    # A real (MAX+1)-pixel-wide image would be expensive to allocate just for
    # this test; guard_dimensions only reads `.size`, so a minimal stand-in
    # with that one attribute exercises the same code path cheaply.
    class OversizedStandIn:
        size = (ops.MAX_IMAGE_DIMENSION + 1, 10)

    with pytest.raises(ops.ImageTooLargeError):
        ops.guard_dimensions(OversizedStandIn())  # type: ignore[arg-type]


def test_guard_dimensions_accepts_normal_image(rgb_image):
    ops.guard_dimensions(rgb_image)  # should not raise


# --- The full canonical pipeline -------------------------------------------


def test_render_identity_params_returns_equivalent_pixels(rgb_image):
    result = ops.render(rgb_image, ops.EditParams())
    assert list(result.getdata()) == list(rgb_image.getdata())


def test_render_does_not_mutate_source(rgb_image):
    original = list(rgb_image.getdata())
    params = ops.EditParams(brightness=40, rotation=ops.Rotation90.CW_90, flip_horizontal=True)
    ops.render(rgb_image, params)
    assert list(rgb_image.getdata()) == original


def test_render_is_deterministic_across_repeated_calls(rgb_image):
    params = ops.EditParams(
        brightness=20, contrast=-10, saturation=15, warmth=25, sharpness=10,
        rotation=ops.Rotation90.CW_90, flip_vertical=True,
    )
    first = ops.render(rgb_image, params)
    second = ops.render(rgb_image, params)
    assert list(first.getdata()) == list(second.getdata())
    assert first.size == second.size


def test_render_crop_applies_after_rotation(rgb_image):
    # 40x30 source. Rotate 90 CW -> 30x40. A crop box valid only in the
    # rotated (30x40) frame must succeed, proving crop is evaluated against
    # the rotated output, not the original 40x30 source.
    params = ops.EditParams(
        rotation=ops.Rotation90.CW_90,
        crop_box=ops.CropBox(0, 0, 30, 35),
    )
    result = ops.render(rgb_image, params)
    assert result.size == (30, 35)


def test_render_order_crop_before_adjustments(rgb_image):
    # Cropping then brightening should yield the cropped region's pixels
    # brightened — not brightened-then-recropped-differently. We verify by
    # comparing against manually composing the same two primitives in order.
    params = ops.EditParams(crop_box=ops.CropBox(2, 2, 10, 10), brightness=30)
    pipeline_result = ops.render(rgb_image, params)

    manual = ops.crop(rgb_image, (2, 2, 10, 10))
    manual = ops.apply_brightness(manual, 30)

    assert list(pipeline_result.getdata()) == list(manual.getdata())


def test_edit_params_is_identity_detection():
    assert ops.EditParams().is_identity()
    assert not ops.EditParams(brightness=1.0).is_identity()
    assert not ops.EditParams(rotation=ops.Rotation90.CW_90).is_identity()


def test_edit_params_with_changes_is_immutable():
    base = ops.EditParams(brightness=10)
    changed = base.with_changes(brightness=50)
    assert base.brightness == 10
    assert changed.brightness == 50
