"""
Raw Serial Dump - Show exactly what bytes are coming through
Tests both EVEN and NO parity to compare
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"  # Change if needed
BAUDRATE = 9600


def dump_raw(parity_mode: str, duration: float = 5.0):
    """Dump raw bytes with specific parity setting"""

    parity_map = {
        "NONE": serial.PARITY_NONE,
        "EVEN": serial.PARITY_EVEN,
        "ODD": serial.PARITY_ODD,
    }

    print(f"\n{'=' * 70}")
    print(f"Testing with parity: {parity_mode}")
    print(f"{'=' * 70}\n")

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=parity_map[parity_mode],
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        print(f"Listening for {duration} seconds...\n")
        start_time = time.time()
        total_bytes = 0
        c0_count = 0

        while (time.time() - start_time) < duration:
            data = ser.read(100)
            if data:
                # Print in hex format, 16 bytes per line
                for i in range(0, len(data), 16):
                    chunk = data[i : i + 16]
                    hex_str = " ".join([f"{b:02X}" for b in chunk])
                    ascii_str = "".join(
                        [chr(b) if 32 <= b < 127 else "." for b in chunk]
                    )
                    print(f"{total_bytes + i:04X}:  {hex_str:<48}  {ascii_str}")

                total_bytes += len(data)
                c0_count += data.count(0xC0)

        ser.close()

        print(f"\nTotal bytes: {total_bytes}")
        print(f"0xC0 start bytes found: {c0_count}")

        if c0_count > 0:
            print(f"✓ LOOKS GOOD! Found {c0_count} valid 0xC0 start bytes")
        else:
            print("✗ No valid 0xC0 start bytes found")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    print("\n" + "=" * 70)
    print("Nibe RS485 Raw Data Analyzer")
    print("=" * 70)
    print(f"Port: {SERIAL_PORT}")
    print(f"Baud rate: {BAUDRATE}")
    print("\nThis will test different parity settings to find the right one.")
    print("Looking for 0xC0 start bytes in the data stream...")

    # Test each parity mode
    for parity in ["NONE", "EVEN", "ODD"]:
        dump_raw(parity, duration=5.0)
        time.sleep(1)

    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)
    print("\nWhich parity setting showed the most 0xC0 bytes?")
    print("Update nibe_serial.py with the correct parity setting.")


if __name__ == "__main__":
    main()
