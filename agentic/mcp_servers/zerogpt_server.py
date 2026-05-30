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
    """Submit text to ZeroGPT via Playwright and extract the AI score.

    Two extraction methods:
    1. Intercept the API response (api.zerogpt.com/api/detect/detectText) — primary
    2. Read the gauge rotation from semi-circle--mask element — fallback

    The API returns fakePercentage (0-100) directly.
    The gauge rotation maps: 0deg = 0% AI, 180deg = 100% AI.
    """
    from playwright.sync_api import sync_playwright

    text = text[:MAX_TEXT_LENGTH]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Intercept API response
        api_data = {}

        def _on_response(response):
            if "detectText" in response.url and "api" in response.url:
                try:
                    body = response.json()
                    data = body.get("data", {})
                    api_data["fake_percentage"] = data.get("fakePercentage")
                    api_data["is_human"] = data.get("isHuman")
                    api_data["ai_words"] = data.get("aiWords", 0)
                    api_data["text_words"] = data.get("textWords", 0)
                    api_data["sentences"] = data.get("sentences", [])
                except Exception:
                    pass

        page.on("response", _on_response)

        try:
            page.goto("https://www.zerogpt.com", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_selector("textarea", timeout=15000)

            textarea = page.locator("textarea").first
            textarea.fill(text)
            time.sleep(0.5)

            detect_btn = page.locator("button:has-text('Detect')").first
            detect_btn.click()

            # Wait up to 20s for either API response or gauge change
            for _ in range(20):
                time.sleep(1)
                if api_data:
                    break

            if api_data and api_data.get("fake_percentage") is not None:
                fp = float(api_data["fake_percentage"])
                ai_sentences = [s for s in api_data.get("sentences", [])
                                if s.get("h") == "ai"]
                return {
                    "ai_probability_pct": fp,
                    "is_human_score": api_data.get("is_human"),
                    "ai_words": api_data["ai_words"],
                    "text_words": api_data["text_words"],
                    "total_sentences": len(api_data.get("sentences", [])),
                    "ai_flagged_sentences": len(ai_sentences),
                    "verdict": (
                        "human" if fp < 20
                        else "mostly-human" if fp < 50
                        else "mixed" if fp < 80
                        else "ai-generated"
                    ),
                }

            # Fallback: read gauge rotation from DOM
            page_content = page.content()
            rotations = re.findall(
                r'semi-circle--mask[^>]*rotate\(([\d.]+)deg\)',
                page_content,
            )
            if rotations:
                deg = float(rotations[0])
                # 0deg = 0% AI, 180deg = 100% AI
                ai_pct = round(deg / 180.0 * 100, 1)
                return {
                    "ai_probability_pct": ai_pct,
                    "extraction_method": "gauge-rotation",
                    "gauge_degrees": deg,
                    "verdict": (
                        "human" if ai_pct < 20
                        else "mostly-human" if ai_pct < 50
                        else "mixed" if ai_pct < 80
                        else "ai-generated"
                    ),
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
