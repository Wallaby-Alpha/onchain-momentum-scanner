import time
import logging
import requests
from typing import Set, Dict, List
from src.config import Config

logger = logging.getLogger(__name__)

STABLECOINS_AND_WRAPPED = {
    # Solana
    "So11111111111111111111111111111111111111112", # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", # USDT
    # EVM
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", # WETH (Mainnet)
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", # USDC (Mainnet)
    "0xdac17f958d2ee523a2206206994597c13d831ec7", # USDT (Mainnet)
    "0x4200000000000000000000000000000000000006", # WETH (Base)
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", # USDC (Base)
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c", # WBNB
    "0x55d398326f99059ff775485246999027b3197955", # USDT (BSC)
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d", # USDC (BSC)
}

# GeckoTerminal network slug mapping
GECKO_NETWORK_MAP = {
    "solana": "solana",
    "base": "base",
    "ethereum": "eth",
    "bsc": "bsc",
    "arbitrum": "arbitrum"
}


def fetch_dexscreener_boosts() -> Set[str]:
    """Fetch top boosted token addresses from DexScreener."""
    tokens = set()
    try:
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                addr = item.get("tokenAddress")
                if addr:
                    tokens.add(addr)
    except Exception as e:
        logger.warning(f"Error fetching DexScreener boosts: {e}")
    return tokens


def fetch_dexscreener_profiles() -> Set[str]:
    """Fetch recent token profile addresses from DexScreener."""
    tokens = set()
    try:
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                addr = item.get("tokenAddress")
                if addr:
                    tokens.add(addr)
    except Exception as e:
        logger.warning(f"Error fetching DexScreener profiles: {e}")
    return tokens


def fetch_geckoterminal_top_pools(chain: str, pages: int = 2) -> Set[str]:
    """Fetch top pool base tokens from GeckoTerminal."""
    tokens = set()
    network = GECKO_NETWORK_MAP.get(chain)
    if not network:
        return tokens

    headers = {"Accept": "application/json;version=20230302"}
    for page in range(1, pages + 1):
        try:
            url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools?page={page}"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                pools = res.json().get("data", [])
                for pool in pools:
                    # Extract base token address from relationships or pool name
                    rel = pool.get("relationships", {})
                    base_token = rel.get("base_token", {}).get("data", {}).get("id")
                    if base_token:
                        parts = base_token.split("_")
                        if len(parts) >= 2:
                            token_addr = parts[1]
                            if token_addr not in STABLECOINS_AND_WRAPPED:
                                tokens.add(token_addr)
            elif res.status_code == 429:
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error fetching GeckoTerminal pools for {chain} page {page}: {e}")
            break
        time.sleep(0.5)
    return tokens


def fetch_dexscreener_search(query: str) -> Set[str]:
    """Search DexScreener by keyword to catch high-volume pairs."""
    tokens = set()
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            pairs = res.json().get("pairs", []) or []
            for p in pairs:
                base_addr = p.get("baseToken", {}).get("address")
                if base_addr and base_addr not in STABLECOINS_AND_WRAPPED:
                    tokens.add(base_addr)
    except Exception as e:
        logger.warning(f"Error searching DexScreener for '{query}': {e}")
    return tokens


def discover_universe() -> List[str]:
    """
    Combines all discovery sources to compile an active candidate universe.
    """
    candidate_tokens: Set[str] = set()

    # 1. DexScreener boosts & profiles
    boosts = fetch_dexscreener_boosts()
    profiles = fetch_dexscreener_profiles()
    candidate_tokens.update(boosts)
    candidate_tokens.update(profiles)
    logger.info(f"Discovered {len(boosts)} boosted and {len(profiles)} profiled tokens.")

    # 2. GeckoTerminal top pools on enabled chains
    for chain in Config.ENABLED_CHAINS:
        pools = fetch_geckoterminal_top_pools(chain, pages=2)
        candidate_tokens.update(pools)
        logger.info(f"Discovered {len(pools)} top pools from GeckoTerminal for chain '{chain}'.")

    # 3. DexScreener search top DEXs, keywords and ecosystems (great source for established midcaps)
    discovery_keywords = [
        "raydium", "meteora", "aerodrome", "uniswap", "orca", 
        "pancakeswap", "sol", "weth", "usdc", "pepe", "ai", "virtual"
    ]
    for q in discovery_keywords:
        searched = fetch_dexscreener_search(q)
        candidate_tokens.update(searched)
        time.sleep(0.15)

    # Filter out known stablecoins/wrapped natives
    cleaned = [t for t in candidate_tokens if t not in STABLECOINS_AND_WRAPPED]
    logger.info(f"Total deduplicated candidate universe: {len(cleaned)} tokens.")
    return cleaned
