#!/usr/bin/env python3
# ruff: noqa: E402
"""Migrate legacy ai-memory group IDs to canonical values."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

INSTALL_DIR = os.environ.get("AI_MEMORY_INSTALL_DIR", os.path.expanduser("~/.ai-memory"))
sys.path.insert(0, os.path.join(INSTALL_DIR, "src"))

from memory.config import (
    COLLECTION_CODE_PATTERNS,
    COLLECTION_DISCUSSIONS,
    COLLECTION_GITHUB,
    get_config,
)
from memory.connectors.github.paths import github_state_file, github_state_candidates
from memory.group_ids import build_group_id_plan
from memory.project import normalize_project_name
from memory.qdrant_client import get_qdrant_client
from qdrant_client import models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy ai-memory group IDs")
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Project directory to migrate (default: current working directory)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag, only print the plan.",
    )
    return parser.parse_args()


def migrate_collection(
    client,
    *,
    collection: str,
    old_group_id: str,
    new_group_id: str,
) -> int:
    total = 0
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="group_id", match=models.MatchValue(value=old_group_id)
                    )
                ]
            ),
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        ids = [point.id for point in points]
        if ids:
            client.set_payload(
                collection_name=collection,
                payload={"group_id": new_group_id},
                points=ids,
                wait=True,
            )
            total += len(ids)
        if next_offset is None:
            return total
        offset = next_offset


def count_group_id(client, collection: str, group_id: str) -> int:
    result = client.count(
        collection_name=collection,
        count_filter=models.Filter(
            must=[models.FieldCondition(key="group_id", match=models.MatchValue(value=group_id))]
        ),
        exact=True,
    )
    return result.count


def migrate_state_file(config, github_repo: str | None, cwd: str) -> tuple[str, str] | None:
    if not github_repo:
        return None

    canonical_path = github_state_file(config.install_dir, github_repo)
    for candidate in github_state_candidates(config.install_dir, github_repo, cwd=cwd):
        if candidate == canonical_path or not candidate.exists():
            continue
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        if not canonical_path.exists():
            candidate.replace(canonical_path)
            return (str(candidate), str(canonical_path))
    return None


def planned_state_file_move(config, github_repo: str | None, cwd: str) -> tuple[str, str] | None:
    if not github_repo:
        return None

    canonical_path = github_state_file(config.install_dir, github_repo)
    for candidate in github_state_candidates(config.install_dir, github_repo, cwd=cwd):
        if candidate == canonical_path or not candidate.exists():
            continue
        if not canonical_path.exists():
            return (str(candidate), str(canonical_path))
    return None


def configured_env_file(config) -> Path:
    return Path(config.install_dir) / "docker" / ".env"


def planned_project_id_update(
    env_file: Path, project_id: str | None, plan
) -> tuple[str, str, str] | None:
    if (
        not project_id
        or project_id.strip() == plan.project_group_id
        or normalize_project_name(project_id) not in plan.legacy_project_ids
    ):
        return None
    if not env_file.exists():
        return None
    return (str(env_file), project_id, plan.project_group_id)


def apply_project_id_update(env_file: Path, old_value: str, new_value: str) -> bool:
    if not env_file.exists():
        return False

    lines = env_file.read_text().splitlines()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith("AI_MEMORY_PROJECT_ID="):
            lines[index] = f"AI_MEMORY_PROJECT_ID={new_value}"
            updated = True
            break

    if not updated:
        return False

    env_file.write_text("\n".join(lines) + "\n")
    return True


def main() -> int:
    args = parse_args()
    config = get_config()
    client = get_qdrant_client(config)

    project_id = os.environ.get("AI_MEMORY_PROJECT_ID")
    plan = build_group_id_plan(
        project_id=project_id,
        github_repo=config.github_repo,
        cwd=args.cwd,
    )
    env_file = configured_env_file(config)
    project_id_update = planned_project_id_update(env_file, project_id, plan)

    actions: list[tuple[str, str, str, int]] = []
    for legacy_id in plan.legacy_project_ids:
        for collection in (COLLECTION_CODE_PATTERNS, COLLECTION_DISCUSSIONS):
            count = count_group_id(client, collection, legacy_id)
            if count:
                actions.append((collection, legacy_id, plan.project_group_id, count))
    if plan.github_group_id:
        for legacy_id in plan.legacy_github_ids:
            count = count_group_id(client, COLLECTION_GITHUB, legacy_id)
            if count:
                actions.append((COLLECTION_GITHUB, legacy_id, plan.github_group_id, count))

    print("## Group ID Migration")
    print("")
    print(f"Apply mode: {'yes' if args.apply else 'no (dry run)'}")
    print(f"Project canonical group_id: {plan.project_group_id}")
    print(f"GitHub canonical group_id: {plan.github_group_id or 'not configured'}")
    print("")

    if not actions:
        print("No legacy Qdrant aliases detected.")
        state_move = (
            migrate_state_file(config, config.github_repo, args.cwd)
            if args.apply
            else planned_state_file_move(config, config.github_repo, args.cwd)
        )
        if project_id_update:
            label = "Updated AI_MEMORY_PROJECT_ID" if args.apply else "Planned AI_MEMORY_PROJECT_ID update"
            if args.apply:
                apply_project_id_update(env_file, project_id_update[1], project_id_update[2])
            print(f"{label}: {project_id_update[1]} -> {project_id_update[2]} ({project_id_update[0]})")
        if state_move:
            label = "Moved state file" if args.apply else "Planned state file move"
            print(f"{label}: {state_move[0]} -> {state_move[1]}")
        return 0

    for collection, old_id, new_id, count in actions:
        print(f"- {collection}: {old_id} -> {new_id} ({count} record(s))")

    state_move = planned_state_file_move(config, config.github_repo, args.cwd)
    if state_move:
        print(f"- state file: {state_move[0]} -> {state_move[1]}")
    if project_id_update:
        print(
            f"- AI_MEMORY_PROJECT_ID: {project_id_update[1]} -> {project_id_update[2]} ({project_id_update[0]})"
        )

    if not args.apply:
        print("")
        print("Re-run with --apply to execute the migration.")
        return 0

    print("")
    for collection, old_id, new_id, _count in actions:
        migrated = migrate_collection(
            client, collection=collection, old_group_id=old_id, new_group_id=new_id
        )
        print(f"{collection}: migrated {migrated} record(s) from {old_id} to {new_id}")

    state_move = migrate_state_file(config, config.github_repo, args.cwd)
    if state_move:
        print(f"Moved state file: {state_move[0]} -> {state_move[1]}")
    else:
        print("State file: no move required")

    if project_id_update:
        if apply_project_id_update(env_file, project_id_update[1], project_id_update[2]):
            print(
                f"Updated AI_MEMORY_PROJECT_ID: {project_id_update[1]} -> {project_id_update[2]} ({project_id_update[0]})"
            )
        else:
            print("AI_MEMORY_PROJECT_ID: no update applied")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
