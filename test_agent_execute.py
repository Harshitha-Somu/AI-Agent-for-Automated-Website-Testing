# test_agent_execute.py
"""
from agent.base_agent import create_agent

# Initialize agent
agent = create_agent()

# Define the input instruction and target
input_state = {
    "instruction": 'search google for "LangGraph agent"',
    "target": "google",
    "mode": "execute" # Run in actual execution mode
}

print("Running test in EXECUTE mode...")
result = agent.invoke(input_state)

print("\n--- TEST REPORT ---")
print(f"Status: {result.get('status')}")
print(f"Duration: {result.get('duration_sec', 0)}s")
print(f"Total Steps: {result.get('total_steps')}")
print(f"Passed Assertions: {result.get('passed_steps')}")
print(f"Failed Assertions: {result.get('failed_steps')}")

for step in result.get("step_results", []):
    screenshot_link = f"(Screenshot: {step['screenshot']})" if step.get('screenshot') else ""
    print(f"  Step {step['step']} ({step['status']}): {step['action']} - {step['detail']} {screenshot_link}")

if result.get('status') == 'error_analyzed':
    print("\n--- FAILURE ANALYSIS ---")
    print(result['failure_analysis_report'])

"""

from agent.base_agent import create_agent

agent = create_agent()

input_state = {
    "instruction": 'search for "Playwright"',
    "target": "https://www.wikipedia.org",
    "mode": "execute",
}

print("Running universal website test...")
result = agent.invoke(input_state)

print("\n--- TEST REPORT ---")
print(f"Status: {result.get('status')}")
print(f"Duration: {result.get('duration', 0)}s")
print(f"Total Steps: {result.get('total_steps')}")
print(f"Passed Steps: {result.get('passed_steps')}")
print(f"Failed Steps: {result.get('failed_steps')}")

for step in result.get("step_results", []):
    screenshot_link = f"(Screenshot: {step['screenshot']})" if step.get('screenshot') else ""
    print(f"  Step {step['step']} ({step['status']}): {step['action']} {screenshot_link}")
