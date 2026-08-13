from secchi.cli import build_parser


def test_web_command_arguments_parse() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "web",
            "duckdb",
            "--registry",
            "pypi",
            "--project",
            "demo",
            "--config",
            "secchi.toml",
            "--slug",
            "secchi-demo",
            "--security-no-cache",
        ]
    )

    assert args.command == "web"
    assert args.package == "duckdb"
    assert args.registry == "pypi"
    assert args.web_project == "demo"
    assert args.web_config == "secchi.toml"
    assert args.slug == "secchi-demo"
    assert args.web_security_refresh is True


def test_security_no_cache_is_available_on_package_commands() -> None:
    parser = build_parser()

    show_args = parser.parse_args(["show", "demo", "--security-no-cache"])
    assert show_args.show_security_refresh is True

    report_args = parser.parse_args(["report", "demo", "--security-no-cache"])
    assert report_args.report_security_refresh is True

    dashboard_args = parser.parse_args(["dashboard", "demo", "--security-no-cache"])
    assert dashboard_args.dashboard_security_refresh is True

    web_args = parser.parse_args(["web", "demo", "--security-no-cache"])
    assert web_args.web_security_refresh is True


def test_no_cache_remains_full_refresh_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["show", "demo", "--no-cache"])
    assert args.refresh is True
