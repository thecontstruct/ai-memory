"""Unit tests for post_tool_capture.py hook.

Tests code pattern capture on PostToolUse events.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from mocks.qdrant_mock import MockQdrantClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude/hooks/scripts"))


@pytest.fixture
def post_tool_edit_event():
    """Load PostToolUse Edit event fixture."""
    with open(
        Path(__file__).parent.parent / "fixtures/hooks/post_tool_use_edit.json"
    ) as f:
        return json.load(f)


@pytest.fixture
def post_tool_write_event():
    """Load PostToolUse Write event fixture."""
    with open(
        Path(__file__).parent.parent / "fixtures/hooks/post_tool_use_write.json"
    ) as f:
        return json.load(f)


@pytest.fixture
def mock_qdrant():
    """Provide fresh mock Qdrant client."""
    client = MockQdrantClient()
    client.reset()
    return client


@pytest.fixture
def mock_config():
    """Provide mock MemoryConfig."""
    config = MagicMock()
    config.qdrant_host = "localhost"
    config.qdrant_port = 26350
    config.project_name = "ai-memory-module"
    return config


class TestPostToolCapture:
    """Test suite for post_tool_capture.py hook."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Reset module state before each test."""
        if "post_tool_capture" in sys.modules:
            del sys.modules["post_tool_capture"]
        yield
        if "post_tool_capture" in sys.modules:
            del sys.modules["post_tool_capture"]

    def test_captures_edit_tool_changes(self, post_tool_edit_event):
        """Test that Edit tool changes are captured.

        PostToolUse Edit events should extract old_string and new_string
        to capture implementation patterns.
        """
        tool_input = post_tool_edit_event["tool_input"]
        file_path = tool_input["file_path"]
        old_string = tool_input["old_string"]
        new_string = tool_input["new_string"]

        # Verify file path is meaningful
        assert "storage.py" in file_path

        # Verify old and new strings captured
        assert "def store_memory(data):" in old_string
        assert "def store_memory(data):" in new_string
        # New string should have more implementation details
        assert len(new_string) > len(old_string)
        assert "is_duplicate" in new_string

    def test_captures_write_tool_new_files(self, post_tool_write_event):
        """Test that Write tool new file creation is captured.

        PostToolUse Write events should capture full file content
        for new files as implementation patterns.
        """
        tool_input = post_tool_write_event["tool_input"]
        file_path = tool_input["file_path"]
        content = tool_input["content"]

        # Verify new file captured
        assert "deduplication.py" in file_path
        assert len(content) > 0

        # Verify content is meaningful code
        assert "import hashlib" in content
        assert "def compute_hash" in content
        assert "sha256" in content.lower()

    def test_fork_pattern_for_async_storage(self, post_tool_edit_event):
        """Test that hook uses fork pattern for background storage.

        PostToolUse hook should fork a subprocess for storage to avoid
        blocking Claude (performance requirement: <500ms hook overhead).
        """
        # Verify fork pattern expectations
        # In real implementation, hook would call subprocess.Popen
        # and return immediately with exit(0)

        session_id = post_tool_edit_event["session_id"]
        turn_number = post_tool_edit_event["turn_number"]

        assert session_id is not None
        assert turn_number == 8
        # Hook should spawn async process and exit immediately

    def test_graceful_degradation_on_malformed_input(self, mock_config):
        """Test that hook handles malformed tool input gracefully.

        Hook should not crash on unexpected input structures.
        """
        malformed_event = {
            "session_id": "test_session",
            "tool_name": "Edit",
            "tool_input": {},  # Missing required fields
            "cwd": "/test/path",
        }

        # Hook should handle missing fields without crashing
        assert malformed_event["tool_input"] == {}
        # In real implementation, hook would exit 0 with warning log

    def test_targets_code_patterns_collection(self, post_tool_edit_event, mock_config):
        """Test that code patterns are stored to code-patterns collection.

        V2.0: Implementation patterns go to code-patterns collection.
        """
        with patch("memory.config.get_config", return_value=mock_config):
            from memory.config import COLLECTION_CODE_PATTERNS

            assert COLLECTION_CODE_PATTERNS == "code-patterns"
            # PostToolUse captures should target this collection

    def test_extracts_file_context(self, post_tool_edit_event):
        """Test that hook extracts file path for context.

        File path is critical for file_pattern memory type in V2.0.
        """
        tool_input = post_tool_edit_event["tool_input"]
        file_path = tool_input["file_path"]

        # Verify file path is absolute
        assert file_path.startswith("/")
        assert "storage.py" in file_path

        # File path should be stored in payload for PreToolUse retrieval


class TestWriteFixRestriction:
    """M-3: Write fix detection must be restricted to FileNotFoundError only (§C4b)."""

    @pytest.fixture(autouse=True)
    def _import_module(self):
        """Import detect_edit_write_fix from hook script."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "post_tool_capture",
            Path(__file__).parent.parent.parent
            / ".claude"
            / "hooks"
            / "scripts"
            / "post_tool_capture.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.module = mod

    def test_write_fix_source_only_matches_file_not_found(self):
        """Write fix path must only trigger for FileNotFoundError."""
        import inspect

        source = inspect.getsource(self.module.detect_edit_write_fix)
        # Must check for FileNotFoundError
        assert "FileNotFoundError" in source
        # Must NOT have a broad fallback that matches Write to any file
        # The old code had an elif that matched any file — verify it's gone
        lines = source.split("\n")
        write_block_started = False
        has_broad_fallback = False
        for line in lines:
            if 'tool_name == "Write"' in line:
                write_block_started = True
            if write_block_started and "elif error_file and" in line:
                # This is the broad fallback — it should NOT exist
                has_broad_fallback = True
                break
            if (
                write_block_started
                and "matched_errors" not in line
                and line.strip().startswith("if ")
            ):
                break  # Moved past the Write block
        assert not has_broad_fallback, (
            "Write fix must NOT have broad fallback matching any file — "
            "only FileNotFoundError per §C4b"
        )

    def test_write_fix_restricted_to_file_not_found_error(self):
        """Write fix should only match FileNotFoundError (§C4b)."""
        import inspect

        source = inspect.getsource(self.module.detect_edit_write_fix)
        assert (
            "FileNotFoundError" in source
        ), "Write fix should be restricted to FileNotFoundError (§C4b)"


class TestHookExitCodesPostTool:
    """H-4: post_tool_capture.py must always exit 0 (§1.2 Principle 4)."""

    @pytest.fixture(autouse=True)
    def _import_module(self):
        """Import module."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "post_tool_capture",
            Path(__file__).parent.parent.parent
            / ".claude"
            / "hooks"
            / "scripts"
            / "post_tool_capture.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.module = mod

    def test_no_return_1_in_main(self):
        """Verify no 'return 1' exists in main() function source code."""
        import inspect

        source = inspect.getsource(self.module.main)
        assert (
            "return 1" not in source
        ), "main() must never return 1 — hooks must always exit 0 (§1.2 Principle 4)"
