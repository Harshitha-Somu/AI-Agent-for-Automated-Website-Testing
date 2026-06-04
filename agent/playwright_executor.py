import os
import time
from playwright.sync_api import sync_playwright, TimeoutError


def run_test_executor(steps, target):
    results = []
    ss_dir = "static/screenshots"
    os.makedirs(ss_dir, exist_ok=True)

    run_id = int(time.time() * 1000)  # unique screenshots per run
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-setuid-sandbox",
                "--no-zygote"
            ]
        )

        context = browser.new_context(
            viewport={"width": 900, "height": 600},
            ignore_https_errors=True
        )

        page = context.new_page()

        # ---------------------------------
        # SAFE NAVIGATION (NO DEFAULT GOOGLE)
        # ---------------------------------
        if target:
            if target.startswith("/"):
                target = "http://localhost:5000" + target
            if not target.startswith("http"):
                target = "https://" + target

            page.goto(target, wait_until="domcontentloaded", timeout=30000)

        time.sleep(0.5)

        # ---------------------------------
        # AMAZON CONTINUE SHOPPING HANDLER
        # ---------------------------------
        try:
            if "amazon" in page.url.lower():
                if page.locator("text=Continue shopping").count() > 0:
                    page.click("text=Continue shopping", timeout=10000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(0.5)
        except Exception:
            pass

        # ---------------------------------
        # EXECUTE STEPS
        # ---------------------------------
        for i, step in enumerate(steps):
            try:
                action = step.get("action")
                value = step.get("value")

                if action == "fill":
                    url = page.url.lower()

                    if "amazon" in url:
                        selectors = [
                            "input#twotabsearchtextbox",
                            "input[aria-label='Search Amazon']"
                        ]
                    elif "google" in url:
                        selectors = [
                            "textarea[name='q']",
                            "input[name='q']"
                        ]
                    elif "myntra" in url:
                        selectors = [
                            "input.desktop-searchBar",
                            "input[placeholder*='Search']",
                            "input[aria-label*='Search']"
                        ]
                    else:
                        selectors = ["input"]

                    filled = False
                    for sel in selectors:
                        try:
                            page.wait_for_selector(sel, timeout=15000)
                            page.click(sel)
                            page.fill(sel, "")
                            page.type(sel, value, delay=60)
                            filled = True
                            break
                        except TimeoutError:
                            continue

                    if not filled:
                        raise Exception("Search input not found on page")

                elif action == "press":
                    page.keyboard.press(value)

                time.sleep(0.5)

                screenshot_name = f"run_{run_id}_step_{i + 1}.png"
                page.screenshot(path=os.path.join(ss_dir, screenshot_name))

                results.append({
                    "step": i + 1,
                    "action": action,
                    "status": "ok",
                    "screenshot": f"/static/screenshots/{screenshot_name}"
                })

            except Exception as e:
                screenshot_name = f"run_{run_id}_fail_{i + 1}.png"
                page.screenshot(path=os.path.join(ss_dir, screenshot_name))

                results.append({
                    "step": i + 1,
                    "action": action,
                    "status": "error",
                    "detail": str(e),
                    "screenshot": f"/static/screenshots/{screenshot_name}"
                })
                break

        context.close()
        browser.close()

    return {
        "status": "executed",
        "step_results": results
    }
