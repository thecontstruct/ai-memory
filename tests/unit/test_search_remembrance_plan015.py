"""Tests for PLAN-015 search + remembrance fixes (H-3, M-7, L-9, L-11).

H-3: Cross-turn access_count dedup — multiple search() calls in same turn
     returning overlapping point IDs should increment each point's access_count
     only once.
M-7: Batch set_payload — one call per collection instead of per-point.
L-9: freshness_status normalization — results normalize to lowercase.
L-11: Non-atomic read-increment-write documented (comment-only, no test needed).
"""

from unittest.mock import MagicMock, patch

from memory.config import MemoryConfig
from memory.injection import InjectionSessionState


class TestCrossTurnAccessCountDedup:
    """H-3: Two search() calls in same turn returning overlapping point IDs
    should increment each point's access_count only once."""

    def _make_mock_point(self, point_id, access_count=0, score=0.85):
        """Create a mock Qdrant ScoredPoint."""
        mock_point = MagicMock()
        mock_point.id = point_id
        mock_point.score = score
        mock_point.payload = {
            "content": f"Test content for {point_id}",
            "type": "decision",
            "group_id": "test-project",
            "stored_at": "2026-01-01T00:00:00Z",
            "access_count": access_count,
        }
        return mock_point

    def _make_mock_retrieved_point(self, point_id, access_count=0):
        """Create a mock Qdrant Record (retrieve result)."""
        mock_point = MagicMock()
        mock_point.id = point_id
        mock_point.payload = {"access_count": access_count}
        return mock_point

    def test_cross_turn_dedup_skips_already_incremented(self):
        """When _access_count_dedup contains a point_id, search() skips incrementing it."""
        # Point appears in both search calls
        overlapping_pid = "overlap-1"
        mock_scored = self._make_mock_point(overlapping_pid, access_count=1)
        mock_retrieved = self._make_mock_retrieved_point(
            overlapping_pid, access_count=1
        )

        mock_response = MagicMock()
        mock_response.points = [mock_scored]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = [mock_retrieved]
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)

            # Shared dedup list across calls (simulates same turn)
            dedup_list = []

            # First call — should increment
            searcher.search(
                query="test query 1",
                collection="discussions",
                group_id="test-project",
                _access_count_dedup=dedup_list,
            )

            assert overlapping_pid in dedup_list
            assert mock_client.set_payload.call_count == 1

            # Reset mock call tracking for second search
            mock_client.set_payload.reset_mock()
            mock_client.retrieve.reset_mock()

            # Second call with same dedup list — should SKIP incrementing
            searcher.search(
                query="test query 2",
                collection="discussions",
                group_id="test-project",
                _access_count_dedup=dedup_list,
            )

            # set_payload should NOT be called for the overlapping point
            mock_client.set_payload.assert_not_called()
            # retrieve should NOT be called (all pids filtered out by dedup)
            mock_client.retrieve.assert_not_called()

    def test_dedup_list_accumulates_across_calls(self):
        """The dedup list grows across multiple search() calls in the same turn."""
        pids = ["pid-a", "pid-b", "pid-c"]
        mock_points = [self._make_mock_point(pid) for pid in pids]
        mock_retrieved = [self._make_mock_retrieved_point(pid) for pid in pids]

        mock_response = MagicMock()
        mock_response.points = mock_points

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = mock_retrieved
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            dedup_list = []

            searcher.search(
                query="test query",
                collection="discussions",
                group_id="test-project",
                _access_count_dedup=dedup_list,
            )

            # All 3 point IDs should be in the dedup list
            assert set(dedup_list) == set(pids)

    def test_no_dedup_list_increments_normally(self):
        """Without _access_count_dedup, all points get incremented (backward compat)."""
        mock_scored = self._make_mock_point("pid-1", access_count=0)
        mock_retrieved = self._make_mock_retrieved_point("pid-1", access_count=0)

        mock_response = MagicMock()
        mock_response.points = [mock_scored]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = [mock_retrieved]
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)

            # No dedup list — should increment normally
            searcher.search(
                query="test query",
                collection="discussions",
                group_id="test-project",
            )

            mock_client.set_payload.assert_called_once()


