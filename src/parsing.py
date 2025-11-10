from typing import Dict, Tuple, Set, List
import logging
from google.transit import gtfs_realtime_pb2 as gtfs
from src.mapping import base_stop_id
from src.config import MODE_OFF, MODE_SOLID, MODE_BLINK, MODE_PULSE

logger = logging.getLogger(__name__)


def aggregate_states_from_blobs(
    blobs: List[bytes],
    stopid_to_station_key: Dict[str, str],
) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
    """Parse GTFS realtime feed blobs and aggregate vehicle statuses.

    For each vehicle, determines the LED mode based on its stop status:
    - STOPPED_AT → SOLID (train at platform)
    - INCOMING_AT → BLINK (train arriving)
    - IN_TRANSIT_TO → PULSE (train departing)

    Args:
        blobs: List of GTFS protobuf binary messages
        stopid_to_station_key: Mapping from GTFS stop ID to station complex key

    Returns:
        Tuple of:
        - routes_by_station: Dict[station_key, Set[route_ids]]
        - mode_by_station: Dict[station_key, max_led_mode]
    """
    routes_by_station: Dict[str, Set[str]] = {}
    mode_by_station: Dict[str, int] = {}
    unknown_stops: Set[str] = set()
    parse_errors = 0
    vehicle_count = 0

    def add(sk: str, route: str, mode: int) -> None:
        """Update or create station state."""
        if sk not in routes_by_station:
            routes_by_station[sk] = set()
        if route:
            routes_by_station[sk].add(route)
        cur = mode_by_station.get(sk, MODE_OFF)
        if mode > cur:
            mode_by_station[sk] = mode

    feed = gtfs.FeedMessage()
    for blob_num, blob in enumerate(blobs, start=1):
        try:
            feed.ParseFromString(blob)
        except Exception as e:
            logger.error(f"Failed to parse GTFS blob {blob_num}: {e}")
            parse_errors += 1
            continue

        for entity in feed.entity:
            v = entity.vehicle
            if not v or not v.current_status or not v.stop_id:
                continue

            vehicle_count += 1
            status = gtfs.VehiclePosition.VehicleStopStatus.Name(v.current_status)
            raw_sid = (v.stop_id or "").upper()
            route = (v.trip.route_id or "").strip().upper()

            # Try to map stop ID to station
            sk = (
                stopid_to_station_key.get(raw_sid)
                or stopid_to_station_key.get(base_stop_id(raw_sid))
            )

            if sk is None:
                # Unknown stop - log once per stop ID
                if raw_sid not in unknown_stops:
                    logger.debug(f"Unknown stop ID: {raw_sid}")
                    unknown_stops.add(raw_sid)
                continue

            if status == "STOPPED_AT":
                add(sk, route, MODE_SOLID)
            elif status == "INCOMING_AT":
                add(sk, route, MODE_BLINK)
            elif status == "IN_TRANSIT_TO":
                add(sk, route, MODE_PULSE)

    if parse_errors:
        logger.warning(f"Failed to parse {parse_errors}/{len(blobs)} feed blobs")

    if unknown_stops:
        logger.info(f"Encountered {len(unknown_stops)} unknown stop IDs (see debug log)")

    logger.debug(f"Processed {vehicle_count} vehicles → {len(mode_by_station)} active stations")
    return routes_by_station, mode_by_station
