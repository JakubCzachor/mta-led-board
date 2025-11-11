"""Flask web server for MTA LED Board statistics and train arrivals."""
from typing import Dict, Set, List, Tuple, Optional
import logging
import time
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from collections import defaultdict

try:
    from .config import MODE_OFF, MODE_SOLID, MODE_BLINK, MODE_PULSE
except ImportError:
    from src.config import MODE_OFF, MODE_SOLID, MODE_BLINK, MODE_PULSE

logger = logging.getLogger(__name__)

# Global state shared with main app
_latest_data = {
    "routes_by_station": {},
    "mode_by_station": {},
    "station_key_to_name": {},
    "layout": {},
    "last_update": 0.0,
    "vehicle_count": 0,
    "feed_update_count": 0,
}


def create_app():
    """Create and configure Flask app."""
    app = Flask(__name__,
                template_folder='../../web/templates',
                static_folder='../../web/static')
    CORS(app)

    @app.route('/')
    def index():
        """Main dashboard page."""
        return render_template('index.html')

    @app.route('/api/stations')
    def get_stations():
        """Get list of all stations with their current status."""
        data = _latest_data.copy()
        routes_by_station = data.get("routes_by_station", {})
        mode_by_station = data.get("mode_by_station", {})
        station_key_to_name = data.get("station_key_to_name", {})

        stations = []
        for sk, routes in routes_by_station.items():
            name = station_key_to_name.get(sk, sk)
            mode = mode_by_station.get(sk, MODE_OFF)
            mode_name = _mode_to_string(mode)

            stations.append({
                "key": sk,
                "name": name,
                "routes": sorted(list(routes)),
                "mode": mode,
                "mode_name": mode_name,
            })

        # Sort by name
        stations.sort(key=lambda s: s["name"])

        return jsonify({
            "stations": stations,
            "count": len(stations),
            "last_update": data.get("last_update", 0),
        })

    @app.route('/api/station/<station_key>')
    def get_station_detail(station_key):
        """Get detailed information for a specific station."""
        data = _latest_data.copy()
        routes_by_station = data.get("routes_by_station", {})
        mode_by_station = data.get("mode_by_station", {})
        station_key_to_name = data.get("station_key_to_name", {})

        if station_key not in routes_by_station:
            return jsonify({"error": "Station not found or no trains"}), 404

        name = station_key_to_name.get(station_key, station_key)
        routes = sorted(list(routes_by_station[station_key]))
        mode = mode_by_station.get(station_key, MODE_OFF)
        mode_name = _mode_to_string(mode)

        return jsonify({
            "key": station_key,
            "name": name,
            "routes": routes,
            "mode": mode,
            "mode_name": mode_name,
            "status": _get_status_description(mode),
            "last_update": data.get("last_update", 0),
        })

    @app.route('/api/search')
    def search_stations():
        """Search stations by name."""
        query = request.args.get('q', '').strip().lower()
        if not query:
            return jsonify({"stations": []})

        data = _latest_data.copy()
        station_key_to_name = data.get("station_key_to_name", {})
        routes_by_station = data.get("routes_by_station", {})
        mode_by_station = data.get("mode_by_station", {})

        results = []
        for sk, name in station_key_to_name.items():
            if query in name.lower():
                routes = sorted(list(routes_by_station.get(sk, [])))
                mode = mode_by_station.get(sk, MODE_OFF)

                results.append({
                    "key": sk,
                    "name": name,
                    "routes": routes,
                    "mode": mode,
                    "mode_name": _mode_to_string(mode),
                    "has_trains": sk in routes_by_station,
                })

        # Sort by name
        results.sort(key=lambda s: s["name"])

        return jsonify({"stations": results})

    @app.route('/api/statistics')
    def get_statistics():
        """Get system-wide statistics."""
        data = _latest_data.copy()
        routes_by_station = data.get("routes_by_station", {})
        mode_by_station = data.get("mode_by_station", {})
        station_key_to_name = data.get("station_key_to_name", {})

        # Count by mode
        mode_counts = defaultdict(int)
        for mode in mode_by_station.values():
            mode_counts[_mode_to_string(mode)] += 1

        # Count by route
        route_counts = defaultdict(int)
        for routes in routes_by_station.values():
            for route in routes:
                route_counts[route] += 1

        # Find busiest stations (most routes)
        busiest = []
        for sk, routes in routes_by_station.items():
            name = station_key_to_name.get(sk, sk)
            busiest.append({
                "key": sk,
                "name": name,
                "route_count": len(routes),
                "routes": sorted(list(routes)),
                "mode": mode_by_station.get(sk, MODE_OFF),
                "mode_name": _mode_to_string(mode_by_station.get(sk, MODE_OFF)),
            })

        busiest.sort(key=lambda x: x["route_count"], reverse=True)

        # Most active routes
        active_routes = [
            {"route": route, "station_count": count}
            for route, count in sorted(route_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return jsonify({
            "total_stations": len(station_key_to_name),
            "active_stations": len(routes_by_station),
            "total_vehicles": data.get("vehicle_count", 0),
            "feed_updates": data.get("feed_update_count", 0),
            "last_update": data.get("last_update", 0),
            "mode_breakdown": dict(mode_counts),
            "busiest_stations": busiest[:20],  # Top 20
            "active_routes": active_routes,
            "uptime": time.time() - data.get("start_time", time.time()),
        })

    @app.route('/api/health')
    def health():
        """Health check endpoint."""
        data = _latest_data.copy()
        age = time.time() - data.get("last_update", 0)

        return jsonify({
            "status": "ok" if age < 60 else "stale",
            "last_update": data.get("last_update", 0),
            "age_seconds": age,
        })

    return app


def update_data(
    routes_by_station: Dict[str, Set[str]],
    mode_by_station: Dict[str, int],
    station_key_to_name: Dict[str, str],
    layout: Dict[str, int],
    vehicle_count: int = 0,
):
    """Update shared data from main app."""
    global _latest_data
    _latest_data["routes_by_station"] = routes_by_station
    _latest_data["mode_by_station"] = mode_by_station
    _latest_data["station_key_to_name"] = station_key_to_name
    _latest_data["layout"] = layout
    _latest_data["last_update"] = time.time()
    _latest_data["vehicle_count"] = vehicle_count
    _latest_data["feed_update_count"] = _latest_data.get("feed_update_count", 0) + 1

    if "start_time" not in _latest_data:
        _latest_data["start_time"] = time.time()


def _mode_to_string(mode: int) -> str:
    """Convert mode integer to string."""
    if mode == MODE_SOLID:
        return "STOPPED_AT"
    elif mode == MODE_BLINK:
        return "INCOMING"
    elif mode == MODE_PULSE:
        return "DEPARTING"
    else:
        return "OFF"


def _get_status_description(mode: int) -> str:
    """Get human-readable status description."""
    if mode == MODE_SOLID:
        return "Train at platform"
    elif mode == MODE_BLINK:
        return "Train arriving"
    elif mode == MODE_PULSE:
        return "Train departing"
    else:
        return "No trains"


def run_server(host: str = "127.0.0.1", port: int = 5000):
    """Run the Flask development server."""
    app = create_app()
    logger.info(f"Starting web server on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
