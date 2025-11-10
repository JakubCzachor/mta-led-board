import argparse, time, asyncio, sys, os
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="data/stations.csv")
    ap.add_argument("--stops",    default="data/stops.txt")
    ap.add_argument("--layout",   default="data/default_layout.csv")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--serial-port", default=None)
    ap.add_argument("--baud", type=int, default=2_000_000)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--httpx", dest="use_httpx", action="store_true", default=True)
    ap.add_argument("--no-httpx", dest="use_httpx", action="store_false")
    args = ap.parse_args()

    stopid_to_station_key, station_key_to_name, _ = build_station_maps(args.stops, args.stations)
    layout = load_layout(args.layout)
    if not layout:
        print("[WARN] Layout is empty; preview works but serial payload will be empty.")

    use_httpx = args.use_httpx
    feeds = FEEDS[:]

    while True:
        t0 = time.perf_counter()

        blobs: List[bytes] = []
        if use_httpx:
            try:
                blobs = asyncio.run(fetch_parallel_httpx(feeds, API_KEY))
            except Exception as e:
                print(f"[HTTP/2] fallback to requests due to: {e!r}")
                use_httpx = False
        if not use_httpx:
            blobs = fetch_parallel_requests(feeds, API_KEY)

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
            print(f"sent {len(pairs)} stations in {t_ms:.1f} ms")

        time.sleep(max(0.0, args.poll))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
