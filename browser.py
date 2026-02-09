import json
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import IG_USERNAME, IG_PASSWORD, COOKIES_FILE


def get_browser():
    """Create and return a Chrome browser instance."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Make the browser look more human
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1280,900")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"[Error] Could not open Chrome: {e}")
        print()
        print("  Make sure Google Chrome is installed.")
        print("  Selenium 4 auto-downloads chromedriver, so you only need Chrome itself.")
        sys.exit(1)

    # Remove the "controlled by automated software" indicator
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception:
        pass
    return driver


def save_cookies(driver):
    """Save browser cookies to file for session reuse."""
    cookies = driver.get_cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)


def load_cookies(driver):
    """Load saved cookies into the browser."""
    if not COOKIES_FILE.exists():
        return False
    try:
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)
        driver.get("https://www.instagram.com/")
        time.sleep(3)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("storeId", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        return True
    except Exception:
        return False


def is_logged_in(driver):
    """Check if we're logged into Instagram."""
    driver.get("https://www.instagram.com/")
    time.sleep(4)
    try:
        driver.find_element(By.NAME, "username")
        return False  # login form found = not logged in
    except Exception:
        return True  # no login form = logged in


def login(driver):
    """
    Log into Instagram using the browser.

    Auto-fills username/password from .env, then waits for the user
    to handle 2FA/challenges in the browser and press Enter here.
    """
    print("[Login] Opening Instagram login page...")
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(5)

    if not IG_USERNAME or not IG_PASSWORD:
        print()
        print("[Login] No credentials in .env - log in manually in the browser.")
        print()
        input("  When you're fully logged in and see your feed, press Enter here... ")
        return

    # Auto-fill credentials
    try:
        print("[Login] Entering credentials...")
        username_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        # Type slowly to look more human
        username_field.clear()
        for char in IG_USERNAME:
            username_field.send_keys(char)
            time.sleep(0.05)

        time.sleep(1)

        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        for char in IG_PASSWORD:
            password_field.send_keys(char)
            time.sleep(0.05)

        time.sleep(1)
        password_field.send_keys(Keys.ENTER)
        print("[Login] Credentials submitted.")

    except Exception as e:
        print(f"[Login] Could not auto-fill credentials: {e}")
        print("  Log in manually in the browser window.")

    # Wait for user to finish any 2FA / challenges
    print()
    print("  ===================================================")
    print("  Look at the Chrome window.")
    print()
    print("  If Instagram asks for 2FA, a code, or 'approve")
    print("  this login' - handle it in the browser now.")
    print()
    print("  Once you see your Instagram feed (home page),")
    print("  come back here and press Enter.")
    print("  ===================================================")
    print()
    input("  Press Enter when you're logged in and see your feed... ")

    # Dismiss any popups
    _dismiss_popups(driver)


def _dismiss_popups(driver):
    """Dismiss common post-login popups."""
    for text in ["Not Now", "Not now"]:
        try:
            buttons = driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
            for btn in buttons:
                btn.click()
                time.sleep(2)
                break
        except Exception:
            pass


def get_logged_in_browser():
    """
    Return a browser that's logged into Instagram.

    Tries saved cookies first, falls back to login.
    """
    driver = get_browser()

    # Try cookies first
    if COOKIES_FILE.exists():
        print("[Browser] Loading saved session...")
        if load_cookies(driver) and is_logged_in(driver):
            print("[Browser] Resumed session from cookies.")
            _dismiss_popups(driver)
            return driver
        print("[Browser] Saved session expired. Need to log in again.")

    # Fresh login - auto-fills credentials, waits for user to finish
    login(driver)
    save_cookies(driver)
    print("[Browser] Session saved.")
    return driver
