"""
FINAL DIAGNOSTIC: Test the configuration we KNOW worked
Earlier we confirmed 57600 NONE showed 0xC0 bytes
Let's verify and show complete messages
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 57600
PARITY = serial.PARITY_NONE

print("=" * 70)
print("FINAL TEST: 57600 baud, NO parity (8N1)")
print("=" * 70)
print("This configuration showed 0xC0 bytes in earlier tests")
print("Capturing for 10 seconds to get complete messages...\n")

ser = serial.Serial(
    port=SERIAL_PORT,
    baudrate=BAUDRATE,
    bytesize=serial.EIGHTBITS,
    parity=PARITY,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.1,
)

buffer = bytearray()
start_time = time.time()

while (time.time() - start_time) < 10.0:
    data = ser.read(100)
    if data:
        buffer.extend(data)

ser.close()

print(f"Captured {len(buffer)} bytes total")
print(f"Data rate: {len(buffer) / 10.0:.1f} bytes/sec\n")

# Find 0xC0 bytes
c0_positions = [i for i, b in enumerate(buffer) if b == 0xC0]
print(f"Found {len(c0_positions)} x 0xC0 start bytes\n")

if c0_positions:
    print("=" * 70)
    print("ANALYZING MESSAGES:")
    print("=" * 70)

    for idx, pos in enumerate(c0_positions[:5], 1):  # First 5 messages
        # Extract enough bytes for a complete message
        msg_end = min(pos + 50, len(buffer))
        msg_bytes = buffer[pos:msg_end]

        if len(msg_bytes) < 4:
            continue

        cmd = msg_bytes[1]
        length = msg_bytes[2]
        expected_total = 3 + length + 1

        print(f"\nMessage {idx} at offset {pos}:")
        print(f"  Command: 0x{cmd:02X}, Length: {length}")

        if len(msg_bytes) >= min(expected_total, 40):
            display_len = min(expected_total, len(msg_bytes), 40)
            hex_str = " ".join([f"{b:02X}" for b in msg_bytes[:display_len]])
            print(f"  Bytes: {hex_str}")

            if len(msg_bytes) >= expected_total:
                # Try checksum
                calc_checksum = 0
                for b in msg_bytes[: expected_total - 1]:
                    calc_checksum ^= b
                actual_checksum = msg_bytes[expected_total - 1]

                checksum_match = calc_checksum == actual_checksum
                print(
                    f"  Checksum: 0x{actual_checksum:02X}, Calculated: 0x{calc_checksum:02X} {'✓' if checksum_match else '✗'}"
                )

                if checksum_match:
                    print(f"  ✓✓✓ VALID MESSAGE!")
                    print(f"\n  THIS IS THE CORRECT CONFIGURATION!")
                    print(f"  Baudrate: {BAUDRATE}, Parity: NONE, Data: 8N1")
else:
    print("⚠ NO 0xC0 BYTES FOUND!")
    print("\nShowing first 100 bytes of raw data:")
    for i in range(0, min(100, len(buffer)), 16):
        chunk = buffer[i : i + 16]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        print(f"  {hex_str}")

    print("\nPossible issues:")
    print("1. RCU still connected/powered (causing conflicts)")
    print("2. Pump needs power cycle")
    print("3. Wrong physical pins connected")

print("\n" + "=" * 70)
