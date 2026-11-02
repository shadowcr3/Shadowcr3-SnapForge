# Contributing to SnapForge

Thanks for considering it. This project is small and opinionated on
purpose — read this before a large PR so your time isn't wasted.

## Before you start

- **Bug fix or small change?** Just open a PR.
- **New feature, or anything touching the architecture?** Open an issue
  first. Check `docs/ROADMAP.md` (is it already planned, and why hasn't it
  shipped yet?) and `docs/DECISIONS.md` (is the thing you want to change a
  deliberate boundary, not an oversight?) before proposing it.

## Architecture rules (non-negotiable)

These aren't style preferences — they're what makes the test suite able to
test `imaging/` without Qt, and what guarantees preview and export can
never silently disagree. A PR that violates one of these will be asked to
change before merge, not merged-then-fixed:

1. **`imaging/` has zero Qt imports and zero filesystem access.** Every
   function takes a `PIL.Image.Image` (+ explicit params) and returns a
   new one. No function in this package mutates its input.
2. **`imaging.operations.render()` is the only place the adjustment order
   is defined.** If you add a new adjustment or geometry operation, it
   goes into `render()`'s canonical pipeline in one place, with a
   docstring comment explaining *why* it sits where it does if that's not
   obvious — see the existing comments for the rotate/flip/crop/color/
   sharpen ordering as the model to follow.
3. **`ui/` never imports `imaging.operations` or `services.import_export`
   directly.** Everything goes through `controllers/editor_controller.py`.
   If the controller doesn't expose what your UI change needs, add a
   method to the controller — don't reach around it.
4. **Undo/redo is snapshots of `EditParams`, not image buffers or diffs.**
   If you're tempted to store a rendered image in history, you're
   probably solving the wrong problem — see `models/history.py`'s
   docstring.
5. **Any change to a documented behavior (non-destructive editing, undo/
   redo, export safety, and so on) needs a test that would fail without
   it.** See "Testing," below.

## Setting up

```bash
git clone https://github.com/shadowcr3/Shadowcr3-SnapForge.git
cd Shadowcr3-SnapForge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Testing

```bash
pytest               # all 95 tests should pass before and after your change
ruff check src/ tests/
```

- `imaging/`, `models/`, and `services/` tests need no Qt — keep them that
  way; don't introduce a Qt dependency into a test that doesn't need one.
- `controllers/` and `ui/` tests use `pytest-qt`'s `qtbot`/`qapp` fixtures
  against a real (headless) `QApplication` — see `tests/test_controller.py`
  and `tests/test_canvas.py` for the pattern. Don't mock Qt signals; drive
  them for real and assert on what actually happened.
- New test fixtures are procedurally generated images (`tests/conftest.py`),
  not real photographs — keep it that way; no binary image files committed
  to the repo as fixtures.
- A bug fix PR should include a test that fails on `main` and passes with
  your fix, where practical.

## Code style

- `ruff check` must pass with zero errors (`ruff.toml`/`pyproject.toml`
  config is the source of truth, not personal preference).
- Prefer explicit over clever. This is a 10-hour-budget initial codebase;
  comments explaining *why* a non-obvious decision was made (see
  `imaging/operations.py` for examples) are worth more here than comments
  restating *what* the next line does.
- No network code. See `docs/DECISIONS.md` — this one really is
  non-negotiable for this project's stated purpose.

## Commit / PR expectations

- Keep PRs scoped to one change. A PR that's "add feature X" plus
  unrelated refactoring is harder to review and harder to revert if X
  turns out wrong.
- Reference the roadmap item or issue your change relates to, if
  applicable.
- If your change affects the documented canonical operation order, update
  the docstring in `imaging/operations.py` and `docs/DECISIONS.md` in the
  same PR — don't leave the docs describing the old behavior.

## Reporting bugs

Open an issue with: what you did, what you expected, what happened
instead, and your OS + Python version. If it's a crash, include the
traceback. If it's a visual/rendering issue, a screenshot helps a lot more
than a description.

## Reporting security issues

Don't open a public issue — see `SECURITY.md`.
