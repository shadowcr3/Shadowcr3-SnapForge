"""The adjustments dock: one slider per tonal control.

The slider-coalescing behavior lives here at the UI boundary:
`valueChanged` drives a live preview only (`controller.preview_adjustment`),
while `sliderReleased` is what commits exactly one history entry
(`controller.commit_adjustment`). Dragging a slider back and forth
therefore never produces more than one undo step.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from snapforge.imaging.operations import ADJUSTMENT_MAX, ADJUSTMENT_MIN, EditParams

_SLIDERS: list[tuple[str, str]] = [
    ("brightness", "Brightness"),
    ("contrast", "Contrast"),
    ("saturation", "Saturation"),
    ("warmth", "Warmth"),
    ("sharpness", "Sharpness"),
]


class _AdjustmentRow(QWidget):
    live_changed = Signal(str, float)
    committed = Signal(str, float)

    def __init__(self, field: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.field = field
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        self._name_label = QLabel(label)
        self._value_label = QLabel("0")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_row = QWidget()
        header_row.setLayout(_row(self._name_label, self._value_label))
        layout.addWidget(header_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(ADJUSTMENT_MIN))
        self.slider.setMaximum(int(ADJUSTMENT_MAX))
        self.slider.setValue(0)
        # A screen reader has nothing to announce for a bare QSlider beyond
        # its numeric value unless it's given an accessible name — this is
        # what ties "−40" back to "Brightness".
        self.slider.setAccessibleName(f"{label} slider")
        self.slider.setAccessibleDescription(
            f"Adjusts {label.lower()} from {int(ADJUSTMENT_MIN)} to "
            f"{int(ADJUSTMENT_MAX)}, 0 is unchanged."
        )
        self.slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.slider.valueChanged.connect(self._on_value_changed)
        self.slider.sliderReleased.connect(self._on_released)
        layout.addWidget(self.slider)

    def set_value_silently(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round(value))
        self.slider.blockSignals(False)
        self._value_label.setText(str(round(value)))

    def _on_value_changed(self, value: int) -> None:
        self._value_label.setText(str(value))
        self.live_changed.emit(self.field, float(value))

    def _on_released(self) -> None:
        self.committed.emit(self.field, float(self.slider.value()))


def _row(left: QWidget, right: QWidget):
    from PySide6.QtWidgets import QHBoxLayout

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(left)
    row.addStretch(1)
    row.addWidget(right)
    return row


class AdjustmentsPanel(QWidget):
    """Owns the five adjustment sliders and talks to the controller directly
    (it is a thin wiring layer, not where any image math happens).
    """

    def __init__(self, controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._rows: dict[str, _AdjustmentRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        section = QLabel("Adjustments")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

        for field, label in _SLIDERS:
            row = _AdjustmentRow(field, label)
            row.live_changed.connect(self._on_live_changed)
            row.committed.connect(self._on_committed)
            layout.addWidget(row)
            self._rows[field] = row

        self.reset_button = QPushButton("Reset adjustments")
        self.reset_button.setToolTip(
            "Resets brightness, contrast, saturation, warmth, and sharpness "
            "back to zero. Crop and rotation are not affected."
        )
        self.reset_button.clicked.connect(self._on_reset)
        layout.addWidget(self.reset_button)
        layout.addStretch(1)

        self.setEnabled(False)

    def slider_widgets(self) -> list[QSlider]:
        """The slider widgets in display order — used by MainWindow to set
        explicit keyboard tab order without reaching into `_rows` directly.
        """
        return [self._rows[field].slider for field, _label in _SLIDERS]

    def sync_from_params(self, params: EditParams) -> None:
        for field, _label in _SLIDERS:
            self._rows[field].set_value_silently(getattr(params, field))

    def _on_live_changed(self, field: str, value: float) -> None:
        self._controller.preview_adjustment(**{field: value})

    def _on_committed(self, field: str, value: float) -> None:
        self._controller.commit_adjustment(**{field: value})

    def _on_reset(self) -> None:
        if self._controller.document is None:
            return
        self._controller.reset_adjustments_only()
        self.sync_from_params(self._controller.document.params)
