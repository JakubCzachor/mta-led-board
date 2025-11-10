import argparse
import time
import asyncio
import sys
import os
import logging
from typing import List

# --- bootstrap so running as a script works (python src/app.py) ---
if __package__ is None or __package__ == "":
    # add repo root to sys.path so "src.*" absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.config import FEEDS, API_KEY
from src.mapping import build_station_maps, load_layout
from src.fetch_async import fetch_parallel_httpx
from src.fetch_threads import fetch_parallel_requests
from src.parsing import aggregate_states_from_blobs
from src.render import build_led_payload, print_test_preview
from src.serial_frame import frame_bytes, send_serial

logger = logging.getLogger(__name__)


def main():
    ap = argparse.ArgumentParser(description="MTA LED Board - Real-time NYC Subway visualization")
    ap.add_argument("--stations", default="python/data/stations.csv", help="Path to stations.csv")
    ap.add_argument("--stops", default="python/data/stops.txt", help="Path to stops.txt")
    ap.add_argument("--layout", default="python/data/default_layout.csv", help="Path to layout CSV")
    ap.add_argument("--test", action="store_true", help="Test mode (console output)")
    ap.add_argument("--serial-port", default=None, help="Serial port for ESP32")
    ap.add_argument("--baud", type=int, default=2_000_000, help="Baud rate")
    ap.add_argument("--poll", type=float, default=1.0, help="Poll interval in seconds")
    ap.add_argument("--httpx", dest="use_httpx", action="store_true", default=True, help="Use httpx (HTTP/2)")
    ap.add_argument("--no-httpx", dest="use_httpx", action="store_false", help="Use requests (HTTP/1.1)")
    ap.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = ap.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger.info("Starting MTA LED Board")
    logger.info(f"Using {'httpx (HTTP/2)' if args.use_httpx else 'requests (HTTP/1.1)'} backend")

    stopid_to_station_key, station_key_to_name, _ = build_station_maps(args.stops, args.stations)
    layout = load_layout(args.layout)
    if not layout:
        logger.warning("Layout is empty; preview works but serial payload will be empty.")

    use_httpx = args.use_httpx
    feeds = FEEDS

    logger.info(f"Monitoring {len(feeds)} GTFS feeds")
    logger.info(f"Poll interval: {args.poll}s")

    while True:
        t0 = time.perf_counter()

        blobs: List[bytes] = []
        if use_httpx:
            try:
                blobs = asyncio.run(fetch_parallel_httpx(feeds, API_KEY))
            except Exception as e:
                logger.warning(f"HTTP/2 backend failed, falling back to requests: {e}")
                use_httpx = False
        if not use_httpx:
            blobs = fetch_parallel_requests(feeds, API_KEY)

        if not blobs:
            logger.error("No data received from any feed")
        else:
            logger.debug(f"Received {len(blobs)} feed responses")

        routes_by_station, mode_by_station = aggregate_states_from_blobs(
            blobs, stopid_to_station_key
        )
        pairs = build_led_payload(routes_by_station, mode_by_station, layout)
        payload = frame_bytes(pairs)

        t_ms = (time.perf_counter() - t0) * 1000.0

        if args.test or not args.serial_port:
            print_test_preview(t_ms, station_key_to_name, layout, routes_by_station, mode_by_station)
        else:
            send_serial(args.serial_port, args.baud, payload)
            logger.info(f"Sent {len(pairs)} stations in {t_ms:.1f} ms")

        time.sleep(max(0.0, args.poll))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
