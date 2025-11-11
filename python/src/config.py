import os
from enum import IntEnum

# Feed list
FEEDS = [
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",  # 1/2/3/4/5/6/7/S
]

# API key is optional (MTA feeds work without authentication)
API_KEY = os.getenv("MTA_API_KEY")

# Timeouts
TIMEOUT_CONNECT = 1.5
TIMEOUT_READ = 4.0

# Feed caching (in seconds)
# MTA updates feeds approximately every 30 seconds
# Lower values = more responsive but higher server load
# Higher values = less server load but slower updates
FEED_CACHE_SECONDS = 5

# LED modes
class LEDMode(IntEnum):
    OFF = 0
    SOLID = 1
    BLINK = 2
    PULSE = 3

# Legacy constants for backward compatibility
MODE_OFF = LEDMode.OFF
MODE_SOLID = LEDMode.SOLID
MODE_BLINK = LEDMode.BLINK
MODE_PULSE = LEDMode.PULSE
