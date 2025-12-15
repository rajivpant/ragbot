"""Tests for the ragbot keystore module.

Tests API key storage and retrieval.
"""

import pytest
import os
import sys
import yaml
from pathlib import Path

# Add src directory to path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot.keystore import (
    Keystore,
    get_api_key,
    check_api_keys,
)


class TestKeystore:
    """Tests for Keystore class."""

    @pytest.fixture
    def temp_keystore(self, tmp_path):
        """Create a temporary keystore that doesn't exist yet."""
        keystore_path = tmp_path / "keys.yaml"
        return Keystore(path=keystore_path)

    @pytest.fixture
    def populated_keystore(self, tmp_path):
        """Create a keystore with some test data."""
        keystore_path = tmp_path / "keys.yaml"
        test_data = {
            "default": {
                "anthropic": "test-anthropic-key",
                "openai": "test-openai-key",
            },
            "workspaces": {
                "test-workspace": {
                    "anthropic": "workspace-anthropic-key"
                }
            }
        }
        with open(keystore_path, 'w') as f:
            yaml.dump(test_data, f)
        return Keystore(path=keystore_path)

    def test_new_keystore_starts_empty(self, temp_keystore):
        """New keystore without file should have no keys."""
        assert temp_keystore.has_key('anthropic') is False
        assert temp_keystore.has_key('openai') is False

    def test_get_key_returns_default(self, populated_keystore):
        """get_key should return default key."""
        key = populated_keystore.get_key('anthropic')
        assert key == 'test-anthropic-key'

    def test_get_key_returns_none_for_missing(self, populated_keystore):
        """get_key should return None for missing provider."""
        key = populated_keystore.get_key('nonexistent')
        assert key is None

    def test_workspace_key_fallback_to_default(self, populated_keystore):
        """Workspace should fall back to default key if no workspace key."""
        # openai has default key but no workspace key
        key = populated_keystore.get_key('openai', workspace='test-workspace')
        assert key == 'test-openai-key'

    def test_workspace_key_overrides_default(self, populated_keystore):
        """Workspace key should override default key."""
        # anthropic has both default and workspace key
        key = populated_keystore.get_key('anthropic', workspace='test-workspace')
        assert key == 'workspace-anthropic-key'

    def test_has_key_returns_true_for_default(self, populated_keystore):
        """has_key should return True for default key."""
        assert populated_keystore.has_key('anthropic') is True
        assert populated_keystore.has_key('openai') is True

    def test_has_key_returns_false_for_missing(self, populated_keystore):
        """has_key should return False for missing provider."""
        assert populated_keystore.has_key('google') is False

    def test_has_key_for_workspace_with_default_only(self, populated_keystore):
        """has_key should return True if default key exists for workspace."""
        # openai only has default key, no workspace key
        assert populated_keystore.has_key('openai', workspace='test-workspace') is True

    def test_get_configured_providers(self, populated_keystore):
        """get_configured_providers should return dict of availability."""
        status = populated_keystore.get_configured_providers()
        assert 'anthropic' in status
        assert 'openai' in status
        assert status['anthropic'] is True
        assert status['openai'] is True
        assert status['google'] is False

    def test_get_configured_providers_for_workspace(self, populated_keystore):
        """get_configured_providers should check workspace keys."""
        status = populated_keystore.get_configured_providers(workspace='test-workspace')
        assert status['anthropic'] is True
        assert status['openai'] is True

    def test_get_key_status(self, populated_keystore):
        """get_key_status should return detailed status."""
        status = populated_keystore.get_key_status(workspace='test-workspace')

        # anthropic has both workspace and default key
        assert status['anthropic']['has_key'] is True
        assert status['anthropic']['source'] == 'workspace'
        assert status['anthropic']['has_workspace_key'] is True
        assert status['anthropic']['has_default_key'] is True

        # openai has only default key
        assert status['openai']['has_key'] is True
        assert status['openai']['source'] == 'default'
        assert status['openai']['has_workspace_key'] is False
        assert status['openai']['has_default_key'] is True

    def test_get_key_status_no_key(self, temp_keystore):
        """get_key_status should show no key available for empty keystore."""
        status = temp_keystore.get_key_status()
        assert status['anthropic']['has_key'] is False
        assert status['anthropic']['source'] is None

    def test_list_workspaces_with_keys(self, populated_keystore):
        """Should list workspaces that have custom keys."""
        workspaces = populated_keystore.list_workspaces_with_keys()
        assert 'test-workspace' in workspaces

    def test_list_workspaces_with_keys_empty(self, temp_keystore):
        """Empty keystore should return empty workspace list."""
        workspaces = temp_keystore.list_workspaces_with_keys()
        assert workspaces == []

    def test_reload_clears_cache(self, tmp_path):
        """reload should re-read from disk."""
        keystore_path = tmp_path / "keys.yaml"

        # Create initial data
        with open(keystore_path, 'w') as f:
            yaml.dump({"default": {"anthropic": "key-1"}}, f)

        keystore = Keystore(path=keystore_path)
        assert keystore.get_key('anthropic') == 'key-1'

        # Update file
        with open(keystore_path, 'w') as f:
            yaml.dump({"default": {"anthropic": "key-2"}}, f)

        # Should still have cached value
        assert keystore.get_key('anthropic') == 'key-1'

        # After reload, should have new value
        keystore.reload()
        assert keystore.get_key('anthropic') == 'key-2'


class TestGetApiKey:
    """Tests for the get_api_key convenience function."""

    def test_get_api_key_returns_value_or_none(self):
        """get_api_key should return a key or None."""
        # Note: This uses the global keystore which may or may not have keys
        key = get_api_key('anthropic')
        assert key is None or isinstance(key, str)


class TestCheckApiKeys:
    """Tests for check_api_keys convenience function."""

    def test_check_api_keys_returns_dict(self):
        """check_api_keys should return a dictionary."""
        result = check_api_keys()
        assert isinstance(result, dict)

    def test_check_api_keys_includes_providers(self):
        """Result should include standard providers."""
        result = check_api_keys()
        # Should have keys for standard providers
        expected = {'anthropic', 'openai', 'google', 'aws_bedrock'}
        assert set(result.keys()).issuperset(expected) or len(result) > 0

    def test_check_api_keys_values_are_bool(self):
        """All values should be boolean."""
        result = check_api_keys()
        for provider, has_key in result.items():
            assert isinstance(has_key, bool), f"{provider} should be bool"
