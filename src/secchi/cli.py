"""Terminal entry point: parse arguments, invoke workflows, render output."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from tomli_w import dumps as toml_dumps

from secchi import __version__
from secchi.config import find_config, list_projects
from secchi.diagnostics import DiagnosticLog, DiagnosticStatus
from secchi.errors import SecchiError
from secchi.models import Registry
from secchi.renderers.summary import render_summary
from secchi.services.comparison import render_comparison
from secchi.services.intelligence import PackageIntelligenceService
from secchi.update import check_for_update
from secchi.workflows import check, compare, dashboard, report, search, show


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secchi",
        description="Open source package intelligence from your terminal.",
    )
    parser.add_argument("--version", action="version", version=f"secchi {__version__}")
    parser.add_argument("--project", "-p", help="Project name from configuration")
    parser.add_argument("--config", "-c", help="Path to secchi.toml or .secchi.toml")
    parser.add_argument(
        "--no-cache",
        dest="refresh",
        action="store_true",
        help=(
            "Bypass the local cache and re-fetch package, registry, GitHub, "
            "and security-advisory signals"
        ),
    )
    parser.add_argument(
        "--security-no-cache",
        dest="security_refresh",
        action="store_true",
        help="Bypass only the advisory cache and re-fetch OSV security data",
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List configured projects and exit"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show every SUCCESS, WARN, and FAILURE diagnostic event",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write readable diagnostics for this run to a file",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Interactively create secchi.toml")

    dashboard_parser = sub.add_parser(
        "dashboard", help="Launch the interactive dashboard"
    )
    dashboard_parser.add_argument(
        "package", nargs="?", help="Package name or registry:name"
    )
    dashboard_parser.add_argument(
        "--registry", choices=[item.value for item in Registry]
    )
    dashboard_parser.add_argument("--project", "-p", dest="dashboard_project")
    dashboard_parser.add_argument("--config", "-c", dest="dashboard_config")
    dashboard_parser.add_argument(
        "--no-cache",
        dest="dashboard_refresh",
        action="store_true",
        help="Re-fetch package data and security advisories instead of using cache",
    )
    dashboard_parser.add_argument(
        "--security-no-cache",
        dest="dashboard_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    web_parser = sub.add_parser(
        "web", help="Serve the interactive dashboard in a local browser"
    )
    web_parser.add_argument("package", nargs="?", help="Package name or registry:name")
    web_parser.add_argument("--registry", choices=[item.value for item in Registry])
    web_parser.add_argument("--project", "-p", dest="web_project")
    web_parser.add_argument("--config", "-c", dest="web_config")
    web_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Local browser server port (default: 8000)",
    )
    web_parser.add_argument(
        "--no-cache",
        dest="web_refresh",
        action="store_true",
        help="Re-fetch package data and security advisories instead of using cache",
    )
    web_parser.add_argument(
        "--security-no-cache",
        dest="web_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    show_parser = sub.add_parser(
        "show", help="Print a concise package intelligence summary"
    )
    show_parser.add_argument("package", help="Package name or registry:name")
    show_parser.add_argument("--registry", choices=[item.value for item in Registry])
    show_parser.add_argument(
        "--no-cache",
        dest="refresh",
        action="store_true",
        help="Re-fetch package data and security advisories instead of using cache",
    )
    show_parser.add_argument(
        "--security-no-cache",
        dest="show_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    search_parser = sub.add_parser(
        "search", help="Find packages across supported registries"
    )
    search_parser.add_argument("package", help="Exact package name")
    search_parser.add_argument("--registry", choices=[item.value for item in Registry])
    search_parser.add_argument("--no-cache", dest="refresh", action="store_true")

    report_parser = sub.add_parser(
        "report", help="Generate a package or project report"
    )
    report_parser.add_argument(
        "package", nargs="?", help="Package name or registry:name"
    )
    report_parser.add_argument(
        "--project", dest="report_project", help="Configured project name"
    )
    report_parser.add_argument(
        "--config", dest="report_config", help="Workspace config path"
    )
    report_parser.add_argument("--registry", choices=[item.value for item in Registry])
    report_parser.add_argument(
        "--format", choices=["json", "html", "md", "markdown"], default="json"
    )
    report_parser.add_argument(
        "--output", "-o", help="Target file path, or '-' for stdout"
    )
    report_parser.add_argument(
        "--no-cache",
        dest="refresh",
        action="store_true",
        help="Re-fetch package data and security advisories instead of using cache",
    )
    report_parser.add_argument(
        "--security-no-cache",
        dest="report_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    check_parser = sub.add_parser(
        "check", help="Evaluate simple package health policies"
    )
    check_parser.add_argument("package", help="Package name or registry:name")
    check_parser.add_argument("--registry", choices=[item.value for item in Registry])
    check_parser.add_argument("--min-health", type=int, default=70)
    check_parser.add_argument("--require-ci", action="store_true")
    check_parser.add_argument("--no-cache", dest="refresh", action="store_true")
    check_parser.add_argument(
        "--security-no-cache",
        dest="check_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    compare_parser = sub.add_parser(
        "compare", help="Compare package choices with agent-readable evidence"
    )
    compare_parser.add_argument(
        "packages",
        nargs="+",
        help="Two or more package names or registry:name references",
    )
    compare_parser.add_argument("--registry", choices=[item.value for item in Registry])
    compare_parser.add_argument("--format", choices=["text", "json"], default="text")
    compare_parser.add_argument("--no-cache", dest="refresh", action="store_true")
    compare_parser.add_argument(
        "--security-no-cache",
        dest="compare_security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )

    monitor_parser = sub.add_parser("monitor", help="Alias for dashboard --project")
    monitor_parser.add_argument("project_name", help="Project name to monitor")
    monitor_parser.add_argument("--no-cache", dest="refresh", action="store_true")
    monitor_parser.add_argument(
        "--security-no-cache",
        dest="security_refresh",
        action="store_true",
        help="Re-fetch only OSV security advisories instead of using their cache",
    )
    for command_parser in (
        dashboard_parser,
        web_parser,
        show_parser,
        search_parser,
        report_parser,
        check_parser,
        compare_parser,
        monitor_parser,
    ):
        command_parser.add_argument(
            "--verbose",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Show every SUCCESS, WARN, and FAILURE diagnostic event",
        )
        command_parser.add_argument(
            "--log-file",
            type=Path,
            default=argparse.SUPPRESS,
            help="Write readable diagnostics for this run to a file",
        )
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
                "    Registry [pypi/crates.io/npm/homebrew/go/cran/pub, default: pypi]: "
            ).strip()
            packages.append({"name": package_name, "registry": registry or "pypi"})
        if packages:
            projects[name] = {
                "description": description,
                "favorite": favorite,
                "packages": packages,
            }
        if input("Add another project? [y/N]: ").strip().lower() not in ("y", "yes"):
            break
    if not projects:
        print("No projects created. Aborting.")
        return
    output_path.write_text(toml_dumps({"projects": projects}))
    print(f"\n✅  Config written to {output_path}")


def _print_diagnostics(diagnostics: DiagnosticLog, *, verbose: bool) -> None:
    events = diagnostics.snapshot()
    visible = (
        events
        if verbose
        else [
            event
            for event in events
            if event.status in (DiagnosticStatus.WARN, DiagnosticStatus.FAILURE)
        ]
    )
    if not visible:
        return
    print("\nDiagnostics:")
    for event in visible:
        print(f"  {event.format()}")


def _run_dashboard(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    service: PackageIntelligenceService,
    diagnostics: DiagnosticLog,
) -> None:
    try:
        request = asyncio.run(
            dashboard.run(
                package=getattr(args, "package", None),
                registry=getattr(args, "registry", None),
                project_name=getattr(args, "dashboard_project", None) or args.project,
                config=getattr(args, "dashboard_config", None) or args.config,
                refresh=getattr(args, "dashboard_refresh", False) or args.refresh,
                security_refresh=(
                    getattr(args, "dashboard_security_refresh", False)
                    or args.security_refresh
                    or args.refresh
                ),
                diagnostics=diagnostics,
            )
        )
    except (SecchiError, ValueError) as exc:
        parser.error(str(exc))
    from secchi.ui.app import Secchi

    Secchi(
        project=request.project,
        config_path=request.config_path,
        force_refresh=request.refresh,
        workspace=request.workspace,
        force_security_refresh=request.security_refresh,
        intelligence=service,
        diagnostics=diagnostics,
    ).run()


def _run_web(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    diagnostics: DiagnosticLog,
) -> None:
    refresh = getattr(args, "web_refresh", False) or args.refresh
    security_refresh = (
        getattr(args, "web_security_refresh", False) or args.security_refresh or refresh
    )
    project_name = getattr(args, "web_project", None) or args.project
    config = getattr(args, "web_config", None) or args.config
    try:
        request = asyncio.run(
            dashboard.run(
                package=getattr(args, "package", None),
                registry=getattr(args, "registry", None),
                project_name=project_name,
                config=config,
                refresh=refresh,
                security_refresh=security_refresh,
                diagnostics=diagnostics,
            )
        )
    except (SecchiError, ValueError) as exc:
        parser.error(str(exc))

    from secchi.web import TextualServeUnavailable, prepare_launch, run_textual_serve

    launch = prepare_launch(
        request,
        package=getattr(args, "package", None),
        registry=getattr(args, "registry", None),
        project_name=project_name,
        refresh=refresh,
        security_refresh=security_refresh,
        verbose=getattr(args, "verbose", False),
        log_file=getattr(args, "log_file", None),
    )
    print(
        "Serving Secchi through Textual's local web server. Open the URL shown "
        "by the server to access this dashboard session."
    )
    try:
        run_textual_serve(launch.command, port=args.port)
    except TextualServeUnavailable as exc:
        parser.error(str(exc))
    except subprocess.CalledProcessError as exc:
        parser.error(f"textual serve exited with status {exc.returncode}.")


def _run_search(
    args: argparse.Namespace, diagnostics: DiagnosticLog, *, verbose: bool
) -> None:
    results = asyncio.run(
        search.run(
            args.package,
            registry=args.registry,
            limit=10,
            diagnostics=diagnostics,
        )
    )
    if not results:
        print(
            f"No packages matching '{args.package}' found in the selected registries."
        )
        _print_diagnostics(diagnostics, verbose=verbose)
        return
    print(f"Matches for {args.package}:\n")
    for result in results:
        description = (result.description or "No description").splitlines()[0]
        marker = "exact" if result.exact else "match"
        print(
            f"{result.registry.display_name:<10} {result.name:<24} {result.version or '—':<12} {marker:<6} {description}"
        )
    _print_diagnostics(diagnostics, verbose=verbose)


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
        args.package = None
        args.dashboard_project = args.project_name
        args.dashboard_config = None
        args.dashboard_refresh = args.refresh
        args.command = "dashboard"
    diagnostics = DiagnosticLog(path=args.log_file)
    service = PackageIntelligenceService(diagnostics=diagnostics)
    if args.list:
        config_path = find_config(args.config)
        if not config_path:
            parser.error("No config file found.")
        for name in list_projects(config_path):
            print(name)
        return
    notice = check_for_update()
    if notice:
        print(f"Notice: {notice.message}", file=sys.stderr)
    if args.command == "dashboard" or args.command is None:
        _run_dashboard(args, parser, service, diagnostics)
        return
    if args.command == "web":
        _run_web(args, parser, diagnostics)
        return
    if args.command == "show":
        try:
            result = asyncio.run(
                show.run(
                    args.package,
                    registry=args.registry,
                    refresh=args.refresh,
                    security_refresh=(
                        getattr(args, "show_security_refresh", False)
                        or args.security_refresh
                        or args.refresh
                    ),
                    service=service,
                )
            )
        except (SecchiError, ValueError) as exc:
            parser.error(str(exc))
        print(render_summary(result.info, result.derived))
        for warning in result.warnings:
            print(f"Warning [{warning.source}]: {warning.message}")
        _print_diagnostics(diagnostics, verbose=args.verbose)
        return
    if args.command == "search":
        _run_search(args, diagnostics, verbose=args.verbose)
        return
    if args.command == "report":
        try:
            output = asyncio.run(
                report.run(
                    package=args.package,
                    project_name=args.report_project,
                    config=args.report_config or args.config,
                    registry=args.registry,
                    format_name=args.format,
                    output=args.output,
                    refresh=args.refresh,
                    security_refresh=(
                        getattr(args, "report_security_refresh", False)
                        or args.security_refresh
                        or args.refresh
                    ),
                    service=service,
                )
            )
        except (SecchiError, ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))
        if args.output == "-":
            print(output.content)
        else:
            output.target.parent.mkdir(parents=True, exist_ok=True)
            output.target.write_text(output.content)
            print(f"Wrote {output.format_name} report to {output.target}")
        _print_diagnostics(diagnostics, verbose=args.verbose)
        return
    if args.command == "check":
        try:
            result = asyncio.run(
                check.run(
                    args.package,
                    registry=args.registry,
                    min_health=args.min_health,
                    require_ci=args.require_ci,
                    refresh=args.refresh,
                    security_refresh=(
                        getattr(args, "check_security_refresh", False)
                        or args.security_refresh
                        or args.refresh
                    ),
                    service=service,
                )
            )
        except (SecchiError, ValueError) as exc:
            parser.error(str(exc))
        for item in result.checks:
            print(f"{'PASS' if item.passed else 'FAIL'}  {item.name}: {item.detail}")
        for warning in result.warnings:
            print(f"Warning [{warning.source}]: {warning.message}")
        _print_diagnostics(diagnostics, verbose=args.verbose)
        if not result.passed:
            raise SystemExit(1)
        return
    if args.command == "compare":
        try:
            comparison = asyncio.run(
                compare.run(
                    args.packages,
                    registry=args.registry,
                    refresh=args.refresh,
                    security_refresh=(
                        getattr(args, "compare_security_refresh", False)
                        or args.security_refresh
                        or args.refresh
                    ),
                    service=service,
                )
            )
        except (SecchiError, ValueError) as exc:
            parser.error(str(exc))
        if args.format == "json":
            import json

            print(json.dumps(comparison.as_dict(), indent=2))
        else:
            print(render_comparison(comparison))
        _print_diagnostics(diagnostics, verbose=args.verbose)
        return
    parser.error("Unknown command")


if __name__ == "__main__":
    main()
