# AGENTS.md

Repository instructions for AI coding agents working in this project.

This file is the durable source of truth for GitHub Copilot, OpenAI Codex, Claude Code, and other compatible coding agents. Read it before making changes. Follow the most specific applicable instruction when several instruction files exist.

## 1:  Non-negotiable rules

- Keep `STATUS.md` accurate at all times.
- `STATUS.md` must exist in the repository root. If it is missing, create it before finishing any task that changes the project.
- Do not finish a task that changes the project without reviewing and, when needed, updating `STATUS.md`.
- Do not invent project facts. Inspect the repository and record uncertainty explicitly.
- Do not overwrite user work or unrelated changes.
- Do not commit secrets, credentials, tokens, private keys, local environment files, database dumps, saved user data, or generated sensitive data.
- Do not add new production dependencies without a clear need and without documenting why.
- Prefer small, focused changes over broad rewrites.
- Preserve existing project style unless the task explicitly asks for a style change.
- Verify meaningful changes with the narrowest reliable test, lint, type-check, build, or run command available.
- If verification cannot be run, document the reason in the final response and in `STATUS.md` when relevant.
- Do not claim that tests, builds, smoke tests, linters, type-checkers, or manual checks passed unless they were actually run.

## 2:  Communication style

Use terse, factual, technical communication.

Do not use playful, whimsical, cute, decorative, or filler progress phrases.

Do not say things like:

- "combobulating"
- "cooking"
- "thinking..."
- "working on it"
- "let me dive in"
- "I'll get started"
- "working my magic"

Allowed status-update style:

- "Reading files."
- "Found the issue."
- "Applying patch."
- "Tests passed."
- "Tests failed: <reason>."

Rules:

- No decorative progress messages.
- No jokes, metaphors, or playful status words.
- No anthropomorphising the process.
- No fake enthusiasm.
- No "I'm going to..." unless asking for confirmation.
- Prefer concise present-tense technical updates.
- Use British English for prose documentation unless the repository already uses another variant consistently.
- When using tools, report only meaningful findings, blockers, or completed changes.
- Provide the result directly for short tasks.
- For long tasks, provide only terse factual status updates.

Bad:

- "Combobulating the codebase..."
- "Let me cook."
- "Working my magic."

Good:

- "Inspecting the failing test."
- "Found one failing import."
- "Updated the config."

## 3:  Standard work loop

For every task:

1. Read this file and any more specific `AGENTS.md` files that apply to the files being edited.
2. Inspect the repository before changing files.
3. Read `STATUS.md` early to understand current project state, risks, validation status, and next steps.
4. Identify the smallest safe change that satisfies the request.
5. Search for all relevant call sites before changing public functions, routes, schemas, commands, or configuration keys.
6. Make focused edits.
7. Run relevant verification when possible.
8. Update documentation when behaviour, setup, architecture, commands, or public APIs change.
9. Update `STATUS.md` if the project state changed.
10. Report changed files, verification performed, and any remaining issues.

For complex work:

- Explore first, then plan, then edit.
- Keep the plan short and operational.
- Re-check assumptions against files, tests, and documentation.
- Prefer incremental patches that can be reviewed independently.
- Do not continue broad refactors when a narrow fix is sufficient.

## 4:  Repository discovery

When the project structure is not yet known:

- List top-level files and directories.
- Read `README.md`, `STATUS.md`, package/build files, and existing docs before editing.
- Identify the language, framework, package manager, test runner, formatter, lint/type-check tools, and CI workflows from repository files.
- Prefer fast search tools such as `rg` when available.
- Do not assume commands from other repositories apply here.
- Treat generated files, build outputs, local caches, virtual environments, and release artifacts as non-source unless the repository clearly tracks them intentionally.

Common files to inspect when present:

