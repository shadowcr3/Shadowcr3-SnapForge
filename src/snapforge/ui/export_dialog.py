"""Export dialog.

Shows format-specific options, warns before overwriting an existing file,
and keeps whatever the user already entered if validation fails rather
than resetting the form.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from snapforge.services.import_export import SUPPORTED_EXPORT_FORMATS, ExportOptions


class ExportDialog(QDialog):
    def __init__(self, suggested_path: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export image")
        self.setMinimumWidth(420)

        self._result_options: ExportOptions | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(sorted(SUPPORTED_EXPORT_FORMATS))
        default_format = "JPEG"
        if suggested_path is not None:
            from snapforge.services.import_export import default_format_for

            default_format = default_format_for(suggested_path) or "JPEG"
        self.format_combo.setCurrentText(default_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        form.addRow("Format", self.format_combo)

        quality_row = QWidget()
        quality_layout = QHBoxLayout(quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setMinimum(1)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setValue(90)
        self.quality_value_label = QLabel("90")
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_value_label.setText(str(v))
        )
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_value_label)
        self.quality_row_label = QLabel("Quality")
        form.addRow(self.quality_row_label, quality_row)

        dest_row = QWidget()
        dest_layout = QHBoxLayout(dest_row)
        dest_layout.setContentsMargins(0, 0, 0, 0)
        self.destination_edit = QLineEdit()
        if suggested_path is not None:
            self.destination_edit.setText(str(suggested_path))
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)
        dest_layout.addWidget(self.destination_edit)
        dest_layout.addWidget(browse_button)
        form.addRow("Destination", dest_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_format_changed(self.format_combo.currentText())

    def _on_format_changed(self, fmt: str) -> None:
        needs_quality = fmt in ("JPEG", "WEBP")
        self.quality_slider.setVisible(needs_quality)
        self.quality_value_label.setVisible(needs_quality)
        self.quality_row_label.setVisible(needs_quality)

    def _browse(self) -> None:
        fmt = self.format_combo.currentText()
        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
        start = self.destination_edit.text() or f"export.{ext}"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Choose export destination", start, f"{fmt} files (*.{ext})"
        )
        if path_str:
            self.destination_edit.setText(path_str)

    def _on_accept(self) -> None:
        dest_text = self.destination_edit.text().strip()
        if not dest_text:
            QMessageBox.warning(self, "No destination", "Choose a destination file first.")
            return  # keep the dialog open with everything the user entered intact

        destination = Path(dest_text)
        overwrite_confirmed = False
        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Overwrite file?",
                f"'{destination.name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite_confirmed = True

        self._result_options = ExportOptions(
            destination=destination,
            format=self.format_combo.currentText(),
            quality=self.quality_slider.value(),
            overwrite_confirmed=overwrite_confirmed,
        )
        self.accept()

    def result_options(self) -> ExportOptions | None:
        return self._result_options
