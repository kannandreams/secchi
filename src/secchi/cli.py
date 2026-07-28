"""CLI entry point — argparse + init command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tomli_w import dumps as toml_dumps

from secchi import __version__
from secchi.config import find_config, list_projects, load_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secchi",
        description="TUI dashboard to monitor your packages across registries.",
    )
    parser.add_argument("--version", action="version", version=f"secchi {__version__}")
    parser.add_argument(
        "--project",
        "-p",
        type=str,
        default=None,
        help="Project name to load from config (e.g., 'myproject')",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help=(
            "Path to config file (default: ./secchi.toml, ./pkgwatch.toml, "
            "or ~/.config/secchi/config.toml)"
        ),
    )
    parser.add_argument(
        "--refresh",
        "-r",
        action="store_true",
        help="Force refresh all package data on startup",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available projects in config and exit",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Interactively create a secchi.toml config file")
    monitor_parser = sub.add_parser("monitor", help="Monitor a project (alias for --project)")
    monitor_parser.add_argument("project_name", type=str, help="Project name to monitor")

    return parser


def cmd_init() -> None:
    """Interactively scaffold a secchi.toml file."""
    output_path = Path.cwd() / "secchi.toml"

    print("🚀  secchi init — create a new config file")
    print()

    if output_path.exists():
        answer = input(f"'{output_path}' already exists. Overwrite? [y/N]: ")
        if answer.lower() not in ("y", "yes"):
            print("Aborted.")
            return

    projects: dict[str, dict] = {}

    while True:
        print()
        name = input("Project name (e.g., 'my-libs'): ").strip()
        if not name:
            print("Project name is required.")
            continue

        desc = input("  Description (optional): ").strip()
        packages: list[dict] = []

        print("  Add packages. Enter name and registry. Leave name empty to finish.")
        while True:
            pkg_name = input("    Package name: ").strip()
            if not pkg_name:
                break

            registry_raw = input("    Registry [pypi/crates.io/npm, default: pypi]: ").strip()
            registry = registry_raw if registry_raw in ("pypi", "crates.io", "npm") else "pypi"

            fav_raw = input("    Favorite? [y/N]: ").strip().lower()
            entry: dict = {"name": pkg_name, "registry": registry}
            if fav_raw in ("y", "yes"):
                entry["favorite"] = True

            packages.append(entry)
            star = " ★" if entry.get("favorite") else ""
            print(f"    [+] Added {pkg_name} ({registry}){star}")

        if not packages:
            print("  No packages added, skipping project.")
            continue

        projects[name] = {"description": desc, "packages": packages}
        print(f"  [+] Project '{name}' saved with {len(packages)} package(s).")

        more = input("\nAdd another project? [y/N]: ")
        if more.lower() not in ("y", "yes"):
            break

    if not projects:
        print("No projects created. Aborting.")
        return

    config = {"projects": projects}
    output_path.write_text(toml_dumps(config))
    print(f"\n✅  Config written to {output_path}")
    first = next(iter(projects))
    print(f"   Run: secchi monitor {first}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
        return

    if args.command == "monitor":
        args.project = args.project_name

    config_path = find_config(args.config)

    if args.list:
        if not config_path:
            print("No config file found. Run 'secchi init' to create one.")
            print("Searched: ./secchi.toml, ./pkgwatch.toml, ~/.config/secchi/config.toml")
            sys.exit(1)

        projects = list_projects(config_path)
        if not projects:
            print(f"No projects found in {config_path}")
            sys.exit(0)

        print(f"Projects in {config_path}:")
        for p in projects:
            print(f"  - {p}")
        return

    # Launch TUI
    if not config_path:
        print("No config file found.")
        print("Run 'secchi init' to create one, or use --config to specify a path.")
        print("Searched: ./secchi.toml, ./pkgwatch.toml, ~/.config/secchi/config.toml")
        sys.exit(1)

    if not args.project:
        projects = list_projects(config_path)
        if len(projects) == 1:
            args.project = projects[0]
        elif projects:
            print(f"Projects in {config_path}:")
            for project_name in projects:
                print(f"  - {project_name}")
            parser.error("--project/-p is required when config has multiple projects")
        else:
            print(f"No projects found in {config_path}")
            sys.exit(1)

    try:
        project = load_project(config_path, args.project)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    from secchi.ui.app import Secchi

    app = Secchi(project=project, config_path=config_path, force_refresh=args.refresh)
    app.run()

if __name__ == "__main__":
    main()
