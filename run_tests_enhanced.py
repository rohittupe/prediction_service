#!/usr/bin/env python3
"""Enhanced test runner with reporting and analysis."""
import os
import sys
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
import argparse
from typing import Dict, List, Any


class TestRunner:
    """Enhanced test runner with reporting capabilities."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_reports_dir = self.project_root / "test-reports"
        self.test_logs_dir = self.project_root / "test-logs"

        self.test_reports_dir.mkdir(exist_ok=True)
        self.test_logs_dir.mkdir(exist_ok=True)

        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def setup_environment(self):
        """Set up the test environment."""
        print("🔧 Setting up test environment...")

        venv_path = self.project_root / "venv"
        if not venv_path.exists():
            print("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

        pip_cmd = str(venv_path / "bin" / "pip") if os.name != 'nt' else str(venv_path / "Scripts" / "pip")

        print("Installing dependencies...")
        subprocess.run([pip_cmd, "install", "-q", "-r", "app/requirements.txt"], check=True)
        subprocess.run([pip_cmd, "install", "-q", "-r", "requirements-test.txt"], check=True)

        print("✅ Environment setup complete")

    def start_application(self) -> subprocess.Popen:
        """Start the application server."""
        print("\n🚀 Starting application...")

        app_dir = self.project_root / "app"
        
        app_process = subprocess.Popen(
            ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=app_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(3)

        try:
            import requests
            response = requests.get("http://localhost:8000/ping")
            if response.status_code == 200:
                print("✅ Application started successfully")
            else:
                print("❌ Application failed to start")
                app_process.terminate()
                sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to connect to application: {e}")
            app_process.terminate()
            sys.exit(1)

        return app_process

    def run_tests(self, test_suite: str = "all", markers: List[str] = None) -> Dict[str, Any]:
        """Run tests with specified configuration."""
        print(f"\n🧪 Running {test_suite} tests...")

        pytest_cmd = [
            str(self.project_root / "venv" / "bin" / "pytest") if os.name != 'nt' else str(
                self.project_root / "venv" / "Scripts" / "pytest"),
            "-v",
            "--tb=short",
            f"--html=test-reports/{test_suite}_{self.timestamp}.html",
            "--cov=app",
            "--cov-report=html:test-reports/htmlcov",
            f"--json-report-file=test-reports/{test_suite}_{self.timestamp}.json",
            "--json-report-summary",
            "--self-contained-html"
        ]

        if markers:
            for marker in markers:
                pytest_cmd.extend(["-m", marker])
        elif test_suite != "all":
            pytest_cmd.extend(["-m", test_suite])

        result = subprocess.run(pytest_cmd, capture_output=True, text=True)

        test_results = {
            "suite": test_suite,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }

        json_report_path = self.test_reports_dir / f"{test_suite}_{self.timestamp}.json"
        if json_report_path.exists():
            with open(json_report_path, 'r') as f:
                test_results["json_report"] = json.load(f)

        return test_results

    def generate_summary_report(self, all_results: List[Dict[str, Any]]):
        """Generate a summary report of all test runs."""
        print("\n📊 Generating summary report...")

        summary = {
            "timestamp": self.timestamp,
            "total_suites": len(all_results),
            "passed_suites": sum(1 for r in all_results if r["success"]),
            "failed_suites": sum(1 for r in all_results if not r["success"]),
            "detailed_results": []
        }

        for result in all_results:
            if "json_report" in result:
                json_report = result["json_report"]
                suite_summary = {
                    "suite": result["suite"],
                    "duration": json_report.get("duration", 0),
                    "total_tests": len(json_report.get("tests", [])),
                    "passed": sum(1 for t in json_report.get("tests", []) if t["outcome"] == "passed"),
                    "failed": sum(1 for t in json_report.get("tests", []) if t["outcome"] == "failed"),
                    "skipped": sum(1 for t in json_report.get("tests", []) if t["outcome"] == "skipped"),
                    "error": sum(1 for t in json_report.get("tests", []) if t["outcome"] == "error")
                }
                summary["detailed_results"].append(suite_summary)

        summary_path = self.test_reports_dir / f"summary_{self.timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print("\n" + "=" * 60)
        print("TEST EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Total Test Suites: {summary['total_suites']}")
        print(f"Passed Suites: {summary['passed_suites']}")
        print(f"Failed Suites: {summary['failed_suites']}")

        for suite in summary["detailed_results"]:
            print(f"\n{suite['suite'].upper()} Tests:")
            print(f"  Total: {suite['total_tests']}")
            print(f"  Passed: {suite['passed']} ✅")
            print(f"  Failed: {suite['failed']} ❌")
            print(f"  Skipped: {suite['skipped']} ⏭️")
            print(f"  Duration: {suite['duration']:.2f}s")

        print("\n" + "=" * 60)
        print(f"Reports saved to: {self.test_reports_dir}")
        print(f"Logs saved to: {self.test_logs_dir}")

    def run_all_test_suites(self, include_stress: bool = False):
        """Run all test suites in order."""
        test_suites = [
            # ("smoke", ["smoke"]),
            ("unit", ["unit"]),
            ("integration", ["integration"]),
            ("e2e", ["e2e"])
        ]

        if include_stress:
            test_suites.append(("stress", ["stress"]))

        all_results = []

        for suite_name, markers in test_suites:
            print(f"\n{'=' * 60}")
            print(f"Running {suite_name.upper()} test suite")
            print('=' * 60)

            result = self.run_tests(suite_name, markers)
            all_results.append(result)

            if not result["success"]:
                print(f"⚠️  {suite_name} tests failed!")

        return all_results

    def cleanup(self, app_process: subprocess.Popen):
        """Clean up after test run."""
        print("\n🧹 Cleaning up...")
        app_process.terminate()
        app_process.wait(timeout=5)
        print("✅ Cleanup complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enhanced test runner for ML Prediction Service")
    parser.add_argument(
        "--suite",
        choices=["all", "unit", "integration", "e2e", "stress"],  # "smoke"
        default="all",
        help="Test suite to run"
    )
    parser.add_argument(
        "--with-stress",
        action="store_true",
        help="Include stress tests (only with --suite all)"
    )
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="Skip environment setup"
    )

    args = parser.parse_args()

    runner = TestRunner()

    if not args.no_setup:
        runner.setup_environment()

    app_process = runner.start_application()

    try:
        if args.suite == "all":
            results = runner.run_all_test_suites(include_stress=args.with_stress)
            runner.generate_summary_report(results)
        else:
            result = runner.run_tests(args.suite)
            runner.generate_summary_report([result])

    finally:
        runner.cleanup(app_process)


if __name__ == "__main__":
    main()
