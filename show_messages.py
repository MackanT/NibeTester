"""
Show what messages the pump is actually sending
This will help diagnose why read requests aren't working
"""

import serial
import time
from nibe_protocol import START_BYTE, MessageType, parse_message

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
PARITY = serial.PARITY_EVEN
INVERT_DATA = True
DURATION = 15

print("=" * 70)
print("MESSAGE MONITOR - Show all pump messages")
print("=" * 70)
print(f"Capturing for {DURATION} seconds...\n")

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
message_count = 0

while (time.time() - start_time) < DURATION:
    data = ser.read(100)
    if data:
        # Invert data
        if INVERT_DATA:
            data = bytes([b ^ 0xFF for b in data])
        buffer.extend(data)

        # Try to parse messages
        while len(buffer) > 0:
            if START_BYTE not in buffer:
                buffer.clear()
                break

            # Find start byte
            start_idx = buffer.index(START_BYTE)
            if start_idx > 0:
                buffer = buffer[start_idx:]

            # Try to parse
            msg = parse_message(buffer)
            if msg:
                message_count += 1
                elapsed = time.time() - start_time

                # Decode command name
                cmd_name = "UNKNOWN"
                if msg.command == MessageType.ANNOUNCEMENT:
                    cmd_name = "ANNOUNCEMENT"
                elif msg.command == MessageType.DATA_RESPONSE:
                    cmd_name = "DATA_RESPONSE"
                elif msg.command == MessageType.READ_REQUEST:
                    cmd_name = "READ_TOKEN"
                elif msg.command == MessageType.WRITE_ACK:
                    cmd_name = "WRITE_ACK"
                elif msg.command == MessageType.RMU_SYSTEM:
                    cmd_name = "RMU_SYSTEM"

                # Show message
                hex_str = msg.raw.hex(" ")
                payload_hex = msg.data.hex(" ") if msg.data else "(none)"

                print(
                    f"[{elapsed:5.1f}s] {cmd_name:15} | Addr=0x{msg.address:02X} Len={msg.length:3} | Payload: {payload_hex}"
                )

                if msg.command == MessageType.READ_REQUEST:
                    print(f"         ^^^ READ TOKEN - We should send read request now!")

                # Remove from buffer
                buffer = buffer[len(msg.raw) :]
            else:
                # Not enough data yet
                if len(buffer) < 50:
                    break
                else:
                    # Bad data, discard one byte
                    buffer.pop(0)

ser.close()

print("\n" + "=" * 70)
print(f"SUMMARY: Received {message_count} messages in {DURATION}s")
print("=" * 70)

if message_count == 0:
    print("✗ NO MESSAGES - Check connection!")
else:
    print(f"✓ Messages received successfully")
    print("\nIf you see READ_TOKEN messages, the pump is ready to receive")
    print("your read requests. We need to send them when token arrives.")

print("=" * 70)