class TestBatchSetPayload:
    """M-7: Batch set_payload — one call per distinct count value per collection."""

    def _make_mock_point(self, point_id, access_count=0, score=0.85):
        mock_point = MagicMock()
        mock_point.id = point_id
        mock_point.score = score
        mock_point.payload = {
            "content": f"Test content for {point_id}",
            "type": "decision",
            "group_id": "test-project",
            "stored_at": "2026-01-01T00:00:00Z",
            "access_count": access_count,
        }
        return mock_point

    def _make_mock_retrieved_point(self, point_id, access_count=0):
        mock_point = MagicMock()
        mock_point.id = point_id
        mock_point.payload = {"access_count": access_count}
        return mock_point

    def test_batch_set_payload_groups_by_count(self):
        """Multiple points with same current access_count should be updated in one call."""
        # 3 points all at access_count=0 → all become 1, should be one set_payload call
        pids = ["p1", "p2", "p3"]
        mock_scored = [self._make_mock_point(pid, access_count=0) for pid in pids]
        mock_retrieved = [
            self._make_mock_retrieved_point(pid, access_count=0) for pid in pids
        ]

        mock_response = MagicMock()
        mock_response.points = mock_scored

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = mock_retrieved
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            searcher.search(
                query="test query",
                collection="discussions",
                group_id="test-project",
            )

        # All 3 points have same new count (1), so ONE set_payload call
        assert mock_client.set_payload.call_count == 1
        call_kwargs = mock_client.set_payload.call_args[1]
        assert call_kwargs["payload"] == {"access_count": 1}
        assert set(call_kwargs["points"]) == set(pids)

    def test_batch_set_payload_separate_calls_for_different_counts(self):
        """Points with different access_counts get separate batch calls."""
        # p1 at count=0, p2 at count=2 → p1 becomes 1, p2 becomes 3 → two set_payload calls
        mock_scored = [
            self._make_mock_point("p1", access_count=0),
            self._make_mock_point("p2", access_count=2),
        ]
        mock_retrieved = [
            self._make_mock_retrieved_point("p1", access_count=0),
            self._make_mock_retrieved_point("p2", access_count=2),
        ]

        mock_response = MagicMock()
        mock_response.points = mock_scored

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = mock_retrieved
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            searcher.search(
                query="test query",
                collection="discussions",
                group_id="test-project",
            )

        # Two distinct new counts (1 and 3) → two set_payload calls
        assert mock_client.set_payload.call_count == 2


class TestFreshnessStatusNormalization:
    """L-9: freshness_status is normalized to lowercase in search results."""

    def _make_mock_point(self, point_id, freshness_status=None, score=0.85):
        mock_point = MagicMock()
        mock_point.id = point_id
        mock_point.score = score
        payload = {
            "content": f"Test content for {point_id}",
            "type": "implementation",
            "group_id": "test-project",
            "stored_at": "2026-01-01T00:00:00Z",
        }
        if freshness_status is not None:
            payload["freshness_status"] = freshness_status
        return mock_point, payload

    def test_freshness_status_normalized_to_lowercase(self):
        """freshness_status 'EXPIRED' in payload becomes 'expired' in results."""
        mock_point = MagicMock()
        mock_point.id = "fs-1"
        mock_point.score = 0.85
        mock_point.payload = {
            "content": "Test content",
            "type": "implementation",
            "group_id": "test-project",
            "freshness_status": "EXPIRED",
        }

        mock_response = MagicMock()
        mock_response.points = [mock_point]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = []
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            results = searcher.search(
                query="test query",
                collection="code-patterns",
                group_id="test-project",
            )

        assert len(results) == 1
        assert results[0]["freshness_status"] == "expired"

    def test_freshness_status_missing_defaults_to_unknown(self):
        """Missing freshness_status in payload becomes 'unknown' in results."""
        mock_point = MagicMock()
        mock_point.id = "fs-2"
        mock_point.score = 0.85
        mock_point.payload = {
            "content": "Test content",
            "type": "implementation",
            "group_id": "test-project",
            # No freshness_status key
        }

        mock_response = MagicMock()
        mock_response.points = [mock_point]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = []
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            results = searcher.search(
                query="test query",
                collection="code-patterns",
                group_id="test-project",
            )

        assert len(results) == 1
        assert results[0]["freshness_status"] == "unknown"

    def test_freshness_status_mixed_case_normalized(self):
        """Mixed case 'Fresh' becomes 'fresh'."""
        mock_point = MagicMock()
        mock_point.id = "fs-3"
        mock_point.score = 0.85
        mock_point.payload = {
            "content": "Test content",
            "type": "implementation",
            "group_id": "test-project",
            "freshness_status": "Fresh",
        }

        mock_response = MagicMock()
        mock_response.points = [mock_point]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_client.retrieve.return_value = []
        mock_client.set_payload.return_value = None

        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.0] * 768]
        mock_embedding.embed_sparse.return_value = None

        config = MemoryConfig(decay_enabled=False, hybrid_search_enabled=False)

        with (
            patch("memory.search.get_qdrant_client", return_value=mock_client),
            patch("memory.search.EmbeddingClient", return_value=mock_embedding),
        ):
            from memory.search import MemorySearch

            searcher = MemorySearch(config=config)
            results = searcher.search(
                query="test query",
                collection="code-patterns",
                group_id="test-project",
            )

        assert len(results) == 1
        assert results[0]["freshness_status"] == "fresh"


