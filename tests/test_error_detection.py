"""Test error_detection.py hook functionality."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent / ".claude" / "hooks" / "scripts"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def detection_module():
    return _load_module("error_detection", _SCRIPTS_DIR / "error_detection.py")


class TestDetectError:
    """Test detect_error() function."""

    def test_nonzero_exit_code(self, detection_module):
        assert detection_module.detect_error({"exitCode": 1, "stderr": ""}) is True

    def test_zero_exit_clean(self, detection_module):
        assert detection_module.detect_error({"exitCode": 0, "stdout": "ok"}) is False

    def test_traceback_in_stderr(self, detection_module):
        tool_response = {
            "exitCode": 0,
            "stderr": "Traceback (most recent call last):\n  File foo.py\nTypeError: x",
        }
        assert detection_module.detect_error(tool_response) is True

    def test_error_keyword_in_stderr(self, detection_module):
        tool_response = {"exitCode": 0, "stderr": "Error: No module named 'x'"}
        assert detection_module.detect_error(tool_response) is True


class TestFormatErrorPattern:
    """Test format_error_pattern()."""

    def test_fix_label(self, detection_module):
        fix = {
            "content": "fix content",
            "score": 0.8,
            "type": "error_pattern",
            "subtype": "fix",
            "file_path": "f.py",
            "resolution_confidence": 0.9,
        }
        result = detection_module.format_error_pattern(fix, 1)
        assert "[FIX]" in result
        assert "Confidence: 90%" in result

    def test_error_label(self, detection_module):
        err = {
            "content": "error content",
            "score": 0.8,
            "type": "error_pattern",
            "subtype": "error",
        }
        result = detection_module.format_error_pattern(err, 1)
        assert "[ERROR]" in result

    def test_no_subtype_defaults_error(self, detection_module):
        item = {"content": "content", "score": 0.7, "type": "error_pattern"}
        result = detection_module.format_error_pattern(item, 1)
        assert "[ERROR]" in result


class TestTwoPhaseRetrievalUnit:
    """Unit tests for two_phase_retrieval()."""

    def _run(self, detection_module, phase1_results, scroll_results=None):
        mock_search = MagicMock()
        mock_search.search.return_value = phase1_results

        mock_client = MagicMock()
        mock_client.scroll.return_value = (scroll_results or [], None)

        mock_qdrant = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_qdrant_models = MagicMock()
        mock_qdrant_models.FieldCondition = MagicMock()
        mock_qdrant_models.Filter = MagicMock()
        mock_qdrant_models.MatchValue = MagicMock()

        import sys

        with patch.dict(
            sys.modules,
            {
                "qdrant_client": mock_qdrant,
                "qdrant_client.models": mock_qdrant_models,
            },
        ):
            return detection_module.two_phase_retrieval(
                search=mock_search,
                error_signature="test error",
                project_name="test_project",
                session_id="sess123",
            )

    def test_empty_phase1_returns_empty(self, detection_module):
        results = self._run(detection_module, phase1_results=[])
        assert results == []

    def test_error_with_no_fix_returns_error_only(self, detection_module):
        phase1 = [
            {
                "score": 0.8,
                "content": "err",
                "type": "error_pattern",
                "subtype": "error",
                "error_group_id": "egid1",
            }
        ]
        results = self._run(detection_module, phase1_results=phase1, scroll_results=[])
        # Should have the error entry, no fix
        assert len(results) == 1
        assert results[0]["subtype"] == "error"

    def test_high_confidence_fix_sorted_first(self, detection_module):
        phase1 = [
            {
                "score": 0.9,
                "content": "err1",
                "type": "error_pattern",
                "subtype": "error",
                "error_group_id": "egid1",
            },
            {
                "score": 0.8,
                "content": "err2",
                "type": "error_pattern",
                "subtype": "error",
                "error_group_id": "egid2",
            },
        ]
        high_fix = MagicMock()
        high_fix.id = "hf"
        high_fix.payload = {
            "content": "hfix",
            "type": "error_pattern",
            "freshness_status": "unverified",
            "resolution_confidence": 0.9,
        }
        low_fix = MagicMock()
        low_fix.id = "lf"
        low_fix.payload = {
            "content": "lfix",
            "type": "error_pattern",
            "freshness_status": "unverified",
            "resolution_confidence": 0.4,
        }

        call_count = [0]

        def scroll_se(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return ([high_fix], None) if idx == 0 else ([low_fix], None)

        mock_search = MagicMock()
        mock_search.search.return_value = phase1
        mock_client = MagicMock()
        mock_client.scroll.side_effect = scroll_se
        mock_qdrant = MagicMock()
        mock_qdrant.QdrantClient.return_value = mock_client
        mock_qdrant_models = MagicMock()
        mock_qdrant_models.FieldCondition = MagicMock()
        mock_qdrant_models.Filter = MagicMock()
        mock_qdrant_models.MatchValue = MagicMock()

        import sys

        with patch.dict(
            sys.modules,
            {
                "qdrant_client": mock_qdrant,
                "qdrant_client.models": mock_qdrant_models,
            },
        ):
            results = detection_module.two_phase_retrieval(
                search=mock_search,
                error_signature="test",
                project_name="proj",
                session_id="s",
            )

        fixes = [r for r in results if r.get("subtype") == "fix"]
        assert fixes[0]["resolution_confidence"] == 0.9
