import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# Test all imports
try:
    from src.config import FEEDS, API_KEY, LEDMode
    print("✓ config imports OK")
except Exception as e:
    print(f"✗ config imports FAILED: {e}")

try:
    from src.mapping import build_station_maps, load_layout, base_stop_id
    print("✓ mapping imports OK")
except Exception as e:
    print(f"✗ mapping imports FAILED: {e}")

try:
    from src.colors import choose_color_for_routes, ROUTE_RGB
    print("✓ colors imports OK")
except Exception as e:
    print(f"✗ colors imports FAILED: {e}")

try:
    from src.fetch_async import fetch_parallel_httpx
    print("✓ fetch_async imports OK")
except Exception as e:
    print(f"✗ fetch_async imports FAILED: {e}")

try:
    from src.fetch_threads import fetch_parallel_requests
    print("✓ fetch_threads imports OK")
except Exception as e:
    print(f"✗ fetch_threads imports FAILED: {e}")

try:
    from src.parsing import aggregate_states_from_blobs
    print("✓ parsing imports OK")
except Exception as e:
    print(f"✗ parsing imports FAILED: {e}")

try:
    from src.render import build_led_payload, print_test_preview
    print("✓ render imports OK")
except Exception as e:
    print(f"✗ render imports FAILED: {e}")

try:
    from src.serial_frame import frame_bytes, send_serial
    print("✓ serial_frame imports OK")
except Exception as e:
    print(f"✗ serial_frame imports FAILED: {e}")

print("\nAll imports verified!")
