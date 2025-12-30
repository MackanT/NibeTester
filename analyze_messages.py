"""
Capture and analyze actual message structure from pump
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 57600
START_BYTE = 0xC0


def capture_messages():
    """Capture data and try to find message patterns"""

    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
    )

    print("Capturing data for 5 seconds...")
    print("Looking for 0xC0 start bytes and surrounding context\n")

    buffer = bytearray()
    start_time = time.time()

    while (time.time() - start_time) < 5.0:
        data = ser.read(100)
        if data:
            buffer.extend(data)

    ser.close()

    print(f"Captured {len(buffer)} bytes total\n")
    print("=" * 70)
    print("MESSAGES STARTING WITH 0xC0:")
    print("=" * 70)

    # Find all 0xC0 positions
    messages = []
    for i in range(len(buffer)):
        if buffer[i] == START_BYTE:
            # Grab next 20 bytes after 0xC0 for analysis
            end = min(i + 20, len(buffer))
            msg_bytes = buffer[i:end]

            if len(msg_bytes) >= 3:
                command = msg_bytes[1]
                length = msg_bytes[2]

                messages.append(
                    {
                        "offset": i,
                        "bytes": msg_bytes,
                        "command": command,
                        "length": length,
                    }
                )

    print(f"\nFound {len(messages)} messages starting with 0xC0:\n")

    for idx, msg in enumerate(messages, 1):
        print(f"Message {idx} at offset {msg['offset']}:")
        print(f"  Command byte: 0x{msg['command']:02X} ({msg['command']})")
        print(f"  Length byte:  {msg['length']} (0x{msg['length']:02X})")

        hex_str = " ".join([f"{b:02X}" for b in msg["bytes"]])
        print(f"  Bytes: {hex_str}")

        # Calculate expected message length
        expected_len = 3 + msg["length"] + 1  # START + CMD + LEN + DATA + CRC
        print(f"  Expected total length: {expected_len} bytes")

        if len(msg["bytes"]) >= expected_len:
            actual_msg = msg["bytes"][:expected_len]
            checksum = actual_msg[-1]

            # Calculate XOR checksum
            calc_checksum = 0
            for b in actual_msg[:-1]:
                calc_checksum ^= b

            checksum_ok = calc_checksum == checksum
            print(
                f"  Checksum: 0x{checksum:02X}, Calculated: 0x{calc_checksum:02X} {'✓' if checksum_ok else '✗'}"
            )

            if checksum_ok:
                print(f"  ✓✓✓ VALID MESSAGE!")
            else:
                print(f"  ✗ Checksum mismatch")
        else:
            print(f"  ⚠ Incomplete (only {len(msg['bytes'])} bytes captured)")

        print()


if __name__ == "__main__":
    capture_messages()
