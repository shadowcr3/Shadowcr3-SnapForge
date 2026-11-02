# Building standalone binaries

SnapForge is packaged with [PyInstaller](https://pyinstaller.org/). These
instructions produce a standalone build on the platform you run them on —
PyInstaller does not cross-compile, so build Windows binaries on Windows
and Linux binaries on Linux (or in CI, one runner per OS — see
`.github/workflows/ci.yml`).

## Before you build: read the LGPL packaging caveat

`docs/DEPENDENCIES.md` documents an unresolved question about whether
PyInstaller's `--onefile` mode adequately satisfies LGPLv3's relinking
requirement for PySide6/Qt. Every command below therefore uses `--onedir`
(a visible folder of individually-replaceable libraries) instead —
**don't switch to `--onefile` without reading that section first.**

## Prerequisites

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

## Windows (.exe)

```powershell
pyinstaller --noconfirm --windowed `
  --name SnapForge `
  --icon packaging\icons\snapforge.ico `
  --paths src `
  src\snapforge\main.py
```

Or run the build script, which does the same thing, self-tests the exe,
and zips the result — the single-command Windows equivalent of
`build_linux.sh`:

```powershell
.\packaging\build_windows.ps1
```

Output: `SnapForge-v0.1.0-windows.zip`. It refuses to zip a build that
fails `--self-test`. (If `packaging\icons\snapforge.ico` doesn't exist in
your checkout, it's skipped automatically — PyInstaller uses its default
icon instead.)

**This script has not been run on real Windows hardware as part of this
release** — it was written to mirror `build_linux.sh`'s verified logic,
not independently tested on Windows. If you hit an issue running it,
please open an issue (see `CONTRIBUTING.md`). It also doesn't yet do
`build_linux.sh`'s Qt-library trimming — the same technique should work
with Windows `.dll` files instead of Linux `.so` files, but that hasn't
been identified or tested either.

## Linux (standalone binary)

Per the LGPL packaging caveat above, this uses `--onedir` (the default
PyInstaller mode — no `--onefile` flag), which produces a folder with the
executable alongside visible, individually-replaceable `.so` files.

Run the build script rather than invoking PyInstaller by hand — it builds,
strips the Qt components verified (via `ldd` against this project's own
built binaries, not guessed) to be unreferenced by anything SnapForge
loads, runs `--self-test` against the trimmed result, and zips it into a
single file:

```bash
./packaging/build_linux.sh
```

Output: `SnapForge-v0.1.0-linux.zip`, ready to share. The script refuses
to zip a build that fails `--self-test`.

Output: `dist/snapforge/` (a folder — distribute the whole thing, not just
the `snapforge` executable inside it). Measured, reproducible result:
**~195 MB**, down from ~232 MB unstripped, confirmed still fully
functional by the script's own `--self-test` run against the trimmed
binary every time it's built — this isn't a one-off manual trim that can
silently go stale.

What the script removes, and why each is safe: `ldd` against
`libQt6Gui.so.6`, `libQt6Widgets.so.6`, `libQt6XcbQpa.so.6`, and the
`xcb` platform plugin — the actual binaries this build produces — shows
their only Qt library dependencies are `Core`, `Gui`, `Widgets`, `DBus`,
and `XcbQpa`. Everything the script deletes (`QtQml`/`QtQuick`\*,
`QtPdf`, `QtVirtualKeyboard`\*, `QtWayland*`, `QtNetwork`, `QtOpenGL`,
`QtSvg`, the EGLFS device-integration libraries, Qt's translation files,
and the `imageformats` plugins — SnapForge builds `QImage` directly from
raw pixel bytes in `ui/canvas.py`, never through a format-sniffing
`QImageReader`) sits outside that dependency graph. `libicudata.so.73`
(~32 MB) stays — it's a hard dependency of `QtCore` for Unicode/text
handling, not trimmable without rebuilding Qt itself without ICU.

For a double-click-friendly, more portable Linux artifact, wrap this
output in an AppImage (see
[`appimage-builder`](https://appimage-builder.readthedocs.io/)) — a
reference `AppImageBuilder.yml` is not included in this initial release
(tracked in `docs/ROADMAP.md`); the script's output above is sufficient to
run and test the packaged build today.

## Verifying a build

**Don't just assume a build works — SnapForge ships a built-in smoke test
for exactly this.** Run the packaged binary with `--self-test`:

```bash
# Linux
./dist/snapforge/snapforge --self-test

# Windows
dist\SnapForge.exe --self-test
```

This drives a real open → adjust → rotate → flip → crop → undo/redo →
zoom → export-to-all-three-formats sequence through the actual packaged
code (not the source tree), with no window shown, and prints
`[self-test] PASS` with exit code 0 on success or `[self-test] FAIL` with
a full traceback and exit code 1 on failure. See
`snapforge.main._run_self_test`'s docstring for exactly what it covers and
why it exists.

This was verified for real as part of preparing this release: built on
Linux via `packaging/build_linux.sh`, then run from `/tmp` with a
deliberately clean environment (no venv/`PYTHONPATH`) under a real
(`Xvfb`-backed) X11 display, confirming the packaged binary doesn't
silently depend on the build environment. `--self-test` passed on the
trimmed ~195 MB build; a plain launch with no flags was also confirmed to
stay up (not crash on startup) rather than fully click-tested.

`--self-test` is a *substitute* for interactive verification when nothing
else is available (e.g. CI, or this sandboxed build environment); it
doesn't replace actually clicking through the UI at least once per
platform before a real release — a few things it can't catch: whether the
window actually renders correctly, font rendering, DPI scaling, and
anything about the crop-rectangle mouse interaction (it exercises
`apply_crop` directly with known-good coordinates, not actual mouse drag
events).

If a plain launch fails with a Qt platform plugin error (commonly
`libxcb-cursor.so.0` not found — hit and fixed during this release's own
build, see `docs/DEPENDENCIES.md`), install your distro's
`libxcb-cursor0` package (or equivalent) alongside the libraries already
listed in `.github/workflows/ci.yml`'s Linux dependency step.

## Why PyInstaller, and what wasn't set up

PyInstaller was chosen for being the most broadly documented option for
PySide6 apps and for working on this project's target platforms (Windows
and Linux) without extra tooling. `cx_Freeze` and `briefcase` are
reasonable alternatives if your packaging needs grow (e.g. native
installers, code signing, auto-update) — swapping is a packaging-layer
change only; it does not touch `src/snapforge/`.

Not set up in this initial release: code signing (Windows Authenticode /
macOS notarization — there is no macOS build target yet), an installer
(vs. a standalone binary), and auto-update. See `docs/ROADMAP.md`.
