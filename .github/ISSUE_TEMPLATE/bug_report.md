---
name: Bug report
about: Something crashed, behaved incorrectly, or produced a wrong result
title: ""
labels: bug
assignees: ""
---

**What happened**
A clear description of the bug.

**What you expected instead**

**Steps to reproduce**
1.
2.
3.

**If it's an image/export problem**
- Source image format (JPEG/PNG/WebP) and roughly its dimensions
- Which adjustments/crop/rotate/flip were applied, in what order
- Export format and quality setting
- If possible, attach a minimal image that reproduces it (strip personal
  EXIF/location data first if the original has any — or let SnapForge's
  export do that for you, see `docs/DECISIONS.md`'s metadata policy)

**If it's a crash**
Paste the full traceback here (from the terminal, if you ran SnapForge
from source — `--onefile` packaged builds may need `--windowed` removed
temporarily per `packaging/BUILD.md` to see console output).

**Environment**
- OS and version:
- SnapForge version (or commit hash if running from source):
- Installed from source / packaged binary:
- Python version (if running from source):
