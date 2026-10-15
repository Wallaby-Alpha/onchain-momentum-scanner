import os
from pathlib import Path
from dotenv import load_dotenv

# Base project path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env if present
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "true").lower() in ("true", "1", "yes")

    # Scanning Schedule
    SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    TOP_PICKS_PER_SCAN = int(os.getenv("TOP_PICKS_PER_SCAN", "3"))
    ALERT_COOLDOWN_HOURS = float(os.getenv("ALERT_COOLDOWN_HOURS", "12"))
    TARGET_UNIVERSE_SIZE = int(os.getenv("TARGET_UNIVERSE_SIZE", "3000"))

    # Size & Age Criteria (Mid-Cap Leaders, not 1-hour rugs)
    MIN_MCAP_USD = float(os.getenv("MIN_MCAP_USD", "1000000"))         # $1M min
    MAX_MCAP_USD = float(os.getenv("MAX_MCAP_USD", "60000000"))        # $60M max
    MIN_AGE_DAYS = float(os.getenv("MIN_AGE_DAYS", "2.5"))              # 2.5 days min
    MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "100000")) # $100k min
    MIN_VOLUME_24H_USD = float(os.getenv("MIN_VOLUME_24H_USD", "300000")) # $300k min
    MAX_FDV_MCAP_RATIO = float(os.getenv("MAX_FDV_MCAP_RATIO", "1.75"))

    # Momentum & Orderflow Thresholds
    MIN_BUYER_RATIO_1H = float(os.getenv("MIN_BUYER_RATIO_1H", "0.45")) # 45%+ buys
    MIN_PRICE_CHANGE_1H = float(os.getenv("MIN_PRICE_CHANGE_1H", "-5.0")) # Normal healthy breather
    MIN_PRICE_CHANGE_6H = float(os.getenv("MIN_PRICE_CHANGE_6H", "-5.0")) # Healthy consolidation allowed
    MIN_PRICE_CHANGE_24H = float(os.getenv("MIN_PRICE_CHANGE_24H", "5.0")) # Must be genuinely green on the day
    MIN_MOMENTUM_SCORE = float(os.getenv("MIN_MOMENTUM_SCORE", "40.0"))

    # Chains
    ENABLED_CHAINS = [
        c.strip().lower() 
        for c in os.getenv("ENABLED_CHAINS", "solana,base,ethereum,bsc").split(",") 
        if c.strip()
    ]

    # Database
    DB_PATH = Path(os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "scanner.db")))
    if not DB_PATH.is_absolute():
        DB_PATH = PROJECT_ROOT / DB_PATH
