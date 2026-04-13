"""Tests for canonical and legacy group ID planning."""

from memory.group_ids import build_group_id_plan


def test_build_group_id_plan_for_owner_repo_project():
    plan = build_group_id_plan(
        project_id="Axonify/Thunderball",
        github_repo="Axonify/Thunderball",
    )

    assert plan.project_group_id == "axonify/thunderball"
    assert plan.github_group_id == "axonify/thunderball"
    assert plan.unified is True
    assert plan.legacy_project_ids == ("axonify-thunderball",)
    assert plan.legacy_github_ids == ("Axonify/Thunderball",)


def test_build_group_id_plan_respects_intentional_split_ids():
    plan = build_group_id_plan(
        project_id="custom-project",
        github_repo="Owner/Repo",
    )

    assert plan.project_group_id == "custom-project"
    assert plan.github_group_id == "owner/repo"
    assert plan.unified is False
    assert plan.legacy_project_ids == ()
    assert plan.legacy_github_ids == ("Owner/Repo",)


def test_build_group_id_plan_treats_flattened_repo_as_legacy_alias():
    plan = build_group_id_plan(
        project_id="axonify-thunderball",
        github_repo="Axonify/Thunderball",
    )

    assert plan.project_group_id == "axonify/thunderball"
    assert plan.github_group_id == "axonify/thunderball"
    assert plan.unified is True
    assert plan.legacy_project_ids == ("axonify-thunderball",)
    assert plan.legacy_github_ids == ("Axonify/Thunderball",)
