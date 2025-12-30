"""
Test HIGHER baud rates - the data volume suggests even faster
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"

# Test even higher baud rates
BAUD_RATES = [57600, 115200, 230400, 460800, 921600]

print("Testing HIGH baud rates")
print("=" * 70)
print("Looking for LOWER data volume (not flooded) with 0xC0 bytes\n")

for baudrate in BAUD_RATES:
    print(f"Testing {baudrate} baud...", end=" ", flush=True)

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        # Collect for 3 seconds
        start = time.time()
        buffer = bytearray()

        while (time.time() - start) < 3.0:
            data = ser.read(100)
            if data:
                buffer.extend(data)

        ser.close()

        c0_count = buffer.count(0xC0)
        bytes_per_sec = len(buffer) / 3.0

        print(
            f"{len(buffer):6d} bytes ({bytes_per_sec:6.0f} B/s), {c0_count:3d} x 0xC0",
            end="",
        )

        # Theoretical max bytes/sec for this baud rate
        # Formula: baudrate / 10 (assuming 8N1 = 10 bits per byte)
        theoretical_max = baudrate / 10.0
        usage_percent = (bytes_per_sec / theoretical_max) * 100

        print(f" - {usage_percent:5.1f}% of max", end="")

        if usage_percent > 90:
            print(" ⚠ DATA FLOOD - too slow!")
        elif c0_count >= 5:
            print(" ✓✓✓ GOOD!")
        elif c0_count > 0:
            print(" ✓ Has 0xC0")
        else:
            print()

        # Show sample if we have reasonable data
        if 10 < len(buffer) < 5000 and c0_count > 0:
            sample = " ".join([f"{b:02X}" for b in buffer[:48]])
            print(f"          Sample: {sample}")

    except Exception as e:
        print(f"ERROR: {e}")

print("\n" + "=" * 70)
print("Look for:")
print("1. Reasonable data volume (not flooded)")
print("2. Multiple 0xC0 start bytes")
print("3. Usage around 10-50% of theoretical max")
