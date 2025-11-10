#include <Arduino.h>
#include <FastLED.h>
#include "Config.h"
#include "Protocol.h"

// ---------------- LED setup ----------------
CRGB leds[LED_COUNT];

// Per-pixel runtime info
static uint8_t curState[LED_COUNT];        // LedState per pixel
static CRGB    baseColor[LED_COUNT];       // target color (solid/blink origin, pulse start color)
static uint32_t animStartMs[LED_COUNT];    // when BLINK/PULSE began
static bool     blinkPhaseOn[LED_COUNT];   // current phase for blink

// Frame bookkeeping
static uint32_t lastShowMs = 0;

// Temporary "seen this frame" markers
static bool *seenThisFrame = nullptr;

// ---------------- Optional gamma table ----------------
#if ENABLE_GAMMA_CORRECTION
static uint8_t gamma8(uint8_t x) {
  // Fast approximate gamma 2.2
  float xf = x / 255.0f;
  xf = powf(xf, 2.2f);
  int out = (int)(xf * 255.0f + 0.5f);
  if (out < 0) out = 0;
  if (out > 255) out = 255;
  return (uint8_t)out;
}
static CRGB gammaCorrect(const CRGB &c) {
  return CRGB(gamma8(c.r), gamma8(c.g), gamma8(c.b));
}
#else
static inline CRGB gammaCorrect(const CRGB &c) { return c; }
#endif

// ---------------- Serial parser state ----------------
enum ParseState {
  PS_FIND_A, PS_FIND_B, PS_READ_COUNT0, PS_READ_COUNT1,
  PS_PAYLOADS, PS_CHECKSUM
};

static ParseState pstate = PS_FIND_A;
static uint8_t checksum = 0;
static uint16_t expectedCount = 0;
static uint16_t receivedCount = 0;

// For streaming payload bytes
static Payload curPayload;
static uint8_t payloadByteIdx = 0;

// ---------------- Helpers ----------------
static inline void resetParser() {
  pstate = PS_FIND_A;
  checksum = 0;
  expectedCount = 0;
  receivedCount = 0;
  payloadByteIdx = 0;
}

static void beginFrame(uint16_t count) {
  expectedCount = count;
  receivedCount = 0;
  payloadByteIdx = 0;
  if (seenThisFrame == nullptr) {
    seenThisFrame = (bool *)malloc(sizeof(bool) * LED_COUNT);
  }
  if (seenThisFrame) {
    memset(seenThisFrame, 0, sizeof(bool) * LED_COUNT);
  }
}

static void endFrame(bool checksumOK) {
  // Turn off SOLID pixels not touched this frame (animations keep running)
  if (seenThisFrame) {
    for (int i = 0; i < LED_COUNT; ++i) {
      if (!seenThisFrame[i] && curState[i] == ST_SOLID) {
        curState[i] = ST_OFF;
      }
    }
  }

  // If checksum failed, we don't apply an immediate show(); let animations refresh
  if (checksumOK) {
    // We will render in the main loop tick respecting FRAME_GUARD_MS
  }
}

static inline void setPixelState(uint16_t idx, LedState st, const CRGB &c) {
  if (idx >= LED_COUNT) return;
  curState[idx]   = st;
  baseColor[idx]  = c;
  blinkPhaseOn[idx] = true;
  animStartMs[idx] = millis();
  if (seenThisFrame) seenThisFrame[idx] = true;
}

// Apply one payload from host
static void applyPayload(const Payload &p) {
  uint16_t idx = p.led_index;
  if (idx >= LED_COUNT) return;

  CRGB c = CRGB(p.r, p.g, p.b);
  switch (p.state) {
    case ST_OFF:   setPixelState(idx, ST_OFF, c); break;
    case ST_SOLID: setPixelState(idx, ST_SOLID, c); break;
    case ST_BLINK: setPixelState(idx, ST_BLINK, c); break;
    case ST_PULSE: setPixelState(idx, ST_PULSE, c); break;
    default:       setPixelState(idx, ST_OFF, CRGB::Black); break;
  }
}

