from typing import Dict, Set, Tuple
import pandas as pd
import numpy as np

def base_stop_id(sid: str) -> str:
    sid = (sid or "").strip().upper()
    return sid[:-1] if len(sid) > 1 and sid[-1] in ("N","S") else sid

def build_station_maps(stops_path: str, stations_csv: str):
    stops = pd.read_csv(stops_path, dtype=str)
    stops["stop_id"] = stops["stop_id"].str.upper()
    if "parent_station" in stops.columns:
        ps = stops["parent_station"].fillna("").str.upper()
        stops["parent_or_self"] = np.where(ps.eq(""), stops["stop_id"], ps)
    else:
        stops["parent_or_self"] = stops["stop_id"]
    stops["stop_id_base"] = stops["stop_id"].map(base_stop_id)

    complex_df = pd.read_csv(stations_csv, dtype=str)
    complex_df["GTFS Stop ID"] = complex_df["GTFS Stop ID"].str.upper()
    complex_df["stop_id_base"] = complex_df["GTFS Stop ID"].map(base_stop_id)
    complex_df["Complex ID"] = complex_df["Complex ID"].astype(str)

    stops = stops.merge(
        complex_df[["stop_id_base","Complex ID","Stop Name"]].drop_duplicates("stop_id_base"),
        on="stop_id_base", how="left"
    )

    stops["station_key"] = np.where(
        stops["parent_or_self"].notna() & (stops["parent_or_self"] != ""),
        stops["parent_or_self"],
        np.where(stops["Complex ID"].notna(), "CPLX_" + stops["Complex ID"], stops["stop_id_base"]),
    )
    stops["display_name"] = stops["Stop Name"].fillna(stops["stop_name"])
    name_map_df = stops.sort_values("display_name").groupby("station_key", as_index=False)["display_name"].first()

    stopid_to_station_key = dict(zip(stops["stop_id"], stops["station_key"]))
    station_key_to_name   = dict(zip(name_map_df["station_key"], name_map_df["display_name"]))
    all_station_keys      = set(station_key_to_name.keys())
    return stopid_to_station_key, station_key_to_name, all_station_keys

def load_layout(layout_path: str) -> Dict[str, int]:
    import csv
    mapping: Dict[str, int] = {}
    with open(layout_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sk = (row.get("station_key") or "").strip()
            if not sk: continue
            try:
                idx = int(row.get("led_index","").strip())
            except Exception:
                continue
            mapping[sk] = idx
    return mapping
