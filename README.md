# Instagram Unfollower

A Python CLI tool to bulk-unfollow Instagram accounts using browser automation. Features rate limiting, progress tracking, crash recovery, and a "do not unfollow" list.

## How It Works

Uses Selenium to control a real Chrome browser - Instagram sees a normal person clicking buttons, not an API bot. Your following list comes from Instagram's official data download (JSON), so no API calls are needed for that either.

## Tech Stack

- **Python 3.9+** - core language
- **Selenium 4** - browser automation (controls Chrome)
- **Google Chrome** - the actual browser Instagram sees
- **python-dotenv** - loads credentials from `.env`
- **Instagram Data Download** - provides your following/followers list as JSON

## Project Structure

```
instagram-unfollower/
├── main.py             # CLI entry point (login, import-json, unfollow, status)
├── config.py           # Central configuration and constants
├── browser.py          # Chrome session management, login, cookie persistence
├── scraper.py          # Parses Instagram JSON data download into CSV
├── unfollower.py       # Selenium-based unfollow logic with rate limiting
├── requirements.txt    # Python dependencies (selenium, python-dotenv)
├── .env                # Your credentials (git-ignored)
├── .env.example        # Template for .env
├── .gitignore          # Ignores credentials, cookies, CSV, venv
├── cookies.json        # Saved browser session (generated, git-ignored)
└── following.csv       # Master tracking file (generated, git-ignored)
```

## Setup

### 1. Prerequisites

- Python 3.9+
- Google Chrome browser installed

### 2. Create a virtual environment

```bash
cd ~/Desktop/instagram-unfollower
python3 -m venv venv
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt. Activate it every time you open a new terminal.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

Optional rate limit overrides:

```
DAILY_UNFOLLOW_LIMIT=200
MIN_DELAY_SECONDS=5
MAX_DELAY_SECONDS=15
```

### 5. Request your Instagram data download

1. Open Instagram app or website
2. Settings > Accounts Center > Your information and permissions > Download your information
3. Select your account
4. Choose "Some of your information" > select **Followers and Following**
5. Format: **JSON**
6. Submit the request (takes minutes to hours)
7. Download and extract the ZIP when ready

## Usage

### Step 1: Log in and save your session

```bash
python main.py login
```

Chrome opens, credentials are auto-filled, you handle 2FA in the browser, press Enter in the terminal when done. Session is saved as cookies for future runs.

### Step 2: Import your following list

```bash
python main.py import-json /path/to/following.json /path/to/followers_1.json
```

The second file (followers) is optional but recommended - it shows you who doesn't follow back.

### Step 3: Edit the CSV

Open `following.csv` in a spreadsheet editor or text editor:

```csv
username,user_id,full_name,follows_you,status,date_unfollowed
your_bestfriend,,,yes,keep,
random_account,,,no,,
another_account,,,yes,,
```

The `follows_you` column is auto-populated when you import both `following.json` and `followers_1.json`:
- **`yes`** - mutual follow (they follow you back)
- **`no`** - non-follower (they don't follow you back)

Set `status` to:
- **`keep`** - accounts you want to keep following
- **`unfollow`** or **leave blank** - accounts that will be unfollowed

### Step 4: Preview (optional)

```bash
python main.py unfollow --dry-run
```

### Step 5: Run the unfollower

```bash
python main.py unfollow
```

By default, non-followers are unfollowed first, then mutuals not marked `keep`. Chrome opens, navigates to each profile, clicks Following > Unfollow. Runs until the daily limit is reached. Run again tomorrow to continue.

You can filter which accounts get unfollowed:

```bash
python main.py unfollow --non-followers          # only unfollow non-followers
python main.py unfollow --mutual-not-keep         # only unfollow mutuals not marked keep
python main.py unfollow --non-followers --mutual-not-keep  # both (same as default)
```

### Step 6: Check progress

```bash
python main.py status
```

No browser needed - just reads the CSV.

## Commands

| Command | Description |
|---------|-------------|
| `python main.py login` | Log in via Chrome and save session |
| `python main.py import-json <following> [followers]` | Import JSON data download into CSV |
| `python main.py unfollow` | Unfollow all eligible (non-followers first, then mutuals) |
| `python main.py unfollow --dry-run` | Preview without executing |
| `python main.py unfollow --non-followers` | Only unfollow accounts that don't follow you back |
| `python main.py unfollow --mutual-not-keep` | Only unfollow mutual follows not marked `keep` |
| `python main.py status` | Show CSV statistics |

## Safety Features

- **Daily limit**: 200 unfollows/day (configurable)
- **Random delays**: Between each unfollow to mimic human behavior
- **Crash recovery**: CSV saved after every single unfollow
- **Session reuse**: Cookies persist across runs - log in once
- **Keep list**: Mark accounts as `keep` and they're never touched
- **Ctrl+C safe**: Saves progress and exits cleanly
- **Re-importing is safe**: Preserves existing `keep` markings
- **Dry run**: Preview what would happen before doing it

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Chrome doesn't open | Make sure Google Chrome is installed |
| Credentials not auto-filled | Check `.env` has correct username/password |
| 2FA required | Handle it in the Chrome window, then press Enter |
| Session expired | Run `python main.py login` again |
| "dialog_failed" errors | Instagram may have changed their UI - open an issue |
| Daily limit reached | Wait until tomorrow, run again |
| Got logged out mid-run | Progress is saved. Run `login` then `unfollow` again |

## Disclaimer

This tool automates browser interactions with Instagram. Automated actions may violate Instagram's Terms of Service. Use at your own risk with conservative rate limits. Intended for personal account management only.
