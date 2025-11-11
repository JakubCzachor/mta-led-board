# Web Dashboard

The MTA LED Board includes a live web dashboard for monitoring NYC Subway activity in real-time.

## Quick Start

```bash
# Start the application with web dashboard
python -m python.src.app --test --web

# Or with custom host/port
python -m python.src.app --test --web --web-host 0.0.0.0 --web-port 8080
```

Then open your browser to: **http://127.0.0.1:5000**

## Features

### Real-time Statistics Dashboard

The main dashboard displays live subway statistics:

- **Active Stations**: Number of stations with trains currently present
- **Total Vehicles**: Total number of subway cars tracked across all feeds
- **At Platform**: Trains stopped at stations
- **Arriving**: Trains approaching stations
- **Departing**: Trains that just left stations

### Station Search

Search for any NYC Subway station by name:

- Type partial station names (e.g., "42", "Grand", "Times")
- Shows matching stations with current train routes
- Click any station to see detailed information
- Displays arrival status for each station

### Live Data Tabs

**Busiest Stations Tab:**
- Top 20 stations with most active routes
- Shows route badges with MTA standard colors
- Displays station status (STOPPED_AT, INCOMING, DEPARTING)

**Active Routes Tab:**
- All active subway routes with station counts
- Route badges styled with official MTA colors
- Sorted by number of active stations

**All Active Stations Tab:**
- Complete list of all stations with trains
- Alphabetically sorted
- Real-time route and status information

### Station Detail View

Click any station to see:
- Station name
- Current status (Train at platform / arriving / departing)
- All active routes at the station
- Route badges with MTA colors
- Status description

### Auto-refresh

- Dashboard automatically updates every 2 seconds
- Connection status indicator (LIVE / UPDATING / STALE / ERROR)
- Last update timestamp displayed

## API Endpoints

The web server provides a REST API for programmatic access:

### `GET /api/health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "last_update": 1762825757.78,
  "age_seconds": 1.4
}
```

### `GET /api/statistics`

System-wide statistics.

**Response:**
```json
{
  "total_stations": 496,
  "active_stations": 282,
  "total_vehicles": 647,
  "feed_updates": 42,
  "last_update": 1762825757.78,
  "mode_breakdown": {
    "STOPPED_AT": 150,
    "INCOMING": 80,
    "DEPARTING": 52
  },
  "busiest_stations": [...],
  "active_routes": [...],
  "uptime": 3600.5
}
```

### `GET /api/stations`

List all currently active stations.

**Response:**
```json
{
  "stations": [
    {
      "key": "631",
      "name": "Grand Central-42 St",
      "routes": ["4", "5", "6"],
      "mode": 1,
      "mode_name": "STOPPED_AT"
    },
    ...
  ],
  "count": 282,
  "last_update": 1762825757.78
}
```

### `GET /api/station/<station_key>`

Detailed information for a specific station.

**Example:** `/api/station/631`

**Response:**
```json
{
  "key": "631",
  "name": "Grand Central-42 St",
  "routes": ["4", "5", "6"],
  "mode": 1,
  "mode_name": "STOPPED_AT",
  "status": "Train at platform",
  "last_update": 1762825757.78
}
```

### `GET /api/search?q=<query>`

Search stations by name.

**Example:** `/api/search?q=42+st`

**Response:**
```json
{
  "stations": [
    {
      "key": "631",
      "name": "Grand Central-42 St",
      "routes": ["4", "5", "6"],
      "mode": 1,
      "mode_name": "STOPPED_AT",
      "has_trains": true
    },
    ...
  ]
}
```

## Integration Examples

### Python

```python
import requests

# Get current statistics
response = requests.get('http://127.0.0.1:5000/api/statistics')
stats = response.json()
print(f"Active stations: {stats['active_stations']}")
print(f"Total vehicles: {stats['total_vehicles']}")

# Search for a station
response = requests.get('http://127.0.0.1:5000/api/search', params={'q': 'times square'})
stations = response.json()['stations']
for station in stations:
    print(f"{station['name']}: {', '.join(station['routes'])}")
```

### JavaScript/Node.js

```javascript
// Fetch current statistics
fetch('http://127.0.0.1:5000/api/statistics')
  .then(res => res.json())
  .then(data => {
    console.log(`Active stations: ${data.active_stations}`);
    console.log(`Total vehicles: ${data.total_vehicles}`);
  });

// Search for a station
fetch('http://127.0.0.1:5000/api/search?q=times+square')
  .then(res => res.json())
  .then(data => {
    data.stations.forEach(station => {
      console.log(`${station.name}: ${station.routes.join(', ')}`);
    });
  });
```

### cURL

```bash
# Get health status
curl http://127.0.0.1:5000/api/health

# Get statistics
curl http://127.0.0.1:5000/api/statistics | jq

# Search stations
curl "http://127.0.0.1:5000/api/search?q=42+st" | jq

# Get specific station
curl http://127.0.0.1:5000/api/station/631 | jq
```

## LED Status Modes

The dashboard uses three status modes matching the physical LED behavior:

- **STOPPED_AT** (Green badge) - Train is stopped at the platform
- **INCOMING** (Yellow badge) - Train is arriving at the station
- **DEPARTING** (Blue badge) - Train just departed from the station

## Route Colors

Route badges use official MTA colors:

- **1/2/3** - Red
- **4/5/6** - Green
- **7** - Purple
- **A/C/E** - Blue
- **B/D/F/M** - Orange
- **G** - Light Green
- **J/Z** - Brown
- **L** - Gray
- **N/Q/R/W** - Yellow
- **S** - Dark Gray

## Technical Details

### Architecture

- **Backend**: Flask web server running in background thread
- **Frontend**: Vanilla JavaScript (no frameworks)
- **Styling**: Custom CSS with MTA branding
- **Updates**: Real-time data shared from main polling loop
- **CORS**: Enabled for cross-origin requests

### Performance

- Web server runs in daemon thread (non-blocking)
- Data updates happen in main application loop
- No database - all data kept in memory
- Minimal overhead (~1ms per update cycle)

### Security Notes

- Default binding to `127.0.0.1` (localhost only)
- Use `--web-host 0.0.0.0` to allow external connections
- No authentication (intended for local/trusted networks)
- Development server (not for production use)

## Troubleshooting

**Web server won't start:**
- Ensure Flask is installed: `pip install flask flask-cors`
- Check if port 5000 is already in use
- Try a different port: `--web-port 8080`

**Dashboard shows "STALE":**
- Data hasn't updated in 60+ seconds
- Check network connection to MTA feeds
- Verify application is still running

**No stations showing:**
- Wait for first data update (2-5 seconds)
- Check console output for errors
- Verify MTA feeds are accessible

**Search returns no results:**
- Use partial names (e.g., "42" instead of "42nd Street")
- Station names may differ from common usage
- Only active stations (with trains) are searchable

## Files

Web dashboard files:

```
web/
├── templates/
│   └── index.html          # Main dashboard HTML
└── static/
    ├── style.css           # Dashboard styles
    └── app.js              # Frontend JavaScript

python/src/
└── web_server.py           # Flask backend server
```
