"""Tests for PLAN-015 config additions to MemoryConfig."""
from memory.config import MemoryConfig, reset_config


class TestPlan015Defaults:
    """Verify new PLAN-015 config fields load with correct defaults."""

    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_max_retrievals_default_is_10(self):
        config = MemoryConfig()
        assert config.max_retrievals == 10

    def test_injection_hard_floor_default(self):
        config = MemoryConfig()
        assert config.injection_hard_floor == 0.45

    def test_injection_threshold_conventions_default(self):
        config = MemoryConfig()
        assert config.injection_threshold_conventions == 0.65

    def test_injection_threshold_code_patterns_default(self):
        config = MemoryConfig()
        assert config.injection_threshold_code_patterns == 0.55

    def test_injection_threshold_discussions_default(self):
        config = MemoryConfig()
        assert config.injection_threshold_discussions == 0.60

    def test_freshness_penalty_defaults(self):
        config = MemoryConfig()
        assert config.freshness_penalty_fresh == 1.0
        assert config.freshness_penalty_aging == 0.9
        assert config.freshness_penalty_stale == 0.0
        assert config.freshness_penalty_expired == 0.0
        assert config.freshness_penalty_unverified == 1.0
        assert config.freshness_penalty_unknown == 0.8

    def test_decay_type_overrides_includes_architecture_decision(self):
        config = MemoryConfig()
        overrides = config.get_decay_type_overrides()
        assert "architecture_decision" in overrides
        assert overrides["architecture_decision"] == 90


class TestGetFreshnessPenalty:
    """Test get_freshness_penalty helper method."""

    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_fresh_returns_1_0(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("fresh") == 1.0

    def test_stale_returns_0_0(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("stale") == 0.0

    def test_expired_returns_0_0(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("expired") == 0.0

    def test_case_insensitive(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("FRESH") == config.get_freshness_penalty("fresh")
        assert config.get_freshness_penalty("STALE") == config.get_freshness_penalty("stale")

    def test_unknown_status_returns_unknown_penalty(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("bogus_status") == config.freshness_penalty_unknown

    def test_empty_string_treated_as_unknown(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty("") == config.freshness_penalty_unknown

    def test_none_treated_as_unknown(self):
        config = MemoryConfig()
        assert config.get_freshness_penalty(None) == config.freshness_penalty_unknown
