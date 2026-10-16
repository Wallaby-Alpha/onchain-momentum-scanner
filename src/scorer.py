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
    if pair_created_at and pair_created_at > 0:
        age_days = (now_ms - pair_created_at) / (86400 * 1000)
        age_known = True
    else:
        # Unknown age — assume established (don't penalise missing metadata)
        age_days = 30.0
        age_known = False

    # -------------------------------------------------------------
    # 1. BASELINE SAFETY GUARDRAILS (Filter out scams, ghost pools, instant rugs)
    # -------------------------------------------------------------
    if age_known and age_days < Config.BASELINE_MIN_AGE_DAYS:
        return False, None, f"Brand new pool (<{Config.BASELINE_MIN_AGE_DAYS*24:.0f}h): {age_days:.1f}d"

    liq_usd = pair.get("liquidity", {}).get("usd", 0.0) or 0.0
    if liq_usd < Config.BASELINE_MIN_LIQUIDITY_USD:
        return False, None, f"Low pool depth: ${liq_usd:,.0f} < ${Config.BASELINE_MIN_LIQUIDITY_USD:,.0f}"

    volume_data = pair.get("volume", {}) or {}
    vol_24h = volume_data.get("h24", 0.0) or 0.0
    if vol_24h < Config.BASELINE_MIN_VOLUME_USD:
        return False, None, f"Dormant/Low volume: ${vol_24h:,.0f} < ${Config.BASELINE_MIN_VOLUME_USD:,.0f}"

    # Anti-Wash sanity check
    turnover = vol_24h / liq_usd if liq_usd > 0 else 0
    txns = pair.get("txns", {}) or {}
    txns_24h = txns.get("h24", {}) or {}
    total_txns_24h = (txns_24h.get("buys", 0) or 0) + (txns_24h.get("sells", 0) or 0)
    if turnover > 45.0 and total_txns_24h < 150:
        return False, None, f"Suspicious wash turnover {turnover:.1f}x with only {total_txns_24h} txns"

    # -------------------------------------------------------------
    # 2. METRICS & TARGET LEVEL EVALUATION
    # -------------------------------------------------------------
    fdv = pair.get("fdv", 0.0) or 0.0
    market_cap = pair.get("marketCap", 0.0) or fdv

    price_change = pair.get("priceChange", {}) or {}
    pc_1h = price_change.get("h1", 0.0) or 0.0
    pc_6h = price_change.get("h6", 0.0) or 0.0
    pc_24h = price_change.get("h24", 0.0) or 0.0

    txns_1h = txns.get("h1", {}) or {}
    buys_1h = txns_1h.get("buys", 0) or 0
    sells_1h = txns_1h.get("sells", 0) or 0
    total_txns_1h = buys_1h + sells_1h
    buyer_ratio_1h = buys_1h / total_txns_1h if total_txns_1h > 0 else 0.5

    vol_1h = volume_data.get("h1", 0.0) or 0.0
    hourly_avg_vol = vol_24h / 24.0 if vol_24h > 0 else 1.0
    vol_accel = vol_1h / hourly_avg_vol if hourly_avg_vol > 0 else 1.0

    # Evaluate against ideal target levels
    hits_age = age_days >= Config.MIN_AGE_DAYS
    hits_mcap = Config.MIN_MCAP_USD <= market_cap <= Config.MAX_MCAP_USD
    hits_liq = liq_usd >= Config.MIN_LIQUIDITY_USD
    hits_vol = vol_24h >= Config.MIN_VOLUME_24H_USD
    hits_trend = (pc_24h >= Config.MIN_PRICE_CHANGE_24H) and (pc_6h >= Config.MIN_PRICE_CHANGE_6H) and (pc_1h >= Config.MIN_PRICE_CHANGE_1H)
    hits_buyers = (buyer_ratio_1h >= Config.MIN_BUYER_RATIO_1H) and (total_txns_1h >= 10)
    hits_fdv = (fdv / market_cap <= Config.MAX_FDV_MCAP_RATIO) if (market_cap > 0 and fdv > 0) else True

    hits_all_targets = bool(hits_age and hits_mcap and hits_liq and hits_vol and hits_trend and hits_buyers and hits_fdv)

    # -------------------------------------------------------------
    # 3. COMPOSITE MOMENTUM SCORE CALCULATION (0 to 100)
    # -------------------------------------------------------------
    # 1. Price Momentum Component (40%)
    blended_pc = (0.45 * pc_1h) + (0.35 * pc_6h) + (0.20 * min(max(pc_24h, -20.0), 100.0))
    trend_score = min(max((blended_pc + 10.0) * 2.5, 0.0), 100.0)

    # 2. Buyer Dominance Component (30%)
    buyer_score = min(max((buyer_ratio_1h - 0.35) / 0.50 * 100.0, 0.0), 100.0)

    # 3. Volume Acceleration Component (20%)
    if vol_accel <= 3.5:
        accel_score = min(max(vol_accel / 3.5 * 100.0, 15.0), 100.0)
    else:
        accel_score = max(100.0 - (vol_accel - 3.5) * 4.0, 50.0)

    # 4. Liquidity Depth Component (10%)
    liq_log = math.log10(max(liq_usd, 1.0))
    liq_score = min(max((liq_log - 4.0) / 2.0 * 100.0, 0.0), 100.0)

    composite_score = (
        0.40 * trend_score +
        0.30 * buyer_score +
        0.20 * accel_score +
        0.10 * liq_score
    )

    # Bonus points for hitting all ideal target levels
    if hits_all_targets:
        composite_score += 5.0

    composite_score = min(max(round(composite_score, 1), 0.0), 100.0)
    price_usd = float(pair.get("priceUsd", 0.0) or 0.0)

    status_badge = "🎯 Prime Target" if hits_all_targets else "⚡ Momentum Watch"

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
        "target_hit": hits_all_targets,
        "status_badge": status_badge,
        "dex_url": pair.get("url", f"https://dexscreener.com/{chain_id}/{token_address}")
    }

    return True, scored_data, "Passed"
