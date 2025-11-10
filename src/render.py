from typing import Dict, Set, List, Tuple
from src.colors import choose_color_for_routes
from src.config import MODE_SOLID, MODE_BLINK, MODE_PULSE

def build_led_payload(
    routes_by_station: Dict[str, Set[str]],
    mode_by_station: Dict[str, int],
    layout: Dict[str, int],
) -> List[Tuple[int,int,int,int,int]]:
    out: List[Tuple[int,int,int,int,int]] = []
    for sk, mode in mode_by_station.items():
        if sk not in layout: continue
        idx = layout[sk]
        r,g,b = choose_color_for_routes(routes_by_station.get(sk, set()))
        out.append((idx, mode, r, g, b))
    out.sort(key=lambda t: t[0])
    return out

def print_test_preview(
    t_ms: float,
    name_map,
    layout,
    routes_by_station,
    mode_by_station,
):
    solid, blink, pulse = [], [], []
    for sk, mode in mode_by_station.items():
        nm = name_map.get(sk, sk)
        if mode == MODE_SOLID: solid.append(nm)
        elif mode == MODE_BLINK: blink.append(nm)
        elif mode == MODE_PULSE: pulse.append(nm)
    for lst in (solid, blink, pulse): lst.sort()
    print("------------------------------------------------------------")
    print("TEST MODE — LED preview")
    print(f"polled in {t_ms:.1f} ms | occupied={len(mode_by_station)} | "
          f"solid={len(solid)} blink={len(blink)} pulse={len(pulse)}")
    if solid: print("  SOLID :", ", ".join(solid[:12]) + (", ..." if len(solid) > 12 else ""))
    if blink: print("  BLINK :", ", ".join(blink[:12]) + (", ..." if len(blink) > 12 else ""))
    if pulse: print("  PULSE :", ", ".join(pulse[:12]) + (", ..." if len(pulse) > 12 else ""))
    print("------------------------------------------------------------")
