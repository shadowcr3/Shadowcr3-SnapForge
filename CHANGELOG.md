# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — Initial build

### Added

- Core architecture: `imaging/` (pure operations), `models/` (document +
  undo/redo history), `services/` (import/export), `controllers/`
  (editor controller), `ui/` (PySide6 presentation layer).
- Import: JPEG, PNG, WebP with EXIF-orientation normalization and
  decompression-bomb-sized-input guarding.
- Adjustments: brightness, contrast, saturation, warmth (linear-gain
  approximation), sharpness — live preview with slider-drag coalesced
  into one undo step per completed drag.
- Geometry: crop (drag-select on canvas), 90°-step rotate, horizontal/
  vertical flip. Rotating or flipping after a crop exists explicitly
  invalidates that crop (see `docs/DECISIONS.md`) rather than silently
  reinterpreting it.
- Full undo/redo with a bounded history depth (100 steps) and correct
  redo-branch invalidation on new edits after an undo.
- Before/After compare toggle.
- Export to JPEG/PNG/WebP: atomic temp-file-then-replace writes,
  post-write verification, and mandatory explicit confirmation before
  overwriting an existing destination file.
- Dark, restrained desktop UI (menu, toolbar, adjustments dock, status
  bar) built on PySide6.
- 95 automated tests covering `imaging/`, `models/`, `services/` (no Qt
  dependency), plus `controllers/` and canvas coordinate mapping via
  `pytest-qt` against a real headless `QApplication`.
- PyInstaller-based packaging instructions for Windows and Linux
  (`packaging/BUILD.md`).

### Fixed (during development, before any tagged release)

- Crop validation previously happened lazily during preview rendering,
  after the (possibly invalid) crop had already been committed to undo
  history — meaning an out-of-bounds crop selection could leave the
  document permanently stuck on a crop that failed every subsequent
  render. Crop bounds are now validated against the correct geometry
  *before* anything is committed; an invalid crop is rejected with an
  error and leaves history untouched. Caught by
  `tests/test_controller.py::test_apply_crop_out_of_bounds_emits_error_not_crash`.

### Added (post-initial-build hardening pass)

- Zoom: fit-to-window (default), discrete zoom in/out steps (10%–800%),
  actual size, and keyboard shortcuts (`Ctrl +`/`Ctrl -`/`Ctrl 1`/`Ctrl 0`),
  with scrollbar panning once zoomed past the viewport. Closes a gap
  against the Initial-scope requirement that explicitly listed zoom
  alongside fit-to-window.
- A documented, explicitly-enforced, and tested metadata policy: every
  export strips all EXIF/ICC/XMP/IPTC metadata (`services/import_export.py`
  `_strip_metadata`; see `docs/DECISIONS.md`).
- `docs/DEPENDENCIES.md`: a real license review of all three runtime
  dependencies, including an identified and documented open question about
  whether PyInstaller `--onefile` builds satisfy PySide6/Qt's LGPLv3
  relinking requirement — not just an assumption that Qt is "fine."
  Packaging now defaults to `--onedir` as the safer choice pending that
  review.
- A built-in `snapforge --self-test` diagnostic mode
  (`snapforge.main._run_self_test`) that drives a real open → adjust →
  rotate/flip → crop → undo/redo → zoom → export-to-all-formats sequence
  headlessly, with no window shown. Added specifically to make "the
  packaged application passes a basic launch, edit, and export smoke test"
  verifiable against the actual packaged binary (not just the source
  tree) — and actually run as part of preparing this release: built on
  Linux and verified from a clean shell environment (no dev venv on
  `PATH`) under a real `Xvfb`-backed X11 display. A new CI job
  (`package-smoke-test`) now builds and runs this on every push.
- GitHub issue templates for bug reports and feature requests.

### Fixed (post-initial-build hardening pass)

- `libxcb-cursor0` was missing from the Linux packaging environment,
  surfacing as a Qt platform-plugin load failure in the packaged binary
  (though not in dev/source runs). Documented in `docs/DEPENDENCIES.md`
  and added to `packaging/BUILD.md`'s troubleshooting notes and
  `.github/workflows/ci.yml`'s dependency list.

### Added (second hardening pass)

