# MTA LED Board — README

A fast Python app that lights a physical LED map of the NYC Subway using GTFS-realtime. It fetches vehicle positions in parallel, maps them to station complexes, assigns route colors (with “sticky” persistence to prevent flicker), and streams compact frames to an ESP32 over USB serial. A **TEST MODE** prints a readable preview if you don’t have hardware connected.

---

## Features

- **Parallel HTTP + protobuf parsing** (threaded or asyncio)
- **Station→Complex mapping** (handles `N/S` stop suffixes, parents, and complex IDs)
- **Route color priority** (letter lines prioritized when mixed)
- **Sticky states** (hold/pulse/blink windows to reduce flicker)
- **Layout-driven rendering** (choose which stations to include; skip Staten Island or far-north Bronx by editing one CSV)
- **Hardware or Test Mode** (serial frames to ESP32 or console preview)
- **8 mm *or* 12 mm pixel support** (layout file defines LED positions; the code is agnostic)

---

## Folder Layout

project/
├─ data/
│ ├─ stops.txt # GTFS stops file (MTA static)
│ ├─ stations.csv # MTA complex mapping (data.gov)
│ ├─ default_layout.csv # Station → LED index/coords you want to light
│ └─ layout_with_names.csv # (optional) helper export
└─ src/
├─ app.py # CLI entrypoint
├─ config.py # Feeds, API key, timings, serial port, behavior flags
├─ fetch_async.py # HTTP/2 asyncio fetch+parse (fastest)
├─ fetch_threads.py # ThreadPool + requests fallback
├─ mapping.py # Stop/complex merging, name picking, route colors
├─ parsing.py # GTFS entity parsing → station states
├─ render.py # Sticky/blink/pulse + layout → frame bytes
└─ serial_frame.py # USB message format (framing, checksum)


> Keep the `data/` directory at project root **next to** `src/`.

---

## Prerequisites

- Python **3.10+** (Windows/macOS/Linux)
- Pip v23+
- (Optional) ESP32 on COM/tty for hardware mode

---

### Install

```bash
# from project root (the folder containing /src and /data)
python -m venv .venv
# Windows PowerShell:
. .venv/Scripts/Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install --upgrade pip
pip install pandas numpy protobuf requests httpx pyserial
```

---

### First Run (TEST MODE)
```bash
python -m src.app --layout data/default_layout.csv --mode test
```
Output:
```yaml
TEST MODE — LED preview
polled in 60.8 ms | occupied=275 | solid=6 blink=0 pulse=6
  SOLID : 14 St-Union Sq, 34 St-Herald Sq, ...
  PULSE : Grand Central-42 St, Queensboro Plaza, ...
```

---

### Hardware Mode (ESP32 over USB)

1. Flash ESP32 with a sketch that:
    - Opens Serial 115200.
    - Reads framed messages (see Serial Frame Format).
    - For each station payload: set pixel color and animation (solid/blink/pulse).
    - Renders with FastLED/NeoPixel.
2. Find USB port:
    - Windows: COM5 (check Device Manager)
    - macOS: /dev/tty.usbserial-*
    - Linux: /dev/ttyUSB0 or /dev/ttyACM0
3. Edit src/config.py:
    - SERIAL_PORT = "COM5"
    - BAUD = 115200
4. Run:
```bash
python -m src.app --layout data/default_layout.csv --mode serial
```

---

### Configuration (edit src/config.py)
# Feeds (GTFS-realtime)
FEEDS = [
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",  # 1/2/3/4/5/6/7/S
]

HTTP_TIMEOUT = (1.5, 4.0)       # connect, read
POLL_MS = 500                   # poll cadence (ms)

# Sticky/animation windows (in ticks = polls)
HOLD_TICKS  = 3     # keep last solid color if briefly idle
PULSE_TICKS = 2     # polls to “pulse” on DEPARTING
BLINK_TICKS = 2     # polls to “blink” on INCOMING

# Rendering
PRIORITIZE_LETTER_LINES = True  # prefer A/C/E/B/D/F/M/N/Q/R/W over number lines
BRIGHTNESS = 255                # lower if power limited

# Serial
SERIAL_PORT = "COM5"            # Windows example
BAUD = 115200

