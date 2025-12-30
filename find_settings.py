"""
Comprehensive settings finder for Nibe Fighter 360P
Tests multiple baud rates, parity modes, AND checks for inverted data
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
TEST_DURATION = 5  # seconds per test

# Test configurations
CONFIGS = [
    (9600, serial.PARITY_NONE, "9600-NONE"),
    (9600, serial.PARITY_EVEN, "9600-EVEN"),
    (9600, serial.PARITY_ODD, "9600-ODD"),
    (4800, serial.PARITY_NONE, "4800-NONE"),
    (4800, serial.PARITY_EVEN, "4800-EVEN"),
    (19200, serial.PARITY_NONE, "19200-NONE"),
    (19200, serial.PARITY_EVEN, "19200-EVEN"),
]

# Look for these bytes (0x5C = F-series start, 0xC0 = our expected start)
TARGET_BYTES = [0x5C, 0xC0, 0x5A, 0x69, 0x68, 0x6D]  # Added more protocol bytes


def analyze_buffer(buffer, config_name):
    """Analyze buffer for start bytes in both normal and inverted form"""

    # Check normal data
    results = {
        "config": config_name,
        "bytes": len(buffer),
        "rate": len(buffer) / TEST_DURATION,
        "found": [],
    }

    for target in TARGET_BYTES:
        count = buffer.count(target)
        if count > 0:
            results["found"].append(f"0x{target:02X}={count}")

    # Check inverted data (XOR with 0xFF)
    inverted = bytearray([b ^ 0xFF for b in buffer])
    inverted_found = []

    for target in TARGET_BYTES:
        count = inverted.count(target)
        if count > 0:
            inverted_found.append(f"0x{target:02X}={count}")

    if inverted_found:
        results["inverted_found"] = inverted_found

    return results


print("=" * 70)
print("COMPREHENSIVE SETTINGS FINDER")
print("=" * 70)
print(f"Testing {len(CONFIGS)} configurations ({TEST_DURATION}s each)")
print(f"Looking for: {', '.join([f'0x{b:02X}' for b in TARGET_BYTES])}")
print("Also checking INVERTED data (RS485 polarity issue)\n")

all_results = []

for baudrate, parity, name in CONFIGS:
    print(f"Testing {name}...", end=" ", flush=True)

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=parity,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        buffer = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < TEST_DURATION:
            data = ser.read(100)
            if data:
                buffer.extend(data)

        ser.close()

        result = analyze_buffer(buffer, name)
        all_results.append(result)

        # Show immediate feedback
        if result["found"]:
            print(f"✓ FOUND: {', '.join(result['found'])}")
        elif result.get("inverted_found"):
            print(f"⚠ INVERTED: {', '.join(result['inverted_found'])}")
        else:
            print(f"✗ ({result['bytes']} bytes)")

    except Exception as e:
        print(f"ERROR: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

# Find best matches
best_normal = [r for r in all_results if r["found"]]
best_inverted = [r for r in all_results if r.get("inverted_found")]

if best_normal:
    print("\n✓ NORMAL DATA - Promising configurations:")
    for r in best_normal:
        print(f"  {r['config']:15} - {r['bytes']} bytes, {r['rate']:.1f} B/s")
        print(f"                  Found: {', '.join(r['found'])}")

if best_inverted:
    print("\n⚠ INVERTED DATA - A/B lines may be swapped in adapter:")
    for r in best_inverted:
        print(f"  {r['config']:15} - {r['bytes']} bytes, {r['rate']:.1f} B/s")
        print(
            f"                  Found (after inverting): {', '.join(r['inverted_found'])}"
        )
    print("\n  FIX: Your USB-RS485 adapter may have A/B backwards.")
    print("       This is a SOFTWARE fix - we can invert data in Python.")

if not best_normal and not best_inverted:
    print("\n✗ NO START BYTES FOUND in any configuration!")
    print("\nPossible issues:")
    print("  1. Fighter 360P uses non-standard protocol/baud rate")
    print("  2. Pump is in a special mode or not fully initialized")
    print("  3. Physical connection issue (check 12V power to pump?)")
    print("  4. Try enabling Modbus in pump menu (see nibepi README)")

    # Show which config got most data
    if all_results:
        best_data = max(all_results, key=lambda r: r["bytes"])
        print(
            f"\n  Most data received at: {best_data['config']} ({best_data['bytes']} bytes)"
        )
        print(f"  This might be closest to correct baud rate.")

print("\n" + "=" * 70)
