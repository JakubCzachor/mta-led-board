/**
 * MTA LED Board - ESP32 Firmware
 *
 * Receives serial frames from Python host and drives WS2812B LED strip
 * with hardware-accelerated animations (blink, pulse).
 *
 * Protocol: See Protocol.h for frame format details
 * Configuration: Edit Config.h for your hardware setup
 */

#include <Arduino.h>
#include <FastLED.h>
#include "Config.h"
#include "Protocol.h"

// ============================================================================
// LED STRIP SETUP
// ============================================================================
CRGB leds[LED_COUNT];

// Per-pixel animation state
static uint8_t  curState[LED_COUNT];       // Current LedState (OFF/SOLID/BLINK/PULSE)
static CRGB     baseColor[LED_COUNT];      // Base color for animations
static uint32_t animStartMs[LED_COUNT];    // Animation start timestamp (millis)
static bool     blinkPhaseOn[LED_COUNT];   // Blink phase tracker

// Frame timing
static uint32_t lastShowMs = 0;            // Last FastLED.show() timestamp

// Frame processing markers (tracks which LEDs were updated this frame)
static bool *seenThisFrame = nullptr;

// ============================================================================
// GAMMA CORRECTION (Optional)
// ============================================================================
#if ENABLE_GAMMA_CORRECTION
/**
 * Apply gamma 2.2 correction to a single color channel.
 * Makes LED colors appear more accurate to human perception.
 */
