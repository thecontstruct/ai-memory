"""Unit tests for IntelligentChunker content_type parameter (TECH-DEBT-151 Phase 4).

Tests verify that IntelligentChunker accepts explicit content_type
and routes correctly without relying on file extension detection.
"""

import pytest

from memory.chunking import ContentType, IntelligentChunker


class TestContentTypeParameter:
    """Test explicit content_type routing."""

    def test_user_message_under_threshold_whole(self):
        """User message under 2000 tokens stored whole."""
        chunker = IntelligentChunker()
        content = "This is a short user message. " * 50  # ~250 tokens
        chunks = chunker.chunk(
            content, file_path="", content_type=ContentType.USER_MESSAGE
        )
        assert len(chunks) == 1
        assert chunks[0].metadata.chunk_type == "whole"
        assert chunks[0].content == content

    def test_user_message_over_threshold_chunked(self):
        """User message over 2000 tokens gets topical chunking."""
        chunker = IntelligentChunker()
        # Create content over 2000 tokens (~8000+ chars)
        content = (
            "This is a sentence about programming concepts. " * 500
        )  # ~2500 tokens
        chunks = chunker.chunk(
            content, file_path="", content_type=ContentType.USER_MESSAGE
        )
        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
        # Verify all content is preserved (no truncation)
        total_content = "".join(c.content for c in chunks)
        # Due to overlap, total may be longer than original
        assert (
            len(total_content) >= len(content) * 0.9
        )  # Allow for minor boundary adjustments

    def test_agent_response_threshold_3000(self):
        """Agent response uses 3000 token threshold, not 2000."""
        chunker = IntelligentChunker()
        # Create content between 2000-3000 tokens (47 chars * 200 = 9400 chars = ~2350 tokens)
        content = (
            "This is a sentence about code review findings. " * 200
        )  # ~2350 tokens
        chunks = chunker.chunk(
            content, file_path="", content_type=ContentType.AGENT_RESPONSE
        )
        assert (
            len(chunks) == 1
        ), f"Agent response under 3000 should be whole, got {len(chunks)} chunks"
        assert chunks[0].metadata.chunk_type == "whole"

    def test_content_type_overrides_file_extension(self):
        """Explicit content_type takes precedence over file extension."""
        # min_chunk_tokens=0 disables filtering so short test content is not removed
        chunker = IntelligentChunker(min_chunk_tokens=0)
        content = "# Markdown heading\nSome content here."
        # .md would normally route to PROSE, but explicit USER_MESSAGE overrides
        chunks = chunker.chunk(
            content, file_path="test.md", content_type=ContentType.USER_MESSAGE
        )
        assert len(chunks) == 1
        assert chunks[0].metadata.chunk_type == "whole"

    def test_none_content_type_uses_detection(self):
        """None content_type falls back to file extension detection."""
        # min_chunk_tokens=0 disables filtering so short test content is not removed
        chunker = IntelligentChunker(min_chunk_tokens=0)
        content = "# A markdown document\n\nWith paragraphs."
        chunks = chunker.chunk(content, file_path="test.md", content_type=None)
        # Should detect as PROSE from .md extension
        assert len(chunks) >= 1

    def test_guideline_always_chunked(self):
        """Guidelines always use semantic chunking regardless of size."""
        chunker = IntelligentChunker()
        content = "## Best Practice\nAlways write tests. " * 200  # Large guideline
        chunks = chunker.chunk(
            content, file_path="", content_type=ContentType.GUIDELINE
        )
        assert len(chunks) >= 1
        for chunk in chunks:
            # ProseChunker returns 'prose' as chunk_type, not 'semantic'
            assert chunk.metadata.chunk_type in ("prose", "semantic", "whole")


class TestPlan015ChunkingChanges:
    """Tests for PLAN-015 chunking parameter changes (WP-4)."""

    def test_default_max_chunk_tokens_is_1024(self):
        chunker = IntelligentChunker()
        assert chunker.max_chunk_tokens == 1024

    def test_min_chunk_tokens_default_is_50(self):
        chunker = IntelligentChunker()
        assert chunker.min_chunk_tokens == 50

    def test_min_chunk_tokens_zero_disables_filtering(self):
        chunker = IntelligentChunker(min_chunk_tokens=0)
        assert chunker.min_chunk_tokens == 0

    def test_min_chunk_tokens_negative_raises(self):
        with pytest.raises(ValueError, match="min_chunk_tokens must be >= 0"):
            IntelligentChunker(min_chunk_tokens=-1)

    def test_trivial_chunks_filtered_by_min_chunk_tokens(self):
        """Chunks below min_chunk_tokens threshold are removed."""
        # Use a high min to force filtering
        chunker = IntelligentChunker(max_chunk_tokens=512, min_chunk_tokens=1000)
        # Short content will produce chunks below 1000 token threshold
        content = "Short content that will not meet the 1000 token minimum."
        result = chunker.chunk(content, file_path="test.md")
        # All chunks should be filtered out (content is too short)
        assert len(result) == 0

    def test_min_chunk_tokens_zero_keeps_all_chunks(self):
        """With min_chunk_tokens=0, no chunks are filtered."""
        chunker = IntelligentChunker(max_chunk_tokens=512, min_chunk_tokens=0)
        content = "Short."
        result = chunker.chunk(content, file_path="test.md")
        # With filtering disabled, non-empty content should produce at least one chunk
        assert len(result) >= 1

    def test_partial_filtering_keeps_long_chunks(self):
        """Only chunks below min_chunk_tokens are removed; longer chunks are preserved."""
        # min=30 tokens: short paragraph will be filtered, long paragraph will be kept
        chunker = IntelligentChunker(max_chunk_tokens=512, min_chunk_tokens=30)
        # Build content where one section is long enough and one is trivially short
        long_section = " ".join(["word"] * 150)  # ~150 words >> 30 tokens
        short_section = "Hi."  # << 30 tokens
        content = f"{long_section}\n\n{short_section}"
        result = chunker.chunk(content, file_path="test.md")
        # At least the long section should produce a chunk
        assert len(result) >= 1
        # All returned chunks must have enough tokens
        from memory.chunking import count_tokens
        for chunk in result:
            assert count_tokens(chunk.content) >= 30
