"""Pytest configuration for Ragbot tests.

Test categories:
- Unit tests (test_config.py, test_keystore.py, test_helpers.py): No external dependencies
- API tests (test_api.py): Uses TestClient, no real LLM calls
- Integration tests (test_models_integration.py): Makes real LLM API calls

Run all unit tests:
    pytest tests/ --ignore=tests/test_models_integration.py

Run integration tests (requires API keys):
    pytest tests/test_models_integration.py -v

Run all tests including expensive models:
    TEST_EXPENSIVE_MODELS=1 pytest tests/
"""

import pytest
import os
import sys

# Add src directory to Python path for all tests
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require API keys)"
    )
    config.addinivalue_line(
        "markers", "expensive: marks tests as expensive (use TEST_EXPENSIVE_MODELS=1 to run)"
    )
