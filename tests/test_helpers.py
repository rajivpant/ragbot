"""Tests for the helpers module.

Tests legacy helper functions that provide backwards compatibility.
"""

import pytest
import os
import sys

# Add src directory to path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from helpers import (
    load_config, process_file, load_files,
    human_format, count_tokens_for_files,
    count_custom_instructions_tokens
)

@pytest.fixture
def setup_files():
    test_config_file = 'test_engines.yaml'
    test_custom_instruction_file = 'test_custom_instructions.md'
    test_curated_dataset_file = 'test_curated_dataset.md'

    # Create test configuration file
    # Note: Using test model names that match engines.yaml structure
    # Model name is arbitrary for config loading tests - doesn't need to be real
    with open(test_config_file, 'w') as f:
        f.write("""
        engines:
          - name: anthropic
            api_key_name: ANTHROPIC_API_KEY
            models:
              - name: test-model
                supports_system_role: true
                max_temperature: 1
                temperature: 0.75
                max_input_tokens: 200000
                max_output_tokens: 64000
            default_model: test-model
        default: anthropic
        temperature_settings:
          precise: 0.25
          balanced: 0.50
          creative: 0.75
        """)

    # Create test custom instruction file
    with open(test_custom_instruction_file, 'w') as f:
        f.write("This is a test custom instruction.")

    # Create test curated dataset file
    with open(test_curated_dataset_file, 'w') as f:
        f.write("This is a test curated dataset.")

    yield test_config_file, test_custom_instruction_file, test_curated_dataset_file

    os.remove(test_config_file)
    os.remove(test_custom_instruction_file)
    os.remove(test_curated_dataset_file)

def test_load_config(setup_files):
    test_config_file, *_ = setup_files
    config = load_config(test_config_file)
    assert 'engines' in config
    assert config['default'] == 'anthropic'

def test_process_file(setup_files):
    test_config_file, test_custom_instruction_file, test_curated_dataset_file = setup_files
    content, path = process_file(test_custom_instruction_file, 'custom_instructions', 1)
    # Verify new standard document block format
    assert '<document index="1">' in content
    assert '<source>' in content
    assert '<document_type>custom_instructions</document_type>' in content
    assert '<document_content>' in content
    assert '</document_content>' in content
    assert '</document>' in content
    assert test_custom_instruction_file in content

def test_load_files(setup_files):
    test_config_file, test_custom_instruction_file, test_curated_dataset_file = setup_files
    content, files = load_files([test_custom_instruction_file], 'custom_instructions')
    # Verify documents container and document structure
    assert '<documents>' in content
    assert '</documents>' in content
    assert '<document index="1">' in content
    assert '<source>' in content
    assert '<document_type>custom_instructions</document_type>' in content
    assert 'This is a test custom instruction.' in content

def test_human_format():
    formatted = human_format(1500)
    assert formatted == '1.5k'

def test_count_tokens_for_files(setup_files):
    test_config_file, test_custom_instruction_file, test_curated_dataset_file = setup_files
    tokens = count_tokens_for_files([test_custom_instruction_file])
    assert tokens > 0

def test_count_custom_instructions_tokens(setup_files):
    test_config_file, test_custom_instruction_file, test_curated_dataset_file = setup_files
    tokens = count_custom_instructions_tokens([test_custom_instruction_file])
    assert tokens > 0

