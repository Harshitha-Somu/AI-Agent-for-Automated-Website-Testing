import os
import json
import re
import time

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

from .playwright_executor import run_test_executor


def extract_search_text(instruction: str) -> str:
    """Best-effort fallback extraction when the LLM is unavailable."""
    instruction = instruction.strip()
    cleaned = re.sub(r"\b(and\s+)?(open|click|select|verify|check).*", "", instruction, flags=re.I)

    patterns = [
        r"search(?:\s+for)?\s+[\"']?(.+?)[\"']?$",
        r"type\s+[\"']?(.+?)[\"']?$",
        r"enter\s+[\"']?(.+?)[\"']?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            return match.group(1).strip(" \"'")
    return cleaned.strip(" \"'")


class GeminiAgent:
    """Plans browser actions with Gemini and delegates execution to Playwright."""

    def __init__(self):
        self.client = None
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        api_key = os.getenv("GEMINI_API_KEY")

        if genai and api_key:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception:
                self.client = None

    def plan_steps(self, instruction: str, target: str, page_snapshot: list) -> list:
        """Use the current page DOM to create site-independent browser actions."""
        if not self.client:
            raise RuntimeError(
                "Gemini client is not initialized. "
                "Please check GEMINI_API_KEY."
            )

        snapshot_json = json.dumps(page_snapshot, ensure_ascii=False, indent=2)
        prompt = f"""
You are an expert web-test planning agent.

User test instruction:
{instruction}

Target website:
{target}

The browser is already open on the target website. The following is a snapshot of
visible/interactive elements currently present on the page. Use ONLY these element
references when an action needs an element. Do not invent CSS selectors, IDs, or
text that are not present in the snapshot.

PAGE ELEMENTS:
{snapshot_json}

Return ONLY a JSON array. No markdown and no explanation.

Allowed actions:
1. fill: {{"action":"fill","ref":"e12","value":"text to enter"}}
2. click: {{"action":"click","ref":"e12"}}
3. press: {{"action":"press","ref":"e12","value":"Enter"}} or omit ref for a page-level key press
4. select: {{"action":"select","ref":"e12","value":"option value or visible label"}}
5. check: {{"action":"check","ref":"e12"}}
6. uncheck: {{"action":"uncheck","ref":"e12"}}
7. scroll: {{"action":"scroll","direction":"down"}}
8. wait: {{"action":"wait","value":1000}}
9. assert_text: {{"action":"assert_text","value":"text that must be visible"}}

Rules:
- Prefer the smallest number of actions that fully satisfy the instruction.
- For search boxes, use the actual ref of the search textbox from the snapshot.
- Use label, placeholder, aria_label, name, data_testid, or visible text from the snapshot to choose the correct element.
- For login/forms, use the ref whose label, placeholder, name, or nearby text matches the requested field.
- For buttons/links, use the ref whose accessible name or visible text matches the instruction.
- Never assume the site is Google, Amazon, Myntra, or any other specific website.
- Do not output navigation to the target URL because the browser is already there.
- Do not use JavaScript or arbitrary code as an action.
"""

        try:
            config = None
            if types:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )

            print("\n========== PLANNER DEBUG ==========")
            print("Instruction:", instruction)
            print("Target:", target)
            print("DOM elements:", len(page_snapshot))
            print("Snapshot characters:", len(snapshot_json))
            print("===================================\n")

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            text = (response.text or "").strip()
            print("\n========== GEMINI RAW RESPONSE ==========")
            print(text)
            print("==========================================\n")


            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
            steps = json.loads(text)
            print("\n========== PARSED STEPS ==========")
            print(steps)
            print("==================================\n")

            if not isinstance(steps, list):
                return []

            allowed = {"fill", "click", "press", "select", "check", "uncheck", "scroll", "wait", "assert_text"}
            clean_steps = []
            for step in steps:
                if not isinstance(step, dict) or step.get("action") not in allowed:
                    continue
                if step["action"] in {"fill", "click", "press", "select", "check", "uncheck"} and not step.get("ref"):
                    if step["action"] != "press":
                        continue
                clean_steps.append(step)
            return clean_steps
        except Exception as exc:
            print(f"Gemini planning failed: {exc}")
            raise RuntimeError(f"Gemini planning failed: {exc}") from exc

    def invoke(self, state):
        start_time = time.time()
        instruction = state.get("instruction", "").strip()
        target = state.get("target", "").strip()
        mode = state.get("mode", "execute")

        # Simulation has no live DOM, so let Gemini plan from the instruction alone.
        if mode == "simulate":
            steps = self.plan_steps(instruction, target, [])

            return {
                "status": "completed_simulated",
                "duration": round(time.time() - start_time, 2),
                "total_steps": len(steps),
                "passed_steps": len(steps),
                "failed_steps": 0,
                "step_results": [
                    {
                        "step": i + 1,
                        "action": s["action"],
                        "status": "simulated",
                        "detail": f"Planned action: {s.get('value', s.get('ref', 'page'))}",
                    }
                    for i, s in enumerate(steps)
                ],
            }

            return {
                "status": "completed_simulated",
                "duration": round(time.time() - start_time, 2),
                "total_steps": len(steps),
                "passed_steps": len(steps),
                "failed_steps": 0,
                "step_results": [
                    {
                        "step": i + 1,
                        "action": s["action"],
                        "status": "simulated",
                        "detail": f"Planned action: {s.get('value', s.get('ref', 'page'))}",
                    }
                    for i, s in enumerate(steps)
                ],
            }

        # For execution, Playwright navigates first, inspects the actual DOM, then
        # asks Gemini to plan against the current page. This removes domain-specific
        # Google/Amazon/Myntra selectors from the automation layer.
        report = run_test_executor(
            steps=[],
            target=target,
            planner=self.plan_steps,
            instruction=instruction,
        )

        total = len(report.get("step_results", []))
        passed = len([s for s in report.get("step_results", []) if s.get("status") == "ok"])

        report.update({
            "status": report.get("status", "executed"),
            "duration": round(time.time() - start_time, 2),
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": total - passed,
        })
        return report


def create_agent():
    return GeminiAgent()
