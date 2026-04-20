# ChatGPT → Claude migration toolkit

Toolkit for reviewing and migrating ChatGPT exports into Claude-friendly bundles.
Current release: `v0.0.1`.

## Install

```bash
pip install -e .
```

For development tools:

```bash
pip install -e .[dev]
```

CLI commands exposed:

- `chatgpt-to-claude`
- `chatgpt-to-claude-tui`
- `chatgpt-to-claude-review-state`

## Project layout

- `src/chatgpt_to_claude_toolkit/` package source
- `tests/` automated tests
- `.github/workflows/` CI and release build workflows

## Main capabilities

- parse common ChatGPT export structures, including some alternate JSON filenames
- export conversations to Markdown with previews
- extract, classify, and summarise attachments
- generate text previews for text attachments
- extract candidate memory items with provenance references
- write `memory_provenance.json` for reviewable traceability
- generate topic bundles, upload plans, validation reports, HTML summaries, and manual attention reports
- provide a TUI for review, filtering, sorting, and inline memory editing
- track migration progress in `migration_state.json`

## Typical workflow

```bash
chatgpt-to-claude-tui /path/to/chatgpt-export.zip ./selection.json
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --selection-file ./selection.json
```

## Useful export controls

```bash
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --dry-run --after 2024-01-01 --before 2025-01-01
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --title-include "kivy" --title-exclude "old"
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --max-conversations 100
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --no-memory --no-projects --no-attachments
```

## Validation and maintenance

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
```

See also:

- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `LICENSE`

## Known limits

- memory extraction is still heuristic rather than model-based
- contradiction detection is approximate
- token estimation is approximate
- browser automation remains guided and selector-dependent
- attachment understanding is still shallow for binary formats

## Smoke test

```bash
python scripts/smoke_test.py
```

## Additional output files

- `conversation_index.csv`
- `manifest.jsonl`
- `filters_used.json`
- `duplicate_titles.json`
- `stale_conversations.json`
- `memory_provenance.json`
- `batch_plan.json`

## Strict validation mode

```bash
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --strict
```

The command exits non-zero if validation finds warnings or errors.

- `selection_summary.json` when a selection file is used
- `REPORT_INDEX.md` as a simple report inventory

## Stale conversation reporting

```bash
chatgpt-to-claude /path/to/chatgpt-export.zip -o ./out --stale-before 2024-01-01
```

- `RUN_SUMMARY.md`
- `report_fingerprints.json`

- `browser_config.sample.json`
- `selection_mismatch_report.json`
## Release management

For each release:

1. update version values in `pyproject.toml` and `src/chatgpt_to_claude_toolkit/__init__.py`
2. update `CHANGELOG.md`
3. run validation commands:

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
```

4. create and push the tag (example for `v0.0.1`):

```bash
VERSION=v0.0.1
git tag -a "$VERSION" -m "Release $VERSION"
git push origin main --follow-tags
```

5. publish the GitHub release:

```bash
gh release create "$VERSION" --title "$VERSION" --notes-file CHANGELOG.md
```
