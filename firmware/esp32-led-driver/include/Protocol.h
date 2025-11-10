#pragma once
#include <Arduino.h>

// Binary frame from host (little-endian):
// [0xAA 0x55]                   (2 bytes header)
// [u16 count]                   (2 bytes, number of payloads)
// repeat 'count' times:
//   [u16 led_index]             (2 bytes)
//   [u8 state]                  (1 byte)  0=OFF, 1=SOLID, 2=BLINK, 3=PULSE
//   [u8 r][u8 g][u8 b]          (3 bytes)
// [u8 checksum]                 (1 byte) sum of ALL bytes incl header modulo 256

enum LedState : uint8_t {
  ST_OFF   = 0,
  ST_SOLID = 1,
  ST_BLINK = 2,
  ST_PULSE = 3
};

struct __attribute__((packed)) Payload {
  uint16_t led_index; // LE
  uint8_t  state;
  uint8_t  r, g, b;
};

struct __attribute__((packed)) FrameHeader {
  uint8_t a;   // 0xAA
  uint8_t b;   // 0x55
  uint16_t count; // LE
};
