# Roadmap

This reflects the project's phased scope. v0.1 (this repository's current
state) is the initial build: correctness and architecture over feature
count.

## v0.1 — Core editor (current)

- [x] Import JPEG/PNG/WebP with EXIF orientation normalization
- [x] Brightness, contrast, saturation, warmth, sharpness adjustments
- [x] Crop (drag-select), 90°-step rotate, horizontal/vertical flip
- [x] Full undo/redo with slider-drag coalescing
- [x] Before/After compare
- [x] Export to JPEG/PNG/WebP with atomic, overwrite-protected writes
- [x] Dark, focused UI

## v0.2 — Quality-of-life

- [ ] Free-angle rotation (with a defined canvas-fill/crop-to-fit policy —
      see `docs/DECISIONS.md` for why this was deferred, not forgotten)
- [ ] Persist and restore recent-files list
- [ ] Keyboard-only crop adjustment (arrow keys to nudge edges)
- [ ] Zoom/pan on the canvas for pixel-level crop precision
- [ ] Export presets (remember last-used format/quality per session)

## v0.3 — Curve-based color

- [ ] Replace the linear-gain `apply_warmth` approximation with a proper
      curve/LUT-based white-balance control
- [ ] Levels/curves panel (histogram-driven)
- [ ] Selective color (per-channel adjustment)

## v0.4 — Format & workflow expansion

- [ ] RAW format support (via `rawpy`/libraw) — read-only import, still
      exports to the existing JPEG/PNG/WebP set
- [ ] Batch export (apply current edit to a folder of images)
- [ ] TIFF import/export

## Later / exploratory

- [ ] A minimal local plugin system for custom filters (sandboxed, no
      network access by default — consistent with the "local-first, no
      silent network calls" principle in `docs/DECISIONS.md`)
- [ ] Multi-image sessions / tabs

Nothing on this list is committed to a date. Items move up when someone
(including the maintainer) has time and a concrete need for them — see
`CONTRIBUTING.md` if that's you.
