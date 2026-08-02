"""Pure workspace state and aggregation helpers shared by UI and workflows."""

from secchi.workspace.aggregate import (
    combine_download_trends,
    combine_install_breakdown,
    combine_package_infos,
    logical_package_refs,
)
from secchi.aggregate import package_key
from secchi.workspace.state import WorkspaceState

__all__ = [
    "WorkspaceState",
    "combine_download_trends",
    "combine_install_breakdown",
    "combine_package_infos",
    "logical_package_refs",
    "package_key",
]
