# ML Prediction Service

## Overview

This is an asynchronous machine learning prediction service built with FastAPI that provides transaction predictions based on member data. The service calculates average transaction size and probability to transact using a simple but effective algorithm.

## Key Features

- **Asynchronous Processing**: Job-based architecture for handling prediction requests
- **RESTful API**: Clean, modern API design with FastAPI
- **Comprehensive Testing**: Unit, integration, E2E, and stress tests included
- **Performance Monitoring**: Built-in metrics and logging
- **CI/CD Ready**: GitHub Actions workflow for automated testing

## Architecture

```
prediction_service/
├── app/                        # Main application code
│   ├── application/           
│   │   └── app.py            # Main FastAPI app with endpoints
│   ├── machine_learning/      
│   │   └── predict.py        # Core prediction algorithm
│   ├── models/               
│   │   └── prediction_request.py  # Pydantic request/response models
│   └── main.py              # Application entry point
├── tests/                    
│   ├── unit/                # Component-level tests
│   ├── integration/         # Component interaction tests
│   ├── e2e/                # End-to-end user journey tests
│   ├── stress/             # Performance and load tests
│   └── utils/              # Test utilities and helpers
├── test-reports/           # Generated test reports (HTML, JSON)
├── test-logs/             # Test execution logs
└── .github/workflows/     # CI/CD pipelines
```

### Tech Stack
- **Backend**: Python 3.9+, FastAPI
- **Testing**: pytest, pytest-asyncio, pytest-html
- **Dependencies**: See `requirements.txt`

## API Endpoints

### 1. Submit Prediction Request
```http
POST /predict
Content-Type: application/json

{
    "member_id": "user123",
    "balance": 1000.0,
    "last_purchase_size": 500.0,
    "last_purchase_date": "2024-01-01"
}
```

**Response:**
```json
{
    "average_transaction_size": 750.0,
    "probability_to_transact": 0.85
}
```

### 2. Check Job Status
```http
GET /status/{job_id}
```

**Response:**
```json
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed"
}
```

### 3. Get Job Results
```http
GET /result/{job_id}
```

**Response:**
```json
{
    "average_transaction_size": 750.0,
    "probability_to_transact": 0.85
}
```

### 4. Health Check
```http
GET /ping
```

**Response:**
```json
{
    "status": "ok"
}
```

## Prediction Algorithm

The service uses a straightforward prediction model:

### Average Transaction Size
```python
average_transaction_size = (balance + last_purchase_size) / 2
```

### Probability to Transact
```python
days_since_last_purchase = (current_date - last_purchase_date).days
probability_to_transact = max(0.0, 1.0 - (days_since_last_purchase / 365))
```

- Recent purchases (0 days) = 100% probability
- Decreases linearly over 365 days
- After 365 days = 0% probability

## Installation

### Prerequisites
- Python 3.9 or higher
- pip package manager
- Virtual environment (recommended)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd prediction_service
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r app/requirements.txt
pip install -r requirements-test.txt  # For testing
```

## Running the Application

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

## Testing

### Test Categories

The project uses pytest markers to categorize tests:

- **unit**: Fast, isolated component tests
- **integration**: Tests for component interactions
- **e2e**: Complete user journey tests
- **stress**: Performance and load tests

### Running Tests

#### Basic Test Execution
```bash
# Run all tests
./run_tests.sh

# Run specific test category
pytest -m unit
pytest -m integration
pytest -m e2e
```

#### Enhanced Test Runner
```bash
# Run all tests with reporting
python run_tests_enhanced.py

# Run specific suite
python run_tests_enhanced.py --suite unit

```


### Running Performance/Stress Tests

### 1. Web UI Mode (Interactive)

```bash
# Start Locust with web UI
locust -f tests/stress/locustfile.py --host http://localhost:8000

# Open browser at http://localhost:8089
# Configure number of users and spawn rate in the UI
```

### 2. Headless Mode (Command Line)

```bash
# Basic load test - 50 users, spawn 5/sec, run for 2 minutes
locust -f tests/stress/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 2m

# Stress test with specific user class
locust -f tests/stress/locustfile.py --host http://localhost:8000 --headless -u 200 -r 10 -t 5m --class-picker StressTestUser

# Generate HTML report
locust -f tests/stress/locustfile.py --host http://localhost:8000 --headless -u 100 -r 10 -t 3m --html stress_report.html
```

### 3. Using Test Scenarios

Run predefined test scenarios:

```bash
# Run a specific scenario
python -m tests.stress.test_scenarios smoke
python -m tests.stress.test_scenarios load
python -m tests.stress.test_scenarios stress
python -m tests.stress.test_scenarios spike


# Run all scenarios
python -m tests.stress.test_scenarios all
```

### Test Scenarios

| Scenario | Users | Spawn Rate | Duration | Purpose |
|----------|-------|------------|----------|---------|
| smoke | 5 | 1/s | 30s | Quick verification |
| load | 50 | 5/s | 3m | Normal load testing |
| stress | 200 | 10/s | 5m | Find breaking point |
| spike | 500 | 100/s | 2m | Sudden traffic spike |

The enhanced runner provides:
- HTML test reports
- JSON test results
- Coverage reports with HTML visualization
- Automatic application startup/shutdown
- Test timing and performance metrics


### Test Reports

Test reports are generated in:
- `test-reports/`: HTML and JSON test results
- `test-reports/htmlcov/`: Coverage HTML reports
- `test-logs/`: Detailed test execution logs

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration. The enhanced workflow (`ci-2.yml`) provides:

### Workflow Structure

1. **Deploy Application**: Initial setup and health check
2. **Parallel Testing**: Unit and integration tests run concurrently
3. **Sequential Testing**: E2E tests run after unit/integration
4. **Conditional Stress Tests**: 
   - Automatic on main branch pushes
   - Manual trigger via workflow dispatch

### Triggering Workflows

```yaml
# Automatic triggers
- Push to main or develop branches
- Pull requests to main branch

# Manual trigger for stress tests
- Go to Actions tab in GitHub
- Select "Enhanced CI/CD Pipeline"
- Click "Run workflow"
- Set "Run stress tests" to "true"
```

### Test Artifacts

All test runs produce downloadable artifacts:
- Test result HTML reports
- Coverage reports
- JSON test summaries

## Configuration

### Environment Variables

```bash
# Application settings
HOST=0.0.0.0
PORT=8000

# Test settings
PYTEST_TIMEOUT=300
TEST_LOG_LEVEL=INFO
```

### pytest Configuration

See `pytest.ini` for test configuration:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

## Monitoring and Logging

### Application Logs
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Performance metrics

### Health Monitoring
- `/ping` endpoint for health checks
- Response time tracking

## Performance Considerations

### Current Performance
- Throughput: ~10-50 requests/second
- Latency: 0-3 seconds (simulated delay)
- Memory: ~100MB base usage

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # Kill the process
   kill -9 <PID>
   ```

2. **Import Errors**
   ```bash
   # Ensure virtual environment is activated
   # Reinstall dependencies
   pip install -r app/requirements.txt
   pip install -r requirements-test.txt
   ```

3. **Test Failures**
   ```bash
   # Run with verbose output
   pytest -vv --tb=short
   # Check test logs
   cat test-logs/test_*.log
   ```
   
Note: There are some tests passing even without job id because they were designed with a workaround.