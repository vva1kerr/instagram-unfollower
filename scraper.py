import csv
import json
import sys
from pathlib import Path
from config import CSV_FILE, CSV_COLUMNS, STATUS_UNFOLLOWED


def _extract_username(entry):
    """
    Extract username from an Instagram data download JSON entry.

    Instagram uses different formats:
      - following.json: {"title": "username", "string_list_data": [{"href": "..."}]}
      - followers_1.json: {"string_list_data": [{"value": "username", ...}]}
    """
    # Try "title" field first (following.json format)
    title = entry.get("title", "").strip()
    if title:
        return title

    # Try "string_list_data[0].value" (followers format)
    try:
        return entry["string_list_data"][0]["value"]
    except (KeyError, IndexError):
        pass

    # Try extracting from href URL as last resort
    try:
        href = entry["string_list_data"][0]["href"]
        # href looks like "https://www.instagram.com/_u/username"
        return href.rstrip("/").split("/")[-1]
    except (KeyError, IndexError):
        pass

    return None


def import_from_json(following_json_path, followers_json_path=None):
    """
    Import following list from Instagram's data download JSON files.

    Instagram provides these when you request "Download Your Information"
    in JSON format. The files are usually at:
      connections/followers_and_following/following.json
      connections/followers_and_following/followers_1.json

    If followers_json_path is provided, also marks who doesn't follow
    you back (helpful for deciding who to unfollow).
    """
    following_path = Path(following_json_path)
    if not following_path.exists():
        print(f"[Error] File not found: {following_path}")
        sys.exit(1)

    # Parse following list
    with open(following_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Instagram JSON format: {"relationships_following": [{"string_list_data": [{"value": "username", ...}]}, ...]}
    if "relationships_following" in data:
        following_list = data["relationships_following"]
    elif isinstance(data, list):
        following_list = data
    else:
        print("[Error] Unexpected JSON format. Expected 'relationships_following' key.")
        print(f"  Top-level keys found: {list(data.keys())}")
        sys.exit(1)

    following_usernames = set()
    for entry in following_list:
        username = _extract_username(entry)
        if username:
            following_usernames.add(username)

    print(f"[Import] Found {len(following_usernames)} accounts you follow.")

    # Parse followers list (optional)
    followers_usernames = set()
    if followers_json_path:
        followers_path = Path(followers_json_path)
        if followers_path.exists():
            with open(followers_path, "r", encoding="utf-8") as f:
                fdata = json.load(f)
            # Could be under different keys depending on Instagram version
            if isinstance(fdata, list):
                followers_list = fdata
            elif "relationships_followers" in fdata:
                followers_list = fdata["relationships_followers"]
            else:
                # Try first key that looks like a list
                followers_list = []
                for v in fdata.values():
                    if isinstance(v, list):
                        followers_list = v
                        break
            for entry in followers_list:
                username = _extract_username(entry)
                if username:
                    followers_usernames.add(username)
            print(f"[Import] Found {len(followers_usernames)} followers.")
        else:
            print(f"[Import] Followers file not found: {followers_path}")
            print("  Continuing without follower comparison.")

    # Load existing CSV to preserve manual edits
    existing = {}
    if CSV_FILE.exists():
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["username"]] = row

    # Build rows
    rows = []
    for username in following_usernames:
        follows_you = "yes" if username in followers_usernames else "no"
        if followers_usernames:
            follows_value = follows_you
        else:
            follows_value = ""  # unknown if no followers file provided

        if username in existing:
            # Preserve existing status and date, update follows_you
            row = existing[username]
            row["follows_you"] = follows_value
            rows.append(row)
        else:
            rows.append({
                "username": username,
                "user_id": "",
                "full_name": "",
                "follows_you": follows_value,
                "status": "",
                "date_unfollowed": "",
            })

    # Keep rows for already-unfollowed users
    for uname, row in existing.items():
        if uname not in following_usernames and row.get("status") == STATUS_UNFOLLOWED:
            rows.append(row)

    # Sort by username
    rows.sort(key=lambda r: r["username"].lower())

    # Write CSV
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    keep = sum(1 for r in rows if r["status"] == "keep")
    unfollow = sum(1 for r in rows if r["status"] == "unfollow")
    unfollowed = sum(1 for r in rows if r["status"] == STATUS_UNFOLLOWED)
    blank = sum(1 for r in rows if r["status"] == "")

    # Show non-mutual info if we have followers data
    if followers_usernames:
        not_following_back = following_usernames - followers_usernames
        mutual = following_usernames & followers_usernames
        print(f"[Import] Mutual follows: {len(mutual)}")
        print(f"[Import] Don't follow you back: {len(not_following_back)}")

    print(f"[Import] CSV written to: {CSV_FILE}")
    print(f"  keep={keep}  unfollow={unfollow}  unfollowed={unfollowed}  unmarked={blank}")
    print()
    print("[Import] Next steps:")
    print("  1. Open following.csv in a spreadsheet or text editor")
    print("  2. Set status to 'keep' for accounts you want to keep following")
    print("  3. Leave status blank (or set to 'unfollow') for accounts to remove")
    print("  4. Run: python main.py unfollow --dry-run   (to preview)")
    print("  5. Run: python main.py unfollow              (to execute)")
