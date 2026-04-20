# Contributing

## Local setup

```bash
pip install -e .[dev]
```

## Checks

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
ruff check src tests
mypy src
```
## Release checklist

1. update versions in:
   - `pyproject.toml`
   - `src/chatgpt_to_claude_toolkit/__init__.py`
2. update `CHANGELOG.md`
3. run checks:

```bash
python -m unittest discover -s tests -v
python -m py_compile src/chatgpt_to_claude_toolkit/*.py
```

4. create and push tag (example for `v0.0.1`):

```bash
VERSION=v0.0.1
git tag -a "$VERSION" -m "Release $VERSION"
git push origin main --follow-tags
```

5. publish release:

```bash
gh release create "$VERSION" --title "$VERSION" --notes-file CHANGELOG.md
```
