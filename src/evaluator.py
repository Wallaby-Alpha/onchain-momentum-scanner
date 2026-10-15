import sys
import time
import argparse
from typing import List, Dict, Any

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from tabulate import tabulate
import requests

from src.database import get_all_alerts, record_evaluation, get_connection
from src.enricher import chunk_list, CHUNK_SIZE


def evaluate_past_alerts(limit: int = 50, save_to_db: bool = True):
    """
    Evaluates how tokens alerted in the past have performed since the alert was fired.
    """
    alerts = get_all_alerts(limit=limit)
    if not alerts:
        print("No alerts found in the database yet. Run scans to generate alerts first.")
        return

    print(f"\nEvaluating performance for {len(alerts)} past alert(s)...")

    # Gather unique token addresses to query current prices
    token_addresses = list({a["token_address"] for a in alerts})
    chunks = list(chunk_list(token_addresses, CHUNK_SIZE))
    
    current_prices: Dict[str, float] = {}
    current_mcaps: Dict[str, float] = {}

    for chunk in chunks:
        joined = ",".join(chunk)
        url = f"https://api.dexscreener.com/latest/dex/tokens/{joined}"
        try:
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                pairs = res.json().get("pairs", []) or []
                for p in pairs:
                    base_addr = p.get("baseToken", {}).get("address")
                    price = float(p.get("priceUsd", 0.0) or 0.0)
                    mcap = float(p.get("marketCap", 0.0) or p.get("fdv", 0.0) or 0.0)
                    # Pick highest liquidity pool price
                    if base_addr and (base_addr not in current_prices or p.get("liquidity", {}).get("usd", 0) > 0):
                        current_prices[base_addr] = price
                        current_mcaps[base_addr] = mcap
        except Exception as e:
            print(f"Error fetching current prices: {e}")
        time.sleep(0.2)

    now_ts = int(time.time())
    table_rows = []
    wins = 0
    big_wins = 0
    total_evaluated = 0

    for a in alerts:
        addr = a["token_address"]
        alert_price = a["price_usd_at_alert"]
        curr_price = current_prices.get(addr)

        if not curr_price or alert_price <= 0:
            change_pct = 0.0
            status_emoji = "⚪"
            curr_price_str = "N/A"
        else:
            total_evaluated += 1
            change_pct = ((curr_price - alert_price) / alert_price) * 100.0
            curr_price_str = f"${curr_price:.4f}" if curr_price >= 0.001 else f"${curr_price:.8f}"
            
            if change_pct > 0:
                wins += 1
            if change_pct >= 20.0:
                big_wins += 1

            if change_pct >= 20.0:
                status_emoji = "🚀"
            elif change_pct > 0:
                status_emoji = "🟢"
            elif change_pct > -10.0:
                status_emoji = "🟡"
            else:
                status_emoji = "🔴"

            if save_to_db:
                hours_since = (now_ts - a["alerted_at"]) / 3600.0
                record_evaluation(
                    alert_id=a["id"],
                    hours_since=hours_since,
                    current_price=curr_price,
                    change_pct=round(change_pct, 2),
                    max_price=curr_price,
                    max_gain=round(change_pct, 2)
                )

        alert_time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(a["alerted_at"]))
        hours_elapsed = round((now_ts - a["alerted_at"]) / 3600.0, 1)

        alert_price_str = f"${alert_price:.4f}" if alert_price >= 0.001 else f"${alert_price:.8f}"
        change_pct_str = f"{change_pct:+.1f}%"

        table_rows.append([
            a["id"],
            alert_time_str,
            f"{hours_elapsed}h ago",
            a["symbol"],
            a["chain_id"],
            f"{a['momentum_score']:.1f}",
            alert_price_str,
            curr_price_str,
            f"{status_emoji} {change_pct_str}"
        ])

    headers = ["ID", "Alerted At", "Elapsed", "Symbol", "Chain", "Score", "Alert Price", "Current Price", "Return %"]
    print("\n" + tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))

    if total_evaluated > 0:
        win_rate = (wins / total_evaluated) * 100.0
        big_win_rate = (big_wins / total_evaluated) * 100.0
        print(f"\n📊 Summary Statistics:")
        print(f"• Total Evaluated: {total_evaluated}")
        print(f"• Positive Return Win Rate: {win_rate:.1f}% ({wins}/{total_evaluated})")
        print(f"• Runners (> +20% gain): {big_win_rate:.1f}% ({big_wins}/{total_evaluated})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate forward performance of alerted tokens.")
    parser.add_argument("--limit", type=int, default=50, help="Number of past alerts to evaluate")
    parser.add_argument("--no-save", action="store_true", help="Do not save evaluation checkpoints to DB")
    args = parser.parse_args()

    evaluate_past_alerts(limit=args.limit, save_to_db=not args.no_save)
