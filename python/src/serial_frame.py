from typing import List, Tuple
import struct
import logging

logger = logging.getLogger(__name__)

# Serial frame format constants (must match ESP32 Protocol.h)
FRAME_HEADER_A = 0xAA
FRAME_HEADER_B = 0x55


def simple_checksum(data: bytes) -> int:
    """Calculate simple checksum (sum of all bytes modulo 256).

    This matches the ESP32 firmware checksum implementation.
    Used to verify data integrity in serial frames.

    Args:
        data: Bytes to checksum

    Returns:
        8-bit checksum value (0-255)
    """
    return sum(data) & 0xFF


def frame_bytes(pairs: List[Tuple[int, int, int, int, int]]) -> bytes:
    """Build binary frame for serial transmission to ESP32.

    Frame format (matches ESP32 Protocol.h):
        [2 bytes] 0xAA 0x55 (header)
        [2 bytes] count of station payloads (little-endian)
        [N×7 bytes] station payloads:
            [2 bytes] LED index (little-endian)
            [1 byte]  LED mode (0=off, 1=solid, 2=blink, 3=pulse)
            [3 bytes] RGB color
        [1 byte]  checksum (sum of all bytes modulo 256)

    Args:
        pairs: List of (led_index, mode, r, g, b) tuples

    Returns:
        Binary frame ready for serial transmission
    """
    hdr = bytearray()
    hdr.append(FRAME_HEADER_A)
    hdr.append(FRAME_HEADER_B)
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
    checksum = simple_checksum(data)
    frame = data + bytes([checksum])

    logger.debug(f"Built frame: {len(frame)} bytes, {len(pairs)} stations, checksum=0x{checksum:02X}")
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
