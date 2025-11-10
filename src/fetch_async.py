from typing import List, Optional
import asyncio
import logging
import httpx
from src.config import TIMEOUT_CONNECT, TIMEOUT_READ

logger = logging.getLogger(__name__)


async def fetch_parallel_httpx(feeds: List[str], api_key: Optional[str]) -> List[bytes]:
    """Fetch GTFS feeds in parallel using HTTP/2.

    Args:
        feeds: List of feed URLs
        api_key: Optional API key (included in x-api-key header if provided)

    Returns:
        List of non-None blob responses
    """
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
    return successful
