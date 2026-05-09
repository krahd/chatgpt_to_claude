# ChatGPT → Claude migration toolkit – Project Status

Last updated: 2026-05-09 18-35

## Project purpose

Toolkit for reviewing and migrating ChatGPT export bundles into Claude-friendly
bundles and review artifacts. The package exposes CLI entrypoints and a TUI to
parse, validate and export conversation data for downstream ingestion.

Current release: v0.0.3 (see `pyproject.toml` and
`src/chatgpt_to_claude_toolkit/__init__.py` for version metadata).

## Current implementation state

- Core CLI commands implemented: `chatgpt-to-claude`,
	`chatgpt-to-claude-tui`, `chatgpt-to-claude-review-state` (exposed via
	`pyproject.toml`).
- Parsing for common ChatGPT export structures and export to Markdown.
- Attachment extraction, classification and preview generation implemented.
- Memory candidate extraction with provenance writing (`memory_provenance.json`).
- Topic bundle generation, summary reports, upload plans and manual attention
	reports implemented as documented in `README.md`.
- Tests: simple unit test(s) present under `tests/` (see
	`tests/test_toolkit.py`).
- Recent implementation work has been merged into `main` and pushed to `origin`.

## Active focus

- Improve migration heuristics (memory extraction and attachment understanding).
- Validate and harden browser automation flows used for attachment previews.
- Maintain CLI usability and update release workflow documentation.

(These focus areas are inferred from the project's `README.md` "Known limits"
and release notes. If the current priorities differ, update this section.)

## Architecture overview

Light-weight Python CLI/TUI package:

- Source package: `src/chatgpt_to_claude_toolkit/`
- CLI entrypoints (defined in `pyproject.toml`) invoke functions in the
	package.
- `scripts/` contains helper and smoke-test utilities; `tests/` contains unit
	tests.
- Outputs are written to the configured output directory and include CSV/JSON
	inventories, manifests, and report Markdown files consumed by reviewers.

### Architecture diagram

The following inline SVG summarises the main components and data flow.

<svg xmlns="http://www.w3.org/2000/svg" width="760" height="220" viewBox="0 0 760 220">
  <title>ChatGPT→Claude toolkit architecture</title>
  <desc>CLI/TUI frontends call library code that parses exports, generates
  artifacts, and writes reports to disk.</desc>
  <rect x="18" y="30" width="200" height="60" rx="6" fill="#f5f7ff" stroke="#2b5cff"/>
  <text x="118" y="65" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">CLI &amp; TUI</text>
  <text x="118" y="80" font-size="11" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">(entrypoints)</text>

  <rect x="270" y="20" width="220" height="95" rx="6" fill="#ffffff" stroke="#2b5cff"/>
  <text x="380" y="45" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">Library</text>
  <text x="380" y="63" font-size="11" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">Parsing • Extraction • Reporting</text>

  <rect x="520" y="30" width="200" height="60" rx="6" fill="#f5fff5" stroke="#1f9b2e"/>
  <text x="620" y="55" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#0b3f1b">Outputs</text>
  <text x="620" y="70" font-size="11" font-family="sans-serif" text-anchor="middle" fill="#0b3f1b">Markdown/JSON/CSV</text>

  <line x1="218" y1="60" x2="270" y2="60" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="490" y1="60" x2="520" y2="60" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)"/>

  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="0" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#333"/>
    </marker>
  </defs>
</svg>

Short explanation: the user-facing CLIs/TUI call into the package library which
performs parsing, extraction and reporting; results are written to disk for
review and downstream upload.

### Flow chart

