from pydantic import BaseModel
from typing import Optional


class PredictionRequest(BaseModel):
    member_id: str
    balance: Optional[int] = None
    last_purchase_size: Optional[int] = None
    last_purchase_date: Optional[str] = None
