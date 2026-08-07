from secchi.cli import build_parser


def test_security_no_cache_is_available_on_package_commands() -> None:
    parser = build_parser()

    show_args = parser.parse_args(["show", "demo", "--security-no-cache"])
    assert show_args.show_security_refresh is True

    report_args = parser.parse_args(["report", "demo", "--security-no-cache"])
    assert report_args.report_security_refresh is True

    dashboard_args = parser.parse_args(["dashboard", "demo", "--security-no-cache"])
    assert dashboard_args.dashboard_security_refresh is True


def test_no_cache_remains_full_refresh_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["show", "demo", "--no-cache"])
    assert args.refresh is True
