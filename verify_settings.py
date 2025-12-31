"""
Quick verification that we can now see proper protocol messages
"""

import serial
import time
from nibe_protocol import START_BYTE, NibeCommand

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
PARITY = serial.PARITY_EVEN
INVERT_DATA = True
DURATION = 10

print("=" * 70)
print("VERIFICATION TEST - 19200 EVEN with DATA INVERSION")
print("=" * 70)
print("Looking for protocol messages after inversion...\n")

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

while (time.time() - start_time) < DURATION:
    data = ser.read(100)
    if data:
        # Invert data
        if INVERT_DATA:
            data = bytes([b ^ 0xFF for b in data])
        buffer.extend(data)
        print(".", end="", flush=True)

ser.close()

print(f"\n\nReceived {len(buffer)} bytes ({len(buffer) / DURATION:.1f} B/s)\n")

# Find protocol messages
frame_starts = [i for i, b in enumerate(buffer) if b == START_BYTE]
announcements = [i for i, b in enumerate(buffer) if b == NibeCommand.MODBUS_READ_REQ]
read_tokens = [i for i, b in enumerate(buffer) if b == NibeCommand.MODBUS_READ_TOKEN]
data_msgs = [i for i, b in enumerate(buffer) if b == NibeCommand.MODBUS_DATA_MSG]

print(f"0x{START_BYTE:02X} frame starts:     {len(frame_starts)}")
print(f"0x{NibeCommand.MODBUS_READ_REQ:02X} announcements:    {len(announcements)}")
print(f"0x{NibeCommand.MODBUS_READ_TOKEN:02X} read tokens:      {len(read_tokens)}")
print(f"0x{NibeCommand.MODBUS_DATA_MSG:02X} data messages:    {len(data_msgs)}")

if frame_starts:
    print(
        f"\n✓ SUCCESS! Found {len(frame_starts)} frame start bytes (0x{START_BYTE:02X})"
    )
    print("\nFirst 3 frames:")
    for i, pos in enumerate(frame_starts[:3]):
        if pos + 10 < len(buffer):
            frame = buffer[pos : pos + 10]
            hex_str = " ".join([f"{b:02X}" for b in frame])
            print(f"  Frame {i + 1} @ {pos}: {hex_str}")

            if len(frame) >= 4:
                addr = frame[1]
                cmd = frame[2]
                length = frame[3]

                cmd_name = "UNKNOWN"
                if cmd == NibeCommand.MODBUS_READ_REQ:
                    cmd_name = "ANNOUNCEMENT"
                elif cmd == NibeCommand.MODBUS_READ_TOKEN:
                    cmd_name = "READ_TOKEN"
                elif cmd == NibeCommand.MODBUS_DATA_MSG:
                    cmd_name = "DATA_MSG"
                elif cmd == NibeCommand.RMU_DATA_MSG:
                    cmd_name = "RMU_DATA"

                print(
                    f"           -> Addr=0x{addr:02X}, Cmd=0x{cmd:02X} ({cmd_name}), Len={length}"
                )

    print("\n" + "=" * 70)
    print("✓✓✓ SETTINGS CONFIRMED CORRECT! ✓✓✓")
    print("=" * 70)
    print("Ready to run test_nibe.py - it should work now!")

else:
    print("\n✗ PROBLEM - Still no frame starts found!")
    print("Check that adapter is connected and pump is powered on.")

print("=" * 70)
