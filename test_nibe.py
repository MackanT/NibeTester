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
    print(f"Settings: 19200 baud, EVEN parity, DATA INVERTED")
    print("=" * 70)

    # Create serial connection
    # Fighter 360P uses 19200 baud, EVEN parity
    # Data inverted due to backwards RS485 adapter
    nibe = NibeSerial(port=SERIAL_PORT, baudrate=19200, invert_data=True)

    # Track received values (async callbacks will populate this)
    register_values = {}

    def on_register_update(address: int, value: int):
        """Callback when register value is received (async)"""
        reg_info = get_register_info(address)
        if reg_info:
            actual_value = reg_info.decode_value(value)
            register_values[address] = actual_value
            print(f"  ✓ {reg_info.title}: {actual_value:.1f} {reg_info.unit}")
        else:
            register_values[address] = value
            print(f"  ✓ Register {address}: {value}")

    # Register callbacks for all temperature sensors
    temp_registers = get_all_temperature_registers()
    for addr in temp_registers:
        nibe.add_register_callback(addr, on_register_update)

    # Connect
    if not nibe.connect():
        print("ERROR: Failed to connect to serial port!")
        print(f"Make sure {SERIAL_PORT} is correct and device is connected.")
        return 1

    print("✓ Connected to Nibe heat pump")
    print("\nWaiting for pump announcements...")
    time.sleep(3)  # Let pump send announcements

    try:
        print(
            "\nRequesting temperature sensors (async - waiting for pump responses)..."
        )
        print("-" * 70)

        # Queue all read requests - they'll be sent when pump sends READ_TOKEN
        for addr in temp_registers:
            nibe.request_register(addr)
            time.sleep(0.3)  # Small delay between queueing

        print(f"\nQueued {len(temp_registers)} read requests")
        print("Waiting for responses (pump sends data on its schedule)...")
        print("This may take 10-30 seconds...\n")

        # Wait for responses to arrive via callbacks
        start_time = time.time()
        last_count = 0

        while time.time() - start_time < 30:
            time.sleep(1)

            if len(register_values) != last_count:
                print(
                    f"  [{int(time.time() - start_time)}s] Received {len(register_values)}/{len(temp_registers)} values"
                )
                last_count = len(register_values)

            # Stop early if we got everything
            if len(register_values) == len(temp_registers):
                print(f"\n✓ All {len(temp_registers)} registers received!")
                break
            msg = nibe.wait_for_message(timeout=1.0)
            if msg:
                # Message handled by callbacks
                pass

            time.sleep(0.5)  # Small delay between reads

        # Summary
        print("\n" + "=" * 70)
        print("Summary - Received Values:")
        print("=" * 70)

        if register_values:
            for addr in sorted(register_values.keys()):
                reg_info = get_register_info(addr)
                value = register_values[addr]

                if reg_info:
                    print(f"{reg_info.title:40s}: {value:6.1f} {reg_info.unit}")
                else:
                    print(f"Register {addr:5d}: {value}")

            print(f"\nTotal: {len(register_values)} registers read")
        else:
            print("No registers read successfully")
            print("\nTroubleshooting:")
            print("- Check that pump is powered on")
            print("- Verify RS485 wiring (see PROTOCOL_FINDINGS.md)")
            print("- Run show_messages.py to see what pump is sending")

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    finally:
        print("\nDisconnecting...")
        nibe.disconnect()
        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
