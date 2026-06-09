"""
MHT-CET Result Checker — Keycloak Login Version
Portal: portal-2026.maharashtracet.org
Auth:   auth-2026.maharashtracet.org (Keycloak)
Flow:   Login → Dashboard → Score Card → Check PCM → Call via Twilio
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

# ── Credentials from GitHub Secrets ─────────────────────────────────────────
MHTCET_EMAIL    = os.environ["MHTCET_EMAIL"]
MHTCET_PASSWORD = os.environ["MHTCET_PASSWORD"]

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]
YOUR_PHONE_NUMBER  = os.environ["YOUR_PHONE_NUMBER"]

PORTAL_URL = "https://portal-2026.maharashtracet.org/"

# ── Phrases meaning result is NOT yet out ────────────────────────────────────
NOT_AVAILABLE_PHRASES = [
    "not available", "not declared", "will be declared",
    "coming soon", "not yet", "result awaited", "no result",
]

# ────────────────────────────────────────────────────────────────────────────

def get_driver():
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
    Handles Keycloak login at auth-2026.maharashtracet.org
    Keycloak standard field IDs: id='username', id='password', id='kc-login'
    """
    print(f"🌐 Opening portal (will redirect to Keycloak login)...")
    driver.get(PORTAL_URL)

    wait = WebDriverWait(driver, 20)

    try:
        # ── Wait for Keycloak login page ──────────────────────────────────
        print("⏳ Waiting for login form...")
        wait.until(EC.presence_of_element_located((By.ID, "username")))
        print(f"  ✅ Login page loaded: {driver.current_url}")

        # ── Email field (Keycloak uses id='username') ─────────────────────
        email_field = driver.find_element(By.ID, "username")
        email_field.clear()
        email_field.send_keys(MHTCET_EMAIL)
        print("  ✅ Entered email")

        # ── Password field (Keycloak uses id='password') ──────────────────
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(MHTCET_PASSWORD)
        print("  ✅ Entered password")

        # ── Sign In button ────────────────────────────────────────────────
        # Keycloak uses: <input id="kc-login" type="submit" value="Sign In">
        # Try id first, then fall back to any submit
        try:
            sign_in = driver.find_element(By.ID, "kc-login")
        except NoSuchElementException:
            sign_in = driver.find_element(
                By.XPATH,
                "//input[@type='submit'] | //button[@type='submit'] | "
                "//button[contains(translate(.,'SIGNIN','signin'),'sign in')]"
            )
        sign_in.click()
        print("  🔐 Clicked Sign In — waiting for dashboard...")

        # ── Wait until we land on the portal dashboard ────────────────────
        wait.until(EC.url_contains("portal-2026.maharashtracet.org"))
        time.sleep(2)

        # ── Confirm login didn't fail ─────────────────────────────────────
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(w in body for w in ["invalid", "incorrect", "wrong", "login failed"]):
            print("  ❌ Login failed — wrong email or password.")
            driver.save_screenshot("debug_login_failed.png")
            return False

        print(f"  ✅ Logged in! Dashboard at: {driver.current_url}")
        return True

    except TimeoutException:
        print("  ❌ Timed out waiting for login page or dashboard.")
        driver.save_screenshot("debug_timeout.png")
        return False
    except Exception as e:
        print(f"  ❌ Login error: {e}")
        driver.save_screenshot("debug_login_error.png")
        traceback.print_exc()
        return False


