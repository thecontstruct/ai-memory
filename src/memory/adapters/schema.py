"""Canonical event schema, validation, and shared utilities for IDE adapters.

All IDE adapters normalize their native hook payloads into the canonical event
dict defined here. The validation function enforces the contract between any
adapter and the storage/retrieval pipeline.

Architecture reference: §2 Canonical Event Schema
PRD reference: FR-101, FR-102
"""

VALID_IDE_SOURCES = {"claude", "gemini", "cursor", "codex"}

VALID_HOOK_EVENTS = {
    "SessionStart",
    "PostToolUse",
    "PreToolUse",
    "PreCompact",
    "UserPromptSubmit",
    "SessionEnd",
    "Stop",
}


def validate_canonical_event(event: dict) -> None:
    """Validate canonical event dict. Raises ValueError on invalid input."""
    required = ["session_id", "cwd", "hook_event_name", "ide_source"]
    for field in required:
        if field not in event or not isinstance(event[field], str):
            raise ValueError(f"Missing or invalid required field: {field}")
    if event["ide_source"] not in VALID_IDE_SOURCES:
        raise ValueError(f"Invalid ide_source: {event['ide_source']}")
    if event["hook_event_name"] not in VALID_HOOK_EVENTS:
        raise ValueError(f"Invalid hook_event_name: {event['hook_event_name']}")

    # user_prompt: required non-empty str for UserPromptSubmit, must be None otherwise
    if event["hook_event_name"] == "UserPromptSubmit":
        up = event.get("user_prompt")
        if not isinstance(up, str) or not up:
            raise ValueError(
                "user_prompt must be a non-empty str for UserPromptSubmit events"
            )
    else:
        up = event.get("user_prompt")
        if up is not None:
            raise ValueError(
                f"user_prompt must be None for {event['hook_event_name']} events"
            )

    optional_str_or_none = ["tool_name", "transcript_path", "trigger"]
    for field in optional_str_or_none:
        if (
            field in event
            and event[field] is not None
            and not isinstance(event[field], str)
        ):
            raise ValueError(
                f"{field} must be str or None, got {type(event[field]).__name__}"
            )

    optional_dict_or_none = ["tool_input"]
    for field in optional_dict_or_none:
        if (
            field in event
            and event[field] is not None
            and not isinstance(event[field], dict)
        ):
            raise ValueError(
                f"{field} must be dict or None, got {type(event[field]).__name__}"
            )

    if "tool_response" in event:
        tr = event["tool_response"]
        if tr is not None and not isinstance(tr, (dict, str)):
            raise ValueError(
                f"tool_response must be dict, str, or None, got {type(tr).__name__}"
            )

    optional_float_or_none = ["context_usage_percent"]
    for field in optional_float_or_none:
        if (
            field in event
            and event[field] is not None
            and not isinstance(event[field], float)
        ):
            raise ValueError(
                f"{field} must be float or None, got {type(event[field]).__name__}"
            )

    optional_int_or_none = ["context_tokens", "context_window_size"]
    for field in optional_int_or_none:
        if (
            field in event
            and event[field] is not None
            and not isinstance(event[field], int)
        ):
            raise ValueError(
                f"{field} must be int or None, got {type(event[field]).__name__}"
            )

    if "is_background_agent" in event and not isinstance(
        event["is_background_agent"], bool
    ):
        raise ValueError(
            f"is_background_agent must be bool, got {type(event['is_background_agent']).__name__}"
        )
