"""Pytest configuration and fixtures."""
import pytest
import sys
import os
from fastapi.testclient import TestClient

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.main import app as application
from tests.utils.test_data import PredictionDataFactory, TestScenarios
from tests.utils.test_logger import get_test_logger

APPLICATION_URL = os.getenv("SERVICE_URL", "http://localhost:8000")
# os.environ['DISABLE_RANDOM_FAILURES'] = 'true'


def pytest_configure(config):
    """Configure pytest with custom settings."""
    config._metadata['Project'] = 'ML Prediction Service'
    config._metadata['Test Framework'] = 'pytest'
    config._metadata['Async Framework'] = 'asyncio'

    if hasattr(config, '_html'):
        config._html.title = "ML Prediction Service - Test Execution Report"


def pytest_html_report_title(report):
    """Set custom HTML report title."""
    report.title = "ML Prediction Service - Test Execution Report"


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(application)


@pytest.fixture
def sample_prediction_request():
    """Sample prediction request for testing."""
    return PredictionDataFactory.create_valid_prediction()


@pytest.fixture
def mock_random(mocker):
    """Mock random.random to control test behavior."""
    return mocker.patch("random.random")


@pytest.fixture
def test_logger():
    """Get test logger for the current test."""
    return get_test_logger("pytest")


def pytest_runtest_makereport(item, call):
    """Add custom information to test reports."""
    if call.when == "call":
        markers = [mark.name for mark in item.iter_markers()]
        item.user_properties.append(("markers", markers))
        
        item.user_properties.append(("module", item.module.__name__))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "stress: Stress and performance tests")
    config.addinivalue_line("markers", "smoke: Quick smoke tests")