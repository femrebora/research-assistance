#!/usr/bin/env python3
"""check_zerogpt.py — automated ZeroGPT AI detection via Playwright.

ZeroGPT has no API. This script uses Playwright to paste text into
zerogpt.com and extract the AI probability score.

Usage:
    ./check_zerogpt.py paper.md
    ./check_zerogpt.py paper.md --json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click


def check_text(text: str, timeout_ms: int = 60000) -> dict | None:
    """Submit text to ZeroGPT and return the AI score. Requires playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "playwright not installed. Run: pip install playwright && playwright install chromium"}

    # Truncate to avoid hitting limits (~15K chars is safe)
    text = text[:15000]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("https://www.zerogpt.com", timeout=30000)
            page.wait_for_selector("textarea", timeout=15000)

            # Fill the textarea
            textarea = page.locator("textarea").first
            textarea.fill(text)

            # Click the detect button (look for button containing "Detect")
            detect_btn = page.locator("button:has-text('Detect')").first
            detect_btn.click()

            # Wait for result — ZeroGPT shows a percentage
            page.wait_for_selector("[class*='percentage'], [class*='score'], [class*='result']", timeout=timeout_ms)

            # Give the animation time to finish
            time.sleep(3)

            # Extract the score
            result = {}
            page_content = page.content()

            # Try multiple selectors for the AI score
            import re
            # Look for percentage patterns like "68%" or "68.2%"
            percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%\s*(?:AI|Artificial)', page_content, re.IGNORECASE)
            if not percentages:
                percentages = re.findall(r'(?:AI|Artificial)[^%]*?(\d+(?:\.\d+)?)\s*%', page_content, re.IGNORECASE)
            if percentages:
                result["ai_probability_pct"] = float(percentages[0])

            # Also try extracting from visible text
            score_elements = page.locator("[class*='percentage'], [class*='score'], [class*='result-value']").all()
            for el in score_elements:
                txt = el.text_content()
                if txt and "%" in txt:
                    nums = re.findall(r'(\d+(?:\.\d+)?)\s*%', txt)
                    if nums:
                        result["ai_probability_pct"] = float(nums[0])
                        break

            if not result:
                result["raw_text"] = page.locator("body").text_content()[:500]

        except Exception as e:
            result = {"error": str(e)}
        finally:
            browser.close()

    return result


def check_file(path: str, timeout: int = 60) -> dict:
    """Check a markdown file via ZeroGPT."""
    text = Path(path).read_text(encoding="utf-8")
    return check_text(text, timeout_ms=timeout * 1000) or {"error": "No result"}


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--json", "-j", "as_json", is_flag=True, help="JSON output")
@click.option("--timeout", "-t", default=60, type=int, help="Timeout in seconds")
def main(file, as_json, timeout):
    """Check a paper via ZeroGPT for AI-generated text probability."""
    text = Path(file).read_text(encoding="utf-8")

    print(f"Checking {file} ({len(text)} chars) via ZeroGPT...", file=sys.stderr)

    result = check_text(text, timeout_ms=timeout * 1000)

    if result is None:
        print("Error: No result from ZeroGPT", file=sys.stderr)
        sys.exit(1)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    score = result.get("ai_probability_pct", "unknown")

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nZeroGPT AI Probability: {score}%")
        if isinstance(score, (int, float)):
            if score < 20:
                print("Verdict: Human-written")
            elif score < 50:
                print("Verdict: Mostly human")
            elif score < 80:
                print("Verdict: Mixed / partially AI")
            else:
                print("Verdict: Likely AI-generated")


if __name__ == "__main__":
    main()
