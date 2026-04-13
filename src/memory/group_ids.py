"""Helpers for canonical and legacy group ID handling."""

from __future__ import annotations

from dataclasses import dataclass

from memory.connectors.github.paths import normalize_github_repo_slug
from memory.project import (
    detect_project,
    normalize_org_repo_slug,
    normalize_project_name,
)


@dataclass(frozen=True)
class GroupIdPlan:
    """Canonical group IDs plus detected legacy aliases."""

    project_group_id: str
    github_group_id: str | None
    legacy_project_ids: tuple[str, ...]
    legacy_github_ids: tuple[str, ...]

    @property
    def unified(self) -> bool:
        return (
            self.github_group_id is None
            or self.project_group_id == self.github_group_id
        )


def build_group_id_plan(
    *,
    project_id: str | None,
    github_repo: str | None,
    cwd: str | None = None,
) -> GroupIdPlan:
    """Build canonical and legacy ID sets for the current install."""
    canonical_github_id = (
        normalize_github_repo_slug(github_repo) if github_repo else None
    )
    normalized_project_slug = normalize_org_repo_slug(project_id)
    normalized_project_name = normalize_project_name(project_id or "")
    canonical_project_id = (
        normalized_project_slug or normalized_project_name or detect_project(cwd)
    )

    if (
        project_id
        and canonical_github_id
        and normalized_project_name == normalize_project_name(canonical_github_id)
    ):
        canonical_project_id = canonical_github_id

    if canonical_project_id == "unnamed-project":
        canonical_project_id = detect_project(cwd)

    legacy_project_ids: list[str] = []
    if project_id and "/" in project_id:
        flattened = normalize_project_name(project_id)
        if flattened and flattened != canonical_project_id:
            legacy_project_ids.append(flattened)
    elif project_id and normalized_project_name != canonical_project_id:
        legacy_project_ids.append(normalized_project_name)

    legacy_github_ids: list[str] = []
    if github_repo:
        raw_repo = github_repo.strip()
        if raw_repo and canonical_github_id and raw_repo != canonical_github_id:
            legacy_github_ids.append(raw_repo)

    return GroupIdPlan(
        project_group_id=canonical_project_id,
        github_group_id=canonical_github_id,
        legacy_project_ids=tuple(dict.fromkeys(legacy_project_ids)),
        legacy_github_ids=tuple(dict.fromkeys(legacy_github_ids)),
    )
