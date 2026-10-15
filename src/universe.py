import time
import logging
import requests
from typing import Set, Dict, List
from src.config import Config
from src.database import get_active_registry_tokens

logger = logging.getLogger(__name__)

STABLECOINS_AND_WRAPPED = {
    # Solana
    "So11111111111111111111111111111111111111112",  # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    # EVM
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH (Mainnet)
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC (Mainnet)
    "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT (Mainnet)
    "0x4200000000000000000000000000000000000006",  # WETH (Base)
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC (Base)
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",  # WBNB
    "0x55d398326f99059ff775485246999027b3197955",  # USDT (BSC)
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",  # USDC (BSC)
    "0x912ce59144191c1204e64559fe8253a0e49e6548",  # ARB
}

GECKO_NETWORK_MAP = {
    "solana": "solana",
    "base": "base",
    "ethereum": "eth",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
}

COINGECKO_LIST_URLS = {
    "base": "https://tokens.coingecko.com/base/all.json",
    "bsc": "https://tokens.coingecko.com/binance-smart-chain/all.json",
    "ethereum": "https://tokens.coingecko.com/uniswap/all.json",
    "arbitrum": "https://tokens.coingecko.com/arbitrum-one/all.json",
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json;version=20230302",
}


def fetch_raydium_top_pools(pages: int = 4) -> Set[str]:
    """
    Fetch top active Solana tokens from Raydium V3 sorted by 24h trading volume.
    Provides ~300-400 live, heavily-traded tokens without relying on keyword matching.
    """
    tokens = set()
    for page in range(1, pages + 1):
        try:
            url = f"https://api-v3.raydium.io/pools/info/list?poolType=all&poolSortField=volume24h&sortType=desc&pageSize=100&page={page}"
            res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if res.status_code == 200:
                pools = res.json().get("data", {}).get("data", []) or []
                for p in pools:
                    for mint_key in ("mintA", "mintB"):
                        addr = p.get(mint_key, {}).get("address")
                        if addr and addr not in STABLECOINS_AND_WRAPPED:
                            tokens.add(addr)
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Error fetching Raydium page {page}: {e}")
            break
    logger.info(f"Loaded {len(tokens)} top-volume tokens from Raydium V3.")
    return tokens


def fetch_geckoterminal_chain_pools(chain: str, pages: int = 2) -> Set[str]:
    """
    Fetch top-volume and trending pool tokens from GeckoTerminal for a specific chain.
    """
    tokens = set()
    net = GECKO_NETWORK_MAP.get(chain)
    if not net:
        return tokens

    # 1. Fetch Trending Pools
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{net}/trending_pools"
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if res.status_code == 200:
            for p in res.json().get("data", []):
                rel = p.get("relationships", {})
                base_token = rel.get("base_token", {}).get("data", {}).get("id")
                if base_token and "_" in base_token:
                    addr = base_token.split("_", 1)[1]
                    if addr and addr not in STABLECOINS_AND_WRAPPED:
                        tokens.add(addr)
        elif res.status_code == 429:
            time.sleep(2.0)
    except Exception as e:
        logger.warning(f"Error fetching GeckoTerminal trending for {chain}: {e}")

    time.sleep(1.2)

    # 2. Fetch Top Volume Pools
    for page in range(1, pages + 1):
        try:
            url = f"https://api.geckoterminal.com/api/v2/networks/{net}/pools?page={page}"
            res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if res.status_code == 200:
                for p in res.json().get("data", []):
                    rel = p.get("relationships", {})
                    base_token = rel.get("base_token", {}).get("data", {}).get("id")
                    if base_token and "_" in base_token:
                        addr = base_token.split("_", 1)[1]
                        if addr and addr not in STABLECOINS_AND_WRAPPED:
                            tokens.add(addr)
            elif res.status_code == 429:
                logger.warning(f"GeckoTerminal 429 on {chain} page {page}. Sleeping 2s...")
                time.sleep(2.5)
            time.sleep(1.2)
        except Exception as e:
            logger.warning(f"Error fetching GeckoTerminal pools for {chain} page {page}: {e}")
            break

    logger.info(f"Loaded {len(tokens)} top/trending tokens for '{chain}' from GeckoTerminal.")
    return tokens


def fetch_dexscreener_boosts() -> Set[str]:
    """Fetch top boosted token addresses from DexScreener."""
    tokens = set()
    try:
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                addr = item.get("tokenAddress")
                if addr and addr not in STABLECOINS_AND_WRAPPED:
                    tokens.add(addr)
    except Exception as e:
        logger.warning(f"Error fetching DexScreener boosts: {e}")
    return tokens


def fetch_dexscreener_profiles() -> Set[str]:
    """Fetch recent token profile addresses from DexScreener."""
    tokens = set()
    try:
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                addr = item.get("tokenAddress")
                if addr and addr not in STABLECOINS_AND_WRAPPED:
                    tokens.add(addr)
    except Exception as e:
        logger.warning(f"Error fetching DexScreener profiles: {e}")
    return tokens


def fetch_coingecko_chain_tokens(chain: str, limit: int = 500) -> Set[str]:
    """Fetch verified EVM tokens for a specific chain from CoinGecko curated lists."""
    tokens = set()
    url = COINGECKO_LIST_URLS.get(chain)
    if not url:
        return tokens
    try:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
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


def discover_universe() -> List[str]:
    """
    Assembles a comprehensive, keyword-independent candidate universe (~3,000 tokens) combining:
    1. Dynamic high-volume DEX trading pools (Raydium V3 for Solana, GeckoTerminal for EVM chains)
    2. Trending DEX pools & DexScreener boosts/profiles
    3. Persistent local SQLite token registry (known active coins continuously monitored)
    4. Verified ecosystem lists (CoinGecko Base/BSC/ETH/Arbitrum) to fill up to TARGET_UNIVERSE_SIZE
    """
    ordered_candidates: List[str] = []

    def add_tokens(tokens):
        for t in tokens:
            if t and t not in STABLECOINS_AND_WRAPPED:
                ordered_candidates.append(t)

    # 1. Live Volume Leaders from Raydium (Solana)
    if "solana" in Config.ENABLED_CHAINS:
        raydium_tokens = fetch_raydium_top_pools(pages=4)
        add_tokens(raydium_tokens)

    # 2. Live Top-Volume & Trending Pools from GeckoTerminal (All Enabled Chains)
    for chain in Config.ENABLED_CHAINS:
        gecko_tokens = fetch_geckoterminal_chain_pools(chain, pages=2)
        add_tokens(gecko_tokens)

    # 3. DexScreener top boosts & profiles
    boosts = fetch_dexscreener_boosts()
    profiles = fetch_dexscreener_profiles()
    add_tokens(boosts)
    add_tokens(profiles)

    # 4. Local SQLite Registry of previously discovered active tokens
    try:
        registered = get_active_registry_tokens(limit=3500)
        add_tokens(registered)
        if registered:
            logger.info(f"Loaded {len(registered)} active tokens from local SQLite registry.")
    except Exception as e:
        logger.warning(f"Could not load local token registry: {e}")

    # 5. Verified ecosystem lists (CoinGecko) to complete universe coverage
    for chain in ["base", "bsc", "ethereum", "arbitrum"]:
        if chain in Config.ENABLED_CHAINS:
            chain_tokens = fetch_coingecko_chain_tokens(chain, limit=500)
            add_tokens(chain_tokens)

    # Deduplicate while preserving priority order (Live active volume leaders first)
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
