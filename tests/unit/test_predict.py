import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from app.machine_learning.predict import get_predictions
from app.models.prediction_request import PredictionRequest

pytestmark = [pytest.mark.unit, pytest.mark.prediction]


class TestGetPredictions:
    """Unit tests for the get_predictions function"""
    
    @pytest.fixture
    def sample_request(self):
        """Create a sample prediction request with all fields"""
        return PredictionRequest(
            member_id="test_123",
            balance=1000,
            last_purchase_size=50,
            last_purchase_date="2024-01-15"
        )
    
    @pytest.mark.asyncio
    async def test_get_predictions_success(self, sample_request):
        """Test successful prediction calculation"""
        with patch('random.random', return_value=0.5):  # Ensure no random failure
            result = await get_predictions(sample_request)
            
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
            
            # Check average calculation: (1000 + 50) / 2 = 525
            assert result["average_transaction_size"] == 525.0
            
            # Check probability is between 0 and 1
            assert 0.0 <= result["probability_to_transact"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_get_predictions_random_failure(self, sample_request):
        """Test random failure simulation (15% chance)"""
        with patch('random.random', return_value=0.1):  # Force failure
            with pytest.raises(Exception) as exc_info:
                await get_predictions(sample_request)
            
            assert str(exc_info.value) == "Unknown error occurred during prediction"
    
    @pytest.mark.asyncio
    async def test_get_predictions_no_failure(self, sample_request):
        """Test prediction succeeds when random > 0.15"""
        with patch('random.random', return_value=0.2):  # No failure
            result = await get_predictions(sample_request)
            
            assert isinstance(result, dict)
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
    
    @pytest.mark.asyncio
    async def test_average_transaction_size_calculation(self):
        """Test average transaction size calculation with various values"""
        test_cases = [
            (1000, 500, 750.0),
            (0, 100, 50.0),
            (2000, 0, 1000.0),
            (1, 1, 1.0),
            (999, 1, 500.0)
        ]
        
        for balance, last_purchase, expected_avg in test_cases:
            request = PredictionRequest(
                member_id="test",
                balance=balance,
                last_purchase_size=last_purchase,
                last_purchase_date="2024-01-15"
            )
            
            with patch('random.random', return_value=0.5):
                result = await get_predictions(request)
                assert result["average_transaction_size"] == expected_avg
    
    @pytest.mark.asyncio
    async def test_probability_with_no_last_purchase_date(self):
        """Test probability calculation when last_purchase_date is None"""
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=None
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            assert result["probability_to_transact"] == 0.0
    
    @pytest.mark.asyncio
    async def test_probability_with_recent_purchase(self):
        """Test probability calculation with recent purchase date"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=yesterday
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            # Should be close to 1.0 for recent purchase
            assert result["probability_to_transact"] > 0.99
    
    @pytest.mark.asyncio
    async def test_probability_with_old_purchase(self):
        """Test probability calculation with old purchase date"""
        old_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=old_date
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            # Should be close to 0.0 for purchase exactly 1 year ago
            assert abs(result["probability_to_transact"] - 0.0) < 0.01
    
    @pytest.mark.asyncio
    async def test_probability_with_very_old_purchase(self):
        """Test probability calculation with purchase > 1 year ago"""
        very_old_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=very_old_date
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            # Should be 0.0 for purchase > 365 days ago
            assert result["probability_to_transact"] == 0.0
    
    @pytest.mark.parametrize("days_ago,expected_min,expected_max", [
        (0, 0.99, 1.0),      # Today
        (30, 0.91, 0.92),    # ~1 month ago
        (90, 0.74, 0.76),    # ~3 months ago
        (180, 0.49, 0.51),   # ~6 months ago
        (365, 0.0, 0.01),    # 1 year ago
        (400, 0.0, 0.0),     # > 1 year ago
    ])
    @pytest.mark.asyncio
    async def test_probability_decay_over_time(self, days_ago, expected_min, expected_max):
        """Test probability decay calculation over time"""
        purchase_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=purchase_date
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            assert expected_min <= result["probability_to_transact"] <= expected_max
    
    @pytest.mark.asyncio
    async def test_invalid_date_format(self):
        """Test handling of invalid date format"""
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date="invalid-date"
        )
        
        with patch('random.random', return_value=0.5):
            with pytest.raises(ValueError):
                await get_predictions(request)
    
    @pytest.mark.asyncio
    async def test_edge_case_zero_values(self):
        """Test with zero balance and purchase size"""
        request = PredictionRequest(
            member_id="test",
            balance=0,
            last_purchase_size=0,
            last_purchase_date="2024-01-15"
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            assert result["average_transaction_size"] == 0.0
            assert result["probability_to_transact"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_large_values(self):
        """Test with very large balance and purchase values"""
        request = PredictionRequest(
            member_id="test",
            balance=999999999,
            last_purchase_size=888888888,
            last_purchase_date="2024-01-15"
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            expected_avg = (999999999 + 888888888) / 2
            assert result["average_transaction_size"] == expected_avg
    
    @pytest.mark.asyncio
    async def test_future_date_handling(self):
        """Test handling of future purchase dates"""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date=future_date
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            # Future date should result in probability > 1 (not capped by the function)
            assert result["probability_to_transact"] > 1.0
    
    @pytest.mark.parametrize("member_id", [
        "simple_id",
        "id-with-dashes",
        "id_with_underscores",
        "123456789",
        "UPPERCASE_ID",
        "id with spaces",
        "special!@#$%^&*()_id",
        ""  # Empty string
    ])
    @pytest.mark.asyncio
    async def test_various_member_ids(self, member_id):
        """Test function works with various member ID formats"""
        request = PredictionRequest(
            member_id=member_id,
            balance=1000,
            last_purchase_size=100,
            last_purchase_date="2024-01-15"
        )
        
        with patch('random.random', return_value=0.5):
            result = await get_predictions(request)
            
            # Function should work regardless of member_id format
            assert "average_transaction_size" in result
            assert "probability_to_transact" in result
    
    @pytest.mark.asyncio
    async def test_random_failure_boundary(self):
        """Test the exact boundary of random failure (15%)"""
        request = PredictionRequest(
            member_id="test",
            balance=1000,
            last_purchase_size=100,
            last_purchase_date="2024-01-15"
        )
        
        # Test just below threshold - should fail
        with patch('random.random', return_value=0.14999):
            with pytest.raises(Exception):
                await get_predictions(request)
        
        # Test at threshold - should succeed
        with patch('random.random', return_value=0.15):
            result = await get_predictions(request)
            assert isinstance(result, dict)
        
        # Test just above threshold - should succeed
        with patch('random.random', return_value=0.15001):
            result = await get_predictions(request)
            assert isinstance(result, dict)