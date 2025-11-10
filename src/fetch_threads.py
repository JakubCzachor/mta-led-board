from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config import TIMEOUT_CONNECT, TIMEOUT_READ

def build_requests_session(api_key: Optional[str]) -> requests.Session:
    sess = requests.Session()
    headers = {"Accept-Encoding":"gzip, deflate", "User-Agent":"gtfs-led-board/2.0"}
    sess.headers.update(headers)
    retry = Retry(total=2, connect=2, read=2, backoff_factor=0.15,
                  status_forcelist=(429,500,502,503,504), allowed_methods=["GET"])
    adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=retry)
    sess.mount("https://", adapter); sess.mount("http://", adapter)
    return sess

def fetch_parallel_requests(feeds: List[str], api_key: Optional[str]) -> List[bytes]:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sess = build_requests_session(api_key)

    def _one(url: str):
        try:
            r = sess.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ))
            r.raise_for_status()
            return r.content
        except Exception:
            return None

    blobs: List[bytes] = []
    with ThreadPoolExecutor(max_workers=len(feeds)) as ex:
        futs = [ex.submit(_one, u) for u in feeds]
        for fut in as_completed(futs):
            b = fut.result()
            if b is not None: blobs.append(b)
    return blobs
