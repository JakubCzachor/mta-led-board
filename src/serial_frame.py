from typing import List, Tuple
import struct

def crc16_ccitt(data: bytes, poly=0x1021, init=0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)
    return crc

def frame_bytes(pairs: List[Tuple[int,int,int,int,int]], version: int = 1) -> bytes:
    hdr = bytearray()
    hdr.append(0xAA)
    hdr.append(version & 0xFF)
    hdr += struct.pack("<H", len(pairs))
    body = bytearray()
    for idx, mode, r, g, b in pairs:
        body += struct.pack("<HBBBB", idx & 0xFFFF, mode & 0xFF, r & 0xFF, g & 0xFF, b & 0xFF)
    data = bytes(hdr + body)
    crc = crc16_ccitt(data)
    return data + struct.pack("<H", crc)

def send_serial(port: str, baud: int, payload: bytes):
    try:
        import serial  # lazy import
    except Exception:
        print("[WARN] pyserial not installed; run in --test or install pyserial.")
        return
    with serial.Serial(port=port, baudrate=baud, timeout=0) as ser:
        ser.write(payload)
        ser.flush()
