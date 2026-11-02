"""The main window.

This module is presentation-only. It never calls into
`imaging.operations` or `services.import_export` directly — every editing
or file action goes through `EditorController`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QToolBar,
)

from snapforge import __version__
from snapforge.controllers.editor_controller import EditorController
from snapforge.services.import_export import SUPPORTED_IMPORT_EXTENSIONS
from snapforge.ui.adjustments_panel import AdjustmentsPanel
from snapforge.ui.canvas import ZOOM_ACTUAL_SIZE, ZOOM_STEPS, ImageCanvas
from snapforge.ui.export_dialog import ExportDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Shadowcr3 SnapForge — v{__version__}")
        self.resize(1280, 800)
        self.setMinimumSize(720, 480)

        self.controller = EditorController()
        self._crop_active = False

        self.canvas = ImageCanvas()
        # QScrollArea gives us panning for free once zoomed past the
        # viewport; `widgetResizable` is toggled between fit mode (True —
        # canvas always matches the viewport, letterboxed) and zoom mode
        # (False — canvas takes its own fixed size, scrollbars appear) by
        # `_on_canvas_zoom_changed`, which `canvas.zoom_changed` drives.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.scroll_area)

        self._build_menu()
        self._build_toolbar()
        self._build_adjustments_dock()
        self._set_tab_order()
        self.canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        self.statusBar().showMessage("Open an image to begin.")

        self._wire_controller_signals()
        self._update_action_states()

    # --- UI construction -------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self.open_action = QAction("&Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self._on_open)
        file_menu.addAction(self.open_action)

        self.export_action = QAction("&Export…", self)
        self.export_action.setShortcut("Ctrl+E")
        self.export_action.triggered.connect(self._on_export)
        file_menu.addAction(self.export_action)

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Edit")

        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.controller.undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.controller.redo)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()
        self.reset_all_action = QAction("Reset &all edits", self)
        self.reset_all_action.triggered.connect(self._on_reset_all)
        edit_menu.addAction(self.reset_all_action)

        view_menu = self.menuBar().addMenu("&View")

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_in_action.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_out_action.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(self.zoom_out_action)

        self.zoom_actual_action = QAction("&Actual Size (100%)", self)
        self.zoom_actual_action.setShortcut("Ctrl+1")
        self.zoom_actual_action.triggered.connect(lambda: self.canvas.set_zoom(1.0))
        view_menu.addAction(self.zoom_actual_action)

        self.zoom_fit_action = QAction("&Fit to Window", self)
        self.zoom_fit_action.setShortcut("Ctrl+0")
        self.zoom_fit_action.triggered.connect(self.canvas.set_zoom_fit)
        view_menu.addAction(self.zoom_fit_action)

        help_menu = self.menuBar().addMenu("&Help")

        getting_started_action = QAction("&Getting Started", self)
        getting_started_action.triggered.connect(self._on_getting_started)
        help_menu.addAction(getting_started_action)

        about_action = QAction("&About SnapForge", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Tools", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.rotate_ccw_action = QAction("Rotate ↺", self)
        self.rotate_ccw_action.setToolTip("Rotate left, 90°")
        self.rotate_ccw_action.triggered.connect(self.controller.rotate_counterclockwise)
        toolbar.addAction(self.rotate_ccw_action)

        self.rotate_cw_action = QAction("Rotate ↻", self)
        self.rotate_cw_action.setToolTip("Rotate right, 90°")
        self.rotate_cw_action.triggered.connect(self.controller.rotate_clockwise)
        toolbar.addAction(self.rotate_cw_action)

        self.flip_h_action = QAction("Flip ↔", self)
        self.flip_h_action.setToolTip("Flip the image left-to-right")
        self.flip_h_action.triggered.connect(self.controller.flip_horizontal)
        toolbar.addAction(self.flip_h_action)

        self.flip_v_action = QAction("Flip ↕", self)
        self.flip_v_action.setToolTip("Flip the image top-to-bottom")
        self.flip_v_action.triggered.connect(self.controller.flip_vertical)
        toolbar.addAction(self.flip_v_action)

        toolbar.addSeparator()

        self.crop_action = QAction("Crop", self)
        self.crop_action.setCheckable(True)
        self.crop_action.setToolTip("Click, then drag on the image to select the area to keep")
        self.crop_action.toggled.connect(self._on_crop_toggled)
        toolbar.addAction(self.crop_action)

        toolbar.addSeparator()

        self.compare_action = QAction("Before / After", self)
        self.compare_action.setCheckable(True)
        self.compare_action.setToolTip("Hold to compare with the original (click to toggle)")
        self.compare_action.toggled.connect(self.controller.set_compare_original)
        toolbar.addAction(self.compare_action)

        toolbar.addSeparator()

        self.zoom_out_button_action = QAction("Zoom −", self)
        self.zoom_out_button_action.triggered.connect(self.canvas.zoom_out)
        toolbar.addAction(self.zoom_out_button_action)

        self.zoom_label = QLabel("Fit")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_label)

        self.zoom_in_button_action = QAction("Zoom +", self)
        self.zoom_in_button_action.triggered.connect(self.canvas.zoom_in)
        toolbar.addAction(self.zoom_in_button_action)

        self.zoom_fit_button_action = QAction("Fit", self)
        self.zoom_fit_button_action.setToolTip("Fit image to window (Ctrl+0)")
        self.zoom_fit_button_action.triggered.connect(self.canvas.set_zoom_fit)
        toolbar.addAction(self.zoom_fit_button_action)

        self._toolbar_actions = [
            self.rotate_ccw_action,
            self.rotate_cw_action,
            self.flip_h_action,
            self.flip_v_action,
            self.crop_action,
            self.compare_action,
            self.zoom_out_button_action,
            self.zoom_in_button_action,
            self.zoom_fit_button_action,
        ]
        self._zoom_menu_actions = [
            self.zoom_in_action,
            self.zoom_out_action,
            self.zoom_actual_action,
            self.zoom_fit_action,
        ]

    def _build_adjustments_dock(self) -> None:
        self.adjustments_panel = AdjustmentsPanel(self.controller)
        dock = QDockWidget("Adjustments", self)
        dock.setWidget(self.adjustments_panel)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _set_tab_order(self) -> None:
        """Explicit keyboard tab order: canvas, then each
        adjustment slider in the order it's displayed, then the reset
        button. Qt's auto-generated order (by widget-creation sequence)
        would mostly match this already, but leaving it implicit means it
        silently breaks if construction order ever changes — this makes it
        a property of the UI instead of an accident of code order.
        """
        previous = self.canvas
        for slider in self.adjustments_panel.slider_widgets():
            self.setTabOrder(previous, slider)
            previous = slider
        self.setTabOrder(previous, self.adjustments_panel.reset_button)

    # --- Controller signal wiring ------------------------------------------

    def _wire_controller_signals(self) -> None:
        c = self.controller
        c.document_opened.connect(self._on_document_opened)
        c.document_closed.connect(self._update_action_states)
        c.preview_updated.connect(self.canvas.set_image)
        c.history_changed.connect(self._on_history_changed)
        c.error_occurred.connect(self._on_error)
        c.status_message.connect(self.statusBar().showMessage)
        c.export_succeeded.connect(self._on_export_succeeded)
        c.export_failed.connect(self._on_export_failed)

    # --- Action handlers -------------------------------------------------

    def _on_open(self) -> None:
        document = self.controller.document
        has_unsaved = document is not None and document.has_unsaved_edits
        if has_unsaved and not self._confirm_discard_unsaved():
            return

        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_IMPORT_EXTENSIONS))
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open image", "", f"Supported images ({extensions})"
        )
        if not path_str:
            return
        self.controller.open_image(Path(path_str))

    def _on_document_opened(self) -> None:
        self.crop_action.setChecked(False)
        self.compare_action.setChecked(False)
        self.canvas.set_zoom_fit()  # each new image starts fit-to-window
        self.adjustments_panel.setEnabled(True)
        self.adjustments_panel.sync_from_params(self.controller.document.params)
        self._update_action_states()

    def _on_canvas_zoom_changed(self, zoom: float | None) -> None:
        # Fit mode: the scroll area forces the canvas to match the viewport
        # (letterboxed inside it). Zoom mode: the canvas takes its own
        # fixed size and the scroll area provides scrollbars/panning.
        self.scroll_area.setWidgetResizable(zoom is None)
        self.zoom_label.setText("Fit" if zoom is None else f"{round(zoom * 100)}%")
        # Mirrors ImageCanvas._step_zoom's own "current" fallback so these
        # buttons' enabled state always agrees with what clicking them does.
        effective = zoom if zoom is not None else ZOOM_ACTUAL_SIZE
        can_zoom_in = effective < ZOOM_STEPS[-1]
        can_zoom_out = effective > ZOOM_STEPS[0]
        self.zoom_in_action.setEnabled(can_zoom_in)
        self.zoom_in_button_action.setEnabled(can_zoom_in)
        self.zoom_out_action.setEnabled(can_zoom_out)
        self.zoom_out_button_action.setEnabled(can_zoom_out)

    def _on_export(self) -> None:
        if not self.controller.has_document:
            return
        suggested = self.controller.document.source_path
        dialog = ExportDialog(suggested, self)
        if dialog.exec() == ExportDialog.DialogCode.Accepted:
            options = dialog.result_options()
            if options is not None:
                self.statusBar().showMessage("Exporting…")
                self.controller.export(options)

    def _on_export_succeeded(self, path_str: str) -> None:
        self.statusBar().showMessage(f"Exported to {path_str}")
        QMessageBox.information(
            self,
            "Export complete",
            f"Your image was exported to:\n{path_str}",
        )

    def _on_export_failed(self, message: str) -> None:
        self.statusBar().showMessage("Export failed.")
        QMessageBox.critical(self, "Export failed", message)

    def _on_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _on_getting_started(self) -> None:
        QMessageBox.information(
            self,
            "Getting Started",
            "1. File → Open (or Ctrl+O) to open a JPEG, PNG, or WebP photo.\n\n"
            "2. Drag the sliders on the right to adjust brightness, "
            "contrast, saturation, warmth, and sharpness. The preview "
            "updates as you drag.\n\n"
            "3. Use the toolbar to Rotate, Flip, or Crop (click Crop, then "
            "drag on the image to pick the area to keep).\n\n"
            "4. Click Before / After to compare with the original photo.\n\n"
            "5. Ctrl+Z to undo, Ctrl+Y to redo — any change can be undone.\n\n"
            "6. File → Export (or Ctrl+E) to save your result. SnapForge "
            "will always ask before overwriting an existing file, and will "
            "never overwrite your original photo unless you explicitly "
            "choose it as the destination.",
        )

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About SnapForge",
            f"Shadowcr3 SnapForge — v{__version__}\n\n"
            "A free, local-first photo editor. Your photos are never "
            "uploaded anywhere — everything happens on your computer.\n\n"
            "https://github.com/shadowcr3/Shadowcr3-SnapForge",
        )

    def _on_reset_all(self) -> None:
        if not self.controller.has_document:
            return
        self.controller.reset_all_edits()
        self.adjustments_panel.sync_from_params(self.controller.document.params)

    def _on_crop_toggled(self, enabled: bool) -> None:
        self._crop_active = enabled
        self.canvas.set_crop_mode(enabled)
        if enabled:
            with contextlib.suppress(TypeError, RuntimeError):
                self.canvas.crop_selected.disconnect(self._on_crop_selected)
            self.canvas.crop_selected.connect(self._on_crop_selected)
            # Entering crop mode always starts from the full rotate/flip
            # output (see operations.render docstring for why this is
            # required for crop coordinates to stay meaningful).
            if self.controller.document is not None and (
                self.controller.document.params.crop_box is not None
            ):
                self.controller.clear_crop()
            self.statusBar().showMessage("Drag on the image to select a crop area.")
        else:
            self.statusBar().showMessage("Ready.")

    def _on_crop_selected(self, left: int, top: int, right: int, bottom: int) -> None:
        self.controller.apply_crop(left, top, right, bottom)
        self.crop_action.setChecked(False)

    def _on_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)

    def _update_action_states(self) -> None:
        has_doc = self.controller.has_document
        self.export_action.setEnabled(has_doc)
        self.reset_all_action.setEnabled(has_doc)
        for action in self._toolbar_actions:
            action.setEnabled(has_doc)
        for action in self._zoom_menu_actions:
            action.setEnabled(has_doc)
        if not has_doc:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.adjustments_panel.setEnabled(False)
            self.zoom_label.setText("Fit")

    # --- Unsaved-changes guard -----------------------------------------

    def _confirm_discard_unsaved(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Discard current edits?",
            "This image has edits that haven't been exported. Opening a new "
            "image will discard them. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        document = self.controller.document
        has_unsaved = document is not None and document.has_unsaved_edits
        if has_unsaved and not self._confirm_discard_unsaved():
            event.ignore()
            return
        event.accept()
