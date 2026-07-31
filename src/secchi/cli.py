"""Command line entry point for package intelligence workflows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from tomli_w import dumps as toml_dumps

from secchi import __version__
from secchi.config import find_config, list_projects, load_project, load_projects
from secchi.models import PackageRef, Project, Registry
from secchi.policy import evaluate_default_policy
from secchi.renderers.reports import (
    build_project_report,
    default_report_path,
    render_project_report,
    render_report,
)
from secchi.renderers.summary import render_summary
from secchi.services.intelligence import PackageIntelligenceService
from secchi.services.resolver import parse_package_spec, resolve_package
from secchi.services.search import PackageSearchService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secchi", description="Open source package intelligence from your terminal."
    )
    parser.add_argument("--version", action="version", version=f"secchi {__version__}")
    parser.add_argument("--project", "-p", help="Project name from configuration")
    parser.add_argument("--config", "-c", help="Path to secchi.toml or .secchi.toml")
    parser.add_argument("--refresh", "-r", action="store_true", help="Bypass local cache")
    parser.add_argument("--list", "-l", action="store_true", help="List configured projects and exit")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Interactively create secchi.toml")

    dashboard = sub.add_parser("dashboard", help="Launch the interactive dashboard")
    dashboard.add_argument("package", nargs="?", help="Package name or registry:name")
    dashboard.add_argument("--registry", choices=[item.value for item in Registry])
    dashboard.add_argument("--project", "-p", dest="dashboard_project")
    dashboard.add_argument("--config", "-c", dest="dashboard_config")
    dashboard.add_argument("--refresh", "-r", dest="dashboard_refresh", action="store_true")

    show = sub.add_parser("show", help="Print a concise package intelligence summary")
    show.add_argument("package", help="Package name or registry:name")
    show.add_argument("--registry", choices=[item.value for item in Registry])
    show.add_argument("--refresh", "-r", action="store_true")

    search = sub.add_parser("search", help="Find packages across supported registries")
    search.add_argument("package", help="Exact package name")
    search.add_argument("--registry", choices=[item.value for item in Registry])
    search.add_argument("--refresh", "-r", action="store_true")

    report = sub.add_parser("report", help="Generate a package or project report")
    report.add_argument("package", nargs="?", help="Package name or registry:name")
    report.add_argument("--project", dest="report_project", help="Configured project name")
    report.add_argument("--config", dest="report_config", help="Workspace config path")
    report.add_argument("--registry", choices=[item.value for item in Registry])
    report.add_argument("--format", choices=["json", "html", "md", "markdown"], default="json")
    report.add_argument(
        "--output", "-o", type=str,
        help="Target file path; defaults to a dated file in the current directory, or '-' for stdout",
    )
    report.add_argument("--refresh", "-r", action="store_true")

    check = sub.add_parser("check", help="Evaluate simple package health policies")
    check.add_argument("package", help="Package name or registry:name")
    check.add_argument("--registry", choices=[item.value for item in Registry])
    check.add_argument("--min-health", type=int, default=70)
    check.add_argument("--require-ci", action="store_true")
    check.add_argument("--refresh", "-r", action="store_true")

    monitor = sub.add_parser("monitor", help="Alias for dashboard --project")
    monitor.add_argument("project_name", help="Project name to monitor")

    sub.add_parser("mcp", help="Run the Model Context Protocol server over stdio")
    return parser


def cmd_init() -> None:
    output_path = Path.cwd() / "secchi.toml"
    print("🚀  secchi init — create a new config file\n")
    if output_path.exists():
        answer = input(f"'{output_path}' already exists. Overwrite? [y/N]: ")
        if answer.lower() not in ("y", "yes"):
            print("Aborted.")
            return
    projects: dict[str, dict] = {}
    while True:
        name = input("Project name (e.g., 'my-libs'): ").strip()
        if not name:
            print("Project name is required.")
            continue
        description = input("  Description (optional): ").strip()
        favorite = input("  Favourite project? [y/N]: ").strip().lower() in ("y", "yes")
        packages: list[dict[str, str]] = []
        print("  Add packages. Leave name empty to finish.")
        while True:
            package_name = input("    Package name: ").strip()
            if not package_name:
                break
            registry = input(
                "    Registry [pypi/crates.io/npm/homebrew/go/cran, default: pypi]: "
            ).strip()
            packages.append({"name": package_name, "registry": registry or "pypi"})
        if packages:
            projects[name] = {"description": description, "favorite": favorite, "packages": packages}
        if input("Add another project? [y/N]: ").strip().lower() not in ("y", "yes"):
            break
    if not projects:
        print("No projects created. Aborting.")
        return
    output_path.write_text(toml_dumps({"projects": projects}))
    print(f"\n✅  Config written to {output_path}")


def _fetch_one(ref: PackageRef, refresh: bool):
    return asyncio.run(PackageIntelligenceService().fetch_package(ref, force_refresh=refresh))


def _require_result(ref: PackageRef, refresh: bool):
    result = _fetch_one(ref, refresh)
    if result.error or result.info is None or result.derived is None:
        message = result.error.message if result.error else "No package data returned."
        raise RuntimeError(f"Could not load {ref.name} from {ref.registry.value}: {message}")
    return result


def _workspace_project(config_path: Path) -> Project:
    projects = load_projects(config_path)
    refs: list[PackageRef] = []
    for project in projects:
        for ref in project.packages:
            refs.append(
                PackageRef(
                    ref.name,
                    ref.registry,
                    ref.favorite or project.favorite,
                    project.name,
                )
            )
    return Project(name="Workspace", description="Configured Secchi workspace", packages=refs)


def _dashboard(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    config_arg = getattr(args, "dashboard_config", None) or args.config
    refresh = getattr(args, "dashboard_refresh", False) or args.refresh
    project_name = getattr(args, "dashboard_project", None) or args.project
    package = getattr(args, "package", None)
    if package:
        try:
            ref = parse_package_spec(package, args.registry)
        except ValueError as exc:
            parser.error(str(exc))
        config_path = find_config(config_arg)
        configured = None
        if config_path and args.registry is None:
            for candidate in load_projects(config_path):
                if candidate.name.lower() == package.lower() or any(
                    item.name.lower() == package.lower() for item in candidate.packages
                ):
                    configured = candidate
                    break
        if configured is not None:
            project = configured
        elif args.registry is None:
            refs = asyncio.run(resolve_package(package))
            if not refs:
                parser.error(f"No exact package named '{package}' was found across registries.")
            project = Project(name=ref.name, packages=refs)
        else:
            project = Project(name=ref.name, packages=[ref])
        config_path = config_path or (Path.cwd() / "secchi.toml")
    else:
        config_path = find_config(config_arg)
        if not config_path:
            parser.error("No config found. Use 'secchi dashboard PACKAGE' or create secchi.toml.")
        try:
            workspace = None
            if project_name:
                project = load_project(config_path, project_name)
            else:
                workspace = load_projects(config_path)
                project = _workspace_project(config_path)
        except ValueError as exc:
            parser.error(str(exc))
    if not project.packages:
        parser.error("The selected workspace has no packages.")
    from secchi.ui.app import Secchi
    Secchi(
        project=project,
        config_path=config_path,
        force_refresh=refresh,
        workspace=workspace if not package else None,
    ).run()


def _search(args: argparse.Namespace) -> None:
    registries = [Registry(args.registry)] if args.registry else list(Registry)
    results = asyncio.run(
        PackageSearchService().search(args.package, registries=registries, limit=10)
    )
    if not results:
        print(f"No packages matching '{args.package}' found in the selected registries.")
        return
    print(f"Matches for {args.package}:\n")
    for result in results:
        description = (result.description or "No description").splitlines()[0]
        marker = "exact" if result.exact else "match"
        print(f"{result.registry.display_name:<10} {result.name:<24} {result.version or '—':<12} {marker:<6} {description}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        cmd_init()
        return
    if args.command == "mcp":
        from secchi.mcp_server import main as mcp_main

        mcp_main()
        return
    if args.command == "monitor":
        args.command = "dashboard"
        args.package = None
        args.dashboard_project = args.project_name
        args.dashboard_config = None
        args.dashboard_refresh = args.refresh
        _dashboard(args, parser)
        return
    if args.command == "dashboard":
        _dashboard(args, parser)
        return
    if args.command == "show":
        try:
            result = _require_result(parse_package_spec(args.package, args.registry), args.refresh)
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(render_summary(result.info, result.derived))
        return
    if args.command == "search":
        _search(args)
        return
    if args.command == "report":
        format_name = "md" if args.format == "markdown" else args.format
        if args.report_project:
            try:
                config_path = find_config(args.report_config or args.config)
                if not config_path:
                    raise RuntimeError("No config found for project report.")
                project = load_project(config_path, args.report_project)
                intelligence = asyncio.run(
                    PackageIntelligenceService().fetch_project(
                        project.packages, force_refresh=args.refresh
                    )
                )
                project_report = build_project_report(project, intelligence.results)
            except (RuntimeError, ValueError, FileNotFoundError) as exc:
                parser.error(str(exc))
            content = render_project_report(format_name, project_report)
            subject = project.title or project.name
            target = (
                Path(args.output)
                if args.output and args.output != "-"
                else default_report_path(subject, format_name, project=True)
            )
        else:
            if not args.package:
                parser.error("Provide a package name or --project PROJECT for a report.")
            try:
                ref = parse_package_spec(args.package, args.registry)
                result = _require_result(ref, args.refresh)
            except (RuntimeError, ValueError) as exc:
                parser.error(str(exc))
            content = render_report(format_name, result.info, result.derived, ref, ref.name)
            target = (
                Path(args.output)
                if args.output and args.output != "-"
                else default_report_path(ref.name, format_name)
            )
        if args.output == "-":
            print(content)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            print(f"Wrote {format_name} report to {target}")
        return
    if args.command == "check":
        try:
            result = _require_result(parse_package_spec(args.package, args.registry), args.refresh)
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        checks = evaluate_default_policy(
            result.info,
            result.derived,
            min_health=args.min_health,
            require_ci=args.require_ci,
        )
        for check in checks:
            print(f"{'PASS' if check.passed else 'FAIL'}  {check.name}: {check.detail}")
        if not all(check.passed for check in checks):
            raise SystemExit(1)
        return

    # Backwards-compatible default: config-driven dashboard.
    if args.list:
        config_path = find_config(args.config)
        if not config_path:
            parser.error("No config file found.")
        for name in list_projects(config_path):
            print(name)
        return
    _dashboard(args, parser)


if __name__ == "__main__":
    main()