class TestInjectionSessionStateDedup:
    """Test new H-3 fields on InjectionSessionState."""

    def test_default_access_count_dedup_empty(self):
        """New state has empty access_count_incremented_this_turn list."""
        state = InjectionSessionState(session_id="test-dedup-1")
        assert state.access_count_incremented_this_turn == []
        assert state._last_turn_count == 0

    def test_turn_advance_clears_dedup_set(self):
        """Advancing turn_count clears the dedup list."""
        state = InjectionSessionState(session_id="test-dedup-2")
        state.access_count_incremented_this_turn = ["pid-1", "pid-2"]
        state._last_turn_count = 1
        state.turn_count = 2

        # Simulate what tier2 hook does on new turn
        if state.turn_count != state._last_turn_count:
            state.access_count_incremented_this_turn = []
            state._last_turn_count = state.turn_count

        assert state.access_count_incremented_this_turn == []
        assert state._last_turn_count == 2

    def test_backward_compat_load_without_new_fields(self, tmp_path):
        """Loading old state JSON without H-3 fields uses defaults (not error)."""
        import json

        session_id = "compat-test-h3"
        old_data = {
            "session_id": session_id,
            "injected_point_ids": ["a"],
            "last_query_embedding": None,
            "topic_drift": 0.5,
            "turn_count": 3,
            "total_tokens_injected": 100,
            "error_state": None,
            "compact_count": 1,
            # Deliberately omitting access_count_incremented_this_turn and _last_turn_count
        }
        path = InjectionSessionState._state_path(session_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(old_data))

            state = InjectionSessionState.load(session_id)

            # Old fields preserved
            assert state.session_id == session_id
            assert state.turn_count == 3
            assert state.compact_count == 1

            # New fields default
            assert state.access_count_incremented_this_turn == []
            assert state._last_turn_count == 0
        finally:
            import contextlib

            with contextlib.suppress(Exception):
                path.unlink(missing_ok=True)

    def test_save_and_load_with_dedup_fields(self):
        """Save and reload preserves the dedup fields."""
        session_id = "save-load-dedup"
        state = InjectionSessionState(session_id=session_id)
        state.access_count_incremented_this_turn = ["pid-x", "pid-y"]
        state._last_turn_count = 5
        state.turn_count = 5

        try:
            state.save()
            loaded = InjectionSessionState.load(session_id)
            assert loaded.access_count_incremented_this_turn == ["pid-x", "pid-y"]
            assert loaded._last_turn_count == 5
        finally:
            import contextlib

            with contextlib.suppress(Exception):
                InjectionSessionState._state_path(session_id).unlink(missing_ok=True)