# Colors & Priority

Approx MTA branding:

- **A/C/E** — blue  
- **B/D/F/M** — orange  
- **N/Q/R/W** — yellow  
- **1/2/3** — red  
- **4/5/6** — green  
- **7** — purple  
- **S** — gray

**Multiple routes at one complex (same poll):**
- If `PRIORITIZE_LETTER_LINES=True`, **letter lines win** over number lines.
- Otherwise, a **stable tie-break** by route code is used.
- Mapping lives in `src/colors.py`.

---

# States (solid / incoming / departing)

Per poll we classify each station:

- **SOLID** — at least one train `STOPPED_AT` (or still within `HOLD_TICKS` grace).
- **INCOMING** — first seen after being absent last tick → **blink** for `BLINK_TICKS`.
- **DEPARTING** — was stopped last tick, now gone → **pulse** for `PULSE_TICKS`.
- **IDLE** — no train; off unless still inside `HOLD_TICKS`.

**Example (TEST mode):**


# Colors & Priority

Approx MTA branding:

- **A/C/E** — blue  
- **B/D/F/M** — orange  
- **N/Q/R/W** — yellow  
- **1/2/3** — red  
- **4/5/6** — green  
- **7** — purple  
- **S** — gray

**Multiple routes at one complex (same poll):**
- If `PRIORITIZE_LETTER_LINES=True`, **letter lines win** over number lines.
- Otherwise, a **stable tie-break** by route code is used.
- Mapping lives in `src/colors.py`.

---

# States (solid / incoming / departing)

Per poll we classify each station:

- **SOLID** — at least one train `STOPPED_AT` (or still within `HOLD_TICKS` grace).
- **INCOMING** — first seen after being absent last tick → **blink** for `BLINK_TICKS`.
- **DEPARTING** — was stopped last tick, now gone → **pulse** for `PULSE_TICKS`.
- **IDLE** — no train; off unless still inside `HOLD_TICKS`.

**Example (TEST mode):**
polled in 62.4 ms | occupied=275 | solid=6 blink=0 pulse=6


Small `SOLID` counts are normal off-peak; `PULSE` often appears right after a departure.

---

# Serial Frame Format (PC → ESP32)

Binary message per tick:

[0xAA 0x55] # header
[u16 count] # number of station payloads (LE)
repeat count times:
    [u16 led_index] # target LED
    [u8 state] # 0=OFF, 1=SOLID, 2=BLINK, 3=PULSE
    [u8 r][u8 g][u8 b] # color 0..255
[u8 checksum] # sum of all bytes mod 256 (including header)


**ESP32 steps:**
1. Find `0xAA 0x55`.  
2. Read `count`, then `count` payloads.  
3. Verify checksum.  
4. Update LED buffer; perform **blink/pulse locally** for smooth animation.

---

# CLI
```bash
python -m src.app [options]
```

**Options**
- `--layout PATH` Layout CSV (default: `data/default_layout.csv`)
- `--mode {test,serial}` `test`=console preview, `serial`=USB to ESP32
- `--backend {async,threads}` `async` (HTTP/2, httpx) or `threads` (requests)
- `--poll-ms INT` Poll cadence in ms (default from config)
- `--one-shot` Fetch once and exit
- `--verbose` Extra logs

**Examples**
```bash
Fastest, HTTP/2 asyncio:
python -m src.app --mode test --backend async

Serial to ESP32, every 500 ms:
python -m src.app --mode serial --backend async --poll-ms 500

One-shot snapshot (debug):
python -m src.app --one-shot --mode test
```
---

# Power & LED Notes

- **12 mm** bullet pixels can draw **~60 mA** each at 5 V on full white.  
  450 LEDs worst-case ≈ **27 A**. Real usage is lower (route colors, partial on).
- Inject power every **50–75** nodes and use adequate wire gauge + fusing.
- **8 mm** nodes work identically; just ensure your **layout CSV** reflects the physical order and count.

---

# Excluding Regions (e.g., far-north Bronx)

Do this via the **layout CSV**. To trim, remove those rows.  
(If you want an auto-trim script by latitude/borough, open an issue and we’ll include it.)

---