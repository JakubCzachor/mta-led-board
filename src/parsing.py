from typing import Dict, Tuple, Set, List
from google.transit import gtfs_realtime_pb2 as gtfs
from src.mapping import base_stop_id
from src.config import MODE_OFF, MODE_SOLID, MODE_BLINK, MODE_PULSE

def aggregate_states_from_blobs(
    blobs: List[bytes],
    stopid_to_station_key: Dict[str, str],
) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
    routes_by_station: Dict[str, Set[str]] = {}
    mode_by_station: Dict[str, int] = {}

    def add(sk: str, route: str, mode: int):
        if sk not in routes_by_station:
            routes_by_station[sk] = set()
        if route: routes_by_station[sk].add(route)
        cur = mode_by_station.get(sk, MODE_OFF)
        if mode > cur: mode_by_station[sk] = mode

    feed = gtfs.FeedMessage()
    for blob in blobs:
        try:
            feed.ParseFromString(blob)
        except Exception:
            continue
        for entity in feed.entity:
            v = entity.vehicle
            if not v or not v.current_status or not v.stop_id: continue
            status = gtfs.VehiclePosition.VehicleStopStatus.Name(v.current_status)
            raw_sid = (v.stop_id or "").upper()
            route = (v.trip.route_id or "").strip().upper()
            sk = stopid_to_station_key.get(raw_sid) or \
                 stopid_to_station_key.get(base_stop_id(raw_sid)) or \
                 base_stop_id(raw_sid)
            if status == "STOPPED_AT":
                add(sk, route, MODE_SOLID)
            elif status == "INCOMING_AT":
                add(sk, route, MODE_BLINK)
            elif status == "IN_TRANSIT_TO":
                add(sk, route, MODE_PULSE)
    return routes_by_station, mode_by_station
