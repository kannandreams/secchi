from secchi.spotlight import FALLBACK_SPOTLIGHT, Spotlight


def test_spotlight_keeps_early_projects_visible() -> None:
    assert FALLBACK_SPOTLIGHT.stars == 1
    assert FALLBACK_SPOTLIGHT.project_stage == "Early project"


def test_spotlight_stage_thresholds() -> None:
    assert Spotlight("a", "b", "c", stars=49).project_stage == "Early project"
    assert Spotlight("a", "b", "c", stars=50).project_stage == "Growing project"
    assert Spotlight("a", "b", "c", stars=500).project_stage == "Established project"
    assert Spotlight("a", "b", "c").project_stage == "Spotlight project"
