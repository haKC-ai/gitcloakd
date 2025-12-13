"""Tests for gitcloakd core functionality."""

import pytest
import tempfile
from pathlib import Path

from gitcloakd.core.config import Config, UserConfig, AgentConfig, AlertConfig
from gitcloakd.core.encryption import GitCrypted


class TestConfig:
    """Tests for Config class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.version == "1.0"
        assert config.initialized is False
        assert len(config.auto_encrypt_patterns) > 0

    def test_add_user(self):
        """Test adding a user."""
        config = Config()
        user = UserConfig(
            name="Test User",
            email="test@example.com",
            gpg_key_id="ABC123",
            role="collaborator"
        )
        config.add_user(user)
        assert len(config.users) == 1
        assert config.users[0].email == "test@example.com"

    def test_remove_user(self):
        """Test removing a user."""
        config = Config()
        user = UserConfig(
            name="Test User",
            email="test@example.com",
            gpg_key_id="ABC123"
        )
        config.add_user(user)
        assert config.remove_user("test@example.com")
        assert len(config.users) == 0

    def test_add_agent(self):
        """Test adding an agent."""
        config = Config()
        agent = AgentConfig(
            name="claude-code",
            type="claude"
        )
        config.add_agent(agent)
        assert len(config.agents) == 1
        assert config.agents[0].name == "claude-code"

    def test_config_serialization(self):
        """Test config to/from dict."""
        config = Config()
        config.owner_email = "owner@example.com"
        config.add_user(UserConfig(
            name="Test",
            email="test@example.com",
            gpg_key_id="ABC"
        ))

        # Convert to dict and back
        data = config._to_dict()
        restored = Config._from_dict(data)

        assert restored.owner_email == config.owner_email
        assert len(restored.users) == 1


class TestGitCrypted:
    """Tests for GitCrypted class."""

    def test_is_initialized_false(self):
        """Test is_initialized returns False for new repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gc = GitCrypted(tmpdir)
            assert gc.is_initialized() is False

    def test_analyze_exposure_empty(self):
        """Test analyze_exposure on empty repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gc = GitCrypted(tmpdir)
            gc.config.auto_encrypt_patterns = ["*.env"]

            results = gc.analyze_exposure()
            assert "sensitive_files" in results
            assert "recommendations" in results
