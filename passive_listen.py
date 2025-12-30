"""
Passive listener - just receive and display what the pump sends
No queries, pure receive mode
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 4800  # Try even slower
PARITY = serial.PARITY_EVEN

print("=" * 70)
print("PASSIVE LISTENING MODE")
print("=" * 70)
print(f"Port: {SERIAL_PORT}")
print(f"Baudrate: {BAUDRATE}, Parity: NONE")
print("Just receiving whatever the pump broadcasts...")
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

        # Highlight 0xC0 in green
        hex_highlighted = hex_str.replace("C0", "\033[92mC0\033[0m")
        print(f"{i:04X}:  {hex_highlighted:<48}  {ascii_str}")

    # Count 0xC0 bytes
    c0_count = buffer.count(0xC0)
    print(f"\n0xC0 bytes found: {c0_count}")

    if c0_count > 0:
        # Show spacing between them
        positions = [i for i, b in enumerate(buffer) if b == 0xC0]
        if len(positions) > 1:
            spacings = [
                positions[i + 1] - positions[i]
                for i in range(min(10, len(positions) - 1))
            ]
            print(f"Spacing between first 0xC0 bytes: {spacings}")

    print(f"\n✓ Pump IS transmitting data!")
    print(f"The issue is likely in how we're parsing the messages,")
    print(f"not in the physical connection.")
else:
    print("NO DATA - check wiring is back to original configuration!")

print("=" * 70)
