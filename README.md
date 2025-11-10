# MTA LED Board

Real-time NYC Subway visualization on a physical LED map. This Python application fetches live train positions via GTFS-realtime, maps them to station complexes, and displays route colors on an LED strip controlled by an ESP32. Features include parallel data fetching, anti-flicker sticky states, and a test mode for hardware-free development.

---

## Features

- **Parallel data fetching** — Async HTTP/2 or threaded requests with protobuf parsing
- **Smart station mapping** — Handles complex IDs, stop suffixes, and parent stations
- **Route color priority** — Configurable precedence for mixed-route stations
- **Anti-flicker states** — Sticky hold/pulse/blink timing reduces LED jitter
- **CSV-driven layout** — Easily customize which stations to display
- **Dual-mode operation** — USB serial output to ESP32 or console test preview
- **Flexible LED support** — Works with 8mm or 12mm pixel strips

---

## Project Structure

```
project/
├─ python/
│  ├─ data/
│  │  ├─ stops.txt           # MTA GTFS static stops
│  │  ├─ stations.csv        # Station complex mappings
│  │  └─ default_layout.csv  # LED index assignments
│  └─ src/
│     ├─ app.py              # CLI entrypoint
│     ├─ config.py           # Configuration (feeds, timings)
│     ├─ fetch_async.py      # HTTP/2 async fetcher
│     ├─ fetch_threads.py    # Threaded fallback fetcher
│     ├─ mapping.py          # Station/complex mapping logic
│     ├─ parsing.py          # GTFS protobuf parser
│     ├─ render.py           # LED rendering logic
│     └─ serial_frame.py     # Binary protocol encoder
└─ firmware/
   └─ esp32-led-driver/
      ├─ include/
      │  ├─ Config.h         # Hardware configuration
      │  └─ Protocol.h       # Serial protocol definitions
      ├─ src/
      │  └─ main.cpp         # ESP32 firmware (FastLED)
      └─ platformio.ini      # PlatformIO build config
```

---

## Installation

**Requirements:**
- Python 3.10+
- ESP32 microcontroller (optional, for hardware mode)

**Setup:**

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies

pip install -r requirements.txt
```

## Quick Start

**Test mode** (no hardware required):
```bash
python -m python.src.app --layout python/data/default_layout.csv --test
```

Example output:
```
TEST MODE — LED preview
polled in 60.8 ms | occupied=275 | solid=6 blink=0 pulse=6
  SOLID : 14 St-Union Sq, 34 St-Herald Sq, ...
  PULSE : Grand Central-42 St, Queensboro Plaza, ...
```

**Hardware mode** (with ESP32):

1. **Flash ESP32 firmware** (see [Firmware Setup](#firmware-setup) below)
2. **Find serial port:**
   - Windows: `COM5` (Device Manager)
   - macOS: `/dev/tty.usbserial-*`
   - Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
3. **Configure** [python/src/config.py](python/src/config.py):
   ```python
   SERIAL_PORT = "COM5"
   BAUD = 115200
   ```
4. **Run:**
   ```bash
   python -m python.src.app --layout python/data/default_layout.csv --serial-port COM5
   ```

## Configuration

Edit [python/src/config.py](python/src/config.py) to customize behavior:

**Data sources:**
```python
FEEDS = [...]  # MTA GTFS-realtime feed URLs (A/C/E, B/D/F/M, etc.)
HTTP_TIMEOUT = (1.5, 4.0)  # Connection and read timeout
```

**Timing:**
```python
POLL_MS = 500        # Refresh rate in milliseconds
HOLD_TICKS = 3       # Frames to hold color after train leaves
PULSE_TICKS = 2      # Frames to pulse on departure
BLINK_TICKS = 2      # Frames to blink on arrival
```

**Display:**
```python
PRIORITIZE_LETTER_LINES = True  # Letter routes win over numbers
BRIGHTNESS = 255                # LED brightness (0-255)
```

### Route Colors

MTA route colors (defined in [python/src/colors.py](python/src/colors.py)):
- **A/C/E** — Blue
- **B/D/F/M** — Orange
- **N/Q/R/W** — Yellow
- **1/2/3** — Red
- **4/5/6** — Green
- **7** — Purple
- **S** — Gray

When multiple routes occupy the same station, letter lines take precedence (if `PRIORITIZE_LETTER_LINES=True`).

### LED States

Each poll cycle assigns one of four states to each station:
- **SOLID** — Train stopped at station (or held briefly after departure)
- **BLINK** — Train arriving (first appearance)
- **PULSE** — Train departing (just left)
- **OFF** — No train present

## Serial Protocol

Binary frame format sent to ESP32:

```
[0xAA 0x55]           # Frame header (2 bytes)
[u16 count]           # Number of LED updates (little-endian)
# Repeat 'count' times:
  [u16 led_index]     # LED position (little-endian)
  [u8 state]          # 0=OFF, 1=SOLID, 2=BLINK, 3=PULSE
  [u8 r][u8 g][u8 b]  # RGB color (0-255)
