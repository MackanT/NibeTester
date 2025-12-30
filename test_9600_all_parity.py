"""
Test 9600 baud with all three parity modes
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 9600
START_BYTE = 0xC0

for parity_name, parity_val in [
    ("NONE", serial.PARITY_NONE),
    ("EVEN", serial.PARITY_EVEN),
    ("ODD", serial.PARITY_ODD),
]:
    print(f"\n{'=' * 70}")
    print(f"Testing 9600 baud with {parity_name} parity")
    print(f"{'=' * 70}\n")

    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
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

    print(f"Received {len(buffer)} bytes")
    print(f"Data rate: {len(buffer) / 5.0:.1f} bytes/sec")

    # Find all C0 positions
    c0_positions = [i for i, b in enumerate(buffer) if b == START_BYTE]
    print(f"Found {len(c0_positions)} x 0xC0 bytes")

    if len(c0_positions) >= 2:
        # Check spacing between 0xC0 bytes
        spacings = [
            c0_positions[i + 1] - c0_positions[i]
            for i in range(min(5, len(c0_positions) - 1))
        ]
        print(f"Spacing between 0xC0 bytes: {spacings}")

        # Show first message
        if len(buffer) > c0_positions[0] + 40:
            msg_start = c0_positions[0]
            msg_bytes = buffer[msg_start : msg_start + 35]
            hex_str = " ".join([f"{b:02X}" for b in msg_bytes])
            print(f"\nFirst message: {hex_str}")

            if len(msg_bytes) >= 3:
                cmd = msg_bytes[1]
                length = msg_bytes[2]
                print(f"Command: 0x{cmd:02X}, Length: {length}")

                expected_len = 3 + length + 1
                if len(msg_bytes) >= expected_len:
                    # Calculate checksum
                    calc_cs = 0
                    for b in msg_bytes[: expected_len - 1]:
                        calc_cs ^= b
                    actual_cs = msg_bytes[expected_len - 1]

                    if calc_cs == actual_cs:
                        print(f"✓✓✓ VALID CHECKSUM! This is the correct setting!")
                    else:
                        print(
                            f"✗ Checksum: expected 0x{actual_cs:02X}, got 0x{calc_cs:02X}"
                        )

print("\n" + "=" * 70)
print("Use the setting with VALID CHECKSUM")
print("=" * 70)
