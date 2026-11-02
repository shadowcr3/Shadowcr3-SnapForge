# Security Policy

## Threat model

SnapForge is a local, offline desktop application. There is no server
component, no account system, and no network code anywhere in `src/` — it
does not make outbound requests, check for updates, or transmit any data.
The practical attack surface is therefore narrow and specific:

1. **Malicious or malformed image files.** The primary input SnapForge
   processes is attacker-influenceable if someone sends you a crafted
   JPEG/PNG/WebP. This is the threat this project takes most seriously.
2. **The local filesystem.** Export writes a file to a path the user
   chooses; a bug here could mean data loss (corrupting/losing the
   user's own files) rather than remote compromise.
3. **Supply chain.** Three runtime dependencies: PySide6, Pillow, numpy.
   A vulnerability in any of them is effectively a vulnerability in
   SnapForge.

Explicitly **out of scope** because the application has no such surface:
network protocol attacks, authentication/authorization, server-side
anything, injection via any API (there is no API).

## What SnapForge does to mitigate the in-scope risks

- **Decompression-bomb / memory-exhaustion protection**: imported images
  are dimension-checked (`imaging.operations.guard_dimensions`, capped at
  12,000px per side) before any processing proceeds.
- **No trust in file extensions**: import validates actual file content via
  Pillow's format sniffing, not the extension — see
  `services.import_export.open_image`.
- **Corrupt/truncated input fails loudly, not silently**: `open_image`
  forces a full decode (`handle.load()`) at import time rather than
  lazily, so corruption surfaces immediately as a reported error rather
  than later as a crash or a bad export.
- **Atomic, verified exports**: `services.import_export.export_image`
  writes to a temp file in the destination directory, re-opens and
  verifies it decodes correctly, and only then atomically replaces the
  destination (`os.replace`). A failure at any step leaves the original
  destination (if any) untouched — never a half-written file presented as
  a successful export.
- **No silent overwrite**: exporting over an existing file requires
  explicit confirmation (`ExportOptions.overwrite_confirmed`), enforced in
  the service layer itself — not just the UI — so a UI bug can't bypass it.
- **No network code**: nothing in `src/` imports `requests`, `urllib`,
  `socket`, or any other networking primitive. This is directly checkable
  by grepping the dependency tree and source, not something you have to
  take on trust. (See `docs/DECISIONS.md`.)

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security vulnerability.

Instead, report it privately via GitHub's "Report a vulnerability" flow on
this repository (Security tab → "Report a vulnerability"), or by
contacting the maintainer directly through the contact information on the
[GitHub profile](https://github.com/shadowcr3).

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce (a minimal malicious/malformed file, if that's the
  vector, is extremely helpful).
- Which version/commit you tested against.

This is a single-maintainer open-source project maintained alongside other
work, not a company with an SLA — I'll do my best to acknowledge reports
promptly and will credit reporters (unless you ask not to be) once a fix
ships.

## Supported versions

As a pre-1.0 project, only the latest released version is supported with
security fixes. There is no long-term-support branch at this stage.
