"""
Check for ANY serial activity on the port
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"

print("\nChecking for ANY data activity on", SERIAL_PORT)
print("This will test if the port is receiving anything at all...")
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

    start = time.time()
    byte_count = 0
    unique_bytes = set()

    while (time.time() - start) < 10:
        data = ser.read(100)
        if data:
            byte_count += len(data)
            unique_bytes.update(data)
            # Show immediate feedback
            print(
                f"[{time.time() - start:.1f}s] Received {len(data)} bytes: {' '.join([f'{b:02X}' for b in data[:16]])}"
            )

    ser.close()

    print(f"\n{'=' * 70}")
    print("RESULTS:")
    print(f"{'=' * 70}")
    print(f"Total bytes received: {byte_count}")
    print(f"Unique byte values: {len(unique_bytes)}")

    if unique_bytes:
        sorted_bytes = sorted(unique_bytes)
        print(f"\nUnique bytes (hex): {' '.join([f'{b:02X}' for b in sorted_bytes])}")
        print(f"Unique bytes (dec): {' '.join([f'{b:3d}' for b in sorted_bytes])}")
        
        # Check for bytes close to 0xC0 (192)
        if any(b in range(0xB0, 0xD0) for b in sorted_bytes):
            print("\n⚠ Found bytes near 0xC0 range - possible parity/bit error!")

    if byte_count == 0:
        print("\n❌ NO DATA RECEIVED AT ALL!")
        print("\nPossible causes:")
        print("1. Pump is not powered on or not transmitting")
        print("2. Wrong wiring (no connection to RS485 lines)")
        print("3. USB-RS485 adapter not working or in wrong mode")
        print("4. Pump requires RCU to be present to transmit")
        print("\nTroubleshooting steps:")
        print("• Power cycle the pump (off/on)")
        print("• Check adapter LED - is it blinking?")
        print("• Try different USB-RS485 adapter if available")
        print("• Verify wiring with multimeter (should see ~2.5V between A and B)")
    else:
        print(f"\n✓ Data is being received!")
        print(f"\nBut no valid 0xC0 start bytes found.")
        print("This suggests:")
        print("1. Wrong baud rate (unlikely if 9600 is confirmed)")
        print("2. Pump is in different protocol mode")
        print("3. Need to send initial handshake to pump")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nCannot open serial port!")
    print("Check: sudo chmod 666 /dev/ttyUSB0")
