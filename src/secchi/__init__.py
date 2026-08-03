"""Secchi — TUI dashboard for monitoring packages across registries."""

from importlib.metadata import PackageNotFoundError, version

try:
    # hatch-vcs derives this value from the current Git tag when Secchi is
    # installed or built, keeping the CLI, TUI, and MCP version synchronized.
    __version__ = version("secchi")
except PackageNotFoundError:
    # This fallback supports direct source-tree imports before installation.
    __version__ = "0+unknown"
