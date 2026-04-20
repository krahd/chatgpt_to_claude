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
