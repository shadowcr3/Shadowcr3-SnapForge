# Packaging

This directory holds everything needed to turn the `src/snapforge` package
into a distributable desktop build.

- **`BUILD.md`** — step-by-step PyInstaller build instructions for Windows
  and Linux, plus how to verify a packaged binary (not just the source
  tree) actually works via the built-in `--self-test` mode.
- **`build_linux.sh`** — the actual Linux build: runs PyInstaller, strips
  Qt components verified via `ldd` to be unused, runs `--self-test`
  against the trimmed result, and zips it into `SnapForge-vX.Y.Z-linux.zip`.
  Reproducible — this is how the ~195 MB measurement in `BUILD.md` was
  produced, not a one-off manual trim.
- **`build_windows.ps1`** — the Windows equivalent: builds, self-tests,
  and zips into `SnapForge-vX.Y.Z-windows.zip`. Not yet run on real
  Windows hardware — see `BUILD.md`.
- **`icons/`** — application icon source files. _Not populated in this
  initial release_ — `BUILD.md`'s Windows command references
  `packaging/icons/snapforge.ico`, which you'll need to add before that
  exact command works; until then, omit the `--icon` flag and PyInstaller
  will use its default icon.

A release artifact built per `BUILD.md` contains a **folder** (`--onedir`
mode, the default used throughout `BUILD.md` — see the LGPL packaging
caveat in `docs/DEPENDENCIES.md` for why `--onefile` is deliberately not
the default here), not a single file: `snapforge/` on Linux,
`SnapForge/` on Windows, containing the executable alongside its bundled
Python runtime, PySide6/Qt, Pillow, and numpy as individually visible
files. **Distribute the whole folder**, not just the executable inside it
— the executable will not run without the rest of the folder next to it.
No separate Python installation is required on the target machine.

Measured on Linux via `packaging/build_linux.sh`: ~195 MB, trimmed from
~232 MB unstripped and reverified with `--self-test` against the trimmed
binary on every run of the script (see `BUILD.md`'s Linux section for
exactly what's removed and the `ldd`-based evidence for why it's safe).

Verify any build you produce with `./snapforge --self-test` (or
`SnapForge.exe --self-test` on Windows) before distributing it — see
`BUILD.md`'s "Verifying a build" section for what that covers and what it
doesn't.

No installer, auto-updater, or code-signing step is part of this initial
release's packaging — see `docs/ROADMAP.md` and the "What wasn't set up"
section of `BUILD.md`.
