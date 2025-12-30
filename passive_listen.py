"""
Passive listener - just receive and display what the pump sends
No queries, pure receive mode
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 9600  # CONFIRMED from nibepi: F-series uses 9600
PARITY = serial.PARITY_EVEN  # CONFIRMED from nibepi: 8E1 (8 data, even parity, 1 stop)

print("=" * 70)
print("PASSIVE LISTENING MODE - CONFIRMED NIBEPI SETTINGS")
print("=" * 70)
print(f"Port: {SERIAL_PORT}")
print(f"Baudrate: {BAUDRATE}, Parity: EVEN (8E1)")
print("Research: nibepi GitHub confirms F-series uses 9600/8E1")
print("Pump SHOULD broadcast automatic messages + read tokens")
print("Listening for 10 seconds...\n")

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
last_data_time = time.time()

while (time.time() - start_time) < 10.0:
    data = ser.read(100)
    if data:
        buffer.extend(data)
        current_time = time.time()
        elapsed = current_time - last_data_time

        # Show real-time data arrival
        if elapsed > 0.5:  # New burst after gap
            print(f"\n[{current_time - start_time:.1f}s] ", end="")

        print(".", end="", flush=True)
        last_data_time = current_time

ser.close()

print(f"\n\nReceived {len(buffer)} bytes total")
print(f"Data rate: {len(buffer) / 10.0:.1f} bytes/sec\n")

if buffer:
    # Show hex dump
    print("First 200 bytes:")
    for i in range(0, min(200, len(buffer)), 16):
        chunk = buffer[i : i + 16]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])

        # Highlight START bytes: 0x5C (F-series frame start) and 0xC0 (our encoding)
        hex_highlighted = hex_str.replace("5C", "\033[92m5C\033[0m")  # Green for 0x5C
        hex_highlighted = hex_highlighted.replace(
            "C0", "\033[93mC0\033[0m"
        )  # Yellow for 0xC0
        print(f"{i:04X}:  {hex_highlighted:<48}  {ascii_str}")

    # Count both potential start bytes
    f_start_count = buffer.count(0x5C)  # F-series actual start byte
    c0_count = buffer.count(0xC0)  # Our protocol's expected start
    print(f"\n0x5C bytes found (F-series frame start): {f_start_count}")
    print(f"0xC0 bytes found (our protocol start): {c0_count}")

    # Analyze F-series frames if found
    if f_start_count > 0:
        positions = [i for i, b in enumerate(buffer) if b == 0x5C]
        if len(positions) > 1:
            spacings = [
                positions[i + 1] - positions[i]
                for i in range(min(10, len(positions) - 1))
            ]
            print(f"Spacing between 0x5C bytes: {spacings}")

        # Show what follows 0x5C
        print(f"\nBytes after first 0x5C:")
        for i in range(min(3, len(positions))):
            pos = positions[i]
            if pos + 10 < len(buffer):
                context = buffer[pos : pos + 10]
                hex_str = " ".join([f"{b:02X}" for b in context])
                print(f"  Position {pos}: {hex_str}")

    # Analyze 0xC0 if found
    if c0_count > 0:
        positions = [i for i, b in enumerate(buffer) if b == 0xC0]
        if len(positions) > 1:
            spacings = [
                positions[i + 1] - positions[i]
                for i in range(min(10, len(positions) - 1))
            ]
            print(f"Spacing between 0xC0 bytes: {spacings}")

    print(f"\n✓ Pump IS transmitting data!")
    if f_start_count > 0:
        print(f"✓ Found {f_start_count} F-series frame starts (0x5C)")
        print(f"This is the correct framing byte for F-series pumps!")
    if c0_count > 0:
        print(f"Note: Also found {c0_count} 0xC0 bytes (may be data, not frame starts)")
else:
    print("NO DATA - check wiring!")

print("=" * 70)
