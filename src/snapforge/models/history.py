"""Undo/redo history for SnapForge.

Requirements this module exists to satisfy:
  * Every supported edit command must have defined undo behavior.
  * Undo/redo must preserve a consistent edit state.
  * New edits after undo must invalidate the abandoned redo branch.
  * Repeatedly moving a slider should not create a history entry per pixel
    of pointer movement — changes should be coalesced.

Design: history is a stack of immutable `EditParams` *snapshots* — a set
of lightweight parameters, not image buffers or diffs. This keeps memory
bounded regardless of source image size and makes every operation
trivially correct to reverse: undo = "go back to the previous snapshot".

Coalescing of continuous input (slider drags) is a *caller* responsibility,
not this class's: the controller calls `push()` only when a drag/commit
completes (e.g. on mouse release), and updates a live preview separately in
the meantime without touching history at all. That keeps this class simple
and keeps the "what counts as one undo step" policy in one place.
"""

from __future__ import annotations

from snapforge.imaging.operations import EditParams

#: Prevent unbounded memory growth from a very long editing session.
MAX_HISTORY_DEPTH = 100


class EditHistory:
    def __init__(self, initial: EditParams | None = None) -> None:
        self._current: EditParams = initial if initial is not None else EditParams()
        self._undo_stack: list[EditParams] = []
        self._redo_stack: list[EditParams] = []

    @property
    def current(self) -> EditParams:
        return self._current

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def push(self, new_params: EditParams) -> None:
        """Commit a completed edit as one undo step.

        No-ops if `new_params` is identical to the current state (dragging a
        slider back to where it started should not create a dead history
        entry).
        """
        if new_params == self._current:
            return
        self._undo_stack.append(self._current)
        if len(self._undo_stack) > MAX_HISTORY_DEPTH:
            self._undo_stack.pop(0)
        self._current = new_params
        # A fresh edit after undo abandons the redo branch.
        self._redo_stack.clear()

    def undo(self) -> EditParams:
        if not self.can_undo():
            return self._current
        self._redo_stack.append(self._current)
        self._current = self._undo_stack.pop()
        return self._current

    def redo(self) -> EditParams:
        if not self.can_redo():
            return self._current
        self._undo_stack.append(self._current)
        self._current = self._redo_stack.pop()
        return self._current

    def reset(self, params: EditParams | None = None) -> None:
        """Used when opening a new image — must NOT carry over the previous
        image's history, so a new image never accidentally inherits the
        previous one's edits.
        """
        self._current = params if params is not None else EditParams()
        self._undo_stack.clear()
        self._redo_stack.clear()
