#!/usr/bin/env python3
"""ZeroGPT MCP Server — automated AI detection via browser automation.

ZeroGPT has no API. This MCP server uses Playwright to submit text to
zerogpt.com and extract the AI probability score.

Provides:
  - check_ai_score(text) — returns AI probability % from ZeroGPT
  - check_file(path)     — checks a file via ZeroGPT

Run: python agentic/mcp_servers/zerogpt_server.py
Requires: playwright (pip install playwright && playwright install chromium)
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PaperForge ZeroGPT")

MAX_TEXT_LENGTH = 15000  # ZeroGPT limit


def _check_via_playwright(text: str, timeout_ms: int = 60000) -> dict:
    """Submit text to ZeroGPT via Playwright and extract the AI score."""
    from playwright.sync_api import sync_playwright
    import playwright  # noqa: F811

    text = text[:MAX_TEXT_LENGTH]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("https://www.zerogpt.com", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_selector("textarea", timeout=15000)

            textarea = page.locator("textarea").first
            textarea.fill(text)
            time.sleep(0.5)

            detect_btn = page.locator("button:has-text('Detect')").first
            detect_btn.click()

            # Wait for result
            time.sleep(3)
            page.wait_for_timeout(2000)

            page_content = page.content()

            # Extract AI percentage
            percentages = re.findall(
                r'(\d+(?:\.\d+)?)\s*%\s*(?:AI|Artificial)',
                page_content, re.IGNORECASE
            )
            if not percentages:
                percentages = re.findall(
                    r'(?:AI|Artificial)[^%]*?(\d+(?:\.\d+)?)\s*%',
                    page_content, re.IGNORECASE
                )

            if percentages:
                return {
                    "ai_probability_pct": float(percentages[0]),
                    "verdict": (
                        "human" if float(percentages[0]) < 20
                        else "mostly-human" if float(percentages[0]) < 50
                        else "mixed" if float(percentages[0]) < 80
                        else "ai-generated"
                    ),
                }

            # Try visible elements
            score_els = page.locator(
                "[class*='percentage'], [class*='score'], [class*='result-value']"
            ).all()
            for el in score_els:
                txt = el.text_content()
                if txt and "%" in txt:
                    nums = re.findall(r'(\d+(?:\.\d+)?)\s*%', txt)
                    if nums:
                        return {
                            "ai_probability_pct": float(nums[0]),
                            "verdict": "see score",
                        }

            return {"error": "Could not extract AI score", "raw_snippet": page_content[:500]}

        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()


@mcp.tool()
def check_ai_score(text: str) -> str:
    """Check if text is AI-generated using ZeroGPT (zerogpt.com).

    Submits the text via Playwright browser automation and returns
    the AI probability percentage (0-100%). Lower = more human-like.

    ZeroGPT analyzes statistical patterns: perplexity, burstiness,
    word distribution, and structural uniformity.

    Args:
        text: The text to check (max ~15000 characters)

    Returns:
        AI probability percentage and verdict
    """
    if len(text) < 50:
        return "Error: Text too short (need >50 characters)"

    result = _check_via_playwright(text)

    if "error" in result:
        return f"ZeroGPT error: {result['error']}"

    score = result.get("ai_probability_pct", "?")
    verdict = result.get("verdict", "?")
    return f"ZeroGPT AI Score: {score}%\nVerdict: {verdict}"


@mcp.tool()
def check_file(path: str) -> str:
    """Check a file's AI-generated probability via ZeroGPT.

    Reads the file, submits to zerogpt.com via Playwright,
    and returns the AI score.

    Args:
        path: Path to the file to check

    Returns:
        AI probability percentage and verdict
    """
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"Error reading file: {e}"

    return check_ai_score(text)


if __name__ == "__main__":
    print("PaperForge ZeroGPT MCP Server starting...", file=sys.stderr)
    mcp.run()
