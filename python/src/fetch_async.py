from typing import List, Optional
import asyncio
import logging
import time
import httpx

try:
    from .config import TIMEOUT_CONNECT, TIMEOUT_READ, FEED_CACHE_SECONDS
except ImportError:
    from src.config import TIMEOUT_CONNECT, TIMEOUT_READ, FEED_CACHE_SECONDS

logger = logging.getLogger(__name__)

# In-memory cache for GTFS feeds
_feed_cache: Optional[List[bytes]] = None
_cache_timestamp: float = 0.0


async def fetch_parallel_httpx(feeds: List[str], api_key: Optional[str]) -> List[bytes]:
    """Fetch GTFS feeds in parallel using HTTP/2.

    Uses in-memory caching to avoid redundant network requests.
    Cache is valid for FEED_CACHE_SECONDS (default: 15s).

    Args:
        feeds: List of feed URLs
        api_key: Optional API key (included in x-api-key header if provided)

    Returns:
        List of non-None blob responses
    """
    global _feed_cache, _cache_timestamp

    # Check if cache is still valid
    now = time.time()
    if _feed_cache and (now - _cache_timestamp) < FEED_CACHE_SECONDS:
        age = now - _cache_timestamp
        logger.info(f"Using cached feeds (age: {age:.1f}s)")
        return _feed_cache

    headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "gtfs-led-board/2.0"
    }
    if api_key:
        headers["x-api-key"] = api_key

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    timeout = httpx.Timeout(TIMEOUT_CONNECT + TIMEOUT_READ)

    async with httpx.AsyncClient(http2=True, headers=headers, limits=limits, timeout=timeout) as client:
        async def _one(url: str) -> Optional[bytes]:
            try:
                logger.debug(f"Fetching {url}")
                r = await client.get(url)
                r.raise_for_status()
                logger.debug(f"Successfully fetched {len(r.content)} bytes from {url}")
                return r.content
            except httpx.TimeoutException as e:
                logger.warning(f"Timeout fetching {url}: {e}")
                return None
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} from {url}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Request error fetching {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None

        results = await asyncio.gather(*(_one(u) for u in feeds))

    successful = [b for b in results if b is not None]
    logger.info(f"Successfully fetched {len(successful)}/{len(feeds)} feeds")

    # Update cache
    _feed_cache = successful
    _cache_timestamp = time.time()

    return successful
