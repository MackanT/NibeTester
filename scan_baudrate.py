"""
Nibe Baud Rate Scanner
Tests common baud rates to find the correct one for your pump
"""

import serial
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

SERIAL_PORT = "/dev/ttyUSB0"  # Change this!
START_BYTE = 0xC0

# Common RS485 baud rates
BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 4800]


def test_baudrate(port: str, baudrate: int, duration: float = 3.0) -> dict:
    """Test a specific baud rate and count valid start bytes"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        start_time = time.time()
        total_bytes = 0
        valid_starts = 0
        buffer = bytearray()

        while (time.time() - start_time) < duration:
            data = ser.read(100)
            if data:
                total_bytes += len(data)
                buffer.extend(data)

                # Count 0xC0 start bytes
                valid_starts += data.count(START_BYTE)

        ser.close()

        # Show sample of raw data
        sample = " ".join([f"{b:02X}" for b in buffer[:20]]) if buffer else "No data"

        return {
            "baudrate": baudrate,
            "total_bytes": total_bytes,
            "valid_starts": valid_starts,
            "score": valid_starts,
            "sample": sample,
        }

    except Exception as e:
        return {"baudrate": baudrate, "error": str(e)}


def main():
    print("=" * 70)
    print("Nibe Baud Rate Scanner")
    print("=" * 70)
    print(f"Testing port: {SERIAL_PORT}")
    print(f"Looking for start byte: 0x{START_BYTE:02X}")
    print()
    print("Testing each baud rate for 3 seconds...")
    print()

    results = []

    for baudrate in BAUD_RATES:
        print(f"Testing {baudrate} baud...", end=" ", flush=True)
        result = test_baudrate(SERIAL_PORT, baudrate)
        results.append(result)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(
                f"Bytes: {result['total_bytes']}, Valid starts: {result['valid_starts']}"
            )

    # Sort by score (most valid start bytes)
    results_sorted = sorted(
        [r for r in results if "error" not in r], key=lambda x: x["score"], reverse=True
    )

    print()
    print("=" * 70)
    print("RESULTS (sorted by likelihood):")
    print("=" * 70)

    for i, result in enumerate(results_sorted, 1):
        print(f"\n{i}. {result['baudrate']} baud")
        print(f"   Total bytes received: {result['total_bytes']}")
        print(f"   Valid 0xC0 start bytes: {result['valid_starts']}")
        print(f"   Sample data: {result['sample']}")

        if result["valid_starts"] > 0:
            print(
                f"   ⭐ RECOMMENDED - Found {result['valid_starts']} valid start bytes!"
            )

    if results_sorted and results_sorted[0]["valid_starts"] > 0:
        print()
        print("=" * 70)
        print(f"✓ Best match: {results_sorted[0]['baudrate']} baud")
        print(
            f"  Update test_nibe.py line 30: baudrate={results_sorted[0]['baudrate']}"
        )
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("⚠ No valid start bytes found at any baud rate!")
        print()
        print("Possible issues:")
        print("1. RCU is still connected (disconnect it!)")
        print("2. Wrong RS485 wiring (A/B swapped?)")
        print("3. Pump is not transmitting (needs to be powered on)")
        print("4. USB-RS485 adapter issue")
        print("=" * 70)


if __name__ == "__main__":
    main()