def go_to_scorecard(driver) -> bool:
    """
    Finds the 'Score Card / Get Score Card' tile on the dashboard and clicks it.
    Based on Image 2: tile has heading 'Score Card' and link 'Get Score Card →'
    """
    wait = WebDriverWait(driver, 15)
    print("\n📋 Finding 'Get Score Card' on dashboard...")

    # Priority order: exact link text → partial text → href keyword
    selectors = [
        (By.LINK_TEXT,         "Get Score Card"),
        (By.PARTIAL_LINK_TEXT, "Score Card"),
        (By.PARTIAL_LINK_TEXT, "Scorecard"),
        (By.XPATH, "//a[contains(translate(.,'SCORECARD','scorecard'),'score card')]"),
        (By.XPATH, "//a[contains(@href,'score') or contains(@href,'result')]"),
        (By.XPATH, "//button[contains(translate(.,'SCORECARD','scorecard'),'score card')]"),
    ]

    for by, value in selectors:
        try:
            el = wait.until(EC.element_to_be_clickable((by, value)))
            print(f"  ✅ Found Score Card link: '{el.text.strip()}' → clicking")
            el.click()
            time.sleep(4)
            print(f"  ✅ Score Card page: {driver.current_url}")
            return True
        except TimeoutException:
            continue
        except Exception:
            continue

    print("  ❌ Could not find Score Card link.")
    driver.save_screenshot("debug_dashboard.png")
    return False


def check_pcm_available(driver) -> bool:
    """
    On the Score Card page, detect whether the PCM score card is available.
    Returns True if result is live.
    """
    print(f"\n🔍 Checking for PCM result on: {driver.current_url}")

    body_text  = driver.find_element(By.TAG_NAME, "body").text
    body_lower = body_text.lower()

    # ── 1. Hard-stop: explicit "not available" message ───────────────────
    for phrase in NOT_AVAILABLE_PHRASES:
        if phrase in body_lower:
            print(f"  ⏳ Not available yet — page says: '{phrase}'")
            return False

    # ── 2. Check if PCM button/link is present and NOT disabled ──────────
    pcm_xpaths = [ 
        "//*[contains(text(),'PCM')]",
        "//*[contains(text(),'Physics') and contains(text(),'Chemistry')]",
        "//*[contains(text(),'MHT-CET PCM')]","//*[contains(text(),'PCB')]" "//*[contains(text(),'MHT-CET PCB')]",,
    ]

    for xpath in pcm_xpaths:
        elements = driver.find_elements(By.XPATH, xpath)
        for el in elements:
            tag      = el.tag_name.lower()
            disabled = el.get_attribute("disabled")
            classes  = (el.get_attribute("class") or "").lower()
            style    = (el.get_attribute("style")  or "").lower()

            is_disabled = (
                disabled is not None
                or "disabled" in classes
                or "locked"   in classes
                or "greyed"   in classes
                or "opacity"  in style        # greyed-out via CSS
            )

            if tag in ["a", "button"] and not is_disabled:
                print(f"  🎉 PCM is CLICKABLE — result is AVAILABLE!")
                driver.save_screenshot("result_found.png")
                return True

            if is_disabled:
                print(f"  ⏳ PCM element exists but is DISABLED (result not declared yet).")
                driver.save_screenshot("debug_pcm_disabled.png")
                return False

    # ── 3. Fallback: look for score/marks numbers on the page ────────────
    score_keywords = [
        "marks obtained", "total marks", "percentile",
        "your score", "rank", "download scorecard", "view scorecard"
    ]
    if any(kw in body_lower for kw in score_keywords):
        print(f"  🎉 Score data found on page — result is AVAILABLE!")
        driver.save_screenshot("result_found.png")
        return True

    print("  ⏳ PCM result not detected yet.")
    driver.save_screenshot("debug_scorecard.png")
    return False


def make_phone_call():
    """Place a Twilio voice call to the user."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    twiml = (
        "<Response>"
        "<Say voice='alice' language='en-IN'>"
        "Hello! Important update. Your MHT CET PCM Score Card is now available. "
        "Please login to portal 2026 dot maharashtracet dot org "
        "and click on Score Card to view and download your result. Good luck!"
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
        if not login(driver):
            print("\n⚠️  Login failed. Check MHTCET_EMAIL / MHTCET_PASSWORD secrets.")
            return

        if not go_to_scorecard(driver):
            print("\n⚠️  Could not open Score Card page.")
            return

        if check_pcm_available(driver):
            print("\n🎉 PCM RESULT IS AVAILABLE!")
            make_phone_call()
        else:
            print("\n🔍 Not available yet. Will check again in 15 minutes.")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        print("✅ Done.")

if __name__ == "__main__":
    main()
