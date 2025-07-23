# QA Automation Take-Home Assignment

Welcome, and thank you for your interest in joining us as the Senior Software Developer in Test!

This take-home assignment is designed to evaluate your ability to design and implement automated tests for an ML-powered application using asynchronous endpoints. You’ll also demonstrate your familiarity with testing frameworks, CI/CD integration, and collaborative development practices.

---

## 🧪 Assignment Overview

You will build a test suite for a simplified asynchronous ML service. The service mimics a real-world system where predictions are requested via an API, processed in the background, and later retrieved by the client.

### ✅ What You’ll Be Testing

The API consists of the following endpoints:

- `POST /predict`: Accepts input data and, if successful, returns predictions.
- `GET /status/<job_id>`: Polls for the job status (`pending`, `complete`, or `failed`).
- `GET /result/<job_id>`: Retrieves the final prediction once complete.

---

## 🧩 Your Tasks

### 1. **Test Implementation**
- Use Python and a framework like `pytest` to:
  - Test each API endpoint
  - Handle asynchronous behavior and job polling
  - Mock or stub components for unit tests
  - Pay special attention to edge cases and failure scenarios when creating the tests
  - Do stress and concurrency testing

### 2. **CI/CD Integration**
- Add a GitHub Actions (or similar) CI configuration to:
  - Spin up the app (via `Docker`, local, or any other methodology)
  - Run your test suite on each push

### 3. **Code Reccomendations**
- The code you are provided with is not perfect by any means. As you are testing/reading the code, you will likely have ideas on possible improvements and gotchas to avoid. Feel free to include improvement suggestions to the code in your submission.

---

## 📦 Submission

Please submit:

- Your source code (tests, mocks, CI config)
- A `README.md` with instructions on how to run your tests locally, as well as any additional notes/considerations/suggestions etc. you might have.

You can either:
- Upload your code as a zip file, or
- Share a link to a GitHub/GitLab etc. repo

---

Good luck! We’re excited to see your approach.