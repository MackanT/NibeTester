"""
Nibe Heat Pump RS485 Diagnostic Tool
Tests all baud rate and parity combinations to find the correct configuration
"""

import serial
import time
from typing import Tuple, Optional

SERIAL_PORT = "/dev/ttyUSB0"

# Test configurations
BAUD_RATES = [9600, 19200, 38400, 57600, 115200]
PARITIES = {
    "NONE": serial.PARITY_NONE,
    "EVEN": serial.PARITY_EVEN,
    "ODD": serial.PARITY_ODD,
}


def create_read_request(register: int) -> bytes:
    """Create Nibe read request with XOR checksum"""
    data = bytearray(
        [
            0xC0,  # Start byte
            0x69,  # Read command
            0x02,  # Length
            register & 0xFF,  # Address low
            (register >> 8) & 0xFF,  # Address high
        ]
    )
    checksum = 0
    for b in data:
        checksum ^= b
    data.append(checksum)
    return bytes(data)


def test_configuration(
    baudrate: int, parity: int, parity_name: str
) -> Tuple[bool, str]:
    """Test a specific baud rate and parity combination"""

    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=parity,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )

        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.2)

        # Send read request for register 40004 (outdoor temp)
        request = create_read_request(40004)
        ser.write(request)
        ser.flush()

        # Clear possible echo
        time.sleep(0.1)
        ser.read(200)

        # Wait for response
        time.sleep(1.0)
        response = ser.read(200)

        ser.close()

        if not response:
            return False, "No response"

        # Check for 0xC0 start byte
        if 0xC0 not in response:
            return False, f"{len(response)} bytes, no 0xC0"

        # Try to parse message
        idx = response.index(0xC0)
        if idx + 3 >= len(response):
            return False, f"0xC0 found but incomplete message"

        cmd = response[idx + 1]
        length = response[idx + 2]
        expected_len = 3 + length + 1

        if idx + expected_len > len(response):
            return False, f"0xC0 found, cmd=0x{cmd:02X}, len={length}, but incomplete"

        # Validate checksum
        msg = response[idx : idx + expected_len]
        calc_checksum = 0
        for b in msg[:-1]:
            calc_checksum ^= b
        actual_checksum = msg[-1]

        if calc_checksum == actual_checksum:
            return True, f"✓✓✓ VALID! Cmd=0x{cmd:02X}, Len={length}, Checksum OK"
        else:
            return (
                False,
                f"0xC0 found, cmd=0x{cmd:02X}, checksum mismatch (0x{actual_checksum:02X} vs 0x{calc_checksum:02X})",
            )

    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    print("=" * 80)
    print("NIBE HEAT PUMP RS485 DIAGNOSTIC TOOL")
    print("=" * 80)
    print(f"Port: {SERIAL_PORT}")
    print(
        f"Testing {len(BAUD_RATES)} baud rates × {len(PARITIES)} parity modes = {len(BAUD_RATES) * len(PARITIES)} combinations"
    )
    print("=" * 80)
    print()

    results = []

    for baudrate in BAUD_RATES:
        print(f"\n{baudrate} baud:")
        print("-" * 80)

        for parity_name, parity_val in PARITIES.items():
            print(f"  {parity_name:6s} parity: ", end="", flush=True)

            success, message = test_configuration(baudrate, parity_val, parity_name)
            print(message)

            if success:
                results.append(
                    {"baudrate": baudrate, "parity": parity_name, "message": message}
                )

    # Summary
    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)

    if results:
        print("\n✓✓✓ FOUND WORKING CONFIGURATION(S):\n")
        for idx, result in enumerate(results, 1):
            print(f"{idx}. Baudrate: {result['baudrate']}, Parity: {result['parity']}")
            print(f"   {result['message']}")
            print()

        print("=" * 80)
        print("UPDATE YOUR CODE WITH THESE SETTINGS:")
        print("=" * 80)
        best = results[0]
        print(f"  baudrate={best['baudrate']}")
        print(f"  parity=serial.PARITY_{best['parity']}")
        print("=" * 80)
    else:
        print("\n✗ NO WORKING CONFIGURATION FOUND\n")
        print("Possible issues:")
        print("  1. RCU is still connected/powered (disconnect completely)")
        print("  2. Wrong physical wiring (check A/B pins)")
        print("  3. Pump is not in RS485 mode")
        print("  4. USB-RS485 adapter issue")
        print("  5. Pump requires specific initialization sequence")
        print("\nTroubleshooting:")
        print("  • Power cycle the pump")
        print("  • Try swapping A and B wires")
        print("  • Check adapter LED for activity")
        print("  • Verify with multimeter: ~2-3V between A and B when idle")
        print("=" * 80)


if __name__ == "__main__":
    main()
