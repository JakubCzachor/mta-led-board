from typing import List, Optional
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .config import TIMEOUT_CONNECT, TIMEOUT_READ, FEED_CACHE_SECONDS
except ImportError:
    from src.config import TIMEOUT_CONNECT, TIMEOUT_READ, FEED_CACHE_SECONDS

logger = logging.getLogger(__name__)

# In-memory cache for GTFS feeds
_feed_cache: Optional[List[bytes]] = None
_cache_timestamp: float = 0.0


def build_requests_session(api_key: Optional[str]) -> requests.Session:
    """Build a requests session with retry logic and connection pooling.

    Args:
        api_key: Optional API key (included in x-api-key header if provided)

    Returns:
        Configured requests.Session
    """
    sess = requests.Session()
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "gtfs-led-board/2.0"
    }
    if api_key:
        headers["x-api-key"] = api_key

    sess.headers.update(headers)
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.15,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def fetch_parallel_requests(feeds: List[str], api_key: Optional[str]) -> List[bytes]:
    """Fetch GTFS feeds in parallel using threaded requests.

    Uses in-memory caching to avoid redundant network requests.
    Cache is valid for FEED_CACHE_SECONDS (default: 15s).

    Args:
        feeds: List of feed URLs
        api_key: Optional API key

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

    from concurrent.futures import ThreadPoolExecutor, as_completed

    sess = build_requests_session(api_key)

    def _one(url: str) -> Optional[bytes]:
        try:
            logger.debug(f"Fetching {url}")
            r = sess.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ))
            r.raise_for_status()
            logger.debug(f"Successfully fetched {len(r.content)} bytes from {url}")
            return r.content
        except requests.Timeout as e:
            logger.warning(f"Timeout fetching {url}: {e}")
            return None
        except requests.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    blobs: List[bytes] = []
    with ThreadPoolExecutor(max_workers=len(feeds)) as ex:
        futs = [ex.submit(_one, u) for u in feeds]
        for fut in as_completed(futs):
            b = fut.result()
            if b is not None:
                blobs.append(b)

    logger.info(f"Successfully fetched {len(blobs)}/{len(feeds)} feeds")

    # Update cache
    _feed_cache = blobs
    _cache_timestamp = time.time()

    return blobs
