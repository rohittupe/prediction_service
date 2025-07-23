from fastapi import FastAPI, HTTPException
from uuid import uuid4
from typing import Dict
import asyncio
from models.prediction_request import PredictionRequest
from machine_learning.predict import get_predictions
import random


class Application(FastAPI):
    jobs: Dict[str, Dict] = {}

    def __init__(self):
        super().__init__()
        self.add_api_route("/predict", self.predict, methods=["POST"])
        self.add_api_route("/status/{job_id}", self.get_status, methods=["GET"])
        self.add_api_route("/result/{job_id}", self.get_result, methods=["GET"])
        self.add_api_route("/ping", self.ping, methods=["GET"])

    async def ping(self):
        """
        Health check endpoint.
        """
        return {"status": "ok"}

    async def predict(self, prediction_request: PredictionRequest) -> Dict[str, float]:
        job_id = str(uuid4())
        self.jobs[job_id] = {"status": "processing", "result": None}
        asyncio.create_task(self.process_job(job_id, prediction_request))
        await asyncio.sleep(random.random() * 3)  # Simulate a long-running task
        return await get_predictions(prediction_request)

    async def process_job(self, job_id: str, member_features: PredictionRequest):
        try:
            result = await self.predict(member_features)
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["result"] = result
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["result"] = str(e)

    async def get_status(self, job_id: str):
        if job_id not in self.jobs:
            raise HTTPException(status_code=404, detail="Job ID not found")
        return {"job_id": job_id, "status": self.jobs[job_id]["status"]}

    async def get_result(self, job_id: str):
        if job_id not in self.jobs:
            raise HTTPException(status_code=404, detail="Job ID not found")
        if self.jobs[job_id]["status"] == "failed":
            raise HTTPException(status_code=500, detail="Unknown error occurred during prediction")
        if self.jobs[job_id]["status"] != "completed":
            raise HTTPException(status_code=400, detail="Result not ready")
        return {"job_id": job_id, "result": self.jobs[job_id]["result"]}
