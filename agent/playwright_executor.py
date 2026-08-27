"""

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

            page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=60000
            )
            page.wait_for_timeout(3000)

        page.wait_for_timeout(1000)

        # ---------------------------------
        # AMAZON CONTINUE SHOPPING HANDLER
        # ---------------------------------
        try:
            if "amazon" in page.url.lower():
                if page.locator("text=Continue shopping").count() > 0:
                    page.click("text=Continue shopping", timeout=10000)
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(1000)
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
                            "#twotabsearchtextbox",
                            "input[name='field-keywords']",
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
                            page.wait_for_selector(sel, timeout=30000)
                            page.click(sel)
                            page.fill(sel, value)
                            filled = True
                            break
                        except TimeoutError:
                            continue

                    if not filled:
                        raise Exception("Search input not found on page")

                elif action == "press":
                    page.keyboard.press(value)

                page.wait_for_timeout(1000)

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
"""




import os
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError


def _page_snapshot(page, limit=100):
    """
    Extract visible/interactable elements and assign stable AI references.

    The references are stored directly on the DOM as data-ai-ref attributes.
    This prevents the resolver from accidentally re-indexing a different
    element list later.
    """

    selector = (
        "input, textarea, select, button, a, "
        "[role='button'], [role='link'], "
        "[role='textbox'], [contenteditable='true']"
    )

    return page.locator(selector).evaluate_all(
        """
        (elements, limit) => {
            const visible = elements.filter(e => {
                const r = e.getBoundingClientRect();
                const s = getComputedStyle(e);

                return (
                    r.width > 0 &&
                    r.height > 0 &&
                    s.visibility !== 'hidden' &&
                    s.display !== 'none'
                );
            }).slice(0, limit);

            return visible.map((e, i) => {
                const ref = `e${i + 1}`;

                // Store the AI reference directly on the element.
                e.setAttribute("data-ai-ref", ref);

                return {
                    ref: ref,
                    tag: e.tagName.toLowerCase(),
                    type: e.getAttribute("type") || "",
                    role: e.getAttribute("role") || "",
                    name: e.getAttribute("name") || "",
                    id: e.id || "",
                    aria_label: e.getAttribute("aria-label") || "",
                    placeholder: e.getAttribute("placeholder") || "",
                    autocomplete: e.getAttribute("autocomplete") || "",

                    text: (
                        e.innerText ||
                        e.value ||
                        ""
                    ).trim().replace(/\\s+/g, " ").slice(0, 160),

                    title: e.getAttribute("title") || "",
                    href: e.getAttribute("href") || "",
                    data_testid: e.getAttribute("data-testid") || "",

                    label: (
                        e.labels && e.labels[0]
                            ? e.labels[0].innerText
                            : (
                                e.closest("label")
                                    ? e.closest("label").innerText
                                    : ""
                            )
                    ).trim().replace(/\\s+/g, " ").slice(0, 120)
                };
            });
        }
        """,
        limit,
    )


def _escape_css(value: str) -> str:
    # Quote an attribute value safely enough for ordinary HTML attributes.
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _generic_textbox(page):
    """Site-independent fallback for a fill action."""
    candidates = [
        "textarea:visible",
        "input:not([type='hidden']):not([type='submit']):not([type='button']):visible",
        "[contenteditable='true']:visible",
        "[role='textbox']:visible",
    ]
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible():
                return locator
        except Exception:
            pass
    return None


def _resolve_ref(page, ref):
    """
    Resolve an AI reference using the data-ai-ref attribute assigned
    during the DOM snapshot.
    """

    if not ref:
        return None

    ref = str(ref).strip()

    if not re.match(r"^e\d+$", ref):
        return None

    locator = page.locator(
        f'[data-ai-ref="{_escape_css(ref)}"]'
    ).first

    try:
        if locator.count() > 0 and locator.is_visible():
            return locator
    except Exception:
        return None

    return None


def _resolve_step_locator(page, step):
    """
    Resolve an AI-generated action target.

    Priority:
    1. Stable AI reference
    2. Explicit selector if supplied
    3. Generic textbox fallback for fill actions
    """

    ref = step.get("ref")

    if ref:
        locator = _resolve_ref(page, ref)

        if locator is not None:
            return locator

    selector = step.get("selector")

    if selector:
        try:
            locator = page.locator(selector).first

            if locator.count() > 0 and locator.is_visible():
                return locator
        except Exception:
            pass

    if step.get("action") == "fill":
        return _generic_textbox(page)

    return None


