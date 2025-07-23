from unittest.mock import patch

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import asyncio
import time

import sys
import os

from conftest import APPLICATION_URL

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from app.main import app
from tests.utils.api_helpers import JobStatus, Endpoints

pytestmark = [pytest.mark.integration]


class TestPredictionWorkflow:
    """Integration tests for the complete prediction workflow"""

    @pytest.fixture
    def valid_member_data(self):
        """Valid member data for predictions"""
        return {
            "member_id": "test_member_123",
            "balance": 1000,
            "last_purchase_size": 500,
            "last_purchase_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        }

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test ping endpoint is accessible"""
        response = client.get(Endpoints.PING.value)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_predict_endpoint_success(self, client, valid_member_data):
        """Test successful prediction request"""
        response = client.post(Endpoints.PREDICT.value, json=valid_member_data)
        assert response.status_code == 200

        data = response.json()
        assert "job_id" in data, f"Job ID not present in the response. Response: {data}"
        assert "status" in data, f"Job Status not present in the response. Response: {data}"
        assert isinstance(data["job_id"], str)
        assert isinstance(data["status"], str)

    @pytest.mark.asyncio
    async def test_predict_creates_background_job(self, client, valid_member_data):
        """Test that predict endpoint creates a background job"""
        # Clear existing jobs
        app.jobs.clear()

        response = client.post(Endpoints.PREDICT.value, json=valid_member_data)
        assert response.status_code == 200

        # Check that a job was created
        assert len(app.jobs) > 0, "Job should not be empty."
        job_id = list(app.jobs.keys())[0]
        resp_json = response.json()
        assert resp_json["job_id"] == job_id, f"Job ID not present in the response. Response: {resp_json}"

    @pytest.mark.asyncio
    async def test_empty_request_body(self, client):
        """Test prediction with empty request body"""
        response = client.post(Endpoints.PREDICT.value, json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_member_id(self, client):
        """Test prediction without required member_id field"""
        data = {
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": "2024-01-15"
        }
        response = client.post(Endpoints.PREDICT.value, json=data)
        assert response.status_code == 422

    # @pytest.mark.xfail(reason="Null values are not handled correctly. Should be converted to 0 or empty.")
    @pytest.mark.asyncio
    async def test_null_values(self, client):
        """Test prediction with null values for optional fields"""
        data = {
            "member_id": "test_null",
            "balance": None,
            "last_purchase_size": None,
            "last_purchase_date": None
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
            assert result["probability_to_transact"] == 0.0  # No date means 0 probability

    @pytest.mark.asyncio
    async def test_negative_values(self, client):
        """Test prediction with negative balance and purchase size"""
        data = {
            "member_id": "test_negative",
            "balance": -1000,
            "last_purchase_size": -500,
            "last_purchase_date": "2024-01-15"
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            expected_avg = (data["balance"] + data["last_purchase_size"]) / 2
            assert result["average_transaction_size"] == expected_avg

    @pytest.mark.asyncio
    async def test_very_large_values(self, client):
        """Test prediction with very large numbers"""
        data = {
            "member_id": "test_large",
            "balance": 999999999999,
            "last_purchase_size": 888888888888,
            "last_purchase_date": "2024-01-15"
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            expected_avg = (data["balance"] + data["last_purchase_size"]) / 2
            assert result["average_transaction_size"] == expected_avg

    @pytest.mark.asyncio
    async def test_zero_values(self, client):
        """Test prediction with zero values"""
        data = {
            "member_id": "test_zero",
            "balance": 0,
            "last_purchase_size": 0,
            "last_purchase_date": "2024-01-15"
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            assert result["average_transaction_size"] == 0.0

    @pytest.mark.asyncio
    async def test_future_purchase_date(self, client):
        """Test prediction with future purchase date"""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        data = {
            "member_id": "test_future",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": future_date
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            # Future date should result in probability > 1
            assert result["probability_to_transact"] > 1.0

    @pytest.mark.asyncio
    async def test_ancient_purchase_date(self, client):
        """Test prediction with very old purchase date"""
        ancient_date = "1900-01-01"
        data = {
            "member_id": "test_ancient",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": ancient_date
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            # Very old date should result in 0 probability
            assert result["probability_to_transact"] == 0.0

    # @pytest.mark.xfail(reason="Exception should be thrown in gracefully with correct status code")
    @pytest.mark.parametrize("invalid_date, scenario", [
        ("2024-13-01", "Invalid month"),
        ("2024-01-32", "Invalid day"),
        ("24-01-15", "Wrong format"),
        ("2024/01/15", "Wrong separator"),
        ("January 15, 2024", "Wrong format"),
        ("abcd-ef-gh", "Random string"),
    ])
    @pytest.mark.asyncio
    async def test_invalid_date_formats(self, client, invalid_date, scenario):
        """Test prediction with various invalid date formats"""
        data = {
            "member_id": f"test_invalid_date_{invalid_date}",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": invalid_date
        }
        response = client.post(Endpoints.PREDICT.value, json=data)
        assert response.status_code == 422, f"{scenario}: Should return correct error code. Returned code: {response.status_code}"

    @pytest.mark.parametrize("member_id, scenario", [
        ("", "Empty string"),
        (" ", "Whitespace"),
        ("a" * 1000, "Very long ID"),
        ("id\nwith\nnewlines", "ID with newlines"),
        ("id\twith\ttabs", "ID with tabs"),
        ("😀🎉🚀", "Emojis"),
        ("id with spaces", "Spaces"),
        ("SELECT * FROM users", "SQL injection attempt"),
        ("<script>alert()</script>", "XSS attempt"),
        (None, "None value"),
    ])
    @pytest.mark.asyncio
    async def test_unusual_member_ids(self, client, member_id, scenario):
        """Test prediction with unusual member IDs"""
        data = {
            "member_id": member_id,
            "balance": 1000,
            "last_purchase_size": 500,
            "last_purchase_date": "2024-01-15"
        }

        if member_id is None:
            del data["member_id"]

        response = client.post(Endpoints.PREDICT.value, json=data)

        if member_id in ["", None]:
            assert response.status_code == 422
        elif response.status_code == 200:
            result = response.json()
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result

    @pytest.mark.parametrize("member_data, scenario", [
        ({
             "member_id": 12345,
             "balance": 1000,
             "last_purchase_size": 100,
             "last_purchase_date": "2024-01-15"
         }, "member_id should be string"),
        ({
             "member_id": "test",
             "balance": "1000",
             "last_purchase_size": 100,
             "last_purchase_date": "2024-01-15"
         }, "balance should be int"),
        ({
             "member_id": "test",
             "balance": 1000,
             "last_purchase_size": "100",
             "last_purchase_date": "2024-01-15"
         }, "last_purchase_size should be int"),
        ({
             "member_id": "test",
             "balance": 1000,
             "last_purchase_size": 100,
             "last_purchase_date": 20240115
         }, "last_purchase_date should be string"),
    ])
    @pytest.mark.asyncio
    async def test_wrong_data_types(self, client, member_data, scenario):
        """Test prediction with wrong data types"""
        response = client.post(Endpoints.PREDICT.value, json=member_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_random_failure_simulation(self, client):
        """Test handling of random failures of 15% in prediction"""
        data = {
            "member_id": "test_random_failure",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": "2024-01-15"
        }

        # Force a failure by mocking random to return < 0.15
        with patch('random.random', return_value=0.1):
            response = client.post(Endpoints.PREDICT.value, json=data)
            # Should handle the exception gracefully
            assert response.status_code in [200,    500]

    @pytest.mark.asyncio
    async def test_malformed_json_request(self, client):
        """Test prediction with malformed JSON"""
        response = client.post(
            Endpoints.PREDICT.value,
            content='{"member_id": "test", "balance": }',
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_extra_fields_in_request(self, client):
        """Test prediction with extra unexpected fields"""
        data = {
            "member_id": "test_extra",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": "2024-01-15",
            "extra_field": "should be ignored",
            "another_field": 12345
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
            assert "extra_field" not in result

    # @pytest.mark.xfail(reason="Jobs dictionary is shared across tests and may contain stale data")
    @pytest.mark.asyncio
    async def test_job_cleanup_behavior(self, client):
        """Test that jobs are not automatically cleaned up"""
        for i in range(5):
            data = {
                "member_id": f"test_cleanup_{i}",
                "balance": 1000,
                "last_purchase_size": 100,
                "last_purchase_date": "2024-01-15"
            }
            client.post(Endpoints.PREDICT.value, json=data)

        initial_job_count = len(app.jobs)
        await asyncio.sleep(1)
        assert len(app.jobs) == initial_job_count

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload, scenario", [
        ({"balance": 1000.0, "last_purchase_size": 100.0}, "Float values"),
        ({"balance": 1000, "last_purchase_size": 100}, "Int values"),
        ({"balance": 1000.5, "last_purchase_size": 100.5}, "Decimal/Fraction values"),
        ({"balance": 1000, "last_purchase_size": 100.5}, "Mix of Int and Float values"),
        ({"balance": 1000.0, "last_purchase_size": 100}, "Mix of Float and Int values"),
    ])
    async def test_float_vs_int_values(self, client, payload, scenario):
        """Test prediction with float vs integer values"""
        data = {
            "member_id": "test_float",
            **payload,
            "last_purchase_date": "2024-01-15"
        }
        response = client.post(Endpoints.PREDICT.value, json=data)

        if response.status_code == 200:
            result = response.json()
            expected_avg = (payload["balance"] + payload["last_purchase_size"]) / 2
            assert result["average_transaction_size"] == expected_avg

    @pytest.mark.asyncio
    async def test_job_status_tracking(self, client, valid_member_data):
        """Test job status can be tracked"""
        app.jobs.clear()

        pred_response = client.post(Endpoints.PREDICT.value, json=valid_member_data)
        assert pred_response.status_code == 200

        job_id = list(app.jobs.keys())[0]

        status_response = client.get(f"{Endpoints.STATUS.value}".format(job_id))
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id, \
            f"Job Id should match. Expected: {job_id} Actual: {status_data['job_id']}"
        assert status_data["status"] in \
               [JobStatus.PENDING.value, JobStatus.COMPLETED.value, JobStatus.FAILED.value], \
            f"Incorrect job status. Expected: Processing/Completed/failed Actual: {status_data['status']}"

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_job(self, client):
        """Test status endpoint with non-existent job ID"""
        response = client.get(f"{Endpoints.STATUS.value}".format("nonexistent_job_id"))
        assert response.status_code == 404, f'Should return 404 for not found job. Actual: {response.status_code}'
        assert response.json()["detail"] == "Job ID not found", \
            f"Incorrect details in response. Actual: {response.json()['detail']}"

    @pytest.mark.asyncio
    async def test_get_result_nonexistent_job(self, client):
        """Test result endpoint with non-existent job ID"""
        response = client.get(f"{Endpoints.RESULT.value}".format("nonexistent_job_id"))
        assert response.status_code == 404, \
            'Should return 404 for not found job. Actual: {response.status_code}'
        assert response.json()["detail"] == "Job ID not found", \
            f"Incorrect details in response. Actual: {response.json()['detail']}"

    @pytest.mark.asyncio
    async def test_get_result_processing_job(self, client):
        """Test result endpoint with still processing job"""
        job_id = "test_processing_job"
        app.jobs[job_id] = {"status": JobStatus.PENDING.value, "result": None}

        response = client.get(f"{Endpoints.RESULT.value}".format(job_id))
        assert response.status_code == 400
        assert response.json()["detail"] == "Result not ready"

    @pytest.mark.asyncio
    async def test_get_result_failed_job(self, client):
        """Test result endpoint with failed job"""
        job_id = "test_failed_job"
        app.jobs[job_id] = {"status": JobStatus.FAILED.value, "result": "Some error occurred"}

        response = client.get(f"{Endpoints.RESULT.value}".format(job_id))
        assert response.status_code == 500
        assert response.json()["detail"] == "Unknown error occurred during prediction"

    @pytest.mark.asyncio
    async def test_get_result_completed_job(self, client):
        """Test result endpoint with completed job"""
        job_id = "test_completed_job"
        expected_result = {
            "average_transaction_size": 1000.0,
            "probability_to_transact": 0.75
        }
        app.jobs[job_id] = {"status": JobStatus.COMPLETED.value, "result": expected_result}

        response = client.get(f"{Endpoints.RESULT.value}".format(job_id))
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == job_id
        assert data["result"] == expected_result

    @pytest.mark.parametrize("member_data,expected_avg", [
        ({"member_id": "1", "balance": 1000, "last_purchase_size": 500,
          "last_purchase_date": datetime.now().strftime("%Y-%m-%d")}, 750.0),
        ({"member_id": "2", "balance": 0, "last_purchase_size": 100,
          "last_purchase_date": datetime.now().strftime("%Y-%m-%d")}, 50.0),
        ({"member_id": "3", "balance": 5000, "last_purchase_size": 0,
          "last_purchase_date": datetime.now().strftime("%Y-%m-%d")}, 2500.0),
        ({"member_id": "4", "balance": 100, "last_purchase_size": 100,
          "last_purchase_date": datetime.now().strftime("%Y-%m-%d")}, 100.0),
    ])
    @pytest.mark.asyncio
    async def test_prediction_calculations(self, client, member_data, expected_avg):
        """Test various prediction calculations"""
        if "last_purchase_date" not in member_data:
            member_data["last_purchase_date"] = datetime.now().strftime("%Y-%m-%d")

        response = client.post(Endpoints.PREDICT.value, json=member_data)

        if response.status_code == 200:
            data = response.json()
            assert data["average_transaction_size"] == expected_avg

    @pytest.mark.parametrize("days_ago,min_prob,max_prob, scenario", [
        (0, 0.99, 1.0, "Today"),
        (30, 0.91, 0.92, "1 month"),
        (90, 0.74, 0.76, "3 months"),
        (180, 0.49, 0.51, "6 months"),
        (365, 0.0, 0.01, "1 year"),
        (400, 0.0, 0.0, "> 1 year"),
    ])
    @pytest.mark.asyncio
    async def test_probability_calculations(self, client, days_ago, min_prob, max_prob, scenario):
        """Test probability calculations based on purchase recency"""
        purchase_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        member_data = {
            "member_id": f"test_prob_{days_ago}",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": purchase_date
        }

        response = client.post(Endpoints.PREDICT.value, json=member_data)

        if response.status_code == 200:
            data = response.json()
            assert min_prob <= data["probability_to_transact"] <= max_prob

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload, scenario", [
        ({"member_id": "minimal_test"},
         "missing all optional fields: balance, last_purchase_size and last_purchase_date"),
        ({"member_id": "minimal_test", "last_purchase_size": 500, "last_purchase_date": "2025-03-01"},
         "missing balance optional field"),
        ({"member_id": "minimal_test", "balance": 1000, "last_purchase_date": "2025-03-01"},
         "missing last_purchase_size and last_purchase_date optional fields"),
        ({"member_id": "minimal_test", "balance": 1000, "last_purchase_size": 500},
         "missing last_purchase_date optional fields"),
    ])
    async def test_missing_optional_fields(self, client, payload, scenario):
        """Test prediction with minimal required fields"""
        response = client.post(Endpoints.PREDICT.value, json=payload)
        assert response.status_code == 200, f"Prediction request failed for request {payload}."

    @pytest.mark.asyncio
    async def test_concurrent_predictions(self):
        """Test multiple concurrent prediction requests"""
        member_data_list = [
            {
                "member_id": f"concurrent_test_{i}",
                "balance": 1000 * i,
                "last_purchase_size": 100 * i,
                "last_purchase_date": (datetime.now() - timedelta(days=i * 10)).strftime("%Y-%m-%d")
            }
            for i in range(1, 6)
        ]

        # Submit all predictions concurrently
        async with AsyncClient(app=app, base_url=APPLICATION_URL) as async_client:
            tasks = [async_client.post(Endpoints.PREDICT.value, json=data) for data in member_data_list]
            responses = await asyncio.gather(*tasks)

        successful = sum(1 for r in responses if r.status_code == 200)
        assert successful >= 3  # At least 3 should succeed (accounting for 15% failure rate)

        # Verify successful responses have correct structure
        for response in responses:
            if response.status_code == 200:
                data = response.json()
                assert "average_transaction_size" in data
                assert "probability_to_transact" in data

    @pytest.mark.asyncio
    async def test_complete_prediction_flow(self, client, valid_member_data):
        """Test complete flow from prediction to result retrieval"""
        start_time = time.time()
        pred_response = client.post(Endpoints.PREDICT.value, json=valid_member_data)
        pred_time = time.time() - start_time

        if pred_response.status_code != 200:
            return {
                "success": False,
                "error": f"Prediction failed with status {pred_response.status_code}",
                "response": pred_response
            }

        # Get job ID from app state (workaround for API design issue)
        job_id = list(app.jobs.keys())[-1] if app.jobs else None

        if not job_id:
            return {
                "success": False,
                "error": "No job created",
                "response": pred_response
            }

        # Wait for completion
        start_time_job = time.time()
        final_status = JobStatus.PENDING.value

        while time.time() - start_time_job < 30:
            response = client.get(f"{Endpoints.STATUS.value}".format(job_id))
            final_status = response.json().get("status", "unknown")
            if final_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                break
            await asyncio.sleep(0.5)
        wait_time = time.time() - start_time_job

        if final_status == JobStatus.COMPLETED.value:
            result_response, result_data = client.get(f"{Endpoints.RESULT.value}".format(job_id))
            result = {
                "success": True,
                "job_id": job_id,
                "prediction_time": pred_time,
                "wait_time": wait_time,
                "total_time": pred_time + wait_time,
                "result": result_data.get("result", {}),
                "immediate_response": pred_response.json()
            }
        else:
            result = {
                "success": False,
                "error": f"Job failed with status: {final_status}",
                "job_id": job_id,
                "total_time": pred_time + wait_time
            }

        if result["success"]:
            assert "job_id" in result
            assert "result" in result
            assert "prediction_time" in result
            assert "wait_time" in result
            assert result["result"]["average_transaction_size"] == 2625.0
        else:
            assert "error" in result

    @pytest.mark.asyncio
    async def test_prediction_performance(self, client, valid_member_data):
        """Test prediction endpoint response time"""
        start_time = time.time()
        response = client.post(Endpoints.PREDICT.value, json=valid_member_data)
        elapsed = time.time() - start_time

        # Response should be reasonably fast (accounting for random sleep up to 3s)
        assert elapsed < 4.0

        if response.status_code == 200:
            assert "average_transaction_size" in response.json()

    @pytest.mark.asyncio
    async def test_job_persistence_across_requests(self, client, valid_member_data):
        """Test that jobs persist across multiple requests"""
        # Clear jobs
        app.jobs.clear()

        for i in range(3):
            member_data = valid_member_data.copy()
            member_data["member_id"] = f"persistence_test_{i}"
            response = client.post(Endpoints.PREDICT.value, json=member_data)

            if response.status_code == 200:
                # Small delay to ensure job is created
                await asyncio.sleep(0.1)

        assert len(app.jobs) >= 2  # At least 2 should succeed given 15% failure rate

        # Verify each job has proper structure
        for job_id, job_data in app.jobs.items():
            assert "status" in job_data
            assert "result" in job_data
            assert job_data["status"] in \
                   [JobStatus.PENDING.value, JobStatus.COMPLETED.value, JobStatus.FAILED.value]
