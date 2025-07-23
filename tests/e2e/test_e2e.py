import pytest
from httpx import AsyncClient
import asyncio
import time

import sys
import os

from conftest import APPLICATION_URL

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from app.main import app
from tests.utils.api_helpers import JobMonitor, analyze_performance_results, Endpoints, JobStatus, \
    complete_prediction_flow, UserType
from tests.utils.test_data import PredictionDataFactory, TestScenarios, validate_prediction_response
from tests.utils.test_logger import get_test_logger

logger = get_test_logger("e2e_tests")
TIMEOUT = 10
POLL_IN = 0.5

pytestmark = [pytest.mark.e2e]


class TestUserJourneys:
    """End-to-end tests simulating complete user journeys"""

    @pytest.fixture
    def job_monitor(self):
        """Create job monitor for tracking"""
        return JobMonitor()

    @pytest.fixture(autouse=True)
    def clear_jobs(self):
        """Clear jobs before and after each test"""
        app.jobs.clear()
        yield
        app.jobs.clear()

    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_single_user_complete_journey(self, job_monitor):
        """Test complete journey for a single user from prediction to result"""
        async with AsyncClient(app=app, base_url=APPLICATION_URL) as api_client:

            logger.info("Starting single user complete journey test")

            # Create an active user profile
            user_data = PredictionDataFactory.create_user_profile("active")
            logger.info(f"Created user profile: {user_data['member_id']}")

            # Step 1: Health check
            response = await api_client.get("/ping")
            assert response.status_code == 200
            logger.info("Health check passed")

            # Step 2: Submit prediction
            start_time = time.time()
            pred_response = await api_client.post(Endpoints.PREDICT.value, json=user_data)
            assert pred_response.status_code == 200

            prediction_data = pred_response.json()
            validation_result = validate_prediction_response(prediction_data)
            assert validation_result["is_valid"], f"Invalid response: {validation_result['errors']}"

            # Step 3: Get job ID and track it
            job_id = list(app.jobs.keys())[-1] if app.jobs else None
            assert job_id is not None, "No job was created"

            job_monitor.track_job(job_id, user_data)

            # Step 4: Check job status
            status_response = await api_client.get(f"{Endpoints.STATUS.value}".format(job_id))
            status_data = status_response.json()
            assert status_response.status_code == 200
            assert status_data["job_id"] == job_id
            assert status_data["status"] in \
                   [JobStatus.PENDING.value, JobStatus.COMPLETED.value, JobStatus.FAILED.value]

            job_monitor.update_job_status(job_id, status_data["status"])
            logger.info(f"Job status: {status_data['status']}")

            # Step 5: Wait for completion and get result
            start_time_job = time.time()
            final_status = JobStatus.PENDING.value
            while time.time() - start_time_job < TIMEOUT:
                status_response = await api_client.get(f"{Endpoints.STATUS.value}".format(job_id))
                status_data = status_response.json()
                final_status = status_data.get("status", "unknown")
                if final_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    break

                await asyncio.sleep(POLL_IN)
            wait_time = time.time() - start_time_job
            logger.info(f"Job {job_id} finished with status '{final_status}' after {wait_time:.2f}s")
            job_monitor.update_job_status(job_id, final_status)

            if final_status == JobStatus.COMPLETED.value:
                result_response = await api_client.get(f"{Endpoints.RESULT.value}".format(job_id))
                result_data = result_response.json()
                assert result_response.status_code == 200
                assert "result" in result_data

                assert result_data["result"]["average_transaction_size"] == prediction_data["average_transaction_size"]
                assert result_data["result"]["probability_to_transact"] == prediction_data["probability_to_transact"]

                logger.info(f"Journey completed successfully in {time.time() - start_time:.2f}s")
            else:
                logger.warning(f"Job failed with status: {final_status}")

            metrics = job_monitor.get_job_metrics()
            logger.info(f"Journey metrics: {metrics}")

            assert final_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]

    @pytest.mark.asyncio
    async def test_multiple_user_types_journey(self):
        """Test different user types going through the prediction flow"""
        logger.info("Testing multiple user types journey")
        async with AsyncClient(app=app, base_url=APPLICATION_URL) as api_client:

            user_types = [UserType.ACTIVE.value, UserType.INACTIVE.value, UserType.NEW.value, UserType.HIGH_VALUE.value]
            results = []

            for user_type in user_types:
                user_data = PredictionDataFactory.create_user_profile(user_type)
                logger.info(f"Testing {user_type} user: {user_data['member_id']}")

                result = await complete_prediction_flow(api_client,user_data)
                results.append({
                    "user_type": user_type,
                    "success": result["success"],
                    "data": result
                })

                if result["success"]:
                    prediction = result["immediate_response"]

                    if user_type == UserType.NEW.value and user_data.get("last_purchase_date") is None:
                        # New users with no purchase history should have 0 probability
                        assert prediction["probability_to_transact"] == 0.0
                    elif user_type == UserType.ACTIVE.value:
                        # Active users should have higher probability
                        assert prediction["probability_to_transact"] > 0.5
                    elif user_type == UserType.INACTIVE.value:
                        # Inactive users should have lower probability
                        assert prediction["probability_to_transact"] < 0.5

            successful = sum(1 for r in results if r["success"])
            logger.info(f"Successfully processed {successful}/{len(user_types)} user types")

            # At least 3 out of 4 should succeed (accounting for random failures)
            assert successful >= 3

    @pytest.mark.asyncio
    async def test_concurrent_users_journey(self):
        """Test multiple concurrent users going through the system"""
        logger.info("Testing concurrent users journey")
        async with AsyncClient(app=app, base_url=APPLICATION_URL) as api_client:

            num_users = 10
            users = TestScenarios.load_test_scenario(num_users)

            start_time = time.time()
            tasks = [complete_prediction_flow(api_client, user) for user in users]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time

            successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
            failed_results = [r for r in results if not (isinstance(r, dict) and r.get("success"))]

            logger.info(f"Processed {num_users} users in {total_time:.2f}s")
            logger.info(f"Success: {len(successful_results)}, Failed: {len(failed_results)}")

            if successful_results:
                performance_metrics = analyze_performance_results(successful_results)
                logger.info(f"Performance metrics: {performance_metrics}")

                assert performance_metrics["success_rate"] >= 70  # At least 70% success rate
                assert performance_metrics["avg_total_time"] < 5.0  # Average time under 5 seconds

            assert len(app.jobs) >= len(successful_results)
