# Issues and Improvements - ML Prediction Service

## Current Issues

### 1. Critical Architecture Issues

#### 1.1 Infinite Recursion Bug
**Location**: `app/application/app.py:65`
```python
async def process_job(job_id: str, request: PredictionRequest):
    result = await predict(request)  # This calls predict endpoint again!
```
**Impact**: Stack overflow, application crash
**Severity**: CRITICAL

#### 1.2 Invalid Decorator Usage
**Location**: `app/machine_learning/predict.py:1`
```python
@staticmethod  # Used outside class context
async def get_predictions(request: PredictionRequest):
```
**Impact**: Syntax error, module won't load
**Severity**: CRITICAL

#### 1.3 API Design Inconsistency
**Issue**: `/predict` endpoint both returns results immediately AND creates an async job
**Impact**: Confusing API behavior, duplicate processing
**Severity**: HIGH

#### 1.4 API Design Inconsistency
**Issue**: `/predict` endpoint does not return correct response. The job id is missing from the response. The expected response fields are job id and status.
**Impact**: Confusing API behavior
**Severity**: HIGH

#### 1.5 Hardcoded Error Rate
**Issue**: 15% failure rate is hardcoded for testing but not configurable.
**Impact**: Cannot adjust failure rate for different environments.
**Severity**: LOW

### 2. Memory and Performance Issues

#### 2.1 Memory Leak
**Issue**: Jobs stored in memory without cleanup mechanism
```python
jobs = {}  # Never cleaned up
```
**Impact**: Continuous memory growth, eventual OOM
**Severity**: HIGH

#### 2.2 No Persistence
**Issue**: In-memory job storage lost on restart
**Impact**: Data loss, poor reliability
**Severity**: HIGH

#### 2.3 Artificial Performance Bottleneck
**Location**: `app/application/app.py:53`
```python
await asyncio.sleep(random.uniform(0, 3))  # Unnecessary delay
```
**Impact**: Reduced throughput
**Severity**: MEDIUM

### 3. Error Handling Issues

#### 3.1 Missing None Validation
**Issue**: No validation for None values in prediction logic
```python
days_since_last_purchase = (datetime.now().date() - last_purchase_date).days
# TypeError if last_purchase_date is None
```
**Severity**: HIGH

#### 3.2 No Error Recovery
**Issue**: Failed jobs have no retry mechanism
**Impact**: Poor reliability
**Severity**: MEDIUM

#### 3.3 No Structured Error Logging
**Issue**: Application currently logs less information, which makes it difficult to trace flows, monitor job state transitions, or debug failures in any environments.
**Impact**: Critical issues not logged, poor readability and debugging issues
**Severity**: MEDIUM

### 4. Security Issues

#### 4.1 No Input Validation Limits
**Issue**: No limits on input sizes
**Impact**: Resource exhaustion
**Severity**: MEDIUM

## Proposed Improvements

### 1. Architecture Improvements

#### 1.1 Fix Process Job Logic
```python
async def process_job(job_id: str, request: PredictionRequest):
    try:
        # Call the prediction function directly
        from app.machine_learning.predict import get_predictions
        result = await get_predictions(request)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
```

#### 1.2 Fix response for /predict Endpoint
```python
{
  "job_id": "some-uuid",
  "status": "processing"
}
```

#### 1.3 Fix API consistency
```python
# Current:
async def predict(self, prediction_request: PredictionRequest):
    job_id = str(uuid4())
    self.jobs[job_id] = {"status": "processing", "result": None}
    asyncio.create_task(self.process_job(job_id, prediction_request))
    await asyncio.sleep(random.random() * 3)  # Why sleep?
    return await get_predictions(prediction_request)  # Returns immediately!

# Recommended - Option 1: True Async API
async def predict(self, prediction_request: PredictionRequest):
    job_id = str(uuid4())
    self.jobs[job_id] = {"status": "processing", "result": None}
    asyncio.create_task(self.process_job(job_id, prediction_request))
    return {"job_id": job_id, "status": "processing"}

# Recommended - Option 2: Synchronous API
async def predict(self, prediction_request: PredictionRequest):
    try:
        result = await get_predictions(prediction_request)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```
### 2. Error Handling Improvements

#### 2.1 Add Input Validation
```python
async def get_predictions(prediction_request: PredictionRequest) -> Dict[str, float]:
    # Add validation
    if prediction_request.balance is None or prediction_request.last_purchase_size is None:
        raise ValueError("Balance and last_purchase_size are required")
    
    if prediction_request.balance < 0 or prediction_request.last_purchase_size < 0:
        raise ValueError("Balance and last_purchase_size must be non-negative")
    
```

### 3. Monitoring Improvements

#### 3.1 Add Structured Logging
```python
import logging

logger = logging.get_logger()

@app.post("/predict")
async def predict(request: PredictionRequest):
    logger.info("prediction_requested", member_id=request.member_id)
    
    try:
        result = await get_predictions(request)
        logger.info("prediction_completed", 
                   member_id=request.member_id,
                   avg_transaction=result["average_transaction_size"])
        return result
    except Exception as e:
        logger.error("prediction_failed", 
                    member_id=request.member_id,
                    error=str(e))
        raise
```
