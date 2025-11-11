from typing import Dict, Set, Tuple
import logging
import os
import pickle
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Cache file for station mappings (speeds up startup significantly)
CACHE_DIR = ".cache"
CACHE_FILE = os.path.join(CACHE_DIR, "station_mappings.pkl")


def base_stop_id(sid: str) -> str:
    """Remove directional suffix (N/S) from GTFS stop ID.

    Examples:
        "F15N" → "F15"
        "F15S" → "F15"
        "F15" → "F15"
    """
    sid = (sid or "").strip().upper()
    return sid[:-1] if len(sid) > 1 and sid[-1] in ("N", "S") else sid


def build_station_maps(stops_path: str, stations_csv: str) -> Tuple[Dict[str, str], Dict[str, str], Set[str]]:
    """Build bidirectional mappings between stops, stations, and complexes.

    The MTA GTFS has individual directional stops (e.g., "F15N", "F15S")
    but a single station complex may serve both. This function:

    1. Reads GTFS stops (with parent_station relationships)
    2. Reads MTA complex CSV (station → complex mapping)
    3. Merges them by base stop ID
    4. Assigns each stop to its parent (if exists) or complex (if exists)

    Performance optimization: Caches the result to .cache/station_mappings.pkl
    to avoid expensive pandas operations on every startup.

    Args:
        stops_path: Path to stops.txt (GTFS)
        stations_csv: Path to stations.csv (MTA)

    Returns:
        Tuple of (stopid_to_station_key, station_key_to_name, all_station_keys)
    """
    # Check if cache exists and is newer than source files
    if os.path.exists(CACHE_FILE):
        try:
            cache_mtime = os.path.getmtime(CACHE_FILE)
            stops_mtime = os.path.getmtime(stops_path)
            stations_mtime = os.path.getmtime(stations_csv)

            if cache_mtime > stops_mtime and cache_mtime > stations_mtime:
                logger.info("Loading station mappings from cache")
                with open(CACHE_FILE, "rb") as f:
                    cached = pickle.load(f)
                logger.info(f"Loaded from cache: {len(cached[0])} stops → {len(cached[2])} stations")
                return cached
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, rebuilding...")

    logger.info(f"Loading stops from {stops_path}")
    stops = pd.read_csv(stops_path, dtype=str)
    stops["stop_id"] = stops["stop_id"].str.upper()

    if "parent_station" in stops.columns:
        ps = stops["parent_station"].fillna("").str.upper()
        stops["parent_or_self"] = np.where(ps.eq(""), stops["stop_id"], ps)
    else:
        logger.warning("No parent_station column found in stops.txt")
        stops["parent_or_self"] = stops["stop_id"]

    stops["stop_id_base"] = stops["stop_id"].map(base_stop_id)

    logger.info(f"Loading station complexes from {stations_csv}")
    complex_df = pd.read_csv(stations_csv, dtype=str)
    complex_df["GTFS Stop ID"] = complex_df["GTFS Stop ID"].str.upper()
    complex_df["stop_id_base"] = complex_df["GTFS Stop ID"].map(base_stop_id)
    complex_df["Complex ID"] = complex_df["Complex ID"].astype(str)

    stops = stops.merge(
        complex_df[["stop_id_base", "Complex ID", "Stop Name"]].drop_duplicates("stop_id_base"),
        on="stop_id_base",
        how="left"
    )

    stops["station_key"] = np.where(
        stops["parent_or_self"].notna() & (stops["parent_or_self"] != ""),
        stops["parent_or_self"],
        np.where(stops["Complex ID"].notna(), "CPLX_" + stops["Complex ID"], stops["stop_id_base"]),
    )
    stops["display_name"] = stops["Stop Name"].fillna(stops["stop_name"])
    name_map_df = stops.sort_values("display_name").groupby("station_key", as_index=False)["display_name"].first()

    stopid_to_station_key = dict(zip(stops["stop_id"], stops["station_key"]))
    station_key_to_name = dict(zip(name_map_df["station_key"], name_map_df["display_name"]))
    all_station_keys = set(station_key_to_name.keys())

    logger.info(f"Built mappings: {len(stopid_to_station_key)} stops → {len(all_station_keys)} stations")

    # Save to cache for faster future startups
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump((stopid_to_station_key, station_key_to_name, all_station_keys), f)
        logger.info(f"Saved station mappings to cache: {CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")

    return stopid_to_station_key, station_key_to_name, all_station_keys

def load_layout(layout_path: str) -> Dict[str, int]:
    """Load LED layout mapping from CSV file.

    Args:
        layout_path: Path to layout CSV with columns: station_key, led_index

    Returns:
        Dictionary mapping station_key → LED index
    """
    import csv

    logger.info(f"Loading layout from {layout_path}")
    mapping: Dict[str, int] = {}
    skipped = 0

    with open(layout_path, newline="", encoding="utf-8") as f:
        for row_num, row in enumerate(csv.DictReader(f), start=2):
            sk = (row.get("station_key") or "").strip()
            if not sk:
                continue

            try:
                idx = int(row.get("led_index", "").strip())
                mapping[sk] = idx
            except (ValueError, AttributeError) as e:
                logger.warning(f"Skipping invalid row {row_num} in {layout_path}: {e}")
                skipped += 1

    logger.info(f"Loaded {len(mapping)} LED mappings ({skipped} rows skipped)")
    return mapping
