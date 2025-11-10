from typing import List, Optional
import httpx
from src.config import TIMEOUT_CONNECT, TIMEOUT_READ

async def fetch_parallel_httpx(feeds: List[str], api_key: Optional[str]) -> List[bytes]:
    headers = {"Accept-Encoding":"gzip, deflate", "User-Agent":"gtfs-led-board/2.0"}
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    timeout = httpx.Timeout(TIMEOUT_CONNECT + TIMEOUT_READ)

    async with httpx.AsyncClient(http2=True, headers=headers, limits=limits, timeout=timeout) as client:
        async def _one(url: str):
            try:
                r = await client.get(url)
                r.raise_for_status()
                return r.content
            except Exception:
                return None
        results = await __import__("asyncio").gather(*(_one(u) for u in feeds))
    return [b for b in results if b is not None]
