from datetime import datetime
from typing import Dict
from models.prediction_request import PredictionRequest
import random
import os


# @staticmethod
async def get_predictions(
    prediction_request: PredictionRequest
) -> Dict[str, float]:
    """
    Calculate average transaction size and probability to transact.

    Args:
        prediction_request (PredictionRequest): The prediction request containing relevant features.

    Returns:
        Dict[str, float]: A dictionary containing the average transaction size and probability to transact.
    """
    if random.random() < 0.15:  # Simulate a 15% chance of failure os.getenv('DISABLE_RANDOM_FAILURES') != 'true' and
        raise Exception("Unknown error occurred during prediction")
    avg_transaction_size = (prediction_request.balance + prediction_request.last_purchase_size) / 2

    if prediction_request.last_purchase_date:
        last_date = datetime.strptime(prediction_request.last_purchase_date, "%Y-%m-%d")
        days_since_last_purchase = (datetime.now() - last_date).days
        probability_to_transact = max(0.0, 1.0 - (days_since_last_purchase / 365))
    else:
        probability_to_transact = 0.0

    return {
        "average_transaction_size": avg_transaction_size,
        "probability_to_transact": probability_to_transact
    }