[u8 checksum]         # Sum of all bytes mod 256 (includes header)
```

**Example frame** (2 LEDs):
```
AA 55          # Header
02 00          # Count = 2 LEDs
05 00 01 FF 00 00  # LED 5: SOLID, Red (255,0,0)
0A 00 03 00 00 FF  # LED 10: PULSE, Blue (0,0,255)
B6             # Checksum
```

**ESP32 firmware behavior:**
1. Sync to `0xAA 0x55` header
2. Read count and payloads
3. Verify checksum (reject frame if mismatch)
4. Update LED buffer and animate locally (blink/pulse handled on-device)

## CLI Usage
```bash
python -m python.src.app [options]
```

**Options:**
- `--layout PATH` Layout CSV file (default: `python/data/default_layout.csv`)
- `--test` Test mode (console output instead of serial)
- `--serial-port PORT` Serial port for ESP32 (e.g., `COM5`, `/dev/ttyUSB0`)
- `--baud RATE` Baud rate (default: 2000000)
- `--httpx` Use httpx backend with HTTP/2 (default)
- `--no-httpx` Use requests backend with HTTP/1.1 (fallback)
- `--poll SECONDS` Poll interval in seconds (default: 1.0)
- `--verbose` Enable detailed logging

**Examples:**
```bash
# Test mode with HTTP/2 (default)
python -m python.src.app --test --verbose

# Hardware mode with 0.5s refresh
python -m python.src.app --serial-port COM5 --poll 0.5

# Use HTTP/1.1 fallback
python -m python.src.app --test --no-httpx
```

## Hardware Considerations

**Power requirements:**
- 12mm pixels: ~60mA each at full brightness (5V)
- 450 LEDs max draw: ~27A (real-world usage is lower)
- Inject power every 50-75 LEDs with appropriate gauge wire

**Layout customization:**
- Edit `python/data/default_layout.csv` to exclude regions (e.g., Staten Island, far-north Bronx)
- Supports both 8mm and 12mm LED strips

---

## Firmware Setup

The ESP32 firmware receives serial frames from Python and drives the LED strip with hardware-accelerated animations.

### Prerequisites

- [PlatformIO](https://platformio.org/install) (VS Code extension or CLI)
- ESP32 development board (ESP32-DevKitC or similar)
- WS2812B LED strip (or compatible: WS2811, APA102, etc.)

### Hardware Configuration

Edit [firmware/esp32-led-driver/include/Config.h](firmware/esp32-led-driver/include/Config.h) to match your setup:

```cpp
// Serial communication
#define SERIAL_BAUD       2000000    // Must match Python --baud setting

// LED strip configuration
#define LED_COUNT         450        // Total number of LEDs
#define LED_PIN           5          // GPIO pin connected to LED data line
#define LED_CHIPSET       WS2812B    // Your LED chipset
#define LED_COLOR_ORDER   GRB        // Color order (GRB, RGB, BGR, etc.)
#define LED_BRIGHTNESS    255        // Global brightness (0-255)
```

### Flashing Firmware

**Using PlatformIO CLI:**
```bash
cd firmware/esp32-led-driver
pio run --target upload
```

**Using PlatformIO IDE (VS Code):**
1. Open `firmware/esp32-led-driver` folder in VS Code
2. Click "Upload" button in PlatformIO toolbar
3. Wait for compilation and upload to complete

**Verify installation:**
- ESP32 should clear all LEDs to black on startup
- Connect Python app with `--serial-port` to test

### Troubleshooting

- **Upload fails**: Check USB cable (must support data), try different port, hold BOOT button during upload
- **LEDs don't light**: Verify `LED_PIN`, `LED_CHIPSET`, and `LED_COLOR_ORDER` in Config.h
- **Wrong colors**: Try different `LED_COLOR_ORDER` values (GRB, RGB, BGR)
- **Serial errors**: Ensure `SERIAL_BAUD` matches Python `--baud` setting (default: 2000000)