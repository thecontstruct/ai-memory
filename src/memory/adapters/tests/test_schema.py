"""Unit tests for adapters/schema.py canonical event validation.

Tests cover every acceptance criterion in Story 1.1.
"""

import pytest

from memory.adapters.schema import (
    VALID_HOOK_EVENTS,
    VALID_IDE_SOURCES,
    validate_canonical_event,
)


def _valid_event(**overrides):
    """Build a minimal valid canonical event dict with optional overrides."""
    base = {
        "session_id": "test-session-123",
        "cwd": "/home/user/project",
        "hook_event_name": "PostToolUse",
        "ide_source": "claude",
        "tool_name": None,
        "tool_input": None,
        "tool_response": None,
        "transcript_path": None,
        "user_prompt": None,
        "trigger": None,
        "context_usage_percent": None,
        "context_tokens": None,
        "context_window_size": None,
        "is_background_agent": False,
    }
    base.update(overrides)
    return base


# --- Constants ---


class TestConstants:
    def test_valid_ide_sources(self):
        assert {"claude", "gemini", "cursor", "codex"} == VALID_IDE_SOURCES

    def test_valid_hook_events(self):
        expected = {
            "SessionStart",
            "PostToolUse",
            "PreToolUse",
            "PreCompact",
            "UserPromptSubmit",
            "SessionEnd",
            "Stop",
        }
        assert expected == VALID_HOOK_EVENTS


# --- Required fields ---


class TestRequiredFields:
    @pytest.mark.parametrize(
        "field", ["session_id", "cwd", "hook_event_name", "ide_source"]
    )
    def test_missing_required_field_raises(self, field):
        event = _valid_event()
        del event[field]
        with pytest.raises(
            ValueError, match=f"Missing or invalid required field: {field}"
        ):
            validate_canonical_event(event)

    @pytest.mark.parametrize(
        "field", ["session_id", "cwd", "hook_event_name", "ide_source"]
    )
    def test_non_str_required_field_raises(self, field):
        event = _valid_event(**{field: 123})
        with pytest.raises(
            ValueError, match=f"Missing or invalid required field: {field}"
        ):
            validate_canonical_event(event)

    def test_valid_event_passes(self):
        validate_canonical_event(_valid_event())


# --- ide_source validation ---


class TestIdeSource:
    @pytest.mark.parametrize("source", ["claude", "gemini", "cursor", "codex"])
    def test_valid_ide_source(self, source):
        validate_canonical_event(_valid_event(ide_source=source))

    def test_invalid_ide_source_raises(self):
        with pytest.raises(ValueError, match="Invalid ide_source"):
            validate_canonical_event(_valid_event(ide_source="vscode"))


# --- hook_event_name validation ---


class TestHookEventName:
    @pytest.mark.parametrize("event_name", VALID_HOOK_EVENTS)
    def test_valid_hook_event_names(self, event_name):
        overrides = {"hook_event_name": event_name}
        if event_name == "UserPromptSubmit":
            overrides["user_prompt"] = "test prompt"
        validate_canonical_event(_valid_event(**overrides))

    def test_invalid_hook_event_name_raises(self):
        with pytest.raises(ValueError, match="Invalid hook_event_name"):
            validate_canonical_event(_valid_event(hook_event_name="BeforeAgent"))


# --- Optional str | None fields ---


class TestOptionalStrOrNone:
    @pytest.mark.parametrize("field", ["tool_name", "transcript_path", "trigger"])
    def test_none_passes(self, field):
        validate_canonical_event(_valid_event(**{field: None}))

    @pytest.mark.parametrize("field", ["tool_name", "transcript_path", "trigger"])
    def test_str_passes(self, field):
        validate_canonical_event(_valid_event(**{field: "some_value"}))

    @pytest.mark.parametrize("field", ["tool_name", "transcript_path", "trigger"])
    def test_non_str_raises(self, field):
        with pytest.raises(ValueError, match=f"{field} must be str or None"):
            validate_canonical_event(_valid_event(**{field: 42}))


# --- tool_input (dict | None) ---


class TestToolInput:
    def test_none_passes(self):
        validate_canonical_event(_valid_event(tool_input=None))

    def test_dict_passes(self):
        validate_canonical_event(_valid_event(tool_input={"file_path": "/test.py"}))

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="tool_input must be dict or None"):
            validate_canonical_event(_valid_event(tool_input="not a dict"))


