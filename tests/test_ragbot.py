import pytest
import json
from ragbot import main
from unittest.mock import patch
import sys
from io import StringIO

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
    mock_load_dotenv = mocker.patch('ragbot.load_dotenv')
    mock_load_profiles = mocker.patch('ragbot.load_profiles')
    mock_load_files = mocker.patch('ragbot.load_files')
    mock_chat = mocker.patch('ragbot.chat')
    mocker.patch('ragbot.openai.api_key', 'test_openai_key')
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