import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths (all relative to project root)
BASE_DIR = Path(__file__).resolve().parent
COOKIES_FILE = BASE_DIR / "cookies.json"
CSV_FILE = BASE_DIR / "following.csv"

# Instagram credentials from .env (used for automated login)
IG_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
IG_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# Rate-limiting defaults (all overridable via .env)
DAILY_UNFOLLOW_LIMIT = int(os.getenv("DAILY_UNFOLLOW_LIMIT", "500"))
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "5"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "15"))

# CSV column names (single source of truth)
CSV_COLUMNS = ["username", "user_id", "full_name", "follows_you", "status", "date_unfollowed"]

# Valid status values
STATUS_KEEP = "keep"
STATUS_UNFOLLOW = "unfollow"
STATUS_UNFOLLOWED = "unfollowed"
STATUS_SKIPPED = "skipped"
