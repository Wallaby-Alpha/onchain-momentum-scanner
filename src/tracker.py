import time
import logging
from typing import Dict, Any, List
from src.config import Config
from src.database import get_last_alert, record_alert
from src.telegram_bot import send_top10_digest

logger = logging.getLogger(__name__)


def should_alert_token(token: Dict[str, Any]) -> bool:
    """
    Determines if a token should be individually alerted based on recent
    alert history and cooldowns.
    """
    token_address = token["token_address"]
    last_alert = get_last_alert(token_address)

    if not last_alert:
        return True  # Never alerted before

    now_ts = int(time.time())
    alerted_at = last_alert["alerted_at"]
    hours_elapsed = (now_ts - alerted_at) / 3600.0

    # If within cooldown window
    if hours_elapsed < Config.ALERT_COOLDOWN_HOURS:
        # Allow re-alerting only if momentum score surged significantly (+15 pts)
        score_diff = token["momentum_score"] - last_alert["momentum_score"]
        if score_diff >= 15.0:
            logger.info(f"Re-alerting {token['symbol']} due to massive score surge (+{score_diff:.1f} pts).")
            return True
        logger.info(f"Skipping {token['symbol']} individual alert - alerted {hours_elapsed:.1f}h ago (cooldown {Config.ALERT_COOLDOWN_HOURS}h).")
        return False

    return True


def process_top_leaders(ranked_tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Always dispatches a Top 10 Leaderboard Digest to Telegram using the
    highest-scored tokens (regardless of cooldown).

    Additionally, sends individual detailed alerts for tokens that pass the
    cooldown check and records them to the database.
    """
    if not ranked_tokens:
        logger.info("No ranked tokens to process.")
        return []

    # --- 1. ALWAYS send the Top-10 digest (best available candidates) ---
    top10 = ranked_tokens[:10]
    logger.info(f"Dispatching Top-{len(top10)} leaderboard digest to Telegram...")
    send_top10_digest(top10)

    # --- 2. Individual detailed alerts (cooldown-gated) ---
    alertable: List[Dict[str, Any]] = []
    for token in ranked_tokens:
        if should_alert_token(token):
            alertable.append(token)
            if len(alertable) >= Config.TOP_PICKS_PER_SCAN:
                break

    if alertable:
        # Record in database for historical performance auditing
        for token in alertable:
            alert_id = record_alert(token)
            logger.info(f"Recorded alert #{alert_id} for {token['symbol']} ({token['token_address']})")
    else:
        logger.info("No new tokens passed cooldown for individual alerts this cycle.")

    return top10