<svg xmlns="http://www.w3.org/2000/svg" width="760" height="160" viewBox="0 0 760 160">
  <title>Execution flow</title>
  <desc>High-level execution flow from input export to reviewer artifacts.</desc>
  <rect x="20" y="30" width="180" height="40" rx="6" fill="#fff7e6" stroke="#d97706"/>
  <text x="110" y="55" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#5c3a00">Input: chatgpt-export.zip</text>

  <rect x="240" y="15" width="220" height="70" rx="6" fill="#eef2ff" stroke="#3730a3"/>
  <text x="350" y="35" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">Parse &amp; Normalise</text>
  <text x="350" y="55" font-size="11" font-family="sans-serif" text-anchor="middle" fill="#0b1b3f">conversations • attachments • metadata</text>

  <rect x="520" y="30" width="180" height="40" rx="6" fill="#f0fdf4" stroke="#065f46"/>
  <text x="610" y="55" font-size="12" font-family="sans-serif" text-anchor="middle" fill="#064e3b">Generate Reports</text>

  <line x1="200" y1="50" x2="240" y2="50" stroke="#333" stroke-width="1.2" marker-end="url(#farrow)"/>
  <line x1="460" y1="50" x2="520" y2="50" stroke="#333" stroke-width="1.2" marker-end="url(#farrow)"/>

  <defs>
    <marker id="farrow" markerWidth="10" markerHeight="10" refX="0" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#333"/>
    </marker>
  </defs>
</svg>

Short explanation: an input export is parsed and normalised, attachments are
processed and previews generated, and final review artifacts are written for
manual or automated review.

## Setup and run instructions

Install editable for development:

```bash
pip install -e .
pip install -e .[dev]  # for development tools
```

Typical CLI usage (examples taken from `README.md`):

```bash
chatgpt-to-claude-tui /path/to/chatgpt-export.zip ./selection.json
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --selection-file ./selection.json
```

Run tests and basic verification:

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
python scripts/smoke_test.py
```

## Configuration and environment variables

- Requires Python 3.11+ (see `pyproject.toml` `requires-python`).
- Optional extras: `browser` extra installs `playwright` for browser automation
	features; development extras include `build`, `ruff`, and `mypy`.
- Sample files: `browser_config.sample.json` is referenced in the README for
	browser automation configuration (update as needed for local environments).

## Important files and directories

- `src/chatgpt_to_claude_toolkit/`: package source
- `pyproject.toml`: package metadata and CLI entrypoints
- `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`
- `tests/`: unit tests; `scripts/`: smoke and helper scripts
- `claude_migration_output/`: example or generated output (repo-tracked)

## Recent changes

- Repository version set to `0.0.3` (pyproject metadata and package fallback).
- Changelog updated with v0.0.3 release notes covering memory extraction,
  attachment classification, and browser automation hardening.
- README release metadata aligned to v0.0.3.

## Tests and verification status

- Unit tests were executed locally: 9 tests ran and passed.
- Smoke test (`scripts/smoke_test.py`) executed and reported `smoke ok`.
- Verification commands run:

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
python scripts/smoke_test.py
```

All commands completed successfully in the local verification run. Include
these steps in release preparation and CI where appropriate.

## Known issues, risks, and limitations

- Memory extraction is heuristic rather than model-based.
- Contradiction detection and token estimation are approximate.
- Browser automation remains guided and selector-dependent.
- Attachment understanding is shallow for some binary formats.

## Recurring tasks

- Run unit tests and smoke tests before releases.
- Update `__version__` in `src/.../__init__.py` and `pyproject.toml` on release.
- Update `CHANGELOG.md` and create a release tag per release management notes.

## Completed tasks

- ✓ Improved memory extraction precision: enhanced text normalisation, enriched provenance
  references with title slug and sentence snippet in source_refs.
- ✓ Improved attachment understanding: added content-based classification fallback for
  text detection despite non-text extension.
- ✓ Hardened browser automation: implemented multiple selector fallbacks and element
  existence checks for resilient uploads.
- ✓ Fixed STATUS.md SVG rendering: escaped XML special characters (&) in inline SVG text nodes.
- ✓ All unit and smoke tests passing (9 tests, verified 2026-05-08 20:28).
- ✓ Release preparation completed for v0.0.3: version metadata and changelog aligned.

## Next steps

1. Evaluate model-based memory extraction and richer attachment analysis.
2. Add broader automated verification for browser-driven flows.

## Longer-term steps

1. Evaluate model-based memory extraction and richer attachment analysis.
2. Add broader automated verification for browser-driven flows.

## Decisions and rationale

- Editable install and simple CLI entrypoints favour developer ergonomics and
	straightforward packaging.
- Small, focused changes are preferred over large refactors (see
	`AGENTS.md`).

## Documentation alignment notes

- Primary docs: `README.md` contains usage and release steps; keep
	`STATUS.md` aligned with `README.md` and `CHANGELOG.md`.

---

Last updated: 2026-05-09 18-35
