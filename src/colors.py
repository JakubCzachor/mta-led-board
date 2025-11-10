from typing import Dict, Tuple, Iterable

ROUTE_RGB: Dict[str, Tuple[int, int, int]] = {
    "A": (0, 57, 166), "C": (0, 57, 166), "E": (0, 57, 166),
    "B": (255, 99, 25), "D": (255, 99, 25), "F": (255, 99, 25), "M": (255, 99, 25),
    "G": (108, 190, 69),
    "J": (163, 130, 78), "Z": (163, 130, 78),
    "L": (167, 169, 172),
    "N": (252, 204, 10), "Q": (252, 204, 10), "R": (252, 204, 10), "W": (252, 204, 10),
    "1": (238, 53, 46), "2": (238, 53, 46), "3": (238, 53, 46),
    "4": (0, 147, 60), "5": (0, 147, 60), "6": (0, 147, 60),
    "7": (185, 51, 173),
    "S": (155, 155, 155), "FS": (155, 155, 155),
    "H": (0, 57, 166),
    "SI": (0, 57, 166),
}

LETTER_PRIORITY = ["A","B","C","D","E","F","G","J","L","M","N","Q","R","W","Z"]
DIGIT_PRIORITY  = [str(i) for i in range(1,8)]
TAIL_PRIORITY   = ["S","FS","H","SI"]

def choose_color_for_routes(routes: Iterable[str]) -> Tuple[int, int, int]:
    uniq = [r for r in { (r or "").strip().upper() for r in routes } if r]
    if not uniq:
        return (80, 80, 80)
    for code in LETTER_PRIORITY:
        if code in uniq: return ROUTE_RGB.get(code, (80,80,80))
    for code in DIGIT_PRIORITY:
        if code in uniq: return ROUTE_RGB.get(code, (80,80,80))
    for code in TAIL_PRIORITY:
        if code in uniq: return ROUTE_RGB.get(code, (80,80,80))
    for r in uniq:
        if r in ROUTE_RGB: return ROUTE_RGB[r]
    return (80, 80, 80)
