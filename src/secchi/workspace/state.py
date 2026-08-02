"""Pure state transitions for workspace navigation and lazy loading."""

from __future__ import annotations

from dataclasses import dataclass, field

from secchi.models import PackageRef


@dataclass
class WorkspaceState:
    """Track selection and per-project loading without depending on Textual."""

    selected_ref: PackageRef | None = None
    loaded_projects: set[str] = field(default_factory=set)
    loading_projects: set[str] = field(default_factory=set)

    def select(self, ref: PackageRef) -> None:
        self.selected_ref = ref

    def should_load(self, project_name: str, *, force: bool = False) -> bool:
        """Return whether a project fetch may start now."""
        if project_name in self.loading_projects:
            return False
        return force or project_name not in self.loaded_projects

    def begin_load(self, project_name: str, *, force: bool = False) -> bool:
        """Mark a project as loading, returning false when it should be skipped."""
        if not self.should_load(project_name, force=force):
            return False
        self.loading_projects.add(project_name)
        return True

    def finish_load(self, project_name: str) -> None:
        """Mark a project as loaded after a successful or partial fetch."""
        self.loading_projects.discard(project_name)
        self.loaded_projects.add(project_name)

    def cancel_load(self, project_name: str) -> None:
        """Clear an in-flight marker when a fetch is cancelled or fails to start."""
        self.loading_projects.discard(project_name)
