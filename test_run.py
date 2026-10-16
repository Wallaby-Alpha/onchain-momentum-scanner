import logging
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from tabulate import tabulate

from src.database import init_db
from src.universe import discover_universe
from src.enricher import enrich_tokens
from src.scorer import evaluate_and_score

# Set clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def run_dry_test():
    print("\n" + "="*70)
    print("🚀 ON-CHAIN MOMENTUM SCANNER - DRY RUN TEST")
    print("="*70 + "\n")
    
    init_db()

    print("Step 1: Discovering candidate tokens across DexScreener & GeckoTerminal...")
    candidates = discover_universe()
    print(f"-> Discovered {len(candidates)} unique candidates.\n")

    print("Step 2: Enriching pairs via DexScreener batch API...")
    pairs = enrich_tokens(candidates)
    print(f"-> Enriched {len(pairs)} primary pairs.\n")

    print("Step 3: Filtering and calculating composite momentum scores...")
    passed = []
    rejected_reasons = {}

    for p in pairs:
        is_pass, data, reason = evaluate_and_score(p)
        if is_pass and data:
            passed.append(data)
        else:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    print(f"\nFiltering Summary:")
    print(f"• Total Pairs Checked: {len(pairs)}")
    print(f"• Passed All Filters: {len(passed)}")
    print(f"• Top Filter Rejection Reasons:")
    sorted_reasons = sorted(rejected_reasons.items(), key=lambda x: x[1], reverse=True)[:8]
    for r, count in sorted_reasons:
        print(f"   - {r}: {count}")

    if not passed:
        print("\nNo tokens passed the strict momentum & age filters on this cycle.")
        return

    # Sort descending by score
    passed.sort(key=lambda x: x["momentum_score"], reverse=True)

    print("\n" + "="*70)
    print("🔥 TOP MOMENTUM LEADERS (MID-CAP & ESTABLISHED)")
    print("="*70)

    rows = []
    for rank, t in enumerate(passed[:10], 1):
        price_str = f"${t['price_usd']:.4f}" if t['price_usd'] >= 0.001 else f"${t['price_usd']:.8f}"
        mcap_val = t["market_cap"]
        mcap_str = f"${mcap_val/1e6:.1f}M" if mcap_val >= 1e6 else f"${mcap_val/1e3:.0f}K"
        rows.append([
            rank,
            t["symbol"],
            t["chain_id"],
            f"{t['momentum_score']:.1f}",
            price_str,
            mcap_str,
            f"${t['liquidity_usd']/1e3:.0f}K",
            f"+{t['price_change_1h']:.1f}%",
            f"+{t['price_change_6h']:.1f}%",
            f"+{t['price_change_24h']:.1f}%",
            f"{t['buyer_ratio_1h']*100:.0f}%",
            f"{t['volume_accel_1h']:.1f}x",
            f"{t['age_days']:.1f}d"
        ])

    headers = [
        "Rank", "Symbol", "Chain", "Score", "Price", "MCap", "Liq",
        "1h %", "6h %", "24h %", "Buy %", "Accel", "Age"
    ]
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print("\nTest completed successfully.\n")

if __name__ == "__main__":
    run_dry_test()
