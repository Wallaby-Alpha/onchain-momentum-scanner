import time
import logging
import requests
from typing import Set, Dict, List
from src.config import Config
from src.database import get_active_registry_tokens

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
    "0x912ce59144191c1204e64559fe8253a0e49e6548", # ARB
}

COINGECKO_LIST_URLS = {
    "base": "https://tokens.coingecko.com/base/all.json",
    "bsc": "https://tokens.coingecko.com/binance-smart-chain/all.json",
    "ethereum": "https://tokens.coingecko.com/uniswap/all.json",
    "arbitrum": "https://tokens.coingecko.com/arbitrum-one/all.json"
}

SOLANA_LABS_LIST_URL = "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json"


def fetch_solana_verified_tokens(limit: int = 1200) -> Set[str]:
    """Fetch verified Solana tokens from the official Solana Labs registry."""
    tokens = set()
    try:
        res = requests.get(SOLANA_LABS_LIST_URL, timeout=10)
        if res.status_code == 200:
            data = res.json()
            raw_tokens = data.get("tokens", [])
            for item in raw_tokens[:limit]:
                addr = item.get("address")
                if addr and addr not in STABLECOINS_AND_WRAPPED:
                    tokens.add(addr)
        logger.info(f"Loaded {len(tokens)} verified Solana tokens from Solana Labs.")
    except Exception as e:
        logger.warning(f"Error fetching Solana verified token list: {e}")
    return tokens


def fetch_coingecko_chain_tokens(chain: str, limit: int = 800) -> Set[str]:
    """Fetch verified EVM tokens for a specific chain from CoinGecko curated lists."""
    tokens = set()
    url = COINGECKO_LIST_URLS.get(chain)
    if not url:
        return tokens
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            raw_tokens = data.get("tokens", [])
            for item in raw_tokens[:limit]:
                addr = item.get("address")
                if addr and addr not in STABLECOINS_AND_WRAPPED:
                    tokens.add(addr)
        logger.info(f"Loaded {len(tokens)} verified tokens for '{chain}' from CoinGecko.")
    except Exception as e:
        logger.warning(f"Error fetching CoinGecko list for {chain}: {e}")
    return tokens


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
    Assembles a comprehensive candidate universe (~3,000 tokens) combining:
    1. Persistent local token registry (known active coins)
    2. Verified ecosystem lists (Solana Labs, CoinGecko Base/BSC/ETH/Arbitrum)
    3. DexScreener top boosts & profiles
    4. DexScreener search expansion across major sectors and DEX protocols
    """
    candidate_tokens: Set[str] = set()

    ordered_candidates: List[str] = []

    def add_tokens(tokens):
        for t in tokens:
            if t and t not in STABLECOINS_AND_WRAPPED:
                ordered_candidates.append(t)

    # 1. Dynamic active DEX tokens (High Priority)
    boosts = fetch_dexscreener_boosts()
    profiles = fetch_dexscreener_profiles()
    add_tokens(boosts)
    add_tokens(profiles)

    discovery_keywords = [
        "raydium", "meteora", "aerodrome", "uniswap", "orca", 
        "pancakeswap", "sol", "weth", "pepe", "ai", "virtual", 
        "depin", "rwa", "meme", "doge", "bonk", "trump", "fartcoin"
    ]
    for q in discovery_keywords:
        searched = fetch_dexscreener_search(q)
        add_tokens(searched)
        time.sleep(0.12)

    # 2. Local Registry of previously active tokens
    try:
        registered = get_active_registry_tokens(limit=3500)
        add_tokens(registered)
        if registered:
            logger.info(f"Loaded {len(registered)} active tokens from local SQLite registry.")
    except Exception as e:
        logger.warning(f"Could not load local token registry: {e}")

    # 3. Verified ecosystem lists to fill universe up to TARGET_UNIVERSE_SIZE
    if "solana" in Config.ENABLED_CHAINS:
        sol_tokens = fetch_solana_verified_tokens(limit=1500)
        add_tokens(sol_tokens)

    for chain in ["base", "bsc", "ethereum", "arbitrum"]:
        if chain in Config.ENABLED_CHAINS:
            chain_tokens = fetch_coingecko_chain_tokens(chain, limit=600)
            add_tokens(chain_tokens)

    # Deduplicate while preserving priority order
    seen = set()
    deduped = []
    for t in ordered_candidates:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    target_size = Config.TARGET_UNIVERSE_SIZE
    if len(deduped) > target_size:
        logger.info(f"Discovered {len(deduped)} tokens. Trimming to target universe size {target_size}.")
        deduped = deduped[:target_size]

    logger.info(f"Total deduplicated candidate universe ready for scan: {len(deduped)} tokens.")
    return deduped
