"""
Capture at 19200 EVEN and show both normal and inverted interpretations
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
PARITY = serial.PARITY_EVEN
DURATION = 10

print("=" * 70)
print("CAPTURING AT 19200 EVEN (10 seconds)")
print("=" * 70)
print("Showing both NORMAL and INVERTED data interpretations\n")

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
        buffer.extend(data)
        print(".", end="", flush=True)

ser.close()

print(f"\n\nReceived {len(buffer)} bytes ({len(buffer) / DURATION:.1f} B/s)\n")

if len(buffer) == 0:
    print("NO DATA RECEIVED!")
    exit(1)

# Create inverted version
inverted = bytearray([b ^ 0xFF for b in buffer])

print("=" * 70)
print("NORMAL DATA - Looking for 0x5C frames")
print("=" * 70)

# Find 0x5C in normal data
normal_5c = [i for i, b in enumerate(buffer) if b == 0x5C]
print(f"Found {len(normal_5c)} x 0x5C bytes at positions: {normal_5c[:10]}")

if normal_5c:
    print("\nFrames starting with 0x5C:")
    for i, pos in enumerate(normal_5c[:5]):  # Show first 5
        if pos + 20 < len(buffer):
            frame = buffer[pos : pos + 20]
            hex_str = " ".join([f"{b:02X}" for b in frame])
            print(f"  Frame {i + 1} @ {pos}: {hex_str}")

            # Try to parse as F-series frame
            if len(frame) >= 5:
                addr = frame[1]
                cmd = frame[2]
                length = frame[3]
                print(f"           -> Addr=0x{addr:02X}, Cmd=0x{cmd:02X}, Len={length}")

print("\n" + "=" * 70)
print("INVERTED DATA - Looking for 0x5C, 0x69, 0x6D")
print("=" * 70)

# Find protocol bytes in inverted data
inv_5c = [i for i, b in enumerate(inverted) if b == 0x5C]
inv_69 = [i for i, b in enumerate(inverted) if b == 0x69]
inv_6d = [i for i, b in enumerate(inverted) if b == 0x6D]

print(f"0x5C (frame start): {len(inv_5c)} found at {inv_5c[:10]}")
print(f"0x69 (read token):  {len(inv_69)} found at {inv_69[:10]}")
print(f"0x6D (announce):    {len(inv_6d)} found at {inv_6d[:10]}")

if inv_5c:
    print("\nINVERTED frames starting with 0x5C:")
    for i, pos in enumerate(inv_5c[:5]):
        if pos + 20 < len(inverted):
            frame = inverted[pos : pos + 20]
            hex_str = " ".join([f"{b:02X}" for b in frame])
            print(f"  Frame {i + 1} @ {pos}: {hex_str}")

            if len(frame) >= 5:
                addr = frame[1]
                cmd = frame[2]
                length = frame[3]
                print(f"           -> Addr=0x{addr:02X}, Cmd=0x{cmd:02X}, Len={length}")

if inv_6d:
    print("\nINVERTED frames with 0x6D (ANNOUNCEMENT):")
    for i, pos in enumerate(inv_6d[:3]):
        start = max(0, pos - 5)  # Show some context before
        if pos + 20 < len(inverted):
            frame = inverted[start : pos + 20]
            hex_str = " ".join([f"{b:02X}" for b in frame])
            print(f"  Frame {i + 1} @ {pos}: {hex_str}")
            # Mark where 0x6D is
            print(f"           {'   ' * (pos - start)}^^ (0x6D here)")

print("\n" + "=" * 70)
print("RECOMMENDATION")
print("=" * 70)

if len(inv_5c) > len(normal_5c) or len(inv_6d) > 0:
    print("✓ INVERTED data looks more promising!")
    print("  Your USB-RS485 adapter is reading A/B backwards.")
    print("  SOLUTION: Invert all received data in Python (XOR with 0xFF)")
    print("\n  We'll update nibe_serial.py to auto-invert data.")
elif len(normal_5c) > 0:
    print("✓ NORMAL data looks correct!")
    print("  Your adapter is reading correctly.")
else:
    print("⚠ Neither normal nor inverted shows clear frames.")
    print("  May need to try different baud rates or check Modbus enable.")

print("=" * 70)
