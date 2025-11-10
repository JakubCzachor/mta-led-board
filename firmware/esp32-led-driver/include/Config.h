#pragma once

// ============================================================================
// HARDWARE CONFIGURATION
// ============================================================================

// Serial communication
#define SERIAL_BAUD       2000000    // Match Python default (2 Mbaud)

// LED strip configuration
#define LED_COUNT         450        // Total number of addressable LEDs
#define LED_PIN           5          // GPIO pin connected to LED data line
#define LED_CHIPSET       WS2812B    // LED chipset (WS2812B, WS2811, APA102, etc.)
#define LED_COLOR_ORDER   GRB        // Color order for your LED strip
#define LED_BRIGHTNESS    255        // Global brightness (0-255)

// ============================================================================
// PROTOCOL CONSTANTS
// ============================================================================

// Frame header bytes
#define FRAME_HEADER_A    0xAA
#define FRAME_HEADER_B    0x55

// Maximum payloads per frame (safety limit)
#define MAX_PAYLOADS_PER_FRAME  500

// ============================================================================
// ANIMATION TIMING
// ============================================================================

// Blink animation: full on/off cycle time
#define BLINK_PERIOD_MS   800        // 800ms = 0.4s on, 0.4s off

// Pulse animation: fade-out duration
#define PULSE_DECAY_MS    1000       // 1 second fade to black

// Frame rate limiting (prevents FastLED.show() spam)
#define FRAME_GUARD_MS    16         // ~60 FPS (1000ms / 60 = 16.67ms)

// ============================================================================
// OPTIONAL FEATURES
// ============================================================================

// Enable gamma correction for more accurate color representation
// Note: Increases CPU usage slightly
#define ENABLE_GAMMA_CORRECTION  0   // 0=disabled, 1=enabled
