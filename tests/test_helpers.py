import pytest
from helpers import load_config, load_profiles, process_file, load_files, human_format, count_tokens, count_custom_instructions_tokens, count_curated_datasets_tokens
import os

@pytest.fixture
def setup_files():
    test_config_file = 'test_engines.yaml'
    test_profiles_file = 'test_profiles.yaml'
    test_custom_instruction_file = 'test_custom_instructions.md'
    test_curated_dataset_file = 'test_curated_dataset.md'

    # Create test configuration file
    with open(test_config_file, 'w') as f:
        f.write("""
        engines:
          - name: openai
            api_key_name: OPENAI_API_KEY
            models:
              - name: gpt-4-turbo
                supports_system_role: true
                max_temperature: 1
                temperature: 0.75
            default_model: gpt-4-turbo
        default: openai
        temperature_settings:
          precise: 0.25
          balanced: 0.50
          creative: 0.75
        """)

    # Create test profiles file
    with open(test_profiles_file, 'w') as f:
        f.write("""
        profiles:
          - name: "Test Profile"
            custom_instructions:
              - "{}"
            curated_datasets:
              - "{}"
        """.format(test_custom_instruction_file, test_curated_dataset_file))

    # Create test custom instruction file
    with open(test_custom_instruction_file, 'w') as f:
        f.write("This is a test custom instruction.")

    # Create test curated dataset file
    with open(test_curated_dataset_file, 'w') as f:
        f.write("This is a test curated dataset.")

    yield test_config_file, test_profiles_file, test_custom_instruction_file, test_curated_dataset_file

    os.remove(test_config_file)
    os.remove(test_profiles_file)
    os.remove(test_custom_instruction_file)
    os.remove(test_curated_dataset_file)

def test_load_config(setup_files):
    test_config_file, *_ = setup_files
    config = load_config(test_config_file)
    assert 'engines' in config
    assert config['default'] == 'openai'

def test_load_profiles(setup_files):
    _, test_profiles_file, *_ = setup_files
    profiles = load_profiles(test_profiles_file)
    assert len(profiles) == 1

def test_process_file(setup_files):
    *_, test_custom_instruction_file = setup_files
    content, path = process_file(test_custom_instruction_file, 'custom_instructions')
    assert "<document:" in content
    assert "</document:" in content

def test_load_files(setup_files):
    *_, test_custom_instruction_file = setup_files
    content, files = load_files([test_custom_instruction_file], 'custom_instructions')
    assert 'This is a test custom instruction.' in content

def test_human_format():
    formatted = human_format(1500)
    assert formatted == '1.5k'

def test_count_tokens(setup_files):
    *_, test_custom_instruction_file = setup_files
    tokens = count_tokens([test_custom_instruction_file])
    assert tokens > 0

def test_count_custom_instructions_tokens(setup_files):
    *_, test_custom_instruction_file = setup_files
    tokens = count_custom_instructions_tokens([test_custom_instruction_file])
    assert tokens > 0

def test_count_curated_datasets_tokens(setup_files):
    *_, test_curated_dataset_file = setup_files
    tokens = count_curated_datasets_tokens([test_curated_dataset_file])
    assert tokens > 0