"""
Test different baud rates quickly looking for message patterns
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATES = [4800, 9600, 19200, 38400, 57600]

print("Quick Baud Rate Test")
print("=" * 70)

for baudrate in BAUD_RATES:
    print(f"\nTesting {baudrate} baud...", end=" ", flush=True)

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )

        # Read for 2 seconds
        start = time.time()
        buffer = bytearray()

        while (time.time() - start) < 2.0:
            data = ser.read(100)
            if data:
                buffer.extend(data)

        ser.close()

        # Count 0xC0 bytes
        c0_count = buffer.count(0xC0)

        # Calculate data rate
        data_rate = len(buffer) / 2.0  # bytes per second

        print(f"Got {len(buffer)} bytes ({data_rate:.0f} B/s), {c0_count} x 0xC0")

        # Show first 32 bytes
        if buffer:
            sample = " ".join([f"{b:02X}" for b in buffer[:32]])
            print(f"  Sample: {sample}")

            # Check for repeating patterns
            if len(buffer) > 20:
                chunk1 = bytes(buffer[0:10])
                repeats = buffer.count(chunk1)
                if repeats > 3:
                    print(
                        f"  ⚠ Pattern repeats {repeats} times - possible wrong baud rate"
                    )

            if c0_count >= 5:
                print(f"  ✓ GOOD CANDIDATE - {c0_count} start bytes found!")

    except Exception as e:
        print(f"ERROR: {e}")

print("\n" + "=" * 70)
print("Check which baud rate has the most 0xC0 bytes")
