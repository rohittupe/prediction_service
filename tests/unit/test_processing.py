import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
import asyncio
from uuid import UUID

import sys
import os

import app.machine_learning.predict
from tests.utils.api_helpers import JobStatus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from app.application.app import Application
from app.models.prediction_request import PredictionRequest


pytestmark = [pytest.mark.unit, pytest.mark.processing]


class TestApplication:
    """Unit tests for the Application class"""
    
    @pytest.fixture
    def app(self):
        """Create an Application instance for testing"""
        return Application()
    
    @pytest.fixture
    def client(self, app):
        """Create a test client for the application"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_prediction_request(self):
        """Create a sample prediction request"""
        return PredictionRequest(
            member_id="test_123",
            balance=1000,
            last_purchase_size=50,
            last_purchase_date="2024-01-15"
        )
    
    @pytest.mark.asyncio
    async def test_ping_success(self, app):
        """Test ping endpoint returns ok status"""
        result = await app.ping()
        assert result == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_predict_success(self, app, sample_prediction_request):
        """Test predict endpoint with successful prediction"""
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {
                "average_transaction_size": 525.0,
                "probability_to_transact": 0.8
            }
            
            result = await app.predict(sample_prediction_request)
            
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
            mock_get_predictions.assert_called_once_with(sample_prediction_request)
    
    @pytest.mark.asyncio
    async def test_predict_creates_job(self, app, sample_prediction_request):
        """Test predict creates a job entry"""
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {
                "average_transaction_size": 525.0,
                "probability_to_transact": 0.8
            }
            
            # Check jobs before prediction
            initial_job_count = len(app.jobs)
            
            await app.predict(sample_prediction_request)
            
            # Verify job was created
            assert len(app.jobs) == initial_job_count + 1
            
            # Check job has proper initial status
            job_id = list(app.jobs.keys())[-1]
            assert app.jobs[job_id]["result"] is None

    @pytest.mark.asyncio
    async def test_predict_creates_job_status(self, app, sample_prediction_request):
        """Test predict creates a job entry"""
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {
                "average_transaction_size": 525.0,
                "probability_to_transact": 0.8
            }

            await app.predict(sample_prediction_request)

            # Check job has proper initial status
            job_id = list(app.jobs.keys())[-1]
            assert app.jobs[job_id]["status"] == JobStatus.PENDING.value
            assert app.jobs[job_id]["result"] is None

    @pytest.mark.asyncio
    async def test_predict_generates_valid_uuid(self, app, sample_prediction_request):
        """Test predict generates valid UUID for job ID"""
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {"average_transaction_size": 525.0}
            
            await app.predict(sample_prediction_request)
            
            # Get the created job ID
            job_id = list(app.jobs.keys())[-1]
            
            # Verify it's a valid UUID
            try:
                UUID(job_id)
            except ValueError:
                pytest.fail(f"Invalid UUID generated: {job_id}")
    
    @pytest.mark.asyncio
    async def test_process_job_success(self, app, sample_prediction_request):
        """Test process_job completes successfully"""
        job_id = "test_job_123"
        app.jobs[job_id] = {"status": JobStatus.PENDING.value, "result": None}
        
        with patch.object(app, 'predict', new_callable=AsyncMock) as mock_predict:
            mock_predict.return_value = {
                "average_transaction_size": 525.0,
                "probability_to_transact": 0.8
            }
            
            await app.process_job(job_id, sample_prediction_request)
            
            assert app.jobs[job_id]["status"] == JobStatus.COMPLETED.value
            assert app.jobs[job_id]["result"] == mock_predict.return_value
    
    @pytest.mark.asyncio
    async def test_process_job_failure(self, app, sample_prediction_request):
        """Test process_job handles exceptions"""
        job_id = "test_job_456"
        app.jobs[job_id] = {"status": JobStatus.PENDING.value, "result": None}
        
        with patch.object(app, 'predict', new_callable=AsyncMock) as mock_predict:
            mock_predict.side_effect = Exception("Prediction failed")
            
            await app.process_job(job_id, sample_prediction_request)
            
            assert app.jobs[job_id]["status"] == JobStatus.FAILED.value
            assert app.jobs[job_id]["result"] == "Prediction failed"
    
    @pytest.mark.asyncio
    async def test_get_status_success(self, app):
        """Test get_status returns correct status"""
        job_id = "test_job_789"
        app.jobs[job_id] = {"status": JobStatus.COMPLETED.value, "result": {"test": "result"}}
        
        result = await app.get_status(job_id)
        
        assert result == {"job_id": job_id, "status": JobStatus.COMPLETED.value}
    
    @pytest.mark.asyncio
    async def test_get_status_not_found(self, app):
        """Test get_status raises 404 for unknown job ID"""
        with pytest.raises(HTTPException) as exc_info:
            await app.get_status("unknown_job_id")
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Job ID not found"
    
    @pytest.mark.asyncio
    async def test_get_result_success(self, app):
        """Test get_result returns result for completed job"""
        job_id = "test_job_completed"
        expected_result = {
            "average_transaction_size": 100.0,
            "probability_to_transact": 0.5
        }
        app.jobs[job_id] = {"status": JobStatus.COMPLETED.value, "result": expected_result}
        
        result = await app.get_result(job_id)
        
        assert result == {"job_id": job_id, "result": expected_result}
    
    @pytest.mark.asyncio
    async def test_get_result_not_found(self, app):
        """Test get_result raises 404 for unknown job ID"""
        with pytest.raises(HTTPException) as exc_info:
            await app.get_result("unknown_job_id")
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Job ID not found"
    
    @pytest.mark.asyncio
    async def test_get_result_failed_job(self, app):
        """Test get_result raises 500 for failed job"""
        job_id = "test_job_failed"
        app.jobs[job_id] = {"status": JobStatus.FAILED.value, "result": "Error message"}
        
        with pytest.raises(HTTPException) as exc_info:
            await app.get_result(job_id)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Unknown error occurred during prediction"
    
    @pytest.mark.asyncio
    async def test_get_result_processing_job(self, app):
        """Test get_result raises 400 for still processing job"""
        job_id = "test_job_processing"
        app.jobs[job_id] = {"status": JobStatus.PENDING.value, "result": None}
        
        with pytest.raises(HTTPException) as exc_info:
            await app.get_result(job_id)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Result not ready"
    
    @pytest.mark.parametrize("status", [JobStatus.PENDING.value, "pending", "queued"])
    @pytest.mark.asyncio
    async def test_get_result_not_ready_statuses(self, app, status):
        """Test get_result raises 400 for various not-ready statuses"""
        job_id = f"test_job_{status}"
        app.jobs[job_id] = {"status": status, "result": None}
        
        with pytest.raises(HTTPException) as exc_info:
            await app.get_result(job_id)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Result not ready"
    
    def test_application_initialization(self, app):
        """Test Application properly initializes with routes"""
        # Check that jobs dictionary is initialized
        app.jobs.clear()
        assert hasattr(app, 'jobs')
        assert isinstance(app.jobs, dict)
        assert len(app.jobs) == 0
        
        # Check routes are registered
        routes = [route.path for route in app.routes]
        assert "/predict" in routes
        assert "/status/{job_id}" in routes
        assert "/result/{job_id}" in routes
        assert "/ping" in routes
    
    @pytest.mark.asyncio
    async def test_predict_with_missing_optional_fields(self, app):
        """Test predict with minimal prediction request"""
        minimal_request = PredictionRequest(member_id="test_minimal")
        
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {
                "average_transaction_size": 0.0,
                "probability_to_transact": 0.0
            }
            
            result = await app.predict(minimal_request)
            
            assert result is not None
            mock_get_predictions.assert_called_once_with(minimal_request)
    
    @pytest.mark.asyncio
    async def test_concurrent_predictions(self, app, sample_prediction_request):
        """Test multiple concurrent predictions"""
        with patch('machine_learning.predict.get_predictions') as mock_get_predictions:
            mock_get_predictions.return_value = {
                "average_transaction_size": 525.0,
                "probability_to_transact": 0.8
            }
            
            # Run multiple predictions concurrently
            tasks = [app.predict(sample_prediction_request) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify all predictions succeeded
            assert len(results) == 5
            assert all("average_transaction_size" in r for r in results)
            
            # Verify correct number of jobs created
            assert len(app.jobs) >= 5

    @pytest.mark.parametrize("invalid_date,expected_error,scenario", [
        ("invalid-date", "time data", "invalid date"),
        ("2024-13-01", "time data", "Invalid month"),
        ("2024-01-32", "time data", "Invalid day"),  # Return unconverted data remains: 2 instead of time data
        ("2024/01/01", "time data", "Wrong format"),
    ])
    @pytest.mark.asyncio
    async def test_invalid_date_formats_raise_error(self, mock_random, invalid_date, expected_error, scenario):
        """Test various invalid date formats."""
        mock_random.return_value = 0.5  # Ensure no random failure

        request = PredictionRequest(
            member_id="test123",
            balance=1000,
            last_purchase_size=500,
            last_purchase_date=invalid_date
        )

        with pytest.raises(ValueError) as exc_info:
            await app.machine_learning.predict.get_predictions(request)

        assert expected_error in str(exc_info.value)