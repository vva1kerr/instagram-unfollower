# Technical Documentation

Complete technical documentation covering architecture, data flow, algorithms, protocols, and implementation details.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Data Flow](#data-flow)
5. [Data Structures](#data-structures)
6. [Algorithms](#algorithms)
7. [Browser Automation Protocol](#browser-automation-protocol)
8. [Authentication and Session Management](#authentication-and-session-management)
9. [JSON Data Import](#json-data-import)
10. [Unfollow Engine](#unfollow-engine)
11. [Rate Limiting Strategy](#rate-limiting-strategy)
12. [Error Handling](#error-handling)
13. [Virtual Environment](#virtual-environment)
14. [Configuration Reference](#configuration-reference)
15. [Why Selenium Over API](#why-selenium-over-api)
16. [Sources and References](#sources-and-references)

---

## Architecture Overview

The project uses a modular design with five Python files, each handling a single concern:

```
main.py (CLI routing + argument parsing)
  ├── browser.py (Chrome lifecycle + authentication)
  ├── scraper.py (JSON parsing + CSV generation)
  └── unfollower.py (browser-driven unfollow actions)

config.py (shared constants - imported by all modules)
```

Data flows through two distinct phases:

```
Phase 1 - Import (offline, no browser):
  Instagram Data Download (JSON) ──> scraper.py ──> following.csv

Phase 2 - Unfollow (browser automation):
  following.csv ──> unfollower.py ──> Chrome browser ──> Instagram web UI
```

The CSV file is the central data store, acting as both the work queue and the audit log.

---

## Tech Stack

### Runtime

| Component | Role | Why |
|-----------|------|-----|
| **Python 3.9+** | Core language | Standard for automation, rich library ecosystem |
| **Selenium 4.20+** | Browser automation framework | Controls Chrome programmatically via WebDriver protocol |
| **Google Chrome** | Web browser | Instagram sees a real browser, not an API client |
| **ChromeDriver** | Bridge between Selenium and Chrome | Auto-managed by Selenium 4's built-in Selenium Manager |

### Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| `selenium` | >=4.20.0 | Browser automation - drives Chrome to click buttons |
| `python-dotenv` | >=1.0.0 | Loads `.env` file variables into `os.environ` |

### Standard Library Modules

| Module | Purpose |
|--------|---------|
| `csv` | Read/write the following.csv tracking file |
| `json` | Parse Instagram data download + save/load cookies |
| `argparse` | CLI subcommand routing |
| `pathlib` | Cross-platform file path handling |
| `random` | Generate random delays between unfollows |
| `time` | Sleep between actions |
| `datetime` | Timestamps for unfollow records and daily limit tracking |
| `sys` | Exit codes and error handling |

---

## Project Structure

### `config.py` - Central Configuration

Single source of truth for paths, credentials, rate limits, and CSV column definitions.

```python
BASE_DIR = Path(__file__).resolve().parent   # project root
COOKIES_FILE = BASE_DIR / "cookies.json"     # browser session
CSV_FILE = BASE_DIR / "following.csv"        # master tracking file
```

All tunable values are overridable via environment variables in `.env`:
- `DAILY_UNFOLLOW_LIMIT` (default: 200)
- `MIN_DELAY_SECONDS` (default: 5)
- `MAX_DELAY_SECONDS` (default: 15)

**Design choice**: Centralizing constants prevents drift between modules. `CSV_COLUMNS` is defined once so `scraper.py` and `unfollower.py` always agree on column ordering.

### `browser.py` - Chrome Session Management

Manages the Chrome browser lifecycle:
- `get_browser()` - creates a Chrome instance with anti-detection options
- `login()` - auto-fills credentials, waits for user to complete 2FA
- `save_cookies()` / `load_cookies()` - session persistence via JSON
- `is_logged_in()` - checks for the presence of a login form
- `get_logged_in_browser()` - top-level function that returns a ready-to-use browser

**Anti-detection measures applied**:
```python
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
```

These prevent Instagram from detecting Selenium via the `navigator.webdriver` flag and Chrome's automation banner.

### `scraper.py` - JSON Data Import

Parses Instagram's official data download files into the CSV. No browser or API calls needed.

Key function: `_extract_username()` handles Instagram's inconsistent JSON formats:
- `following.json` stores usernames in the `title` field
- `followers_1.json` stores usernames in `string_list_data[0].value`
- Falls back to parsing the `href` URL as a last resort

### `unfollower.py` - Unfollow Engine

The core automation logic. Reads the CSV, drives Chrome to each profile, and clicks the unfollow button.

Key function: `_find_and_click_unfollow()` uses a three-strategy approach to find the Unfollow button (detailed in [Unfollow Engine](#unfollow-engine)).

### `main.py` - CLI Entry Point

Routes commands via `argparse` subparsers:
- `login` - opens browser, saves session
- `import-json` - parses JSON files into CSV
- `unfollow [--dry-run] [--non-followers] [--mutual-not-keep]` - runs the unfollow engine
- `status` - reads CSV locally, no browser needed

**Design choice**: Uses lazy imports inside command functions so `status` and `import-json` work without importing Selenium at all.

---

## Data Flow

### Complete Workflow

```
┌─────────────────────────────────────────────────┐
│ 1. INSTAGRAM DATA DOWNLOAD (manual, one-time)   │
│    User requests data from Instagram settings    │
│    Instagram emails a ZIP with JSON files        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 2. IMPORT (python main.py import-json)           │
│    following.json ─┐                             │
│    followers_1.json┘──> scraper.py ──> CSV       │
│    No browser. No API. Pure file parsing.        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 3. USER EDITS CSV                                │
│    Sets status="keep" for accounts to protect    │
│    Everything else gets unfollowed               │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 4. UNFOLLOW (python main.py unfollow)            │
│    For each target in CSV:                       │
│      Chrome navigates to profile                 │
│      Clicks "Following" button                   │
│      Clicks "Unfollow" in dropdown               │
│      Updates CSV row (status + timestamp)        │
│      Saves CSV to disk                           │
│      Waits random delay                          │
│    Stops at daily limit                          │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 5. REPEAT DAILY                                  │
│    Run again tomorrow to continue                │
│    Progress persists via CSV timestamps          │
└─────────────────────────────────────────────────┘
```

---

## Data Structures

### CSV Schema (`following.csv`)

| Column | Type | Description |
|--------|------|-------------|
| `username` | string | Instagram handle (without @) |
| `user_id` | string | Numeric ID (empty when imported from JSON download) |
| `full_name` | string | Display name (empty when imported from JSON download) |
| `follows_you` | string | `"yes"` (mutual), `"no"` (non-follower), or `""` (unknown). Auto-populated by `import-json` when both following and followers files are provided. |
| `status` | string | One of: `""`, `"keep"`, `"unfollow"`, `"unfollowed"` |
| `date_unfollowed` | string | ISO 8601 timestamp, empty until unfollowed |

### Status State Machine

```
                    ┌──────────────┐
                    │   (blank)    │  ← Initial state from import
                    │  = pending   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            │            ▼
       ┌──────────┐       │     ┌────────────┐
       │  "keep"  │       │     │ "unfollow"  │
       │ (manual) │       │     │  (manual)   │
       └──────────┘       │     └──────┬──────┘
       [terminal]         │            │
                          │            │  both blank and "unfollow"
                          │            │  are processed by unfollower
                          ▼            ▼
                    ┌──────────────────────┐
                    │    "unfollowed"      │  ← Set by unfollower.py
                    │  + date_unfollowed   │    [terminal state]
                    └──────────────────────┘
```

- **blank**: Default state after import. Will be unfollowed.
- **keep**: User manually marks this. Unfollower skips it entirely.
- **unfollow**: User can explicitly mark this. Same behavior as blank.
- **unfollowed**: Set by the unfollow engine. Includes timestamp. Terminal state.

### Priority Ordering (`follows_you` column)

The `follows_you` column determines unfollow order within the work queue:

```
Priority 1: follows_you = "no"   (non-followers - they don't follow you back)
Priority 2: follows_you = "yes"  (mutuals - they follow you, but not marked keep)
Priority 3: follows_you = ""     (unknown - no followers file was provided)
```

This ensures non-followers are cleaned up first, preserving mutual relationships as long as possible.

### Cookies Schema (`cookies.json`)

A JSON array of cookie objects as returned by Selenium's `driver.get_cookies()`:

```json
[
  {
    "name": "sessionid",
    "value": "...",
    "domain": ".instagram.com",
    "path": "/",
    "expiry": 1738000000,
    "secure": true,
    "httpOnly": true
  }
]
```

The critical cookie is `sessionid` - this is Instagram's session token. As long as this cookie is valid, the browser is "logged in" without needing to re-enter credentials.

### Instagram Data Download JSON Formats

**following.json** (accounts you follow):
```json
{
  "relationships_following": [
    {
      "title": "username",
      "string_list_data": [
        {
          "href": "https://www.instagram.com/_u/username",
          "timestamp": 1770511008
        }
      ]
    }
  ]
}
```

**followers_1.json** (accounts that follow you):
```json
[
  {
    "title": "",
    "media_list_data": [],
    "string_list_data": [
      {
        "href": "https://www.instagram.com/username",
        "value": "username",
        "timestamp": 1770329780
      }
    ]
  }
]
```

Note the inconsistency: following uses `title` for the username, followers uses `string_list_data[0].value`. The `_extract_username()` function handles both.

---

## Algorithms

### Username Extraction (`_extract_username`)

A three-strategy fallback chain to handle Instagram's inconsistent JSON:

```
1. Try entry["title"]                           → following.json format
2. Try entry["string_list_data"][0]["value"]     → followers_1.json format
3. Try parsing entry["string_list_data"][0]["href"] URL → last resort
```

### CSV Merge (on re-import)

When `import-json` is run on an existing CSV:

```
For each username in the JSON:
  If username exists in CSV:
    Keep existing row (preserves status + date_unfollowed)
    Update follows_you based on current followers file
  Else:
    Create new row with blank status
    Set follows_you = "yes"/"no" based on followers file (or "" if not provided)

For each row in existing CSV not in JSON:
  If status == "unfollowed":
    Keep row (audit trail)
  Else:
    Drop row (user unfollowed them outside the tool)
```

This ensures re-importing never destroys manual `keep` markings, and `follows_you` stays up to date.

### Unfollow Mode Filtering

The `run_unfollow()` function accepts a `mode` parameter controlled by CLI flags:

```
mode=None (default, or both flags):
  Build queue: non_followers + mutuals + unknown
  → Non-followers first, then mutuals not marked keep, then unknown

mode="non_followers" (--non-followers flag):
  Build queue: only accounts where follows_you == "no"
  → Ignores mutuals entirely

mode="mutual_not_keep" (--mutual-not-keep flag):
  Build queue: only accounts where follows_you == "yes"
  → Ignores non-followers entirely
```

In all modes, accounts with `status == "keep"` are never included in the queue.

### Daily Budget Calculation

```python
already_today = count rows where:
    status == "unfollowed" AND
    date_unfollowed starts with today's date (YYYY-MM-DD)

remaining_budget = DAILY_UNFOLLOW_LIMIT - already_today
```

Works across sessions: if you unfollow 100, stop, restart, it knows 100 were done today.

### Unfollow Button Detection (three-strategy cascade)

```
Strategy 1: XPath selectors for <button> elements
  Try: //button[text()='Unfollow']
  Try: //button[contains(text(), 'Unfollow')]
  Try: //*[@role='dialog']//button[text()='Unfollow']
  Try: //*[@role='dialog']//button[contains(text(), 'Unfollow')]

Strategy 2: Any element with "Unfollow" text
  Find all //*[text()='Unfollow']
  Click the first one that's clickable

Strategy 3: JavaScript DOM traversal
  document.querySelectorAll('button, div, span, a')
  Find element where textContent.trim() === 'Unfollow'
  Click via JavaScript
```

This cascade handles Instagram's frequent UI changes. When they change from `<button>` to `<div>` or restructure the dialog, at least one strategy should still work.

---

## Browser Automation Protocol

### How Selenium Controls Chrome

```
Python Script ──(WebDriver Protocol)──> ChromeDriver ──(DevTools Protocol)──> Chrome
```

1. **WebDriver Protocol** (W3C standard): Selenium sends JSON commands over HTTP to ChromeDriver. Commands like "navigate to URL", "find element", "click element" are sent as REST API calls.

2. **ChromeDriver**: A standalone binary that translates WebDriver commands into Chrome DevTools Protocol (CDP) commands. Selenium 4 auto-downloads the correct version via Selenium Manager.

3. **Chrome DevTools Protocol (CDP)**: The native debugging protocol built into Chrome. ChromeDriver uses it to control the browser at a low level - injecting JavaScript, intercepting network requests, manipulating the DOM.

### Why a Real Browser Beats an API Client

| Aspect | API Client (instagrapi) | Real Browser (Selenium) |
|--------|------------------------|------------------------|
| Detection | Easy - no browser fingerprint | Hard - real Chrome with real cookies |
| 2FA/Challenges | Must handle programmatically | User handles in the browser window |
| Session | Custom session tokens | Real browser cookies |
| Instagram updates | API endpoints change/break | UI changes are more gradual |
| Speed | Fast (direct HTTP) | Slower (full page loads) |
| Resource usage | Low (no browser) | Higher (Chrome process running) |

### Anti-Detection Measures

The browser is configured to minimize automation fingerprints:

```python
# 1. Remove navigator.webdriver flag
#    Instagram's JavaScript checks: if (navigator.webdriver) { flag_as_bot() }
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})

# 2. Remove "Chrome is being controlled by automated test software" banner
options.add_experimental_option("excludeSwitches", ["enable-automation"])

# 3. Disable AutomationControlled blink feature
options.add_argument("--disable-blink-features=AutomationControlled")

# 4. Disable automation extension
options.add_experimental_option("useAutomationExtension", False)

# 5. Human-like credential entry (character by character with delays)
for char in username:
    field.send_keys(char)
    time.sleep(0.05)
```

---

## Authentication and Session Management

### Login Flow

```
get_logged_in_browser()
  │
  ├── cookies.json exists?
  │   ├── YES: Load cookies → Navigate to Instagram → Login form present?
  │   │   ├── No form (logged in) → Return browser ✓
  │   │   └── Form found (expired) → Fall through to fresh login
  │   └── NO: Fall through to fresh login
  │
  └── FRESH LOGIN
      ├── .env has credentials?
      │   ├── YES: Auto-fill username + password → Submit
      │   └── NO: Prompt user to log in manually
      ├── Print instructions for user to handle 2FA in browser
      ├── Wait for user to press Enter (they confirm they see their feed)
      ├── Dismiss "Save Login Info?" and "Notifications?" popups
      └── Save cookies → Return browser ✓
```

### Cookie Persistence

Cookies are saved as a JSON file after each session. On the next run:

1. Browser opens to `instagram.com`
2. Saved cookies are injected via `driver.add_cookie()`
3. Page refreshes with the cookies active
4. If `sessionid` cookie is still valid, Instagram treats us as logged in

Cookie fields `sameSite` and `storeId` are stripped before injection to avoid Selenium compatibility issues.

### Why Cookies Over Session Tokens

Unlike API-based tools that store proprietary session blobs, browser cookies are the native web authentication mechanism. Instagram's `sessionid` cookie is the same one your regular Chrome browser uses. This means:
- Instagram can't distinguish our session from a normal browser session
- Session validity is the same as a normal user (~30 days)
- No special token refresh logic needed

---

## JSON Data Import

### Why Use the Data Download Instead of the API?

Instagram's API (`user_following()` endpoint) aggressively challenges automated requests with push-notification verification ("Approve this login on your phone"). Even after approval, subsequent API calls often get re-challenged. This creates an unresolvable loop for programmatic access.

The data download is Instagram's official, supported way to export your data under GDPR/privacy regulations. It produces clean JSON files with zero API calls and zero challenge risk.

### Request Process

1. Instagram app: Settings > Accounts Center > Your information and permissions > Download your information
2. Select account > "Some of your information" > **Followers and Following**
3. Format: **JSON** (not HTML)
4. Submits a request that Instagram processes asynchronously
5. Download link sent via email or available in Settings (typically minutes to hours)
6. ZIP file contains: `connections/followers_and_following/following.json` and `followers_1.json`

### Parsing Logic

The `_extract_username()` function handles Instagram's inconsistent JSON structure with a three-level fallback (see [Algorithms](#algorithms)). The import also:

- **Merges with existing CSV**: Preserves `keep`/`unfollow` markings from previous imports
- **Retains unfollowed records**: Users with `status=unfollowed` stay in the CSV as an audit trail
- **Sorts alphabetically**: By username for easy manual editing
- **Populates `follows_you` column**: If both files are provided, marks each account as `"yes"` (mutual) or `"no"` (non-follower). This drives unfollow priority ordering.
- **Computes mutual follows**: Shows summary of followers-you-back vs. non-mutual

---

## Unfollow Engine

### Target Selection

Before processing begins, the engine builds a work queue:

1. Load all CSV rows where `status` is blank or `"unfollow"` (skip `"keep"` and `"unfollowed"`)
2. Split into `non_followers` (follows_you=no) and `mutuals` (follows_you=yes)
3. Apply mode filter:
   - **Default**: `non_followers` + `mutuals` + `unknown` (in that order)
   - **`--non-followers`**: only `non_followers`
   - **`--mutual-not-keep`**: only `mutuals`
   - **Both flags**: same as default
4. Trim to remaining daily budget
5. Process sequentially

### Per-Account Flow

```
driver.get("https://www.instagram.com/{username}/")
  │
  ├── Wait 3 seconds for page load
  │
  ├── Find all <button> elements on page
  │   ├── Button text == "Following" → Click it (opens dropdown menu)
  │   ├── Button text == "Follow" → Already unfollowed, mark done
  │   └── Neither found → Skip (account may be deleted/private)
  │
  ├── Wait 2 seconds for dropdown to appear
  │
  ├── Find "Unfollow" in the dropdown (3-strategy cascade)
  │   ├── Strategy 1: XPath button selectors (4 patterns)
  │   ├── Strategy 2: Any element with "Unfollow" text
  │   └── Strategy 3: JavaScript DOM scan
  │
  ├── Click "Unfollow"
  │
  ├── Wait 2 seconds
  │
  ├── Verify: check if button now says "Follow" (confirms success)
  │
  ├── Update CSV row: status="unfollowed", date_unfollowed=now
  │
  ├── Save CSV to disk (crash safety)
  │
  └── Sleep random(MIN_DELAY, MAX_DELAY) seconds
```

### Why Save After Every Unfollow?

Writing a few KB CSV to disk takes <1ms. The alternative (batch save) risks losing the entire session's progress if:
- Process is killed (`kill -9`, power loss)
- Chrome crashes
- Python hits an unhandled exception
- Network drops

After-each-save guarantees at most one unfollow is lost from the record.

---

## Rate Limiting Strategy

### Layer 1: Daily Unfollow Cap

```python
DAILY_UNFOLLOW_LIMIT = 200  # configurable via .env
```

Tracked by counting CSV rows where `date_unfollowed` starts with today's date. Works across sessions and restarts.

Instagram's exact limits are undocumented and vary by account. Community-observed limits:
- ~200-400 unfollows per day
- ~60 actions per hour (follows + unfollows + likes combined)
- Aggressive patterns trigger 24-48 hour action blocks

### Layer 2: Per-Action Random Delay

```python
delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
```

`random.uniform()` produces a continuous (not integer) random value. This is harder to fingerprint than fixed or integer-spaced intervals.

### Layer 3: Page Load Time as Natural Throttle

Each unfollow requires a full page navigation (`driver.get()`), which takes 2-4 seconds for the page to load plus 3 seconds of explicit wait. This adds ~5-7 seconds of natural delay on top of the configured random delay.

### Estimated Time to Completion

| Accounts to unfollow | Days at 200/day | Run time per day (at 5-15s delay) |
|---------------------|-----------------|----------------------------------|
| 500 | 3 days | ~30 min |
| 1,000 | 5 days | ~30 min |
| 2,000 | 10 days | ~30 min |
| 5,000 | 25 days | ~30 min |
| 8,000 | 40 days | ~30 min |

Each daily run processes 200 accounts at ~10 seconds average per account = ~33 minutes.

---

## Error Handling

### Error Matrix

| Scenario | Detection | Response |
|----------|-----------|----------|
| Chrome not installed | Exception in `webdriver.Chrome()` | Print install instructions, exit |
| Cookies expired | `is_logged_in()` finds login form | Trigger fresh login flow |
| Login fields not found | WebDriverWait timeout | Fall back to manual login |
| "Following" button not found | Button text scan finds nothing | Skip account, continue |
| "Unfollow" dialog fails | All 3 strategies fail | Skip account, mark as "dialog_failed" |
| Account deleted/private | No "Following" or "Follow" button | Skip with "not_found" |
| Already unfollowed | "Follow" button found instead | Mark as unfollowed, continue |
| Redirected to login page | URL contains "login" | Save progress, stop, tell user to re-login |
| Ctrl+C | `KeyboardInterrupt` caught in loop | Save CSV, exit cleanly |
| Any other exception | Generic `except` in main loop | Log error, skip account, continue |
| Browser crash | `finally` block in `cmd_unfollow` | Save cookies, print message |

### Crash Recovery

1. CSV is saved after every unfollow → at most 1 lost record
2. Status field acts as a checkpoint → re-running skips completed accounts
3. Daily budget uses timestamps → works correctly after restart

---

## Virtual Environment

### What It Is

A Python virtual environment (`venv`) is an isolated directory containing its own Python interpreter and packages. It prevents this project's dependencies from conflicting with system packages or other projects.

### Setup

```bash
python3 -m venv venv          # create
source venv/bin/activate       # activate (every new terminal)
pip install -r requirements.txt # install deps
deactivate                     # when done
```

### Why It's Required

Modern Linux distributions (Ubuntu 23.04+, Fedora 38+, Debian 12+) enforce PEP 668, blocking `pip install` outside a venv to protect system Python packages.

### What It Creates

```
venv/
├── bin/python          # isolated interpreter
├── bin/pip             # isolated pip
├── bin/activate        # activation script
└── lib/python3.x/
    └── site-packages/  # where selenium etc. are installed
```

---

## Configuration Reference

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTAGRAM_USERNAME` | (required) | Your Instagram username |
| `INSTAGRAM_PASSWORD` | (required) | Your Instagram password |
| `DAILY_UNFOLLOW_LIMIT` | `200` | Max unfollows per calendar day |
| `MIN_DELAY_SECONDS` | `5` | Minimum random delay between unfollows |
| `MAX_DELAY_SECONDS` | `15` | Maximum random delay between unfollows |

---

## Why Selenium Over API

This project originally used `instagrapi` (Instagram's private API wrapper). It was faster and more efficient, but Instagram's anti-bot measures made it impractical:

| Problem | API (instagrapi) | Browser (Selenium) |
|---------|------------------|-------------------|
| Login challenges | "Approve on phone" flow not supported programmatically. Even after approval, subsequent API calls get re-challenged. | User handles 2FA/challenges in a real browser. No programmatic resolution needed. |
| Session fingerprinting | API client has no browser fingerprint. Instagram flags it immediately. | Real Chrome with real cookies. Indistinguishable from normal usage. |
| `user_following()` blocked | Endpoint returns ChallengeRequired even with valid session. | Not needed - data comes from Instagram's official JSON export. |
| Rate limiting | Aggressive. API calls are fingerprinted and throttled. | More lenient. Instagram expects browsers to be slower. |

The tradeoff is speed (Selenium is slower) and resource usage (Chrome uses more memory), but reliability is far more important for a tool that runs across multiple days.

---

## Sources and References

### Libraries

- **Selenium** - Browser automation framework
  - Documentation: https://www.selenium.dev/documentation/
  - Python bindings: https://selenium-python.readthedocs.io/
  - PyPI: https://pypi.org/project/selenium/
  - WebDriver W3C spec: https://www.w3.org/TR/webdriver2/

- **python-dotenv** - Environment variable loading
  - GitHub: https://github.com/theskumar/python-dotenv
  - PyPI: https://pypi.org/project/python-dotenv/

### Instagram

- Instagram Data Download: https://help.instagram.com/181231772500920
- Instagram Terms of Use: https://help.instagram.com/581066165581870

### Background Research

- instagrapi (previous approach): https://github.com/subzeroid/instagrapi
- instagrapi challenge handling limitations: https://github.com/subzeroid/instagrapi/issues/509
- Instagram ChallengeRequired analysis: https://github.com/subzeroid/instagrapi/issues/1510
- Chrome DevTools Protocol: https://chromedevtools.github.io/devtools-protocol/
- Selenium anti-detection techniques: https://www.selenium.dev/documentation/webdriver/troubleshooting/upgrade_to_selenium_4/
- PEP 668 (externally managed environments): https://peps.python.org/pep-0668/

### Python Standard Library

- csv module: https://docs.python.org/3/library/csv.html
- json module: https://docs.python.org/3/library/json.html
- argparse module: https://docs.python.org/3/library/argparse.html
- pathlib module: https://docs.python.org/3/library/pathlib.html
- random module: https://docs.python.org/3/library/random.html
- datetime module: https://docs.python.org/3/library/datetime.html
