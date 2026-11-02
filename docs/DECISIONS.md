# Decisions

Boundaries drawn deliberately during the v0.1 build, recorded here so they
read as decisions rather than oversights, and so future contributors know
*why* before changing them.

## Rotation is 90°-step only in v0.1

Free-angle rotation requires choosing a canvas-size/fill policy (does the
canvas grow to fit the rotated bounding box? get filled with a background
color? auto-crop to the largest axis-aligned rectangle that avoids empty
corners?) plus a resampling filter decision. Those are real UX decisions,
not implementation details, and picking one in a 10-hour initial build
without being able to validate it against actual usage felt worse than
shipping the simpler, unambiguous quarter-turn rotation and revisiting this
in v0.2 (see `docs/ROADMAP.md`).

## Crop and rotation interact by invalidating, not reinterpreting

`imaging.operations.render()` applies rotate/flip *before* crop (see that
function's docstring for the full reasoning). A direct consequence: a crop
box is only meaningful in the coordinate space of whatever rotation/flip
was active when it was drawn. If the user crops, then changes rotation,
the existing crop box would silently refer to the wrong region if it were
kept.

Two options existed: (a) attempt to algebraically remap the crop box
through the new rotation, or (b) clear the stale crop and tell the user.
(a) is more convenient but adds real geometric complexity (and edge cases
around flips) for a `v0.1` scope; (b) is simple, obviously correct, and
impossible to get subtly wrong. We chose (b) —
`EditorController._invalidate_crop_on_geometry_change`. This is revisitable
once the core editor has more usage to justify the complexity of (a).

## Warmth is a linear channel-gain approximation, not a true color-temperature curve

A perceptually accurate "white balance temperature" control works in a
different color space (typically CIE xy or a Planckian-locus
approximation) and is meaningfully more complex than a slider. v0.1 uses a
simple, deterministic linear gain on the R and B channels — documented as
an approximation in `imaging/operations.py` — because it is cheap,
predictable, fully unit-testable, and good enough to be useful immediately.
A curve-based replacement is tracked in `docs/ROADMAP.md` (v0.3) and is
designed to be a drop-in replacement for `apply_warmth` without touching
any other part of the pipeline, since every adjustment function has the
same `(image, amount) -> image` contract.

## Rendering runs on the UI thread in v0.1 — no background worker yet

Moving expensive processing off the UI thread is a reasonable thing to do
for responsiveness, but v0.1 does not do this: every call to
`imaging.operations.render()` — live slider drag, discrete crop/rotate/flip,
and export — runs synchronously on the Qt main thread.

This was a deliberate priority call: correctness and architecture came
first, threading is UI refinement. It was tested against small images in
this build and was not validated against a ~150ms interactive-preview
target on a full 12-megapixel photo on real target hardware — that
specific claim is untested, not just "not yet optimized." If dragging a
slider on a large image is sluggish in practice, moving `render()` calls
to a worker thread
(with the live-preview path debounced/cancelled on rapid re-drags) is the
fix, and the existing architecture supports it without disruption: the
controller already separates "fire a render" from "receive a result" via
`preview_updated`'s signal — a worker thread would just change what's on
the sending side of that signal, not the signal's contract.

## No network code, anywhere, by design

SnapForge does not make HTTP requests, does not check for updates, and does
not phone home. This isn't a feature flag that happens to default to off —
there is no networking dependency in `pyproject.toml` and no import of
`requests`/`urllib`/`socket` anywhere in `src/`. Anyone auditing the
dependency tree can confirm this directly rather than taking a privacy
policy's word for it. See `SECURITY.md`.

## Export strips all metadata (EXIF, ICC, XMP/IPTC) — no selective preservation

A clear, documented metadata policy matters here, and a simple one is fine
for an initial release — it doesn't need to be a full metadata editor.
v0.1's policy is the simplest privacy-safe option: strip everything,
unconditionally, on every export. No EXIF (including GPS coordinates,
device identifiers, capture timestamps), ICC profile, or XMP/IPTC data
survives export.

This was a close call against "preserve EXIF, strip only GPS" — selective
preservation is more useful (keeps the camera/lens/timestamp info
photographers often want) but requires a UI for the user to see and control
what's being kept, which doesn't exist in v0.1. Shipping selective
preservation without that visibility would mean exporting location data a
user never consciously chose to keep — worse than the inconvenience of
losing metadata nobody asked to remove. Orientation specifically is not
actually lost in practice: `imaging.operations.normalize_orientation`
bakes it into the pixel data at import time, before export's stripping
policy is even relevant.

See `services/import_export.py`'s module docstring for the full reasoning
and `_strip_metadata`, which makes this an explicit, tested step rather
than an accident of which `Image.save()` keyword arguments this module
happens not to pass. Selective, user-visible metadata control is tracked
as a long-term feature — see `docs/ROADMAP.md`.

## JPEG export flattens transparency onto white, not black or "leave undefined"

JPEG has no alpha channel. Pillow's save silently drops alpha if you don't
handle it first, which looks fine for images with no transparency and
produces an undefined/black result for images that do. `services.import_
export._coerce_for_format` flattens onto white explicitly — documented
behavior, not silent data loss — because it's the least-surprising default
for the common "export a PNG-with-transparency as a JPEG for sharing" case.
