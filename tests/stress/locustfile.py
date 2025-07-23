"""
Locust performance/stress test for Prediction Service

To run:
1. Install locust: pip install locust
2. Run with web UI: locust -f tests/stress/locustfile.py --host http://localhost:8000
3. Run headless: locust -f tests/stress/locustfile.py --host http://localhost:8000 --headless -u 100 -r 10 -t 60s

Configuration options:
- -u: Number of users to simulate
- -r: Spawn rate (users per second)
- -t: Test duration
- --host: Target host URL
"""

from locust import HttpUser, task, between, events
from locust.env import Environment
from datetime import datetime, timedelta
import random
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictionUser(HttpUser):
    """Simulates a user making prediction requests"""
    
    # Wait time between requests (1-3 seconds)
    wait_time = between(1, 3)
    
    # Track job IDs for this user
    job_ids = []
    
    def on_start(self):
        """Called when a user starts"""
        self.user_id = f"stress_test_user_{random.randint(1000, 9999)}"
        logger.info(f"Starting user: {self.user_id}")
        
        # Initial health check
        self.client.get("/ping")
    
    @task(3)
    def predict_active_user(self):
        """Simulate an active user making a prediction"""
        data = {
            "member_id": f"{self.user_id}_active_{random.randint(1, 1000)}",
            "balance": random.randint(5000, 20000),
            "last_purchase_size": random.randint(500, 3000),
            "last_purchase_date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
        }
        
        with self.client.post("/predict", json=data, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    result = response.json()
                    if "average_transaction_size" in result and "probability_to_transact" in result:
                        response.success()
                        # Track this as a successful prediction
                        self.environment.stats.get("/predict", "POST").log(
                            response.elapsed.total_seconds() * 1000, 
                            len(response.content or b"")
                        )
                    else:
                        response.failure("Invalid response structure")
                except Exception as e:
                    response.failure(f"Failed to parse response: {e}")
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(2)
    def predict_inactive_user(self):
        """Simulate an inactive user making a prediction"""
        data = {
            "member_id": f"{self.user_id}_inactive_{random.randint(1, 1000)}",
            "balance": random.randint(100, 2000),
            "last_purchase_size": random.randint(10, 200),
            "last_purchase_date": (datetime.now() - timedelta(days=random.randint(180, 365))).strftime("%Y-%m-%d")
        }
        
        self.client.post("/predict", json=data, name="/predict")
    
    @task(1)
    def predict_new_user(self):
        """Simulate a new user with no purchase history"""
        data = {
            "member_id": f"{self.user_id}_new_{random.randint(1, 1000)}",
            "balance": random.randint(0, 500),
            "last_purchase_size": 0,
            "last_purchase_date": None
        }
        
        self.client.post("/predict", json=data, name="/predict")
    
    @task(1)
    def predict_high_value_user(self):
        """Simulate a high-value customer"""
        data = {
            "member_id": f"{self.user_id}_vip_{random.randint(1, 1000)}",
            "balance": random.randint(20000, 100000),
            "last_purchase_size": random.randint(5000, 20000),
            "last_purchase_date": (datetime.now() - timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
        }
        
        with self.client.post("/predict", json=data, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"VIP user prediction failed with {response.status_code}")
    
    @task(1)
    def check_job_status(self):
        """Check status of a previously created job"""
        if self.job_ids:
            job_id = random.choice(self.job_ids)
            with self.client.get(f"/status/{job_id}", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 404:
                    # Job might have been cleaned up
                    self.job_ids.remove(job_id)
                    response.success()
                else:
                    response.failure(f"Status check failed with {response.status_code}")
    
    @task(1)
    def get_job_result(self):
        """Try to get result of a job"""
        if self.job_ids:
            job_id = random.choice(self.job_ids)
            with self.client.get(f"/result/{job_id}", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                    self.job_ids.remove(job_id)  # Remove completed job
                elif response.status_code == 400:
                    # Still processing
                    response.success()
                elif response.status_code == 404:
                    # Job not found
                    self.job_ids.remove(job_id)
                    response.success()
                else:
                    response.failure(f"Result retrieval failed with {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Periodic health check"""
        with self.client.get("/ping", catch_response=True) as response:
            if response.status_code == 200 and response.json().get("status") == "ok":
                response.success()
            else:
                response.failure("Health check failed")


class StressTestUser(HttpUser):
    """User behavior for stress testing with edge cases"""
    
    wait_time = between(0.5, 1.5)  # More aggressive timing
    
    @task(1)
    def predict_edge_case_zero_values(self):
        """Test with zero values"""
        data = {
            "member_id": f"stress_zero_{random.randint(1, 10000)}",
            "balance": 0,
            "last_purchase_size": 0,
            "last_purchase_date": datetime.now().strftime("%Y-%m-%d")
        }
        self.client.post("/predict", json=data, name="/predict_edge_zero")
    
    @task(1)
    def predict_edge_case_large_values(self):
        """Test with very large values"""
        data = {
            "member_id": f"stress_large_{random.randint(1, 10000)}",
            "balance": 999999999,
            "last_purchase_size": 888888888,
            "last_purchase_date": "2024-01-01"
        }
        self.client.post("/predict", json=data, name="/predict_edge_large")
    
    @task(1)
    def predict_edge_case_future_date(self):
        """Test with future date"""
        data = {
            "member_id": f"stress_future_{random.randint(1, 10000)}",
            "balance": 1000,
            "last_purchase_size": 100,
            "last_purchase_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        }
        self.client.post("/predict", json=data, name="/predict_edge_future")
    
    @task(1)
    def predict_invalid_request(self):
        """Test with invalid request to stress error handling"""
        invalid_requests = [
            {},  # Empty request
            {"member_id": ""},  # Empty member ID
            {"member_id": "test", "balance": "not_a_number"},  # Invalid type
            {"member_id": "test", "last_purchase_date": "invalid_date"},  # Invalid date
        ]
        
        data = random.choice(invalid_requests)
        with self.client.post("/predict", json=data, catch_response=True) as response:
            if response.status_code in [422, 400, 500]:
                response.success()  # Expected error
            else:
                response.failure("Invalid request should have failed")
    
    @task(2)
    def rapid_fire_predictions(self):
        """Send multiple predictions rapidly"""
        for _ in range(5):
            data = {
                "member_id": f"rapid_{random.randint(1, 100000)}",
                "balance": random.randint(100, 10000),
                "last_purchase_size": random.randint(10, 1000),
                "last_purchase_date": "2024-01-15"
            }
            self.client.post("/predict", json=data, name="/predict_rapid")
            time.sleep(0.1)  # Small delay between requests


@events.init.add_listener
def on_locust_init(environment: Environment, **kwargs):
    """Called when locust starts"""
    logger.info("Initializing Locust stress test for Prediction Service")
    logger.info(f"Target host: {environment.host}")


@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Called when test starts"""
    logger.info("Starting stress test")
    logger.info(f"Total users: {environment.runner.target_user_count if environment.runner else 'N/A'}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Called when test stops"""
    logger.info("Stress test completed")
    
    # Print summary statistics
    if environment.stats:
        logger.info("\n=== Test Summary ===")
        logger.info(f"Total requests: {environment.stats.total.num_requests}")
        logger.info(f"Failed requests: {environment.stats.total.num_failures}")
        logger.info(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
        logger.info(f"Min response time: {environment.stats.total.min_response_time}ms")
        logger.info(f"Max response time: {environment.stats.total.max_response_time}ms")
        
        if environment.stats.total.num_requests > 0:
            failure_rate = (environment.stats.total.num_failures / environment.stats.total.num_requests) * 100
            logger.info(f"Failure rate: {failure_rate:.2f}%")


class SpikeTestUser(HttpUser):
    """User for spike testing - sudden load increase"""
    
    wait_time = between(0.1, 0.5)  # Very aggressive
    
    @task
    def spike_prediction(self):
        """Rapid predictions for spike test"""
        data = {
            "member_id": f"spike_{random.randint(1, 1000000)}",
            "balance": random.randint(1000, 5000),
            "last_purchase_size": random.randint(100, 500),
            "last_purchase_date": "2024-01-15"
        }
        self.client.post("/predict", json=data, name="/predict_spike")
