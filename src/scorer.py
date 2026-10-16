import time
import math
import logging
from typing import Dict, Any, Optional, Tuple
from src.config import Config

logger = logging.getLogger(__name__)


def evaluate_and_score(pair: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Evaluates a DexScreener pair against the mid-cap, older-coin filters,
    and calculates a composite momentum score.
    
    Returns:
        (passed: bool, scored_token_dict: Optional[Dict], rejection_reason: str)
    """
    chain_id = pair.get("chainId", "").lower()
    if chain_id not in Config.ENABLED_CHAINS:
        return False, None, f"Chain '{chain_id}' not in enabled chains"

    base_token = pair.get("baseToken", {})
    token_address = base_token.get("address")
    symbol = base_token.get("symbol", "UNKNOWN")
    name = base_token.get("name", "Unknown")

    if not token_address:
        return False, None, "Missing token address"

    # Age check (pairCreatedAt in milliseconds)
    pair_created_at = pair.get("pairCreatedAt")
    now_ms = int(time.time() * 1000)
    if pair_created_at:
        age_days = (now_ms - pair_created_at) / (86400 * 1000)
    else:
        # If age is unknown, treat with caution
        age_days = 0.0

    if age_days < Config.MIN_AGE_DAYS:
        return False, None, f"Too young: {age_days:.1f}d < {Config.MIN_AGE_DAYS}d"

    # Market Cap & FDV
    fdv = pair.get("fdv", 0.0) or 0.0
    market_cap = pair.get("marketCap", 0.0) or fdv
    if market_cap < Config.MIN_MCAP_USD or market_cap > Config.MAX_MCAP_USD:
        return False, None, f"MCap ${market_cap:,.0f} outside [${Config.MIN_MCAP_USD:,.0f}, ${Config.MAX_MCAP_USD:,.0f}]"

    if market_cap > 0 and fdv > 0:
        if (fdv / market_cap) > Config.MAX_FDV_MCAP_RATIO:
            return False, None, f"FDV/MCap overhang: {(fdv/market_cap):.2f} > {Config.MAX_FDV_MCAP_RATIO}"

    # Liquidity check
    liq_usd = pair.get("liquidity", {}).get("usd", 0.0) or 0.0
    if liq_usd < Config.MIN_LIQUIDITY_USD:
        return False, None, f"Low liquidity: ${liq_usd:,.0f} < ${Config.MIN_LIQUIDITY_USD:,.0f}"

    # 24h Volume check
    volume_data = pair.get("volume", {}) or {}
    vol_24h = volume_data.get("h24", 0.0) or 0.0
    if vol_24h < Config.MIN_VOLUME_24H_USD:
        return False, None, f"Low 24h volume: ${vol_24h:,.0f} < ${Config.MIN_VOLUME_24H_USD:,.0f}"

    # Price changes
    price_change = pair.get("priceChange", {}) or {}
    pc_1h = price_change.get("h1", 0.0) or 0.0
    pc_6h = price_change.get("h6", 0.0) or 0.0
    pc_24h = price_change.get("h24", 0.0) or 0.0

    if pc_1h < Config.MIN_PRICE_CHANGE_1H:
        return False, None, f"1h price change {pc_1h:.1f}% < {Config.MIN_PRICE_CHANGE_1H}%"
    if pc_6h < Config.MIN_PRICE_CHANGE_6H:
        return False, None, f"6h price change {pc_6h:.1f}% < {Config.MIN_PRICE_CHANGE_6H}%"
    if pc_24h < Config.MIN_PRICE_CHANGE_24H:
        return False, None, f"24h price change {pc_24h:.1f}% < {Config.MIN_PRICE_CHANGE_24H}%"

    # Transaction activity & Buyer Dominance
    txns = pair.get("txns", {}) or {}
    txns_1h = txns.get("h1", {}) or {}
    buys_1h = txns_1h.get("buys", 0) or 0
    sells_1h = txns_1h.get("sells", 0) or 0
    total_txns_1h = buys_1h + sells_1h

    if total_txns_1h < 15:
        return False, None, f"Insufficient 1h txns: {total_txns_1h} < 15"

    buyer_ratio_1h = buys_1h / total_txns_1h if total_txns_1h > 0 else 0.5
    if buyer_ratio_1h < Config.MIN_BUYER_RATIO_1H:
        return False, None, f"Buyer ratio {buyer_ratio_1h:.2f} < {Config.MIN_BUYER_RATIO_1H}"

    # Volume Acceleration (1h run-rate vs 24h baseline)
    vol_1h = volume_data.get("h1", 0.0) or 0.0
    hourly_avg_vol = vol_24h / 24.0 if vol_24h > 0 else 1.0
    vol_accel = vol_1h / hourly_avg_vol if hourly_avg_vol > 0 else 1.0

    # Anti-Wash sanity check
    turnover = vol_24h / liq_usd if liq_usd > 0 else 0
    txns_24h = txns.get("h24", {}) or {}
    total_txns_24h = (txns_24h.get("buys", 0) or 0) + (txns_24h.get("sells", 0) or 0)
    if turnover > 35.0 and total_txns_24h < 300:
        return False, None, f"Suspicious wash turnover {turnover:.1f}x with only {total_txns_24h} txns"

    # -------------------------------------------------------------
    # MOMENTUM SCORE CALCULATION (0 to 100)
    # -------------------------------------------------------------
    # 1. Price Momentum Component (40%)
    # Blend 1h (45%), 6h (35%), 24h (20%), normalized
    blended_pc = (0.45 * pc_1h) + (0.35 * pc_6h) + (0.20 * min(max(pc_24h, 0.0), 100.0))
    trend_score = min(max(blended_pc * 3.0, 0.0), 100.0)

    # 2. Buyer Dominance Component (30%)
    # 50% buys = 50 pts, 70% buys = 80 pts, 85%+ buys = 100 pts
    buyer_score = min(max((buyer_ratio_1h - 0.35) / 0.50 * 100.0, 0.0), 100.0)

    # 3. Volume Activity & Acceleration Component (20%)
    # Baseline 1.0x = 60 pts, 2.5x = 90 pts, 3.5x+ = 100 pts. Off-peak 0.6x = 45 pts.
    if vol_accel <= 3.5:
        accel_score = min(max(vol_accel / 3.5 * 100.0, 20.0), 100.0)
    else:
        accel_score = max(100.0 - (vol_accel - 3.5) * 4.0, 50.0)

    # 4. Liquidity Depth & Market Quality (10%)
    # Scaled from $20k to $1M+:
    # $20k = 15 pts, $100k = 50 pts, $500k = 85 pts, $1M+ = 100 pts
    liq_log = math.log10(max(liq_usd, 1.0))
    liq_score = min(max((liq_log - 4.0) / 2.0 * 100.0, 0.0), 100.0)

    composite_score = (
        0.40 * trend_score +
        0.30 * buyer_score +
        0.20 * accel_score +
        0.10 * liq_score
    )
    composite_score = round(composite_score, 1)

    if composite_score < Config.MIN_MOMENTUM_SCORE:
        return False, None, f"Momentum score {composite_score} < threshold {Config.MIN_MOMENTUM_SCORE}"

    price_usd = float(pair.get("priceUsd", 0.0) or 0.0)

    scored_data = {
        "token_address": token_address,
        "pair_address": pair.get("pairAddress"),
        "chain_id": chain_id,
        "symbol": symbol,
        "name": name,
        "price_usd": price_usd,
        "market_cap": market_cap,
        "fdv": fdv,
        "liquidity_usd": liq_usd,
        "volume_24h": vol_24h,
        "volume_1h": vol_1h,
        "volume_accel_1h": round(vol_accel, 2),
        "price_change_1h": round(pc_1h, 2),
        "price_change_6h": round(pc_6h, 2),
        "price_change_24h": round(pc_24h, 2),
        "buyer_ratio_1h": round(buyer_ratio_1h, 2),
        "txns_1h_buys": buys_1h,
        "txns_1h_sells": sells_1h,
        "age_days": round(age_days, 1),
        "momentum_score": composite_score,
        "dex_url": pair.get("url", f"https://dexscreener.com/{chain_id}/{token_address}")
    }

    return True, scored_data, "Passed"
