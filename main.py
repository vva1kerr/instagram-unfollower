#!/usr/bin/env python3
"""
Instagram Unfollower - Selenium-based unfollowing with rate limiting.

Usage:
    python main.py login                       Log in and save session
    python main.py import-json <following.json> [followers.json]
                                               Import data download into CSV
    python main.py unfollow                    Unfollow accounts per CSV
    python main.py unfollow --dry-run          Preview what would be unfollowed
    python main.py status                      Show current CSV statistics
"""

import argparse
import csv
import sys
from config import CSV_FILE, CSV_COLUMNS, STATUS_KEEP, STATUS_UNFOLLOW, STATUS_UNFOLLOWED, STATUS_SKIPPED


def cmd_login(args):
    """Log into Instagram and save cookies for later."""
    from browser import get_logged_in_browser, save_cookies
    driver = None
    try:
        driver = get_logged_in_browser()
        save_cookies(driver)
        print()
        print("[Login] Done! Session saved for future runs.")
        input("  Press Enter to close the browser... ")
    except Exception as e:
        print(f"\n[Error] {e}")
        if driver:
            print("  Browser is still open - you can check what happened.")
            input("  Press Enter to close the browser... ")
    finally:
        if driver:
            driver.quit()


def cmd_import_json(args):
    """Import following list from Instagram's JSON data download."""
    from scraper import import_from_json
    import_from_json(args.following_json, args.followers_json)


def cmd_unfollow(args):
    """Run the unfollow process using Selenium."""
    from browser import get_logged_in_browser, save_cookies
    from unfollower import run_unfollow
    driver = None
    try:
        driver = get_logged_in_browser()
        mode = None
        if args.non_followers and args.mutual_not_keep:
            mode = None  # both flags = all eligible
        elif args.non_followers:
            mode = "non_followers"
        elif args.mutual_not_keep:
            mode = "mutual_not_keep"
        run_unfollow(driver, dry_run=args.dry_run, mode=mode)
    except Exception as e:
        print(f"\n[Error] {e}")
    finally:
        if driver:
            save_cookies(driver)
            driver.quit()
        print("[Browser] Done.")


def cmd_status(args):
    """Show CSV statistics without opening a browser."""
    if not CSV_FILE.exists():
        print(f"[Status] No CSV found at {CSV_FILE}")
        print("  Run 'python main.py import-json <file>' first.")
        return

    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    keep = sum(1 for r in rows if r["status"] == STATUS_KEEP)
    unfollow = sum(1 for r in rows if r["status"] == STATUS_UNFOLLOW)
    unfollowed = sum(1 for r in rows if r["status"] == STATUS_UNFOLLOWED)
    skipped = sum(1 for r in rows if r["status"] == STATUS_SKIPPED)
    blank = sum(1 for r in rows if r["status"] == "")

    print(f"[Status] CSV: {CSV_FILE}")
    print(f"  Total rows:    {total}")
    print(f"  keep:          {keep}")
    print(f"  unfollow:      {unfollow}")
    print(f"  unfollowed:    {unfollowed}")
    print(f"  skipped:       {skipped}")
    print(f"  unmarked:      {blank}")
    if unfollowed or skipped:
        still_following = total - unfollowed - skipped
        print(f"  still following: {still_following}")


def main():
    parser = argparse.ArgumentParser(
        description="Instagram Unfollower - Selenium-based unfollowing with rate limiting."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # login
    subparsers.add_parser("login", help="Log into Instagram and save session")

    # import-json
    import_parser = subparsers.add_parser(
        "import-json",
        help="Import following list from Instagram's JSON data download"
    )
    import_parser.add_argument(
        "following_json",
        help="Path to following.json from Instagram data download"
    )
    import_parser.add_argument(
        "followers_json",
        nargs="?",
        default=None,
        help="(Optional) Path to followers.json to compare mutual follows"
    )

    # unfollow
    unfollow_parser = subparsers.add_parser("unfollow", help="Unfollow accounts per CSV")
    unfollow_parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview unfollows without executing"
    )
    unfollow_parser.add_argument(
        "--non-followers", action="store_true",
        help="Only unfollow accounts that don't follow you back"
    )
    unfollow_parser.add_argument(
        "--mutual-not-keep", action="store_true",
        help="Only unfollow mutual follows that aren't marked as 'keep'"
    )

    # status
    subparsers.add_parser("status", help="Show CSV statistics")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "login": cmd_login,
        "import-json": cmd_import_json,
        "unfollow": cmd_unfollow,
        "status": cmd_status,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
