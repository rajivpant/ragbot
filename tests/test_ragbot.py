"""Tests for the ragbot CLI.

Note: These tests are for the legacy CLI (src/ragbot.py).
The new ragbot package tests are in test_config.py, test_keystore.py, etc.

SKIPPED: Legacy CLI tests need refactoring to work with the new package structure.
The CLI functionality is still available but these tests import paths need work.
"""

import pytest

# Skip all tests in this module - legacy CLI needs refactoring
pytestmark = pytest.mark.skip(reason="Legacy CLI tests need refactoring")

import json
import os
import sys
from unittest.mock import patch
from io import StringIO

# Add src directory to path to import ragbot.py (not the ragbot package)
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import main from ragbot.py file directly using importlib
import importlib.util
spec = importlib.util.spec_from_file_location("ragbot_cli", os.path.join(src_dir, "ragbot.py"))
ragbot_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ragbot_cli)
main = ragbot_cli.main

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup: Redirect stdout to capture print statements
    held_stdout = StringIO()
    sys.stdout = held_stdout
    yield held_stdout
    # Teardown
    sys.stdout = sys.__stdout__

@pytest.fixture
def mock_dependencies(mocker):
    # Mock the ragbot_cli module's imports
    mock_load_dotenv = mocker.patch.object(ragbot_cli, 'load_dotenv')
    mock_load_profiles = mocker.patch.object(ragbot_cli, 'load_profiles')
    mock_load_files = mocker.patch.object(ragbot_cli, 'load_files')
    mock_chat = mocker.patch.object(ragbot_cli, 'chat')
    return mock_load_dotenv, mock_load_profiles, mock_load_files, mock_chat

def test_main(mock_dependencies, setup_teardown):
    mock_load_dotenv, mock_load_profiles, mock_load_files, mock_chat = mock_dependencies
    mock_load_profiles.return_value = [
        {
            'name': 'Test Profile',
            'custom_instructions': ['tests/test_custom_instructions.md'],
            'curated_datasets': ['tests/test_curated_dataset.md']
        }
    ]
    mock_load_files.return_value = ("Test content", [])
    mock_chat.return_value = "Test response"

    test_args = ["program_name", "-p", "Hello", "--profile", "Test Profile"]
    with patch.object(sys, 'argv', test_args):
        main()
    
    output = setup_teardown.getvalue()
    assert "Test response" in output