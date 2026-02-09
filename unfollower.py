import csv
import random
import sys
import time
from datetime import datetime, date
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import (
    CSV_FILE,
    CSV_COLUMNS,
    STATUS_KEEP,
    STATUS_UNFOLLOW,
    STATUS_UNFOLLOWED,
    STATUS_SKIPPED,
    DAILY_UNFOLLOW_LIMIT,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
)


def load_csv():
    """Load all rows from CSV."""
    if not CSV_FILE.exists():
        print(f"[Error] CSV not found: {CSV_FILE}")
        print("  Run 'python main.py import-json <file>' first.")
        sys.exit(1)
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(rows):
    """Write all rows back to CSV."""
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def count_unfollowed_today(rows):
    """Count how many unfollows were already done today."""
    today_str = date.today().isoformat()
    return sum(
        1 for r in rows
        if r["status"] == STATUS_UNFOLLOWED
        and r["date_unfollowed"].startswith(today_str)
    )


def _find_and_click_unfollow(driver, username):
    """
    Navigate to a user's profile and unfollow them.

    Returns True if unfollowed, False if skipped/failed.
    """
    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(3)

    # Look for the "Following" button (means we currently follow them)
    # Instagram uses different button text: "Following", "Requested", etc.
    buttons = driver.find_elements(By.TAG_NAME, "button")
    following_btn = None
    for btn in buttons:
        try:
            text = btn.text.strip()
            if text in ("Following", "Requested"):
                following_btn = btn
                break
        except Exception:
            continue

    if not following_btn:
        # Check if we already don't follow them
        for btn in buttons:
            try:
                if btn.text.strip() == "Follow":
                    return "already_unfollowed"
            except Exception:
                continue
        return "not_found"

    # Click "Following" to open the unfollow menu/dialog
    following_btn.click()
    time.sleep(2)

    # Find and click "Unfollow" in the menu that appeared.
    # Instagram uses various element types (button, div, span) so we
    # search broadly for anything containing "Unfollow" text.
    unfollow_clicked = False

    # Strategy 1: Any button with "Unfollow" text
    for xpath in [
        "//button[text()='Unfollow']",
        "//button[contains(text(), 'Unfollow')]",
        "//*[contains(@role, 'dialog')]//button[text()='Unfollow']",
        "//*[contains(@role, 'dialog')]//button[contains(text(), 'Unfollow')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, xpath)
            el.click()
            unfollow_clicked = True
            break
        except Exception:
            continue

    # Strategy 2: Any clickable element with exact "Unfollow" text (div, span, etc.)
    if not unfollow_clicked:
        try:
            # Find ALL elements on page, look for "Unfollow" text
            all_elements = driver.find_elements(By.XPATH, "//*[text()='Unfollow']")
            for el in all_elements:
                try:
                    el.click()
                    unfollow_clicked = True
                    break
                except Exception:
                    continue
        except Exception:
            pass

    # Strategy 3: Use JavaScript to find and click it
    if not unfollow_clicked:
        try:
            driver.execute_script("""
                var elements = document.querySelectorAll('button, div, span, a');
                for (var el of elements) {
                    if (el.textContent.trim() === 'Unfollow') {
                        el.click();
                        return true;
                    }
                }
                return false;
            """)
            unfollow_clicked = True
        except Exception:
            pass

    if not unfollow_clicked:
        return "dialog_failed"

    time.sleep(2)

    # Verify: check if the button now says "Follow" (confirming unfollow worked)
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        try:
            if btn.text.strip() == "Follow":
                return "success"
        except Exception:
            continue

    # Can't confirm but the click happened - assume success
    return "success"


def run_unfollow(driver, dry_run=False, mode=None):
    """
    Unfollow accounts marked 'unfollow' (or blank) in CSV.

    Uses Selenium to visit each profile and click the unfollow button.

    mode:
      None              - all eligible (non-followers first, then mutuals)
      "non_followers"   - only accounts where follows_you=no
      "mutual_not_keep" - only mutual follows (follows_you=yes) not marked keep
    """
    rows = load_csv()

    # Check daily budget
    already_today = count_unfollowed_today(rows)
    remaining_budget = DAILY_UNFOLLOW_LIMIT - already_today
    if remaining_budget <= 0:
        print(f"[Unfollow] Daily limit reached ({DAILY_UNFOLLOW_LIMIT}). "
              f"Already unfollowed {already_today} today. Try again tomorrow.")
        return

    # Build work queue: blank or "unfollow" status
    all_targets = [
        r for r in rows
        if r["status"] in (STATUS_UNFOLLOW, "")
    ]

    # Filter by mode
    non_followers = [r for r in all_targets if r.get("follows_you", "") == "no"]
    mutuals = [r for r in all_targets if r.get("follows_you", "") == "yes"]

    if mode == "non_followers":
        targets = non_followers
        mode_label = "non-followers only"
    elif mode == "mutual_not_keep":
        targets = mutuals
        mode_label = "mutual follows (not keep) only"
    else:
        # Default: non-followers first, then mutuals
        targets = non_followers + mutuals
        # Add any with unknown follows_you status at the end
        unknown = [r for r in all_targets if r.get("follows_you", "") not in ("yes", "no")]
        targets = targets + unknown
        mode_label = "all (non-followers first)"

    if not targets:
        print(f"[Unfollow] No accounts to unfollow for mode: {mode_label}.")
        return

    to_process = targets[:remaining_budget]

    non_f_count = sum(1 for r in to_process if r.get("follows_you", "") == "no")
    mutual_count = sum(1 for r in to_process if r.get("follows_you", "") == "yes")
    other_count = len(to_process) - non_f_count - mutual_count

    print(f"[Unfollow] Mode: {mode_label}")
    print(f"  Eligible: {len(targets)} accounts ({len(non_followers)} non-followers, {len(mutuals)} mutuals)")
    print(f"  Will process: {len(to_process)} today (budget: {remaining_budget})")
    if non_f_count:
        print(f"    Non-followers: {non_f_count}")
    if mutual_count:
        print(f"    Mutuals (not keep): {mutual_count}")
    if other_count:
        print(f"    Other: {other_count}")

    if dry_run:
        print("\n[Dry Run] Would unfollow:")
        for t in to_process:
            fy = t.get("follows_you", "")
            if fy == "yes":
                tag = " (follows you)"
            elif fy == "no":
                tag = " (non-follower)"
            else:
                tag = ""
            print(f"  @{t['username']}{tag}")
        print(f"\n[Dry Run] Total: {len(to_process)} accounts")
        return

    unfollowed_count = 0
    skipped_count = 0
    for i, target in enumerate(to_process):
        username = target["username"]

        print(f"[{i+1}/{len(to_process)}] Unfollowing @{username}...", end=" ", flush=True)

        try:
            result = _find_and_click_unfollow(driver, username)

            if result == "success":
                target["status"] = STATUS_UNFOLLOWED
                target["date_unfollowed"] = datetime.now().isoformat(timespec="seconds")
                unfollowed_count += 1
                print("OK")

            elif result == "already_unfollowed":
                target["status"] = STATUS_UNFOLLOWED
                target["date_unfollowed"] = datetime.now().isoformat(timespec="seconds")
                print("ALREADY UNFOLLOWED (marked done)")

            elif result == "not_found":
                target["status"] = STATUS_SKIPPED
                target["date_unfollowed"] = datetime.now().isoformat(timespec="seconds")
                print("SKIPPED (account no longer exists)")
                skipped_count += 1

            elif result == "dialog_failed":
                target["status"] = STATUS_SKIPPED
                target["date_unfollowed"] = datetime.now().isoformat(timespec="seconds")
                print("SKIPPED (unfollow dialog issue)")
                skipped_count += 1

        except KeyboardInterrupt:
            print("\n[Unfollow] Interrupted by user. Saving progress...")
            save_csv(rows)
            print(f"  Unfollowed {unfollowed_count} this session.")
            sys.exit(0)

        except Exception as e:
            print(f"ERROR: {e}")
            target["status"] = STATUS_SKIPPED
            target["date_unfollowed"] = datetime.now().isoformat(timespec="seconds")
            skipped_count += 1
            # Check if we got logged out
            if "login" in driver.current_url:
                print("[Unfollow] Got redirected to login page. Session may have expired.")
                print("  Saving progress. Re-run 'python main.py login' then try again.")
                save_csv(rows)
                return

        # Save after each action (crash safety)
        save_csv(rows)

        # Random delay before next unfollow (skip after last one)
        if i < len(to_process) - 1:
            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            print(f"  Waiting {delay:.0f}s...")
            time.sleep(delay)

    print(f"\n[Unfollow] Done. Unfollowed {unfollowed_count}, skipped {skipped_count} this session.")
    remaining = sum(1 for r in rows if r["status"] in (STATUS_UNFOLLOW, ""))
    if remaining:
        print(f"  {remaining} accounts still pending. Run again tomorrow if you hit the limit.")
