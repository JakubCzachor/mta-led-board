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
_cache_etags: dict = {}  # URL -> ETag mapping
_cache_last_modified: dict = {}  # URL -> Last-Modified mapping


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

    Uses smart caching with ETag and Last-Modified headers to detect
    when MTA actually updates the data. Falls back to time-based cache
    if conditional requests aren't supported.

    Args:
        feeds: List of feed URLs
        api_key: Optional API key

    Returns:
        List of non-None blob responses
    """
    global _feed_cache, _cache_timestamp, _cache_etags, _cache_last_modified

    # Minimum time between checks (avoid hammering server)
    now = time.time()
    if _feed_cache and (now - _cache_timestamp) < FEED_CACHE_SECONDS:
        age = now - _cache_timestamp
        logger.debug(f"Time-based cache valid (age: {age:.1f}s)")
        return _feed_cache

    from concurrent.futures import ThreadPoolExecutor, as_completed

    sess = build_requests_session(api_key)

    def _one(url: str) -> Optional[tuple]:
        """Fetch one feed with conditional request support.

        Returns: (content, etag, last_modified) or None if unchanged
        """
        try:
            # Add conditional headers if we have cached values
            headers = {}
            if url in _cache_etags:
                headers["If-None-Match"] = _cache_etags[url]
            if url in _cache_last_modified:
                headers["If-Modified-Since"] = _cache_last_modified[url]

            logger.debug(f"Fetching {url} (conditional: {bool(headers)})")
            r = sess.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), headers=headers)

            # 304 Not Modified - data hasn't changed
            if r.status_code == 304:
                logger.debug(f"Feed unchanged: {url}")
                return None

            r.raise_for_status()

            # Extract caching headers
            etag = r.headers.get("ETag")
            last_modified = r.headers.get("Last-Modified")

            logger.debug(f"Successfully fetched {len(r.content)} bytes from {url}")
            return (r.content, etag, last_modified)
        except requests.Timeout as e:
            logger.warning(f"Timeout fetching {url}: {e}")
            return None
        except requests.HTTPError as e:
            # Don't treat 304 as error
            if e.response.status_code != 304:
                logger.error(f"HTTP error {e.response.status_code} from {url}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    # Fetch all feeds
    results = []
    with ThreadPoolExecutor(max_workers=len(feeds)) as ex:
        futs = {ex.submit(_one, url): i for i, url in enumerate(feeds)}
        for fut in as_completed(futs):
            idx = futs[fut]
            result = fut.result()
            results.append((idx, result))

    # Sort by original order
    results.sort(key=lambda x: x[0])

    # Process results
    updated_count = 0
    unchanged_count = 0
    new_feeds = []

    for idx, result in results:
        if result is None:
            # Either error or 304 Not Modified
            if _feed_cache and idx < len(_feed_cache):
                unchanged_count += 1
            continue

        content, etag, last_modified = result
        updated_count += 1
        new_feeds.append(content)

        # Update cache headers
        url = feeds[idx]
        if etag:
            _cache_etags[url] = etag
        if last_modified:
            _cache_last_modified[url] = last_modified

    # If nothing changed, return old cache
    if unchanged_count > 0 and updated_count == 0 and _feed_cache:
        logger.info(f"All feeds unchanged ({unchanged_count}/{len(feeds)}) - using cache")
        _cache_timestamp = time.time()  # Reset timer
        return _feed_cache

    # Mix of updated and unchanged feeds
    if updated_count > 0:
        logger.info(f"Feeds updated: {updated_count}, unchanged: {unchanged_count}")
        _feed_cache = new_feeds
        _cache_timestamp = time.time()
        return new_feeds

    # Fallback
    return new_feeds if new_feeds else (_feed_cache or [])
