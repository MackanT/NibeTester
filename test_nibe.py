"""
Nibe Fighter 360P - Simple Test Application
Read temperature sensors and display values
"""

import time
import sys
import logging
from nibe_serial import NibeSerial
from nibe_registers import get_register_info, get_all_temperature_registers


def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Configuration
    # Windows: "COM3", Linux: "/dev/ttyUSB0"
    SERIAL_PORT = "/dev/ttyUSB0"  # CHANGE THIS to your port!

    print("=" * 70)
    print("Nibe Fighter 360P - Temperature Monitor")
    print("=" * 70)
    print(f"Serial Port: {SERIAL_PORT}")
    print("=" * 70)

    # Create serial connection
    nibe = NibeSerial(port=SERIAL_PORT, baudrate=57600)

    # Track received values
    register_values = {}

    def on_register_update(address: int, value: int):
        """Callback when register value is received"""
        reg_info = get_register_info(address)
        if reg_info:
            actual_value = reg_info.decode_value(value)
            register_values[address] = actual_value
            print(f"  {reg_info.title}: {actual_value:.1f} {reg_info.unit}")
        else:
            register_values[address] = value
            print(f"  Register {address}: {value} (unknown)")

    # Register callbacks for temperature sensors
    temp_registers = get_all_temperature_registers()
    for addr in temp_registers:
        nibe.add_register_callback(addr, on_register_update)

    # Connect
    if not nibe.connect():
        print("ERROR: Failed to connect to serial port!")
        print(f"Make sure {SERIAL_PORT} is correct and device is connected.")
        return 1

    print("✓ Connected to Nibe heat pump")
    print("\nWaiting for initial communication...")

    try:
        # Wait a bit for pump to send announcements
        time.sleep(3)

        print("\nRequesting temperature sensors...")
        print("-" * 70)

        # Request all temperature registers
        for addr in temp_registers:
            nibe.read_register(addr)
            time.sleep(0.2)  # Small delay between requests

        # Monitor for responses
        print("\nReceiving data... (waiting 30 seconds)")
        start_time = time.time()

        while time.time() - start_time < 30:
            msg = nibe.wait_for_message(timeout=1.0)
            if msg:
                # Message handled by callbacks
                pass

            # Show progress
            if int(time.time() - start_time) % 5 == 0:
                print(
                    f"  ({int(time.time() - start_time)}s) Received {len(register_values)} values..."
                )

        # Summary
        print("\n" + "=" * 70)
        print("Summary - Received Values:")
        print("=" * 70)

        for addr in sorted(register_values.keys()):
            reg_info = get_register_info(addr)
            value = register_values[addr]

            if reg_info:
                print(f"{reg_info.title:40s}: {value:6.1f} {reg_info.unit}")
            else:
                print(f"Register {addr:5d}: {value}")

        print(f"\nTotal: {len(register_values)} registers read")

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    finally:
        print("\nDisconnecting...")
        nibe.disconnect()
        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