// Stream bytes from Serial and parse frames
static void parseSerial() {
  while (Serial.available() > 0) {
    uint8_t b = (uint8_t)Serial.read();

    switch (pstate) {
      case PS_FIND_A:
        if (b == FRAME_HEADER_A) {
          pstate = PS_FIND_B;
          checksum = b;
        }
        break;

      case PS_FIND_B:
        if (b == FRAME_HEADER_B) {
          pstate = PS_READ_COUNT0;
          checksum = (checksum + b) & 0xFF;
        } else {
          // restart
          pstate = PS_FIND_A;
        }
        break;

      case PS_READ_COUNT0:
        expectedCount = b;          // low byte
        checksum = (checksum + b) & 0xFF;
        pstate = PS_READ_COUNT1;
        break;

      case PS_READ_COUNT1: {
        uint16_t hi = b;           // high byte
        checksum = (checksum + b) & 0xFF;
        expectedCount |= (hi << 8);

        if (expectedCount > MAX_PAYLOADS_PER_FRAME) {
          // absurd count, drop
          resetParser();
          break;
        }
        beginFrame(expectedCount);
        pstate = (expectedCount == 0) ? PS_CHECKSUM : PS_PAYLOADS;
        payloadByteIdx = 0;
        break;
      }

      case PS_PAYLOADS:
        // stream into curPayload
        ((uint8_t*)&curPayload)[payloadByteIdx++] = b;
        checksum = (checksum + b) & 0xFF;

        if (payloadByteIdx == sizeof(Payload)) {
          // LE: led_index already in little-endian byte order from host
          applyPayload(curPayload);
          receivedCount++;
          payloadByteIdx = 0;
          if (receivedCount >= expectedCount) {
            pstate = PS_CHECKSUM;
          }
        }
        break;

      case PS_CHECKSUM: {
        // Compare running checksum (includes header and payloads) to received checksum byte
        bool ok = (checksum == b);
        endFrame(ok);
        resetParser(); // ready for next frame
        break;
      }
    }
  }
}

// Render LEDs from current states
static void renderLeds() {
  const uint32_t now = millis();

  for (int i = 0; i < LED_COUNT; ++i) {
    const LedState st = (LedState)curState[i];
    const CRGB src = baseColor[i];

    switch (st) {
      case ST_OFF:
        leds[i] = CRGB::Black;
        break;

      case ST_SOLID:
        leds[i] = src;
        break;

      case ST_BLINK: {
        uint32_t t = (now - animStartMs[i]) % BLINK_PERIOD_MS;
        bool onHalf = (t < (BLINK_PERIOD_MS / 2));
        leds[i] = onHalf ? src : CRGB::Black;
        break;
      }

      case ST_PULSE: {
        uint32_t elapsed = now - animStartMs[i];
        if (elapsed >= PULSE_DECAY_MS) {
          // End of pulse: pixel goes OFF unless host refreshes it
          curState[i] = ST_OFF;
          leds[i] = CRGB::Black;
        } else {
          // Ease-out brightness (cosine)
          float phase = (float)elapsed / (float)PULSE_DECAY_MS; // 0..1
          float amp = 0.5f * (1.0f + cosf(phase * PI));         // 1..0 cosine
          uint8_t r = (uint8_t)(src.r * amp);
          uint8_t g = (uint8_t)(src.g * amp);
          uint8_t b = (uint8_t)(src.b * amp);
          leds[i] = CRGB(r, g, b);
        }
        break;
      }
    }

#if ENABLE_GAMMA_CORRECTION
    leds[i] = gammaCorrect(leds[i]);
#endif
  }

  if (now - lastShowMs >= FRAME_GUARD_MS) {
    FastLED.show();
    lastShowMs = now;
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  // Small delay for USB CDC enumeration
  delay(200);

  FastLED.addLeds<LED_CHIPSET, LED_PIN, LED_COLOR_ORDER>(leds, LED_COUNT).setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(LED_BRIGHTNESS);

  // Clear all pixels
  for (int i = 0; i < LED_COUNT; ++i) {
    leds[i] = CRGB::Black;
    curState[i] = ST_OFF;
    baseColor[i] = CRGB::Black;
    animStartMs[i] = 0;
    blinkPhaseOn[i] = true;
  }
  FastLED.show();
}

void loop() {
  parseSerial();
  renderLeds();
}
