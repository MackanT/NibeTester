"""
Show actual bytes received at 9600 baud
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"

for parity_name, parity_val in [
    ("EVEN", serial.PARITY_EVEN),
    ("NONE", serial.PARITY_NONE),
]:
    print(f"\n{'=' * 70}")
    print(f"9600 baud with {parity_name} parity - RAW DATA")
    print(f"{'=' * 70}\n")

    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=parity_val,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
    )

    buffer = bytearray()
    start = time.time()

    while (time.time() - start) < 5.0:
        data = ser.read(100)
        if data:
            buffer.extend(data)

    ser.close()

    print(f"Received {len(buffer)} bytes\n")

    if buffer:
        # Show all bytes in hex dump format
        for i in range(0, min(len(buffer), 200), 16):
            chunk = buffer[i : i + 16]
            hex_str = " ".join([f"{b:02X}" for b in chunk])
            ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])
            print(f"{i:04X}:  {hex_str:<48}  {ascii_str}")

        # Show unique byte values
        unique = sorted(set(buffer))
        print(
            f"\nUnique bytes ({len(unique)}): {' '.join([f'{b:02X}' for b in unique])}"
        )

        # Check if 0x5C (which looks like 0xC0 with bit errors)
        if 0x5C in buffer:
            print("⚠ Found 0x5C - might be 0xC0 with parity issues")
        if 0x40 in buffer:
            print("⚠ Found 0x40 - might be 0xC0 with bit flips")
    else:
        print("NO DATA RECEIVED!")

print("\n" + "=" * 70)
print("If no data at all, the pump might need an init message first")
print("=" * 70)
