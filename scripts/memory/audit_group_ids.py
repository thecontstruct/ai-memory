#!/usr/bin/env python3
# ruff: noqa: E402
"""Audit canonical and legacy group IDs for the current project."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

INSTALL_DIR = os.environ.get(
    "AI_MEMORY_INSTALL_DIR", os.path.expanduser("~/.ai-memory")
)
sys.path.insert(0, os.path.join(INSTALL_DIR, "src"))

from memory.config import (
    COLLECTION_CODE_PATTERNS,
    COLLECTION_DISCUSSIONS,
    COLLECTION_GITHUB,
    get_config,
)
from memory.connectors.github.paths import github_state_file, resolve_github_state_file
from memory.group_ids import build_group_id_plan
from memory.project import normalize_project_name
from memory.qdrant_client import get_qdrant_client
from qdrant_client import models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit legacy ai-memory group IDs")
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Project directory to audit (default: current working directory)",
    )
    parser.add_argument(
        "--fail-on-legacy",
        action="store_true",
        help="Exit non-zero when legacy aliases are detected",
    )
    return parser.parse_args()


def count_group_id(client, collection: str, group_id: str) -> int:
    result = client.count(
        collection_name=collection,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="group_id", match=models.MatchValue(value=group_id)
                )
            ]
        ),
        exact=True,
    )
    return result.count


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

    print("## Group ID Audit")
    print("")
    print(f"Project cwd: {Path(args.cwd).resolve()}")
    print(f"Canonical project group_id: {plan.project_group_id}")
    print(f"Canonical GitHub group_id: {plan.github_group_id or 'not configured'}")
    print(f"Unified IDs: {'yes' if plan.unified else 'no'}")
    print("")

    print("### Canonical Counts")
    for collection, gid in [
        (COLLECTION_CODE_PATTERNS, plan.project_group_id),
        (COLLECTION_DISCUSSIONS, plan.project_group_id),
    ]:
        print(f"- {collection}: {count_group_id(client, collection, gid)}")
    if plan.github_group_id:
        print(
            f"- {COLLECTION_GITHUB}: {count_group_id(client, COLLECTION_GITHUB, plan.github_group_id)}"
        )
    print("")

    legacy_rows: list[tuple[str, str, dict[str, int]]] = []
    for legacy_id in plan.legacy_project_ids:
        counts = {
            COLLECTION_CODE_PATTERNS: count_group_id(
                client, COLLECTION_CODE_PATTERNS, legacy_id
            ),
            COLLECTION_DISCUSSIONS: count_group_id(
                client, COLLECTION_DISCUSSIONS, legacy_id
            ),
        }
        if any(counts.values()):
            legacy_rows.append(("project", legacy_id, counts))

    for legacy_id in plan.legacy_github_ids:
        counts = {
            COLLECTION_GITHUB: count_group_id(client, COLLECTION_GITHUB, legacy_id)
        }
        if any(counts.values()):
            legacy_rows.append(("github", legacy_id, counts))

    legacy_found = bool(legacy_rows)
    if legacy_rows:
        print("### Legacy Aliases")
        for kind, legacy_id, counts in legacy_rows:
            print(f"- {kind} alias `{legacy_id}`")
            for collection, count in counts.items():
                print(f"  {collection}: {count}")
        print("")

    if (
        project_id
        and project_id.strip() != plan.project_group_id
        and normalize_project_name(project_id) in plan.legacy_project_ids
    ):
        legacy_found = True
        print("### Config Mismatch")
        print(f"- AI_MEMORY_PROJECT_ID: {project_id} -> {plan.project_group_id}")
        print("")

    state_path = (
        resolve_github_state_file(config.install_dir, config.github_repo, cwd=args.cwd)
        if config.github_repo
        else None
    )
    expected_state = (
        github_state_file(config.install_dir, config.github_repo)
        if config.github_repo
        else None
    )
    print("### GitHub Sync State")
    print(f"- canonical path: {expected_state or 'not configured'}")
    print(f"- active path: {state_path or 'not found'}")

    if state_path and expected_state and Path(state_path) != expected_state:
        legacy_found = True

    if legacy_found and args.fail_on_legacy:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
