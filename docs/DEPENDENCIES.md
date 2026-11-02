# Dependency inventory and license review

Every dependency should have a clear technical purpose and a license
reviewed for compatibility with GPL-3.0 distribution — PySide6/Qt
specifically needs real review here, not just an assumption that it's
"GPL-compatible." This document is that review. It is maintained alongside
`pyproject.toml` — if a dependency is added, changed, or removed there,
update this file in the same change (per `CONTRIBUTING.md`).

**This is engineering due diligence, not legal advice.** The maintainer
should have this confirmed by someone qualified before a public release
that will be distributed at scale — the analysis below is accurate to the
best of available research as of this writing, not a substitute for that
review.

## Runtime dependencies

| Dependency | Pinned version | License | GPL-3.0 compatibility |
|---|---|---|---|
| PySide6-Essentials | `==6.12.0` | LGPLv3 (Qt/PySide also offer GPLv2, GPLv3, or a commercial license; the PyPI wheels are the LGPLv3 build) | **Compatible, with one packaging caveat — see below.** LGPLv3 permits use in a GPL-3.0 application; dynamically linking an LGPL library from GPL code is the standard, well-established case the LGPL exists for. |
| Pillow | `==13.0.0` | HPND (Historical Permission Notice and Disclaimer) — a permissive license in the BSD/MIT family | Compatible. Permissive, attribution-only, no copyleft obligations that conflict with GPL-3.0. |
| numpy | `==2.5.4` | BSD-3-Clause | Compatible. Permissive, same reasoning as Pillow. |

Versions are pinned exactly (not `>=` ranges) in `pyproject.toml` so a
fresh install is fast and reproducible — it fetches exactly these
versions instead of letting pip's resolver search through every release
of every package trying to find a compatible combination.

### The PySide6/LGPL packaging caveat

The LGPL's core user-facing guarantee is that someone who receives your
application can **replace the LGPL-licensed library with a modified version
of their own** and have the application still work — which is why LGPL
code is normally distributed as a separate, replaceable shared library
(`.dll`/`.so`), not statically fused into your binary.

A `--onefile` PyInstaller build bundles PySide6/Qt's shared libraries
inside the single executable and extracts them to a temp directory at
each run. Whether that satisfies LGPLv3's relinking requirement is
genuinely debatable — the libraries are technically still separate
`.dll`/`.so` files at the point they're loaded, but a user can't
straightforwardly swap one before running the bundled `.exe` the way they
could with a `--onedir` build (executable + a visible folder of
`.dll`/`.so` files sitting next to it, which they clearly can replace).
`packaging/BUILD.md` and `packaging/build_linux.sh` therefore default to
`--onedir` everywhere, specifically to sidestep this unresolved question.
**That default is not a substitute for a real review**, and the honest
options if you need a `--onefile` build are:

1. Keep using `--onedir` for any release meant for broad distribution —
   the visible, swappable DLL folder is the unambiguous way to satisfy
   LGPLv3's relinking requirement.
2. Get this specific question (does PyInstaller `--onefile` satisfy LGPLv3
   relinking) reviewed by someone with real FOSS-licensing expertise before
   shipping `--onefile` builds at any scale.
3. Since this project is GPL-3.0-only (not merely LGPL-compatible), it
   could instead build PySide6/Qt from source under the **GPLv3** option
   Qt also offers, which has no separate-library requirement to begin with
   — at the cost of losing the convenience of the prebuilt PyPI wheel.

`packaging/BUILD.md` is updated to flag this rather than presenting
`--onefile` as a settled choice.

## Development-only dependencies

Not distributed with the application — installed only via the `[dev]`
extra for running tests, linting, and building packages. These have no
bearing on the *distributed* application's license obligations, but are
listed here for completeness, so every release has a record of exactly
which versions were used to build and test it.

| Dependency | Pinned version | License | Role |
|---|---|---|---|
| pytest | `==9.1.1` | MIT | Test runner |
| pytest-qt | `==4.5.0` | MIT | Drives real Qt signals/widgets in tests against a headless `QApplication` |
| ruff | `==0.17.3` | MIT | Linting |
| PyInstaller | `==6.22.3` | GPL-2.0-or-later, **with an explicit bootloader exception** that permits building and distributing non-free (including commercial) applications with it — see [PyInstaller's license](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt). This project is GPL-3.0 regardless, so the exception is moot for us either way; it matters only in that PyInstaller itself does not impose GPL on the applications it packages. |

## Why each runtime dependency exists

- **PySide6-Essentials** — the desktop UI toolkit. SnapForge only imports
  `QtCore`, `QtGui`, and `QtWidgets`, all of which live in the
  `PySide6-Essentials` package, so that's what's declared — not the full
  `PySide6` metapackage, which also pulls in `PySide6-Addons`, `PySide6-Pdf`,
  and `PySide6-WebEngine` (~180MB combined) that this app never imports and
  never needs. Chosen over PyQt6 specifically because PySide6's LGPL default
  avoids PyQt6's GPL-or-commercial-license choice being forced onto anyone
  who later wants to embed SnapForge in a differently-licensed context;
  since this project is GPL-3.0, either binding would technically work, but
  PySide6 is the more conventional choice for GPL projects using Qt.
- **Pillow** — image decode/encode/transform backend. No credible
  alternative was considered; it's the de facto standard Python imaging
  library and is what the entire `imaging/` module's operations are built
  on.
- **numpy** — used in exactly one place, `imaging.operations.apply_warmth`,
  for vectorized per-channel pixel math. Not used anywhere else; if
  `apply_warmth`'s linear-gain approximation is ever replaced by the
  curve-based approach tracked in `docs/ROADMAP.md`, re-evaluate whether
  numpy is still needed at all.

## Supply-chain hygiene

- Runtime and dev dependencies are kept separate in `pyproject.toml`
  (`[project.dependencies]` vs. `[project.optional-dependencies.dev]`).
- Version constraints use `>=` floors, not exact pins, which is appropriate
  for a library-style `pyproject.toml` but means **a release build should
  pin exact versions** (e.g. via a lockfile or `pip freeze` into
  `packaging/`) so the dependency inventory above reflects what was
  actually shipped, not just what's permitted. Not yet done — tracked
  here rather than silently assumed.
- No dependency in this list requires network access to function as part
  of SnapForge's own operation (see `docs/DECISIONS.md`'s "no network
  code" entry).
