from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("chatgpt-to-claude-toolkit")
except PackageNotFoundError:
    __version__ = "0.0.3"  # fallback for non-installed / editable dev installs
