"""API test helper utilities."""
import time
from enum import Enum
from typing import Dict, Any, List
from httpx import AsyncClient
import asyncio
from datetime import datetime
from tests.utils.test_logger import get_test_logger

logger = get_test_logger("api_helpers")


class JobStatus(Enum):
    PENDING = 'processing'  # In the requirement it is 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'


class MethodType(Enum):
    GET = 'GET'
    POST = 'POST'


class Endpoints(Enum):
    PREDICT = '/predict'
    STATUS = '/status/{}'
    RESULT = '/result/{}'
    PING = "/ping"


class UserType(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NEW = "new"
    HIGH_VALUE = "high_value"


class JobMonitor:
    """Monitor and analyze job execution."""

    def __init__(self):
        self.jobs_tracked: Dict[str, Dict[str, Any]] = {}

    def track_job(self, job_id: str, initial_data: Dict[str, Any]):
        """Start tracking a job."""
        self.jobs_tracked[job_id] = {
            "created_at": datetime.now(),
            "initial_data": initial_data,
            "status_history": [],
            "completed_at": None,
            "final_status": None
        }

    def update_job_status(self, job_id: str, status: str):
        """Update job status."""
        if job_id in self.jobs_tracked:
            self.jobs_tracked[job_id]["status_history"].append({
                "status": status,
                "timestamp": datetime.now()
            })

            if status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                self.jobs_tracked[job_id]["completed_at"] = datetime.now()
                self.jobs_tracked[job_id]["final_status"] = status

    def get_job_metrics(self) -> Dict[str, Any]:
        """Get metrics for all tracked jobs."""
        total_jobs = len(self.jobs_tracked)
        completed = sum(1 for j in self.jobs_tracked.values()
                        if j["final_status"] == JobStatus.COMPLETED.value)
        failed = sum(1 for j in self.jobs_tracked.values()
                     if j["final_status"] == JobStatus.FAILED.value)
        in_progress = total_jobs - completed - failed

        completion_times = []
        for job in self.jobs_tracked.values():
            if job["completed_at"] and job["created_at"]:
                duration = (job["completed_at"] - job["created_at"]).total_seconds()
                completion_times.append(duration)

        return {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": completed / total_jobs * 100 if total_jobs > 0 else 0,
            "avg_completion_time": sum(completion_times) / len(completion_times)
            if completion_times else 0
        }


async def complete_prediction_flow(async_client: AsyncClient,
                                   member_data: Dict[str, Any],
                                   timeout: float = 30.0,
                                   poll_interval: float = 0.5) -> Dict[str, Any]:
    """
    Execute complete prediction flow using AsyncClient.
    
    Args:
        async_client: The httpx AsyncClient instance
        member_data: The prediction request data
        timeout: Maximum time to wait for job completion
        poll_interval: Time between status checks
        
    Returns:
        Dictionary with flow results including success status, timings, and results
    """
    start_time = time.time()
    try:
        pred_response = await async_client.post(Endpoints.PREDICT.value, json=member_data)
        pred_time = time.time() - start_time

        if pred_response.status_code != 200:
            return {
                "success": False,
                "error": f"Prediction failed with status {pred_response.status_code}",
                "response": pred_response,
                "status_code": pred_response.status_code
            }
        pred_data = pred_response.json()

        # Try to get job ID from response (if API returns it)
        job_id = pred_data.get("job_id")

        # If job_id not in response, get from app state (workaround)
        if not job_id:
            try:
                from app.main import app
                job_id = list(app.jobs.keys())[-1] if app.jobs else None
            except Exception as e:
                logger.warning(f"Could not get job_id from app state: {e}")

        if not job_id:
            return {
                "success": True,
                "job_id": None,
                "prediction_time": pred_time,
                "wait_time": 0,
                "total_time": pred_time,
                "result": pred_data,
                "immediate_response": pred_data
            }

        # Wait for job completion
        start_wait = time.time()
        final_status = JobStatus.PENDING.value

        while time.time() - start_wait < timeout:
            try:
                status_response = await async_client.get(f"{Endpoints.STATUS.value}".format(job_id))
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    final_status = status_data.get("status", "unknown")

                    if final_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                        break
                elif status_response.status_code == 404:
                    # Job not found
                    break
            except Exception as e:
                logger.error(f"Error checking job status: {e}")
                break

            await asyncio.sleep(poll_interval)

        wait_time = time.time() - start_wait

        # Get result if completed
        if final_status == JobStatus.COMPLETED.value:
            try:
                result_response = await async_client.get(f"{Endpoints.RESULT.value}".format(job_id))
                if result_response.status_code == 200:
                    result_data = result_response.json()
                    return {
                        "success": True,
                        "job_id": job_id,
                        "prediction_time": pred_time,
                        "wait_time": wait_time,
                        "total_time": pred_time + wait_time,
                        "result": result_data.get("result", {}),
                        "immediate_response": pred_data,
                        "final_status": final_status
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get result: status {result_response.status_code}",
                        "job_id": job_id,
                        "total_time": pred_time + wait_time,
                        "final_status": final_status
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error getting result: {str(e)}",
                    "job_id": job_id,
                    "total_time": pred_time + wait_time,
                    "final_status": final_status
                }
        else:
            return {
                "success": False,
                "error": f"Job failed with status: {final_status}",
                "job_id": job_id,
                "total_time": pred_time + wait_time,
                "final_status": final_status
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "response": None
        }


async def submit_concurrent_predictions(async_client: AsyncClient,
                                        user_data_list: List[Dict[str, Any]],
                                        max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """
    Submit multiple predictions concurrently using AsyncClient.
    
    Args:
        async_client: The httpx AsyncClient instance
        user_data_list: List of user data dictionaries
        max_concurrent: Maximum concurrent requests per batch
        
    Returns:
        List of results for each prediction
    """
    results = []

    # Process in batches
    for i in range(0, len(user_data_list), max_concurrent):
        batch = user_data_list[i:i + max_concurrent]

        # Submit batch concurrently
        tasks = [complete_prediction_flow(async_client, data) for data in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                results.append({
                    "success": False,
                    "error": str(result),
                    "user_data": batch[j]
                })
            else:
                results.append(result)

    return results


def analyze_performance_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze performance test results."""
    successful = [r for r in results if r.get("success", False)]
    failed = [r for r in results if not r.get("success", False)]

    if not successful:
        return {
            "success_rate": 0,
            "total_requests": len(results),
            "successful": 0,
            "failed": len(failed)
        }

    response_times = [r.get("total_time", 0) for r in successful]
    prediction_times = [r.get("prediction_time", 0) for r in successful]
    wait_times = [r.get("wait_time", 0) for r in successful]

    return {
        "success_rate": len(successful) / len(results) * 100,
        "total_requests": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "avg_total_time": sum(response_times) / len(response_times),
        "avg_prediction_time": sum(prediction_times) / len(prediction_times),
        "avg_wait_time": sum(wait_times) / len(wait_times),
        "min_total_time": min(response_times),
        "max_total_time": max(response_times),
        "p95_total_time": sorted(response_times)[int(len(response_times) * 0.95)]
    }