- `README.md`
- `STATUS.md`
- `pyproject.toml`, `requirements.txt`, `Pipfile`, `environment.yml`, `pytest.ini`, `tox.ini`, `noxfile.py`
- `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`
- `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `settings.gradle`
- `Makefile`, `justfile`, `Taskfile.yml`
- `.github/workflows/*`
- Docker and compose files
- `docs/`, `examples/`, `scripts/`, `tests/`
- release files such as `CHANGELOG.md`, `RELEASE.md`, `VERSION`, release notes, or package metadata

## 5:  Project-specific map

Each repository should keep this section useful. Replace the placeholders below with real project information as soon as it is known.

### 5.1:  Project shape

- Purpose: `<brief project purpose>`
- Main runtime surfaces: `<CLI / web app / API / desktop app / library / plugin / other>`
- Primary languages/frameworks: `<languages and frameworks>`
- Supported platforms: `<platforms>`

### 5.2:  Important paths

- `README.md`: human-facing overview and start-here documentation.
- `STATUS.md`: complete current project status report; mandatory upkeep.
- `docs/`: user-facing and maintainer-facing documentation, when present.
- `tests/`: automated verification, when present.
- `scripts/`: development, validation, release, or maintenance helpers, when present.

Add project-specific source paths here, for example:

- `<path>`: `<role>`
- `<path>`: `<role>`

### 5.3:  Safety invariants

Document project-specific invariants here. Examples:

- Preview before destructive operations.
- Back up before mutating user data.
- Keep undo/rollback paths intact.
- Preserve local-only defaults unless remote access is explicitly requested.
- Validate paths stay inside allowed roots.
- Keep approval checks for destructive or expensive actions.

Do not weaken safety invariants without explicit user instruction and documentation.

## 6:  `STATUS.md` maintenance

`STATUS.md` is mandatory project state, not optional documentation.

Update `STATUS.md` whenever a meaningful project change occurs, including changes to:

- code behaviour
- architecture
- public APIs, command-line interfaces, routes, schemas, or data contracts
- dependencies or lockfiles
- configuration, settings, environment variables, or secrets handling
- setup, run, build, package, or release instructions
- tests, verification status, CI, or known test gaps
- repository structure
- documentation that affects usage or development
- known issues, risks, limitations, or residual verification gaps
- pending tasks, next steps, or long-term direction
- implementation status
- important design decisions and rationale

Do not update `STATUS.md` for purely trivial changes that do not alter project state, such as typo-only edits in comments, unless the task specifically asks for documentation maintenance.

### 6.1:  Required `STATUS.md` timestamp

`STATUS.md` must contain a `Last updated` line near the top:

```text
Last updated: yyyy-mm-dd hh-mm
```

Rules:

- Use exactly the format above, replacing the timestamp values.
- Use 24-hour time.
- Use the user's local timezone. If no other project-specific timezone is stated, use `America/Montevideo`.
- Get the current local time from the system or environment when possible; do not guess timestamps.
- Use hyphens between date parts and between hour/minute parts.
- Do not include seconds.
- Duplicate the exact same `Last updated` line as the final line at the very bottom of `STATUS.md`.
- When updating `STATUS.md`, update both the top and bottom `Last updated` lines in the same edit.
- The top and bottom `Last updated` lines must match exactly.
- Treat missing, stale, malformed, or mismatched `Last updated` lines as a blocking documentation error for any task that changes project state.

### 6.2:  Required `STATUS.md` content

`STATUS.md` must be a complete project status report, not a short changelog.

Include the following sections where relevant:

- Project purpose
- Current implementation state
- Active focus
- Architecture overview
- Setup and run instructions
- Configuration and environment variables
- Important files and directories
- Current capabilities
- Recent changes
- Tests and verification status
- Known issues, risks, and limitations
- Pending tasks
- Next steps
- Longer-term steps
- Decisions and rationale
- Documentation alignment notes

Keep the report current and useful for the next agent or human developer opening the repository.

## 7:  Starter `STATUS.md` policy

Prefer committing a barebones root-level `STATUS.md` when a repository is created instead of asking the first agent to invent it.

A starter `STATUS.md` should include:

- project title
- correctly formatted top `Last updated` line
- purpose placeholder
- current state placeholder
- setup/run placeholder
- architecture overview placeholder
- important files placeholder
- verification status placeholder
- known issues placeholder
- next steps placeholder
- long-term steps placeholder
- diagram placeholders or initial diagrams when meaningful
- matching final `Last updated` line at the bottom

Agents may expand the starter file after inspecting the repository, but they must preserve the timestamp contract and keep the report factual.

## 8:  Diagrams in `STATUS.md`

`STATUS.md` must include useful inline SVG diagrams when the project has enough structure for them to be meaningful.

Include, where relevant:

- at least one architecture diagram
- at least one flow chart, execution-flow diagram, or data-flow diagram

The diagrams must represent the current project accurately. Do not add generic filler diagrams.

SVG rules:

- Embed SVG directly in `STATUS.md`; do not rely on external image files for the required diagrams.
- Keep all text inside its intended box.
- Keep all text inside the SVG canvas.
- Keep arrows and connector lines out of unrelated boxes and labels.
- Ensure connected arrows terminate cleanly at shape boundaries.
- Make the SVG canvas larger when needed for spacing and legibility.
- Prefer generous spacing over compactness.
- Use simple, maintainable SVG primitives: `svg`, `g`, `rect`, `line`, `path`, `text`, `defs`, `marker`, `title`, `desc`.
- Avoid overlapping text, arrows, boxes, and labels.
- Avoid cramped labels.
- Keep labels concise.
- Include a short text explanation immediately before or after each SVG so the status report remains useful in plain-text views.
- Prefer accessible SVG structure where practical, including `<title>` and `<desc>` elements.
- Prioritise correctness, legibility, and maintainability over decoration.
- Update diagrams when architecture, module relationships, data flow, execution flow, or deployment shape meaningfully changes.
- Avoid trivial diagram edits when no relevant structural or flow change has occurred.

Before finishing diagram edits, visually inspect the SVG text positions, box sizes, arrow routing, and canvas bounds.

If the repository stores generated or large diagrams outside Markdown for human docs, `STATUS.md` may link to them too, but the required status diagrams should remain inline unless the user explicitly changes this policy.

## 9:  Coding standards

- Follow existing style, naming, layout, and architecture.
- Prefer clear, maintainable code over clever code.
- Keep functions and modules focused.
- Avoid unrelated refactors.
- Avoid formatting-only churn unless formatting is the task or required by tooling.
- Preserve public APIs unless the task explicitly requires changing them.
- Preserve data formats, route contracts, CLI flags, config keys, file formats, and public exports unless a breaking change is explicitly requested.
- Handle errors deliberately; do not hide failures with broad silent catches.
- Keep logging useful and non-noisy.
- Add comments only when they explain non-obvious decisions, constraints, or trade-offs.
- Remove dead code only when it is clearly unused and removal is within task scope.

## 10:  Tests and verification

Use the narrowest reliable verification first, then broaden when appropriate.

Preferred order:

1. Targeted unit test or focused command for the changed area.
2. Relevant lint/type-check/format check.
3. Broader test suite when change risk justifies it.
4. Build/package check for release, packaging, or distribution changes.
5. Manual run or smoke test when automated coverage is unavailable.

Rules:

- Add or update tests for behavioural changes when the repository has a test pattern.
- Do not delete failing tests to make a suite pass.
- If tests fail, distinguish failures caused by your change from pre-existing failures when possible.
- Record verification commands and outcomes in the final response.
- Do not claim that tests, linting, type-checking, builds, or smoke tests passed unless they were actually run.
- Record verification status in `STATUS.md` when it affects project state, release readiness, risk, or pending work.
- If real external validation is required but not run, record it as unverified, not as passed.

Project-specific validation commands should be added here when known:

```bash
# Example placeholders; replace with real commands.
# pytest -q
# npm test
# npm run format:check
# python -m build
```

## 11:  Dependencies

Before adding a dependency:

- Check whether the repository already has a suitable dependency.
- Prefer standard-library or existing project utilities when reasonable.
- Confirm the package manager and lockfile in use.
- Document why the dependency is needed.
- Update lockfiles using the repository's normal package manager when possible.
- Consider security, maintenance, licence, size, and transitive impact.

Do not add dependencies only for trivial convenience.

## 12:  Security and privacy

- Never expose, print, commit, or fabricate secrets.
- Treat `.env`, credential files, private keys, tokens, database dumps, saved user data, local model caches, and user-generated content as sensitive unless the repository clearly treats them as test fixtures.
- Do not weaken authentication, authorisation, validation, sandboxing, confirmation prompts, or permission checks unless explicitly requested and justified.
- Avoid introducing command injection, path traversal, unsafe deserialisation, cross-site scripting, SQL injection, insecure random values, or insecure temporary-file handling.
- Validate external inputs at trust boundaries.
- Keep generated logs and errors free of unnecessary sensitive data.
- For tools that mutate filesystems, mailboxes, external services, DAWs, model runtimes, or user data, preserve preview, confirmation, backup, dry-run, and undo safeguards where present.

## 13:  Git and file safety

- Check worktree state before large edits when possible.
- Do not overwrite files that contain user changes unrelated to the task.
- Do not run destructive commands such as `rm -rf`, `git reset --hard`, `git clean -fd`, or force-push unless explicitly instructed.
- Do not create commits, branches, tags, releases, or pull requests unless explicitly asked.
- Keep generated files out of version control unless the project already tracks them or the task requires them.
- Respect `.gitignore` and existing repository conventions.
- Stage explicit paths only when staging is requested and the worktree is mixed.

## 14:  Documentation

Update documentation when behaviour, setup, commands, configuration, architecture, public APIs, or user-facing workflows change.

Documentation should be:

- accurate
- concise
- actionable
- consistent with the repository's terminology
- free of stale claims

Prefer linking to existing canonical docs over duplicating long explanations.

When capabilities, APIs, prompts, or workflows change, search for all affected documentation copies and keep them aligned.

## 15:  Versioning, releases, and packaging

When a task touches versioning, packaging, or release readiness:

- Identify every source of version truth before editing.
- Update package metadata, source constants, installers, changelog/release notes, docs, and `STATUS.md` consistently.
- Run or document relevant build/package checks.
- Do not create tags, releases, or publish packages unless explicitly asked.
- Record release blockers, failed publish steps, manual fallbacks, and external verification gaps in `STATUS.md`.

Project-specific version files should be listed here when known:

- `<version file>`
- `<package metadata>`
- `<release notes/changelog>`

## 16:  Compatibility with multiple agents

This repository may be edited by different coding agents.

Rules:

- Keep instructions plain Markdown and tool-agnostic where possible.
- Do not rely on one agent's private memory or proprietary feature for critical project knowledge.
- Put durable project knowledge in tracked files such as `AGENTS.md`, `STATUS.md`, `README.md`, and docs.
- If nested `AGENTS.md` files exist, apply the most specific relevant instructions for the files being changed.
- When instructions conflict, follow this priority order:
  1. Direct user request for the current task
  2. More specific nested `AGENTS.md`
  3. Root `AGENTS.md`
  4. Other repository documentation
  5. Existing code conventions

## 17:  Optional compatibility files

`AGENTS.md` should remain complete on its own.

If the repository uses tool-specific compatibility entry points such as `CLAUDE.md`, `.github/copilot-instructions.md`, `GEMINI.md`, or Cursor rules, keep them short and point back to this file unless the tool requires otherwise.

Do not allow compatibility files to drift into conflicting policy.

## 18:  Instruction-file maintenance

When maintaining this file:

- Keep it durable and repository-wide.
- Keep rules specific enough to change agent behaviour.
- Remove rules that become obsolete.
- Prefer concise bullets over long prose.
- Do not add volatile project status here; put changing status in `STATUS.md`.
- Keep project-specific details in the project map, validation, safety, and release sections.

## 19:  Final response requirements

When finishing a task, report concisely:

- what changed
- files changed
- verification commands run and results
- whether `STATUS.md` was updated
- remaining issues, blockers, or follow-up work

Do not include decorative commentary.
