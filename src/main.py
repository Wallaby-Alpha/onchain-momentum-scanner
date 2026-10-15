import sys
import time
import signal
import logging
import argparse
from typing import List, Dict, Any

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.config import Config
from src.database import init_db
from src.universe import discover_universe
from src.enricher import enrich_tokens
from src.scorer import evaluate_and_score
from src.tracker import process_top_leaders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("OnChainScanner")

RUNNING = True

def handle_shutdown(signum, frame):
    global RUNNING
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    RUNNING = False


def execute_scan_cycle() -> List[Dict[str, Any]]:
    """
    Executes one complete scanning, scoring, and alerting pass.
    """
    start_time = time.time()
    logger.info("=== Starting New On-Chain Momentum Scan Cycle ===")

    # 1. Discover candidates
    candidate_tokens = discover_universe()
    if not candidate_tokens:
        logger.warning("No candidate tokens discovered.")
        return []

    # 2. Enrich pairs via DexScreener
    primary_pairs = enrich_tokens(candidate_tokens)
    if not primary_pairs:
        logger.warning("No valid pairs returned from DexScreener.")
        return []

    # 3. Filter and Score
    passed_tokens: List[Dict[str, Any]] = []
    rejected_count = 0
    
    for pair in primary_pairs:
        passed, scored_data, reason = evaluate_and_score(pair)
        if passed and scored_data:
            passed_tokens.append(scored_data)
        else:
            rejected_count += 1

    logger.info(f"Filtered {len(primary_pairs)} pairs: {len(passed_tokens)} passed, {rejected_count} rejected.")

    # 4. Rank descending by momentum score
    passed_tokens.sort(key=lambda x: x["momentum_score"], reverse=True)

    # 5. Process top leaders (cooldown + database + telegram alerts)
    alerted = process_top_leaders(passed_tokens)

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"=== Scan Cycle Completed in {elapsed}s. Alerted: {len(alerted)} token(s) ===")
    return passed_tokens


def main():
    parser = argparse.ArgumentParser(description="On-Chain Momentum Scanner")
    parser.add_argument("--once", action="store_true", help="Run a single scan cycle and exit")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    init_db()
    logger.info("Database initialized.")

    if args.once:
        logger.info("Running in single-pass mode (--once)...")
        execute_scan_cycle()
        return

    logger.info(f"Starting background daemon. Scanning every {Config.SCAN_INTERVAL_MINUTES} minute(s)...")
    while RUNNING:
        try:
            execute_scan_cycle()
        except Exception as e:
            logger.error(f"Error during scan cycle: {e}", exc_info=True)

        # Sleep in small increments to respond quickly to shutdown signals
        sleep_seconds = Config.SCAN_INTERVAL_MINUTES * 60
        for _ in range(sleep_seconds):
            if not RUNNING:
                break
            time.sleep(1)

    logger.info("Scanner stopped cleanly.")


if __name__ == "__main__":
    main()
