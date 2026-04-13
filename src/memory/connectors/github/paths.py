"""Helpers for GitHub repo normalization and sync state paths."""

from __future__ import annotations

from pathlib import Path

from memory.project import normalize_project_name


def normalize_github_repo_slug(repo: str) -> str:
    """Normalize a GitHub owner/repo slug for stable tenant IDs.

    Examples:
        "Axonify/thunderball" -> "axonify/thunderball"
        "owner/repo" -> "owner/repo"
        "owner repo" -> "owner-repo"
    """
    raw = (repo or "").strip()
    if not raw:
        return normalize_project_name(raw)

    if "/" not in raw:
        return normalize_project_name(raw)

    owner, name = raw.split("/", 1)
    owner_norm = normalize_project_name(owner)
    repo_norm = normalize_project_name(name)
    return f"{owner_norm}/{repo_norm}"


def github_state_dir(install_dir: str | Path) -> Path:
    """Canonical shared directory for GitHub sync state files."""
    return Path(install_dir) / "github-state"


def github_state_file(install_dir: str | Path, repo: str) -> Path:
    """Canonical state file path for a GitHub repo."""
    repo_safe = normalize_github_repo_slug(repo).replace("/", "__")
    return github_state_dir(install_dir) / f"github_sync_state_{repo_safe}.json"


def github_state_candidates(
    install_dir: str | Path,
    repo: str,
    cwd: str | Path | None = None,
) -> list[Path]:
    """Return canonical and legacy candidate paths for GitHub sync state."""
    candidates: list[Path] = []

    def add(path: Path) -> None:
        if path not in candidates:
            candidates.append(path)

    install_root = Path(install_dir)
    cwd_path = Path(cwd) if cwd is not None else Path.cwd()

    normalized_safe = normalize_github_repo_slug(repo).replace("/", "__")
    raw_safe = (repo or "").replace("/", "__")

    add(github_state_dir(install_root) / f"github_sync_state_{normalized_safe}.json")
    if raw_safe and raw_safe != normalized_safe:
        add(github_state_dir(install_root) / f"github_sync_state_{raw_safe}.json")

    for base in [install_root / ".audit" / "state", cwd_path / ".audit" / "state"]:
        add(base / f"github_sync_state_{normalized_safe}.json")
        if raw_safe and raw_safe != normalized_safe:
            add(base / f"github_sync_state_{raw_safe}.json")
        add(base / "github_sync_state.json")

    return candidates


def resolve_github_state_file(
    install_dir: str | Path,
    repo: str,
    cwd: str | Path | None = None,
) -> Path | None:
    """Return the first existing GitHub sync state file candidate."""
    for candidate in github_state_candidates(install_dir, repo, cwd=cwd):
        if candidate.exists():
            return candidate
    return None