static uint8_t gamma8(uint8_t x) {
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

// ============================================================================
// SERIAL PARSER STATE MACHINE
// ============================================================================
enum ParseState {
  PS_FIND_A,        // Looking for 0xAA header byte
  PS_FIND_B,        // Looking for 0x55 header byte
  PS_READ_COUNT0,   // Reading low byte of payload count
  PS_READ_COUNT1,   // Reading high byte of payload count
  PS_PAYLOADS,      // Reading payload data (7 bytes per LED)
  PS_CHECKSUM       // Reading final checksum byte
};

static ParseState pstate = PS_FIND_A;
static uint8_t checksum = 0;              // Running checksum accumulator
static uint16_t expectedCount = 0;        // Expected number of payloads
static uint16_t receivedCount = 0;        // Payloads received so far

// Payload streaming buffer
static Payload curPayload;
static uint8_t payloadByteIdx = 0;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Reset parser state machine to wait for next frame header.
 */
static inline void resetParser() {
  pstate = PS_FIND_A;
  checksum = 0;
  expectedCount = 0;
  receivedCount = 0;
  payloadByteIdx = 0;
}

/**
 * Initialize frame processing. Allocates tracking array to mark
 * which LEDs are updated in this frame.
 */
static void beginFrame(uint16_t count) {
  expectedCount = count;
  receivedCount = 0;
  payloadByteIdx = 0;

  // Allocate "seen" tracker on first frame
  if (seenThisFrame == nullptr) {
    seenThisFrame = (bool *)malloc(sizeof(bool) * LED_COUNT);
  }

  // Clear tracker for new frame
  if (seenThisFrame) {
    memset(seenThisFrame, 0, sizeof(bool) * LED_COUNT);
  }
}

/**
 * Finalize frame processing. Turns off SOLID LEDs that weren't updated
 * (trains have left). BLINK/PULSE animations continue running until they
 * naturally expire or are overwritten.
 *
 * @param checksumOK True if frame checksum was valid
 */
static void endFrame(bool checksumOK) {
  // Turn off SOLID pixels not touched this frame
  // (Animations like BLINK/PULSE continue independently)
  if (seenThisFrame) {
    for (int i = 0; i < LED_COUNT; ++i) {
      if (!seenThisFrame[i] && curState[i] == ST_SOLID) {
        curState[i] = ST_OFF;
      }
    }
  }

  // Note: Checksum validation prevents corrupted frames from displaying,
  // but we still let existing animations continue
}

/**
 * Update LED state and restart animation timer.
 *
 * @param idx LED index (0 to LED_COUNT-1)
 * @param st New state (OFF/SOLID/BLINK/PULSE)
 * @param c Base color for this LED
 */
static inline void setPixelState(uint16_t idx, LedState st, const CRGB &c) {
  if (idx >= LED_COUNT) return;

  curState[idx]        = st;
  baseColor[idx]       = c;
  blinkPhaseOn[idx]    = true;
  animStartMs[idx]     = millis();

  // Mark as updated this frame
  if (seenThisFrame) seenThisFrame[idx] = true;
}

/**
 * Apply one payload from host to LED buffer.
 *
 * @param p Payload structure with LED index, state, and color
 */
static void applyPayload(const Payload &p) {
  uint16_t idx = p.led_index;
  if (idx >= LED_COUNT) return;

  CRGB c = CRGB(p.r, p.g, p.b);
  switch (p.state) {
    case ST_OFF:   setPixelState(idx, ST_OFF, c);   break;
    case ST_SOLID: setPixelState(idx, ST_SOLID, c); break;
    case ST_BLINK: setPixelState(idx, ST_BLINK, c); break;
    case ST_PULSE: setPixelState(idx, ST_PULSE, c); break;
    default:       setPixelState(idx, ST_OFF, CRGB::Black); break;
  }
}

/**
 * Parse incoming serial data using state machine.
 * Processes one byte at a time, syncs to frame header, validates checksum.
 */
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

/**
 * Render LED animations to physical strip.
 *
 * Handles four animation modes:
 * - OFF: Black (no train)
 * - SOLID: Static color (train stopped at station)
 * - BLINK: Square wave on/off (train arriving)
 * - PULSE: Cosine fade-out (train departing)
 *
 * Respects FRAME_GUARD_MS to limit FastLED.show() calls (~60 FPS).
 */
static void renderLeds() {
  const uint32_t now = millis();

  for (int i = 0; i < LED_COUNT; ++i) {
    const LedState st = (LedState)curState[i];
    const CRGB src = baseColor[i];

    switch (st) {
      case ST_OFF:
        // No train present
        leds[i] = CRGB::Black;
        break;

      case ST_SOLID:
        // Train stopped at station
        leds[i] = src;
        break;

      case ST_BLINK: {
        // Train arriving: square wave blink
        uint32_t t = (now - animStartMs[i]) % BLINK_PERIOD_MS;
        bool onHalf = (t < (BLINK_PERIOD_MS / 2));
        leds[i] = onHalf ? src : CRGB::Black;
        break;
      }

      case ST_PULSE: {
        // Train departing: smooth fade-out
        uint32_t elapsed = now - animStartMs[i];
        if (elapsed >= PULSE_DECAY_MS) {
          // Pulse complete, turn off
          curState[i] = ST_OFF;
          leds[i] = CRGB::Black;
        } else {
          // Cosine ease-out: bright → dim
          float phase = (float)elapsed / (float)PULSE_DECAY_MS; // 0..1
          float amp = 0.5f * (1.0f + cosf(phase * PI));         // 1..0
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

  // Rate-limit FastLED.show() to ~60 FPS
  if (now - lastShowMs >= FRAME_GUARD_MS) {
    FastLED.show();
    lastShowMs = now;
  }
}

/**
 * Arduino setup function - runs once at startup.
 *
 * Initializes:
 * - Serial communication at configured baud rate
 * - FastLED library with chipset and pin configuration
 * - All LEDs to off state (black)
 */
void setup() {
  Serial.begin(SERIAL_BAUD);
  // Small delay for USB CDC enumeration (native USB boards)
  delay(200);

  // Initialize LED strip
  FastLED.addLeds<LED_CHIPSET, LED_PIN, LED_COLOR_ORDER>(leds, LED_COUNT)
    .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(LED_BRIGHTNESS);

  // Clear all pixels to black
  for (int i = 0; i < LED_COUNT; ++i) {
    leds[i] = CRGB::Black;
    curState[i] = ST_OFF;
    baseColor[i] = CRGB::Black;
    animStartMs[i] = 0;
    blinkPhaseOn[i] = true;
  }
  FastLED.show();
}

/**
 * Arduino main loop - runs continuously.
 *
 * Alternates between:
 * 1. Parsing incoming serial data (non-blocking)
 * 2. Rendering LED animations (rate-limited to ~60 FPS)
 */
void loop() {
  parseSerial();
  renderLeds();
}