def run_test_executor(steps, target, planner=None, instruction=""):
    results = []
    ss_dir = "static/screenshots"
    os.makedirs(ss_dir, exist_ok=True)

    run_id = int(time.time() * 1000)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            #args=[
             #   "--disable-dev-shm-usage",
              #  "--no-sandbox",
              #  "--disable-gpu",
           # ],
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--disable-background-networking",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.on(
            "crash",
            lambda _: print("!!! PAGE CRASHED !!!")
        )

        page.on(
            "close",
            lambda _: print("!!! PAGE CLOSED !!!")
        )

        browser.on(
            "disconnected",
            lambda _: print("!!! BROWSER DISCONNECTED !!!")
        )

        try:
            if not target:
                raise ValueError("Target website URL is required")

            if target.startswith("/"):
                target = "http://localhost:5000" + target
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

            page.goto(target, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            print("\n========== PAGE DEBUG ==========")
            print("URL:", page.url)
            print("TITLE:", page.title())

            try:
                print("BODY TEXT:")
                print(page.locator("body").inner_text(timeout=10000)[:5000])
            except Exception as exc:
                print("BODY TEXT ERROR:", exc)

            print("================================\n")
            page.wait_for_timeout(1500)

            # NEW: inspect the actual website before deciding what to click/fill.
            if planner:
                snapshot = _page_snapshot(page)
                planned_steps = planner(instruction, target, snapshot)
                if planned_steps:
                    steps = planned_steps

            # LLM unavailable: use a generic, domain-independent search/fill fallback.
            """
            if not steps:
                search_text = instruction
                steps = [
                    {"action": "fill", "ref": None, "value": search_text},
                    {"action": "press", "value": "Enter"},
                ]
            """
            if not steps:
                raise RuntimeError(
                    "AI planner did not generate any valid browser actions. "
                    "Check GEMINI_API_KEY, Gemini response, or page DOM snapshot."
                )

            for i, step in enumerate(steps):
                action = step.get("action")
                value = step.get("value")
                if page.is_closed():
                    raise RuntimeError(
                        "Browser page was closed before executing the action."
                    )
                try:
                    if action == "fill":
                        locator = _resolve_step_locator(page, step)
                        if locator is None:
                            raise Exception("No visible text field could be resolved")
                        locator.click()
                        locator.fill(str(value or ""))

                    elif action == "click":
                        locator = _resolve_step_locator(page, step)
                        if locator is None:
                            raise Exception("Target element for click could not be resolved")
                        locator.click(timeout=15000)

                    elif action == "press":
                        locator = _resolve_step_locator(page, step)
                        if locator is not None:
                            locator.press(str(value or "Enter"))
                        else:
                            page.keyboard.press(str(value or "Enter"))

                    elif action == "select":
                        locator = _resolve_step_locator(page, step)
                        if locator is None:
                            raise Exception("Select element could not be resolved")
                        try:
                            locator.select_option(label=str(value))
                        except Exception:
                            locator.select_option(str(value))

                    elif action == "check":
                        locator = _resolve_step_locator(page, step)
                        if locator is None:
                            raise Exception("Checkbox could not be resolved")
                        locator.check()

                    elif action == "uncheck":
                        locator = _resolve_step_locator(page, step)
                        if locator is None:
                            raise Exception("Checkbox could not be resolved")
                        locator.uncheck()

                    elif action == "scroll":
                        amount = 700 if str(value or step.get("direction", "down")).lower() == "down" else -700
                        page.mouse.wheel(0, amount)

                    elif action == "wait":
                        page.wait_for_timeout(int(value or 1000))

                    elif action == "assert_text":
                        expected = str(value or "").strip()
                        if not expected:
                            raise Exception("assert_text requires a value")
                        page.get_by_text(expected, exact=False).first.wait_for(timeout=10000)

                    else:
                        raise Exception(f"Unsupported action: {action}")

                    page.wait_for_timeout(1000)
                    screenshot_name = f"run_{run_id}_step_{i + 1}.png"
                    page.screenshot(path=os.path.join(ss_dir, screenshot_name), full_page=False)

                    results.append({
                        "step": i + 1,
                        "action": action,
                        "status": "ok",
                        "detail": value or step.get("ref", ""),
                        "screenshot": f"/static/screenshots/{screenshot_name}",
                    })

                except Exception as exc:
                    screenshot_path = None

                    try:
                        if not page.is_closed():
                            screenshot_name = f"run_{run_id}_fail_{i + 1}.png"
                            page.screenshot(
                                path=os.path.join(ss_dir, screenshot_name),
                                full_page=False
                            )
                            screenshot_path = f"/static/screenshots/{screenshot_name}"
                    except Exception as screenshot_exc:
                        print(
                            "Could not capture failure screenshot:",
                            screenshot_exc
                        )

                    results.append({
                        "step": i + 1,
                        "action": action,
                        "status": "error",
                        "detail": str(exc),
                        "screenshot": screenshot_path,
                    })

                    break

        finally:
            try:
                context.close()
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass

    return {
        "status": "executed" if results and all(r["status"] == "ok" for r in results) else "error",
        "step_results": results,
    }
