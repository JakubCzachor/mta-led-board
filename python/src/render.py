from typing import Dict, Set, List, Tuple
import logging

try:
    from .colors import choose_color_for_routes
    from .config import MODE_SOLID, MODE_BLINK, MODE_PULSE
except ImportError:
    from src.colors import choose_color_for_routes
    from src.config import MODE_SOLID, MODE_BLINK, MODE_PULSE

logger = logging.getLogger(__name__)


def build_led_payload(
    routes_by_station: Dict[str, Set[str]],
    mode_by_station: Dict[str, int],
    layout: Dict[str, int],
) -> List[Tuple[int, int, int, int, int]]:
    """Build LED frame payload from station states.

    For each station in the layout, determine the color (from its routes)
    and mode (solid/blink/pulse), then return as list of tuples ready
    for serial framing.

    Args:
        routes_by_station: Map of station key → active route IDs
        mode_by_station: Map of station key → LED mode
        layout: Map of station key → LED index (position on strip)

    Returns:
        List of (led_index, mode, r, g, b) tuples, sorted by index
    """
    out: List[Tuple[int, int, int, int, int]] = []

    for sk, mode in mode_by_station.items():
        if sk not in layout:
            continue

        idx = layout[sk]
        r, g, b = choose_color_for_routes(routes_by_station.get(sk, set()))
        out.append((idx, mode, r, g, b))

    out.sort(key=lambda t: t[0])
    logger.debug(f"Built LED payload with {len(out)} active stations")
    return out


def print_test_preview(
    t_ms: float,
    name_map: Dict[str, str],
    layout: Dict[str, int],
    routes_by_station: Dict[str, Set[str]],
    mode_by_station: Dict[str, int],
) -> None:
    """Print human-readable preview of LED states (for --test mode).

    Categorizes stations by LED mode and prints them grouped.

    Args:
        t_ms: Time taken to poll in milliseconds
        name_map: Map of station key → display name
        layout: Map of station key → LED index
        routes_by_station: Map of station key → route IDs
        mode_by_station: Map of station key → LED mode
    """
    solid, blink, pulse = [], [], []

    for sk, mode in mode_by_station.items():
        nm = name_map.get(sk, sk)
        if mode == MODE_SOLID:
            solid.append(nm)
        elif mode == MODE_BLINK:
            blink.append(nm)
        elif mode == MODE_PULSE:
            pulse.append(nm)

    for lst in (solid, blink, pulse):
        lst.sort()

    # Format output
    print("------------------------------------------------------------")
    print("TEST MODE — LED preview")
    print(
        f"polled in {t_ms:.1f} ms | occupied={len(mode_by_station)} | "
        f"solid={len(solid)} blink={len(blink)} pulse={len(pulse)}"
    )
    if solid:
        solid_str = ", ".join(solid[:12]) + (", ..." if len(solid) > 12 else "")
        print(f"  SOLID : {solid_str}")
    if blink:
        blink_str = ", ".join(blink[:12]) + (", ..." if len(blink) > 12 else "")
        print(f"  BLINK : {blink_str}")
    if pulse:
        pulse_str = ", ".join(pulse[:12]) + (", ..." if len(pulse) > 12 else "")
        print(f"  PULSE : {pulse_str}")
    print("------------------------------------------------------------")
