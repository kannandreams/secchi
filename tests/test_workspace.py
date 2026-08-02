from secchi.models import (
    DownloadCounts,
    DownloadTrendPoint,
    GitHubStats,
    PackageInfo,
    PackageRef,
    Registry,
)
from secchi.workspace import (
    WorkspaceState,
    combine_install_breakdown,
    combine_package_infos,
    logical_package_refs,
    package_key,
)


def test_logical_package_refs_collapses_registry_duplicates_and_preserves_favorite() -> (
    None
):
    refs = logical_package_refs(
        [
            PackageRef("DuckDB", Registry.PYPI),
            PackageRef("duckdb", Registry.NPM, favorite=True),
            PackageRef("polars", Registry.PYPI),
        ]
    )

    assert [(ref.name, ref.favorite) for ref in refs] == [
        ("DuckDB", True),
        ("polars", False),
    ]


def test_combine_package_infos_uses_primary_source_and_merges_signals() -> None:
    pypi = PackageInfo(
        name="duckdb",
        registry=Registry.PYPI,
        latest_version="1.0.0",
        total_downloads=100,
        download_counts=DownloadCounts(today=1, week=7, month=30),
        download_trend=[DownloadTrendPoint("2026-01-01", 10)],
    )
    npm = PackageInfo(
        name="duckdb",
        registry=Registry.NPM,
        latest_version="2.0.0",
        total_downloads=50,
        download_counts=DownloadCounts(today=2, week=8, month=20),
        download_trend=[
            DownloadTrendPoint("2026-01-01", 5),
            DownloadTrendPoint("2026-01-02", 6),
        ],
    )
    npm.github_stats = GitHubStats(stars=42, resolved=True)

    combined = combine_package_infos(PackageRef("duckdb", Registry.PYPI), [pypi, npm])

    assert combined.latest_version == "1.0.0"
    assert combined.source_registries == [Registry.PYPI, Registry.NPM]
    assert combined.total_downloads == 150
    assert combined.download_counts.month == 50
    assert [(point.date, point.count) for point in combined.download_trend] == [
        ("2026-01-01", 15),
        ("2026-01-02", 6),
    ]
    assert combined.github_stats.stars == 42


def test_combine_install_breakdown_is_ranked_by_download_share() -> None:
    pypi = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        download_counts=DownloadCounts(month=75),
    )
    npm = PackageInfo(
        name="demo",
        registry=Registry.NPM,
        download_counts=DownloadCounts(month=25),
    )

    breakdown = combine_install_breakdown([pypi, npm])

    assert [method.label for method in breakdown.methods] == ["PyPI", "npm"]
    assert [method.percent for method in breakdown.methods] == [75.0, 25.0]
    assert breakdown.caption == "Combined from registry 30-day download totals."


def test_workspace_state_supports_lazy_loading_and_force_refresh() -> None:
    state = WorkspaceState()
    ref = PackageRef("demo", Registry.PYPI, project_name="demo")

    state.select(ref)
    assert state.selected_ref == ref
    assert state.begin_load("demo") is True
    assert state.begin_load("demo") is False
    assert state.should_load("demo") is False

    state.finish_load("demo")
    assert state.loading_projects == set()
    assert state.should_load("demo") is False
    assert state.begin_load("demo", force=True) is True

    state.cancel_load("demo")
    assert state.loading_projects == set()


def test_workspace_package_keys_include_project_scope() -> None:
    first = PackageRef("shared", Registry.PYPI, project_name="first")
    second = PackageRef("shared", Registry.PYPI, project_name="second")

    assert package_key(first) != package_key(second)
