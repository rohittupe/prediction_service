"""Test data factories and generators."""
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from faker import Faker

from tests.utils.api_helpers import UserType

fake = Faker()


class PredictionDataFactory:
    """Factory for generating test prediction data."""
    
    @staticmethod
    def create_valid_prediction(
        member_id: Optional[str] = None,
        balance: Optional[int] = None,
        last_purchase_size: Optional[int] = None,
        last_purchase_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a valid prediction request."""
        return {
            "member_id": member_id or f"user-{fake.uuid4()}",
            "balance": balance if balance is not None else random.randint(100, 10000),
            "last_purchase_size": last_purchase_size if last_purchase_size is not None 
                                else random.randint(10, 5000),
            "last_purchase_date": last_purchase_date or 
                                (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d")
        }
    
    @staticmethod
    def create_invalid_prediction(error_type: str = "missing_fields") -> Dict[str, Any]:
        """Create an invalid prediction request for error testing."""
        if error_type == "missing_fields":
            return {"member_id": f"user-{fake.uuid4()}"}
        
        elif error_type == "null_values":
            return {
                "member_id": f"user-{fake.uuid4()}",
                "balance": None,
                "last_purchase_size": None,
                "last_purchase_date": "2024-01-01"
            }
        
        elif error_type == "invalid_date":
            return {
                "member_id": f"user-{fake.uuid4()}",
                "balance": 1000,
                "last_purchase_size": 500,
                "last_purchase_date": "not-a-date"
            }
        
        elif error_type == "negative_values":
            return {
                "member_id": f"user-{fake.uuid4()}",
                "balance": -1000,
                "last_purchase_size": -500,
                "last_purchase_date": "2024-01-01"
            }
        
        elif error_type == "wrong_types":
            return {
                "member_id": f"user-{fake.uuid4()}",
                "balance": "not-a-number",
                "last_purchase_size": "also-not-a-number",
                "last_purchase_date": "2024-01-01"
            }
        
        else:
            return {"invalid": "request"}
    
    @staticmethod
    def create_batch(count: int, **kwargs) -> List[Dict[str, Any]]:
        """Create a batch of valid predictions."""
        return [
            PredictionDataFactory.create_valid_prediction(**kwargs)
            for _ in range(count)
        ]
    
    @staticmethod
    def create_user_profile(user_type: str = UserType.ACTIVE.value) -> Dict[str, Any]:
        """Create user profile based on type."""
        if user_type == UserType.ACTIVE.value:
            # Active user with recent purchases
            return {
                "member_id": f"active-{fake.uuid4()}",
                "balance": random.randint(5000, 20000),
                "last_purchase_size": random.randint(500, 3000),
                "last_purchase_date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
            }
        
        elif user_type == UserType.INACTIVE.value:
            # Inactive user with old purchases
            return {
                "member_id": f"inactive-{fake.uuid4()}",
                "balance": random.randint(100, 2000),
                "last_purchase_size": random.randint(10, 200),
                "last_purchase_date": (datetime.now() - timedelta(days=random.randint(180, 365))).strftime("%Y-%m-%d")
            }
        
        elif user_type == UserType.NEW.value:
            # New user with no purchase history
            return {
                "member_id": f"new-{fake.uuid4()}",
                "balance": random.randint(0, 500),
                "last_purchase_size": 0,
                "last_purchase_date": None
            }
        
        elif user_type == UserType.HIGH_VALUE.value:
            # High value customer
            return {
                "member_id": f"vip-{fake.uuid4()}",
                "balance": random.randint(20000, 100000),
                "last_purchase_size": random.randint(5000, 20000),
                "last_purchase_date": (datetime.now() - timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
            }
        
        else:
            return PredictionDataFactory.create_valid_prediction()


class TestScenarios:
    """Pre-defined test scenarios."""
    
    @staticmethod
    def load_test_scenario(num_users: int = 100) -> List[Dict[str, Any]]:
        """Generate data for load testing."""
        users = []

        user_distribution = {
            "active": int(num_users * 0.4),
            "inactive": int(num_users * 0.3),
            "new": int(num_users * 0.2),
            "high_value": int(num_users * 0.1)
        }
        
        for user_type, count in user_distribution.items():
            for _ in range(count):
                users.append(PredictionDataFactory.create_user_profile(user_type))

        while len(users) < num_users:
            users.append(PredictionDataFactory.create_valid_prediction())
        
        return users


def validate_prediction_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate prediction response structure and values."""
    validation_results = {
        "is_valid": True,
        "errors": []
    }

    required_fields = ["average_transaction_size", "probability_to_transact"]
    for field in required_fields:
        if field not in response_data:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Missing required field: {field}")

    if "average_transaction_size" in response_data:
        avg_size = response_data["average_transaction_size"]
        if not isinstance(avg_size, (int, float)):
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Invalid type for average_transaction_size: {type(avg_size)}")
        elif avg_size < 0:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Negative average_transaction_size: {avg_size}")

    if "probability_to_transact" in response_data:
        prob = response_data["probability_to_transact"]
        if not isinstance(prob, (int, float)):
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Invalid type for probability_to_transact: {type(prob)}")
        elif not 0 <= prob <= 1:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Probability out of range [0,1]: {prob}")
    
    return validation_results