# --- tool_response (dict | str | None) ---


class TestToolResponse:
    def test_none_passes(self):
        validate_canonical_event(_valid_event(tool_response=None))

    def test_dict_passes(self):
        validate_canonical_event(_valid_event(tool_response={"exitCode": 0}))

    def test_str_passes(self):
        validate_canonical_event(_valid_event(tool_response="<result>ok</result>"))

    def test_non_dict_str_raises(self):
        with pytest.raises(
            ValueError, match="tool_response must be dict, str, or None"
        ):
            validate_canonical_event(_valid_event(tool_response=42))

    def test_list_raises(self):
        with pytest.raises(
            ValueError, match="tool_response must be dict, str, or None"
        ):
            validate_canonical_event(_valid_event(tool_response=["a", "b"]))


# --- user_prompt (asymmetric validation) ---


class TestUserPrompt:
    def test_user_prompt_submit_requires_non_empty_str(self):
        event = _valid_event(
            hook_event_name="UserPromptSubmit",
            user_prompt="how should I handle errors?",
        )
        validate_canonical_event(event)

    def test_user_prompt_submit_none_raises(self):
        event = _valid_event(
            hook_event_name="UserPromptSubmit",
            user_prompt=None,
        )
        with pytest.raises(ValueError, match="user_prompt must be a non-empty str"):
            validate_canonical_event(event)

    def test_user_prompt_submit_empty_str_raises(self):
        event = _valid_event(
            hook_event_name="UserPromptSubmit",
            user_prompt="",
        )
        with pytest.raises(ValueError, match="user_prompt must be a non-empty str"):
            validate_canonical_event(event)

    def test_user_prompt_submit_non_str_raises(self):
        event = _valid_event(
            hook_event_name="UserPromptSubmit",
            user_prompt=123,
        )
        with pytest.raises(ValueError, match="user_prompt must be a non-empty str"):
            validate_canonical_event(event)

    def test_non_user_prompt_submit_none_passes(self):
        validate_canonical_event(_valid_event(user_prompt=None))

    def test_non_user_prompt_submit_non_none_raises(self):
        with pytest.raises(
            ValueError, match="user_prompt must be None for PostToolUse"
        ):
            validate_canonical_event(_valid_event(user_prompt="should be none"))


# --- is_background_agent (bool) ---


class TestIsBackgroundAgent:
    def test_bool_true_passes(self):
        validate_canonical_event(_valid_event(is_background_agent=True))

    def test_bool_false_passes(self):
        validate_canonical_event(_valid_event(is_background_agent=False))

    def test_non_bool_raises(self):
        with pytest.raises(ValueError, match="is_background_agent must be bool"):
            validate_canonical_event(_valid_event(is_background_agent=1))

    def test_string_raises(self):
        with pytest.raises(ValueError, match="is_background_agent must be bool"):
            validate_canonical_event(_valid_event(is_background_agent="true"))


# --- context_usage_percent (float | None) ---


class TestContextUsagePercent:
    def test_none_passes(self):
        validate_canonical_event(_valid_event(context_usage_percent=None))

    def test_float_passes(self):
        validate_canonical_event(_valid_event(context_usage_percent=0.95))

    def test_int_raises(self):
        with pytest.raises(
            ValueError, match="context_usage_percent must be float or None"
        ):
            validate_canonical_event(_valid_event(context_usage_percent=95))


# --- context_tokens / context_window_size (int | None) ---


class TestContextInts:
    @pytest.mark.parametrize("field", ["context_tokens", "context_window_size"])
    def test_none_passes(self, field):
        validate_canonical_event(_valid_event(**{field: None}))

    @pytest.mark.parametrize("field", ["context_tokens", "context_window_size"])
    def test_int_passes(self, field):
        validate_canonical_event(_valid_event(**{field: 128000}))

    @pytest.mark.parametrize("field", ["context_tokens", "context_window_size"])
    def test_non_int_raises(self, field):
        with pytest.raises(ValueError, match=f"{field} must be int or None"):
            validate_canonical_event(_valid_event(**{field: "128000"}))

    @pytest.mark.parametrize("field", ["context_tokens", "context_window_size"])
    def test_float_raises(self, field):
        with pytest.raises(ValueError, match=f"{field} must be int or None"):
            validate_canonical_event(_valid_event(**{field: 128000.0}))
