"""
Find and decode actual Nibe messages in the data stream
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
START_BYTE = 0xC0


def find_messages(data: bytes):
    """Search for 0xC0 start bytes and try to parse messages"""
    messages = []
    i = 0

    while i < len(data):
        if data[i] == START_BYTE:
            # Found potential message start
            if i + 3 < len(data):  # Need at least START + CMD + LEN + CRC
                start = i
                command = data[i + 1]
                length = data[i + 2]

                # Check if we have the complete message
                expected_end = i + 3 + length + 1  # START + CMD + LEN + DATA + CRC

                if expected_end <= len(data):
                    msg_bytes = data[start:expected_end]
                    messages.append(
                        {
                            "offset": start,
                            "command": command,
                            "length": length,
                            "bytes": msg_bytes,
                            "hex": " ".join([f"{b:02X}" for b in msg_bytes]),
                        }
                    )
                    i = expected_end  # Skip past this message
                    continue
        i += 1

    return messages


print("\nNibe Message Finder")
print("=" * 70)
print("Searching for 0xC0 start bytes and decoding messages...")
print("Listening for 10 seconds...\n")

try:
    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
    )

    buffer = bytearray()
    start_time = time.time()
    c0_positions = []

    while (time.time() - start_time) < 10:
        data = ser.read(100)
        if data:
            # Track where we find 0xC0 bytes
            for i, byte in enumerate(data):
                if byte == START_BYTE:
                    c0_positions.append(len(buffer) + i)

            buffer.extend(data)

    ser.close()

    print(f"\n{'=' * 70}")
    print("RAW DATA ANALYSIS:")
    print(f"{'=' * 70}")
    print(f"Total bytes collected: {len(buffer)}")
    print(f"0xC0 start bytes found: {len(c0_positions)}")

    if c0_positions:
        print(f"\n0xC0 found at positions: {c0_positions[:10]}")  # Show first 10

        # Try to parse messages
        messages = find_messages(bytes(buffer))

        print(f"\n{'=' * 70}")
        print(f"DECODED MESSAGES: {len(messages)} found")
        print(f"{'=' * 70}\n")

        for i, msg in enumerate(messages[:10], 1):  # Show first 10 messages
            print(f"Message {i} (offset {msg['offset']}):")
            print(f"  Command: 0x{msg['command']:02X} ({msg['command']})")
            print(f"  Length:  {msg['length']} bytes")
            print(f"  Hex:     {msg['hex']}")
            print()

        if len(messages) > 10:
            print(f"... and {len(messages) - 10} more messages")

        if messages:
            print(f"\n✓ SUCCESS! Pump is transmitting valid Nibe messages!")
            print(f"\nNext step: Fix the parser in nibe_serial.py")
        else:
            print(f"\n⚠ Found 0xC0 bytes but couldn't decode complete messages")
            print("This might mean:")
            print("1. Messages are incomplete (need longer capture)")
            print("2. Message format is different than expected")
    else:
        print("\n❌ No 0xC0 bytes found in this capture")
        print("Try running again - data might be periodic")

    # Show first 200 bytes in hex dump format
    print(f"\n{'=' * 70}")
    print("FIRST 200 BYTES (HEX DUMP):")
    print(f"{'=' * 70}\n")

    for i in range(0, min(200, len(buffer)), 16):
        chunk = buffer[i : i + 16]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])

        # Highlight 0xC0 bytes
        hex_highlighted = hex_str.replace("C0", "\033[92mC0\033[0m")  # Green

        print(f"{i:04X}:  {hex_highlighted:<48}  {ascii_str}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
