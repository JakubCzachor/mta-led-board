from typing import List, Tuple
import struct
import logging

logger = logging.getLogger(__name__)

# Serial frame format constants
FRAME_HEADER = 0xAA
CRC_POLY = 0x1021  # CRC-16-CCITT polynomial
CRC_INIT = 0xFFFF  # Initial CRC value


def crc16_ccitt(data: bytes, poly: int = CRC_POLY, init: int = CRC_INIT) -> int:
    """Calculate CRC-16-CCITT checksum.

    This uses the CCITT polynomial (0x1021) with initial value 0xFFFF.
    Used to verify data integrity in serial frames.

    Args:
        data: Bytes to checksum
        poly: CRC polynomial (default 0x1021)
        init: Initial CRC value (default 0xFFFF)

    Returns:
        16-bit CRC value
    """
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)
    return crc


def frame_bytes(pairs: List[Tuple[int, int, int, int, int]], version: int = 1) -> bytes:
    """Build binary frame for serial transmission to ESP32.

    Frame format:
        [1 byte]  0xAA (header)
        [1 byte]  version number
        [2 bytes] count of station payloads (little-endian)
        [N×7 bytes] station payloads:
            [2 bytes] LED index
            [1 byte]  LED mode (0=off, 1=solid, 2=blink, 3=pulse)
            [3 bytes] RGB color
        [2 bytes] CRC-16-CCITT checksum

    Args:
        pairs: List of (led_index, mode, r, g, b) tuples
        version: Protocol version (default 1)

    Returns:
        Binary frame ready for serial transmission
    """
    hdr = bytearray()
    hdr.append(FRAME_HEADER)
    hdr.append(version & 0xFF)
    hdr += struct.pack("<H", len(pairs))

    body = bytearray()
    for idx, mode, r, g, b in pairs:
        body += struct.pack(
            "<HBBBB",
            idx & 0xFFFF,
            mode & 0xFF,
            r & 0xFF,
            g & 0xFF,
            b & 0xFF,
        )

    data = bytes(hdr + body)
    crc = crc16_ccitt(data)
    frame = data + struct.pack("<H", crc)

    logger.debug(f"Built frame: {len(frame)} bytes, {len(pairs)} stations, CRC={crc:04X}")
    return frame


def send_serial(port: str, baud: int, payload: bytes) -> None:
    """Send payload to ESP32 over serial.

    Args:
        port: Serial port name (e.g., "COM5", "/dev/ttyUSB0")
        baud: Baud rate (typically 115200 or 2000000)
        payload: Binary data to send

    Raises:
        RuntimeError: If pyserial not installed
        SerialException: If serial port cannot be opened
    """
    try:
        import serial  # Lazy import
    except ImportError:
        logger.error("pyserial not installed. Run: pip install pyserial")
        raise RuntimeError("pyserial required for serial mode")

    try:
        logger.debug(f"Opening serial port {port} at {baud} baud")
        with serial.Serial(port=port, baudrate=baud, timeout=1.0) as ser:
            ser.write(payload)
            ser.flush()
            logger.debug(f"Sent {len(payload)} bytes to {port}")
    except serial.SerialException as e:
        logger.error(f"Serial error on {port}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending to {port}: {e}")
        raise
