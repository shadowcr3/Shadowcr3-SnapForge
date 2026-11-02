"""Application entry point.

Kept intentionally small: this module's only job is to stand up QApplication
and the main window. All real logic lives in controllers/, models/,
imaging/, and services/.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from snapforge.ui.main_window import MainWindow
from snapforge.ui.theme import STYLESHEET


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _run_self_test()

    app = QApplication(sys.argv)
    app.setApplicationName("Shadowcr3 SnapForge")
    app.setOrganizationName("Shadowcr3")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    return app.exec()


def _run_self_test() -> int:
    """Drive a real open -> adjust -> crop -> rotate -> undo/redo -> export
    sequence through the actual MainWindow/EditorController, with no window
    shown and no user interaction.

    This exists specifically to satisfy the "packaged application passes a
    basic launch, edit, and export smoke test" acceptance check
    against the real packaged binary — not just the source tree in a dev
    environment — since a frozen executable has no REPL to drive it from.
    Run it as `snapforge --self-test` (or the packaged binary with the same
    flag; see `packaging/BUILD.md`'s verification section). It never opens
    a visible window and exits with a clear PASS/FAIL plus a nonzero exit
    code on failure, so it's usable in CI or a release checklist, not just
    interactively.
    """
    import contextlib
    import tempfile
    import traceback
    from pathlib import Path

    from PIL import Image

    from snapforge.imaging.operations import Rotation90
    from snapforge.services.import_export import ExportOptions

    app = QApplication(sys.argv)

    def step(label: str) -> None:
        print(f"[self-test] {label}", flush=True)

    try:
        from PySide6.QtWidgets import QMessageBox

        # Modal dialogs block waiting for a click that will never come in
        # this unattended mode; neutralize them for the duration of the
        # self-test only; the production app's real dialogs are untouched —
        # this function is the only thing that ever does this.
        QMessageBox.information = staticmethod(lambda *a, **k: None)
        QMessageBox.critical = staticmethod(lambda *a, **k: None)
        QMessageBox.question = staticmethod(
            lambda *a, **k: QMessageBox.StandardButton.Yes
        )

        step("constructing MainWindow (no window shown)")
        window = MainWindow()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            step("creating a synthetic source image")
            source_path = tmp / "self_test_source.png"
            img = Image.new("RGB", (120, 90))
            pixels = img.load()
            for x in range(120):
                for y in range(90):
                    pixels[x, y] = (x * 2 % 256, y * 2 % 256, 128)
            img.save(source_path)

            step(f"opening {source_path.name}")
            if not window.controller.open_image(source_path):
                raise RuntimeError("open_image reported failure")
            assert window.controller.has_document

            step("applying adjustments (brightness, contrast)")
            window.controller.commit_adjustment(brightness=20.0)
            window.controller.commit_adjustment(contrast=-10.0)
            params = window.controller.document.params
            assert params.brightness == 20.0
            assert params.contrast == -10.0

            step("rotating and flipping")
            window.controller.rotate_clockwise()
            window.controller.flip_horizontal()
            assert window.controller.document.params.rotation == Rotation90.CW_90

            step("cropping")
            # Source was 120x90; after one 90 CW rotation the working
            # geometry is 90x120 (rotate/flip apply before crop — see
            # imaging.operations.render's docstring). Using only the public
            # controller API here deliberately, not a computed/private
            # lookup, so this test exercises exactly what a real caller can.
            window.controller.apply_crop(2, 2, 88, 118)
            assert window.controller.document.params.crop_box is not None

            step("undo x2, redo x1")
            window.controller.undo()
            window.controller.undo()
            window.controller.redo()

            step("zooming in/out")
            window.canvas.zoom_in()
            assert window.canvas.zoom is not None
            window.canvas.set_zoom_fit()
            assert window.canvas.zoom is None

            step("exporting to JPEG, PNG, and WebP")
            for fmt, ext in (("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")):
                dest = tmp / f"self_test_export.{ext}"
                window.controller.export(ExportOptions(destination=dest, format=fmt))
                if not dest.exists():
                    raise RuntimeError(f"{fmt} export did not produce a file")
                with Image.open(dest) as reopened:
                    reopened.load()
                step(f"  {fmt} -> {reopened.size} OK")

            step("confirming source file was never modified")
            with Image.open(source_path) as original:
                original.load()
                assert original.size == (120, 90)

        print("[self-test] PASS", flush=True)
        return 0

    except Exception:
        print("[self-test] FAIL", flush=True)
        traceback.print_exc()
        return 1
    finally:
        with contextlib.suppress(Exception):
            app.quit()


if __name__ == "__main__":
    sys.exit(main())
