from __future__ import annotations

from snapforge.imaging.operations import EditParams
from snapforge.models.history import EditHistory


def test_initial_state_is_identity_and_has_nothing_to_undo():
    history = EditHistory()
    assert history.current == EditParams()
    assert not history.can_undo()
    assert not history.can_redo()


def test_push_commits_one_step():
    history = EditHistory()
    history.push(EditParams(brightness=20))
    assert history.current == EditParams(brightness=20)
    assert history.can_undo()
    assert not history.can_redo()


def test_push_identical_params_is_a_noop():
    history = EditHistory()
    history.push(EditParams(brightness=20))
    history.push(EditParams(brightness=20))  # identical -> should not stack
    history.undo()
    assert history.current == EditParams()
    assert not history.can_undo()


def test_undo_redo_restore_expected_states():
    history = EditHistory()
    history.push(EditParams(brightness=10))
    history.push(EditParams(brightness=20))
    history.push(EditParams(brightness=30))

    assert history.undo() == EditParams(brightness=20)
    assert history.undo() == EditParams(brightness=10)
    assert history.current == EditParams(brightness=10)
    assert history.can_redo()

    assert history.redo() == EditParams(brightness=20)
    assert history.redo() == EditParams(brightness=30)
    assert not history.can_redo()


def test_new_edit_after_undo_discards_redo_branch():
    history = EditHistory()
    history.push(EditParams(brightness=10))
    history.push(EditParams(brightness=20))
    history.undo()
    assert history.can_redo()

    history.push(EditParams(brightness=99))  # new branch
    assert not history.can_redo()
    assert history.current == EditParams(brightness=99)


def test_undo_past_the_start_is_a_safe_noop():
    history = EditHistory()
    assert history.undo() == EditParams()
    assert history.undo() == EditParams()


def test_redo_without_prior_undo_is_a_safe_noop():
    history = EditHistory()
    history.push(EditParams(brightness=5))
    assert history.redo() == EditParams(brightness=5)


def test_reset_clears_history_entirely():
    history = EditHistory()
    history.push(EditParams(brightness=10))
    history.push(EditParams(brightness=20))
    history.undo()

    history.reset()
    assert history.current == EditParams()
    assert not history.can_undo()
    assert not history.can_redo()


def test_history_depth_is_bounded():
    from snapforge.models.history import MAX_HISTORY_DEPTH

    history = EditHistory()
    for i in range(MAX_HISTORY_DEPTH + 20):
        history.push(EditParams(brightness=float(i % 100 - 50) or 1.0))
    undo_count = 0
    while history.can_undo():
        history.undo()
        undo_count += 1
    assert undo_count <= MAX_HISTORY_DEPTH
