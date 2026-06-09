"""
MHT-CET Result Checker — Exact Login Version
Based on: auth-2026.maharashtracet.org + portal-2026.maharashtracet.org
Logs in → clicks Score Card → checks if PCM result is available → calls you!
"""

import os
import time
import traceback
from twilio.rest import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ── Credentials (stored as GitHub Secrets) ───────────────────────────────────
MHTCET_EMAIL    = os.environ["MHTCET_EMAIL"]
MHTCET_PASSWORD = os.environ["MHTCET_PASSWORD"]

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]  # e.g. +12015551234
YOUR_PHONE_NUMBER  = os.environ["YOUR_PHONE_NUMBER"]   # e.g. +919876543210

# ── URLs ─────────────────────────────────────────────────────────────────────
PORTAL_URL = "https://portal-2026.maharashtracet.org/"
# Portal auto-redirects to login if not logged in

# ── Keywords that mean result is NOT yet available ───────────────────────────
NOT_AVAILABLE_PHRASES = [
    "not available",
    "not declared",
    "will be declared",
    "coming soon",
    "not yet",
    "result awaited",
    "no result",
]

# ────────────────────────────────────────────────────────────────────────────

def get_driver():
    """Create a headless Chrome browser."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def login(driver) -> bool:
    """
    Opens portal (auto-redirects to login page).
    Fills Registered Email ID + Password → clicks Sign In.
    """
    print(f"🌐 Opening portal: {PORTAL_URL}")
    driver.get(PORTAL_URL)

    wait = WebDriverWait(driver, 20)

    try:
        # Wait for the login form to appear
        print("⏳ Waiting for login page...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @type='email']")))
        time.sleep(1)

        # ── Registered Email ID field ─────────────────────────────────────
        email_field = driver.find_element(By.XPATH, "//input[@type='text' or @type='email']")
        email_field.clear()
        email_field.send_keys(MHTCET_EMAIL)
        print(f"  ✅ Entered email")

        # ── Password field ─────────────────────────────────────────────────
        password_field = driver.find_element(By.XPATH, "//input[@type='password']")
        password_field.clear()
        password_field.send_keys(MHTCET_PASSWORD)
        print(f"  ✅ Entered password")

        # ── Sign In button ─────────────────────────────────────────────────
        sign_in_btn = driver.find_element(
            By.XPATH,
            "//button[contains(text(),'Sign In') or contains(text(),'sign in') or contains(text(),'LOGIN') or @type='submit']"
        )
        sign_in_btn.click()
        print("  🔐 Clicked Sign In...")

        # Wait for dashboard to load (URL changes to portal)
        wait.until(EC.url_contains("portal-2026.maharashtracet.org"))
        print(f"  ✅ Logged in! Dashboard loaded.")
        time.sleep(2)
        return True

    except TimeoutException:
        print("  ❌ Login timed out — page didn't load or redirect failed.")
        driver.save_screenshot("debug_login_timeout.png")
        return False
    except NoSuchElementException as e:
        print(f"  ❌ Could not find login element: {e}")
        driver.save_screenshot("debug_login_element.png")
        return False
    except Exception as e:
        print(f"  ❌ Login error: {e}")
        driver.save_screenshot("debug_login_error.png")
        traceback.print_exc()
        return False


def go_to_scorecard(driver) -> bool:
    """
    On the dashboard, find the 'Score Card' tile and click 'Get Score Card'.
    Returns True if navigation succeeded.
    """
    wait = WebDriverWait(driver, 15)
    print("\n📋 Looking for Score Card section on dashboard...")

    try:
        # Find "Get Score Card" link — visible in Image 2
        scorecard_link = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//*[contains(text(),'Get Score Card') or contains(text(),'Score Card') or contains(text(),'Scorecard')]"
            "[self::a or self::button or ancestor::a or ancestor::button]"
        )))
        print(f"  ✅ Found Score Card link: '{scorecard_link.text}'")
        scorecard_link.click()
        time.sleep(3)
        print(f"  ✅ Navigated to Score Card page: {driver.current_url}")
        return True

    except TimeoutException:
        # Try finding any link with scorecard href
        try:
            links = driver.find_elements(By.XPATH, "//a[contains(@href,'score') or contains(@href,'result')]")
            if links:
                print(f"  🔗 Found score/result link via href: {links[0].get_attribute('href')}")
                links[0].click()
                time.sleep(3)
                return True
        except Exception:
            pass

        print("  ❌ Could not find Score Card link on dashboard.")
        driver.save_screenshot("debug_dashboard.png")
        return False


def check_pcm_available(driver) -> bool:
    """
    On the Score Card page, check if PCM result is actually available.
    Returns True if PCM score card is available.
    """
    wait = WebDriverWait(driver, 10)
    current_url = driver.current_url
    print(f"\n🔍 Checking Score Card page for PCM result... ({current_url})")

    page_text = driver.find_element(By.TAG_NAME, "body").text

    # ── Check for "not available" messages first ──────────────────────────
    page_lower = page_text.lower()
    for phrase in NOT_AVAILABLE_PHRASES:
        if phrase in page_lower:
            print(f"  ⏳ Result not yet available (found: '{phrase}')")
            return False

    # ── Look specifically for PCM ─────────────────────────────────────────
    pcm_indicators = ["PCM", "Physics", "Chemistry", "Mathematics", "MHT-CET PCM"]
    pcm_found = any(indicator in page_text for indicator in pcm_indicators)

    # ── Look for score/marks data (means result is declared) ─────────────
    score_indicators = [
        "Total Marks", "Marks Obtained", "Percentile",
        "Score", "Rank", "Download", "View Score"
    ]
    score_data_found = any(indicator in page_text for indicator in score_indicators)

    # ── Check if PCM option is clickable (not disabled/greyed) ───────────
    try:
        pcm_elements = driver.find_elements(
            By.XPATH,
            "//*[contains(text(),'PCM') or contains(text(),'Physics, Chemistry')]"
        )
        for el in pcm_elements:
            # If element is a clickable link/button, result is likely available
            tag = el.tag_name
            disabled = el.get_attribute("disabled")
            classes = el.get_attribute("class") or ""

            if tag in ["a", "button"] and not disabled and "disabled" not in classes.lower():
                print(f"  🎉 PCM element is CLICKABLE — result likely available!")
                driver.save_screenshot("result_available.png")
                return True

            if disabled or "disabled" in classes.lower() or "locked" in classes.lower():
                print(f"  ⏳ PCM element found but is DISABLED — result not yet available.")
                return False

    except Exception as e:
        print(f"  ⚠️  Error checking PCM element: {e}")

    # ── Final decision based on page content ─────────────────────────────
    if pcm_found and score_data_found:
        print("  🎉 PCM + Score data both found — result is AVAILABLE!")
        driver.save_screenshot("result_available.png")
        return True

    if pcm_found and not score_data_found:
        print("  ⏳ PCM section exists but no score data yet — result not declared.")
        return False

    print("  ⏳ PCM result not detected on this page.")
    driver.save_screenshot("debug_scorecard_page.png")
    return False


def make_phone_call():
    """Call the user via Twilio to announce result availability."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    twiml = (
        "<Response>"
        "<Say voice='alice' language='en-IN'>"
        "Hello! Urgent alert. Your MHT CET PCM Score Card is now available on the portal. "
        "Please login to portal-2026 dot maharashtracet dot org "
        "and click on Score Card to view and download your PCM result. "
        "All the best!"
        "</Say>"
        "<Pause length='1'/>"
        "<Say voice='alice' language='en-IN'>"
        "Repeating: Your MHT CET PCM Score Card is now available. Please check now!"
        "</Say>"
        "</Response>"
    )

    call = client.calls.create(
        twiml=twiml,
        to=YOUR_PHONE_NUMBER,
        from_=TWILIO_FROM_NUMBER,
    )
    print(f"📞 Call placed! SID: {call.sid}")


def main():
    print("=" * 55)
    print("  MHT-CET PCM Score Card Checker")
    print("=" * 55)

    driver = get_driver()

    try:
        # Step 1: Login
        if not login(driver):
            print("\n⚠️  Login failed. Check MHTCET_EMAIL / MHTCET_PASSWORD secrets.")
            return

        # Step 2: Go to Score Card section
        if not go_to_scorecard(driver):
            print("\n⚠️  Could not navigate to Score Card page.")
            return

        # Step 3: Check if PCM result is available
        if check_pcm_available(driver):
            print("\n🎉 PCM RESULT IS AVAILABLE! Calling you now...")
            make_phone_call()
        else:
            print("\n🔍 PCM result not yet available. Will check again in 15 minutes.")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()

    finally:
        driver.quit()
        print("\n✅ Browser closed.")


if __name__ == "__main__":
    main()
