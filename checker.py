"""
MHT-CET Result Checker
Monitors the official MHT-CET website and calls you via Twilio when results go live.
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

# ── Configuration (set these as GitHub Secrets) ─────────────────────────────
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]   # e.g. +12015551234
YOUR_PHONE_NUMBER  = os.environ["YOUR_PHONE_NUMBER"]    # e.g. +919876543210

# ── URLs to monitor ──────────────────────────────────────────────────────────
URLS_TO_CHECK = [
    "https://cetcell.mahacet.org/",
    "https://mahacet.org/",
]

# ── Keywords that indicate results are available ─────────────────────────────
RESULT_KEYWORDS = [
    "result declared",
    "result available",
    "result out",
    "score card",
    "scorecard",
    "result link",
    "check result",
    "view result",
    "result announced",
    "mht cet result",
    "mhtcet result",
    "result 2025",
    "result 2026",
]

# ────────────────────────────────────────────────────────────────────────────

def fetch_page_text(url: str) -> str:
    """Download a page and return its visible text (lowercase)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script / style noise
    for tag in soup(["script", "style"]):
        tag.decompose()

    return soup.get_text(separator=" ").lower()


def check_for_results() -> tuple[bool, str]:
    """
    Returns (found: bool, matched_keyword: str).
    Checks all configured URLs for result keywords.
    """
    for url in URLS_TO_CHECK:
        print(f"Checking: {url}")
        try:
            text = fetch_page_text(url)
            for keyword in RESULT_KEYWORDS:
                if keyword in text:
                    print(f"  ✅ MATCH found — keyword: '{keyword}'")
                    return True, keyword
            print("  ⏳ No result keyword found yet.")
        except requests.RequestException as exc:
            print(f"  ⚠️  Could not reach {url}: {exc}")

    return False, ""


def make_phone_call(matched_keyword: str) -> None:
    """Place a Twilio voice call to notify the user."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Text-to-Speech message read over the call
    twiml_message = (
        "<Response>"
        "<Say voice='alice' language='en-IN'>"
        "Hello! This is your MHT CET result alert. "
        "Your MHT CET result has been declared and is now available online. "
        "Please visit the official M H T C E T website to check your result. "
        "Good luck!"
        "</Say>"
        "<Pause length='1'/>"
        "<Say voice='alice' language='en-IN'>"
        "Repeating: Your MHT CET result is now available. Visit mahacet dot org."
        "</Say>"
        "</Response>"
    )

    call = client.calls.create(
        twiml=twiml_message,
        to=YOUR_PHONE_NUMBER,
        from_=TWILIO_FROM_NUMBER,
    )
    print(f"📞 Phone call placed! Call SID: {call.sid}")


def main():
    print("=" * 50)
    print("  MHT-CET Result Checker")
    print("=" * 50)

    found, keyword = check_for_results()

    if found:
        print(f"\n🎉 Result detected via keyword: '{keyword}'")
        print("📞 Calling you now...")
        make_phone_call(keyword)
    else:
        print("\n🔍 Result not available yet. Will check again next run.")


if __name__ == "__main__":
    main()