- `packaging/build_linux.sh`: a reproducible build script that builds,
  trims Qt components verified via `ldd` against this project's own built
  binaries to be unreferenced (`QtQml`/`QtQuick`\*, `QtPdf`,
  `QtVirtualKeyboard`\*, `QtWayland*`, `QtNetwork`, `QtOpenGL`, `QtSvg`,
  EGLFS libraries, Qt translations, `imageformats` plugins), and runs
  `--self-test` against the trimmed result automatically. Measured,
  reproducible: **~195 MB**, down from ~232 MB unstripped. Both Windows
  and Linux `BUILD.md` instructions now default to `--onedir` (not
  `--onefile`), consistent with the LGPL packaging caveat in
  `docs/DEPENDENCIES.md`.
- Accessible names and descriptions on the image canvas and
  every adjustment slider, kept current as state changes (crop mode,
  image loaded/cleared); explicit keyboard tab order from canvas through
  each slider to the reset button, rather than relying on construction
  order. New tests: `tests/test_adjustments_panel.py` (first dedicated
  coverage for that widget) and accessibility assertions in
  `tests/test_canvas.py`.
- `tests/test_self_test_entrypoint.py`: regression test for `--self-test`
  itself, run as a real subprocess.
- CI `package-smoke-test` job now builds via `build_linux.sh` and smoke-
  tests the actual trimmed binary on every push, not just the source tree.

### Fixed (dependency and usability pass)

- Runtime dependency switched from the full `PySide6` metapackage to
  `PySide6-Essentials` — SnapForge only uses `QtCore`/`QtGui`/`QtWidgets`,
  so this drops ~180MB of unused `PySide6-Addons`/`PySide6-Pdf`/
  `PySide6-WebEngine` downloads that were never needed.
- All runtime and dev dependencies pinned to exact tested versions
  (`==`, not `>=`) in `pyproject.toml`, so `pip install` is fast and
  deterministic instead of the resolver searching across many releases.
  Verified with a fresh install from a clean virtual environment.
- Fixed the GitHub repository links throughout the project (README,
  SECURITY.md, pyproject.toml, CONTRIBUTING.md) to point at the real
  repository and maintainer account.

### Changed (code cleanup and beginner-friendliness pass)

- Removed every internal planning-document citation (`TRD §X.Y`) from code
  comments and docs, rewriting the surrounding explanation in plain
  language so nothing refers to a document outside this repository.
- Removed all `# noqa: ...` lint-suppression comments from the source —
  turned out the underlying lint rules (`N802`, `BLE001`) were never
  actually enabled by this project's ruff configuration, so the comments
  were dead clutter with no effect; confirmed by testing `ruff check`
  with them removed.
- Added a friendly empty-state message on the canvas ("Open an image to
  get started") instead of a blank area when no image is loaded.
- Added a **Help** menu with **Getting Started** (a plain-language
  walkthrough) and **About SnapForge**.
- Added tooltips to the remaining toolbar actions that didn't have them.
- New `packaging/build_windows.ps1`: builds, self-tests, and zips the
  Windows build in one command, mirroring `build_linux.sh`.
- Both build scripts now also zip their output (`SnapForge-vX.Y.Z-
  {linux,windows}.zip`), and refuse to zip a build that fails
  `--self-test`.
- First dedicated test coverage for `MainWindow` (`tests/test_main_window.py`).

### Known limitations (tracked in `docs/ROADMAP.md`)

- Rotation is quarter-turn-only; no free-angle rotation yet.
- Warmth is a linear channel-gain approximation, not a true
  color-temperature curve.
- No RAW format support.
- No batch export.
- Rendering runs on the UI thread (no background worker); untested against
  the ~150ms interactive-preview target on a full-resolution photo on real
  hardware (see `docs/DECISIONS.md`).
- Packaging has been built and smoke-tested on Linux only. The Windows
  `BUILD.md` instructions have not been executed against real Windows
  hardware, and there is no Windows equivalent of `build_linux.sh`'s
  automated trimming yet.
- The PyInstaller `--onefile`/LGPL relinking question in
  `docs/DEPENDENCIES.md` is documented with a recommended mitigation
  (default to `--onedir`) but has not been resolved by a qualified legal
  reviewer.
