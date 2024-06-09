import pytest
from ragbot_streamlit import get_token_counts, find_closest_max_tokens

def test_get_token_counts():
    custom_instruction_path = ['tests/test_custom_instructions.md']
    curated_dataset_path = ['tests/test_curated_dataset.md']
    engine = 'openai'
    model = 'gpt-4-turbo'
    custom_instructions_tokens, curated_datasets_tokens, max_input_tokens = get_token_counts(custom_instruction_path, curated_dataset_path, engine, model)
    assert custom_instructions_tokens > 0
    assert curated_datasets_tokens > 0

def test_find_closest_max_tokens():
    max_tokens_mapping = {str(2**i): 2**i for i in range(8, 17)}
    closest_option = find_closest_max_tokens(1500, max_tokens_mapping)
    assert closest_option == '1024'