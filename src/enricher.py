import time
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE = 30  # Max addresses DexScreener supports per request


def chunk_list(items: List[Any], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def fetch_token_batch(addresses: List[str]) -> List[Dict[str, Any]]:
    """
    Query DexScreener for a chunk of up to 30 token addresses.
    """
    if not addresses:
        return []
    
    joined = ",".join(addresses)
    url = f"https://api.dexscreener.com/latest/dex/tokens/{joined}"
    
    for attempt in range(3):
        try:
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                data = res.json()
                return data.get("pairs", []) or []
            elif res.status_code == 429:
                sleep_time = (attempt + 1) * 2
                logger.warning(f"DexScreener 429 rate limit hit. Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.warning(f"DexScreener returned status {res.status_code}")
                time.sleep(1)
        except Exception as e:
            logger.warning(f"DexScreener request error: {e}")
            time.sleep(1)
            
    return []


def enrich_tokens(token_addresses: List[str]) -> List[Dict[str, Any]]:
    """
    Enriches a list of token addresses with full DexScreener data,
    grouping pairs by token and picking the primary (highest liquidity) pool.
    """
    all_pairs: List[Dict[str, Any]] = []
    chunks = list(chunk_list(token_addresses, CHUNK_SIZE))
    
    logger.info(f"Enriching {len(token_addresses)} tokens across {len(chunks)} API batches...")
    for idx, chunk in enumerate(chunks):
        pairs = fetch_token_batch(chunk)
        all_pairs.extend(pairs)
        # Gentle rate limit throttle (approx 3-4 req/sec)
        time.sleep(0.25)

    # Group pairs by base token address and select the one with highest USD liquidity
    token_primary_pair: Dict[str, Dict[str, Any]] = {}
    
    for pair in all_pairs:
        base_token = pair.get("baseToken", {})
        addr = base_token.get("address")
        if not addr:
            continue
            
        liq_usd = pair.get("liquidity", {}).get("usd", 0.0) or 0.0
        
        # If we haven't seen this token, or if this pair has higher liquidity, choose it
        if addr not in token_primary_pair:
            token_primary_pair[addr] = pair
        else:
            existing_liq = token_primary_pair[addr].get("liquidity", {}).get("usd", 0.0) or 0.0
            if liq_usd > existing_liq:
                token_primary_pair[addr] = pair

    logger.info(f"Successfully enriched {len(token_primary_pair)} distinct primary token pairs.")
    return list(token_primary_pair.values())
