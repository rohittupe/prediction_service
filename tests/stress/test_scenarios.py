"""
Predefined test scenarios for Locust performance testing

Run these scenarios using:
python -m tests.stress.test_scenarios
"""

import subprocess
import sys
import time
import os
from datetime import datetime


class TestScenario:
    """Base class for test scenarios"""
    
    def __init__(self, name, description, users, spawn_rate, duration, user_class=None):
        self.name = name
        self.description = description
        self.users = users
        self.spawn_rate = spawn_rate
        self.duration = duration
        self.user_class = user_class
        self.host = os.environ.get("PREDICTION_SERVICE_URL", "http://localhost:8000")
    
    def get_command(self):
        """Get locust command for this scenario"""
        # Get the absolute path to the locustfile
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        locustfile_path = os.path.join(current_dir, "locustfile.py")
        project_root = os.path.dirname(os.path.dirname(current_dir))
        report_dir = os.path.join(project_root, "test_reports")
        
        # Ensure report directory exists
        os.makedirs(report_dir, exist_ok=True)
        
        cmd = [
            "locust",
            "-f", locustfile_path,
            "--host", self.host,
            "--headless",
            "-u", str(self.users),
            "-r", str(self.spawn_rate),
            "-t", self.duration,
            "--html", os.path.join(report_dir, f"stress_{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        ]
        
        if self.user_class:
            cmd.extend(["--class-picker", self.user_class])
        
        return cmd
    
    def run(self):
        """Execute the test scenario"""
        print(f"\n{'='*60}")
        print(f"Running: {self.name}")
        print(f"Description: {self.description}")
        print(f"Configuration: {self.users} users, spawn rate {self.spawn_rate}/s, duration {self.duration}")
        print(f"Target: {self.host}")
        print(f"{'='*60}\n")
        
        cmd = self.get_command()
        print(f"Command: {' '.join(cmd)}\n")
        
        try:
            subprocess.run(cmd, check=True)
            print(f"\n✓ {self.name} completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"\n✗ {self.name} failed with error: {e}")
            return False
        
        return True


# Define test scenarios
SCENARIOS = {
    "smoke": TestScenario(
        name="smoke_test",
        description="Quick smoke test to verify system is working",
        users=5,
        spawn_rate=1,
        duration="30s"
    ),
    
    "load": TestScenario(
        name="load_test",
        description="Standard load test with moderate users",
        users=50,
        spawn_rate=5,
        duration="3m"
    ),
    
    "stress": TestScenario(
        name="stress_test",
        description="Stress test to find breaking point",
        users=200,
        spawn_rate=10,
        duration="5m",
        user_class="StressTestUser"
    ),
    
    "spike": TestScenario(
        name="spike_test",
        description="Sudden spike in traffic",
        users=500,
        spawn_rate=100,
        duration="2m",
        user_class="SpikeTestUser"
    ),
}


def run_scenario(scenario_name):
    """Run a specific test scenario"""
    if scenario_name not in SCENARIOS:
        print(f"Error: Unknown scenario '{scenario_name}'")
        print(f"Available scenarios: {', '.join(SCENARIOS.keys())}")
        return False
    
    scenario = SCENARIOS[scenario_name]
    return scenario.run()


def run_all_scenarios():
    """Run all test scenarios in sequence"""
    results = {}
    
    for name, scenario in SCENARIOS.items():
        success = scenario.run()
        results[name] = success
        
        # Cool down between tests
        if success:
            print("\nCooling down for 30 seconds...")
            time.sleep(30)
    
    # Print summary
    print(f"\n{'='*60}")
    print("Test Summary:")
    print(f"{'='*60}")
    for name, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{name:20} {status}")
    
    return all(results.values())


def main():
    """Main entry point for running test scenarios"""
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        if scenario == "all":
            success = run_all_scenarios()
        else:
            success = run_scenario(scenario)
    else:
        print("Usage: python -m tests.stress.test_scenarios <scenario_name|all>")
        print(f"\nAvailable scenarios:")
        for name, scenario in SCENARIOS.items():
            print(f"  {name:15} - {scenario.description}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
