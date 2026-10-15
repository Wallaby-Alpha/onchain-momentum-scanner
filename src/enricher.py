import time
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any
from src.database import upsert_registry_tokens

logger = logging.getLogger(__name__)

CHUNK_SIZE = 30  # Max addresses DexScreener supports per request
CONCURRENCY = 4  # 4 concurrent requests (safe within DexScreener limits)


def chunk_list(items: List[Any], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


async def fetch_token_batch_async(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, addresses: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch a chunk of up to 30 tokens from DexScreener asynchronously.
    """
    if not addresses:
        return []

    joined = ",".join(addresses)
    url = f"https://api.dexscreener.com/latest/dex/tokens/{joined}"

    async with semaphore:
        for attempt in range(3):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("pairs", []) or []
                    elif response.status == 429:
                        sleep_time = (attempt + 1) * 2
                        logger.warning(f"DexScreener 429 hit. Sleeping {sleep_time}s...")
                        await asyncio.sleep(sleep_time)
                    else:
                        await asyncio.sleep(0.5)
            except Exception as e:
                await asyncio.sleep(0.5)
        return []


async def enrich_tokens_async(token_addresses: List[str]) -> List[Dict[str, Any]]:
    """
    Asynchronously enriches thousands of tokens from DexScreener in parallel batches.
    """
    chunks = list(chunk_list(token_addresses, CHUNK_SIZE))
    logger.info(f"Asynchronously enriching {len(token_addresses)} tokens across {len(chunks)} API batches...")

    connector = aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver(),
        limit=CONCURRENCY * 2,
        ssl=False
    )
    semaphore = asyncio.Semaphore(CONCURRENCY)
    all_pairs: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_token_batch_async(session, semaphore, chunk)
            for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)
        for pairs in results:
            all_pairs.extend(pairs)

    # Group pairs by base token address and select the primary pair with highest USD liquidity
    token_primary_pair: Dict[str, Dict[str, Any]] = {}
    tokens_to_register = []

    for pair in all_pairs:
        base_token = pair.get("baseToken", {})
        addr = base_token.get("address")
        if not addr:
            continue

        liq_usd = pair.get("liquidity", {}).get("usd", 0.0) or 0.0

        if addr not in token_primary_pair:
            token_primary_pair[addr] = pair
            tokens_to_register.append({
                "token_address": addr,
                "chain_id": pair.get("chainId", "unknown"),
                "symbol": base_token.get("symbol"),
                "name": base_token.get("name")
            })
        else:
            existing_liq = token_primary_pair[addr].get("liquidity", {}).get("usd", 0.0) or 0.0
            if liq_usd > existing_liq:
                token_primary_pair[addr] = pair

    # Retain all successfully discovered active tokens in SQLite registry
    if tokens_to_register:
        try:
            upsert_registry_tokens(tokens_to_register)
        except Exception as e:
            logger.warning(f"Could not update token registry: {e}")

    logger.info(f"Enrichment complete: {len(token_primary_pair)} distinct primary pairs resolved from {len(all_pairs)} total pools.")
    return list(token_primary_pair.values())


def enrich_tokens(token_addresses: List[str]) -> List[Dict[str, Any]]:
    """Synchronous entry point that runs the async enrichment loop."""
    return asyncio.run(enrich_tokens_async(token_addresses))
