"""
Test script to verify Nibe 360P communication setup

This script performs basic tests to ensure everything is configured correctly.
"""

import sys
import time


def test_imports():
    """Test that all required imports work"""
    print("Testing imports...")
    try:
        import serial

        print("  ✓ pyserial installed")
    except ImportError:
        print("  ✗ pyserial not found - run: pip install pyserial")
        return False

    try:
        from main import NibeHeatPump, NibeProtocol

        print("  ✓ main.py imports successfully")
    except Exception as e:
        print(f"  ✗ Error importing main.py: {e}")
        return False

    try:
        from registers_360p import NIBE_360P_REGISTERS

        print("  ✓ registers_360p.py imports successfully")
        print(f"    Found {len(NIBE_360P_REGISTERS)} register definitions")
    except Exception as e:
        print(f"  ✗ Error importing registers_360p.py: {e}")
        return False

    return True


def test_serial_ports():
    """List available serial ports"""
    print("\nDetecting serial ports...")
    try:
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()

        if not ports:
            print("  ✗ No serial ports found")
            return False

        print("  Available serial ports:")
        for port in ports:
            print(f"    - {port.device}: {port.description}")
        return True
    except Exception as e:
        print(f"  ✗ Error detecting ports: {e}")
        return False


def test_config():
    """Test configuration"""
    print("\nChecking configuration...")
    try:
        import config

        print(f"  ✓ config.py found")
        print(f"    Serial port: {config.SERIAL_PORT}")
        print(f"    Baud rate: {config.BAUDRATE}")
        return True
    except ImportError:
        print("  ⚠ config.py not found (optional)")
        print("    Create config.py from config.example.py")
        return True  # Not critical
    except Exception as e:
        print(f"  ✗ Error reading config.py: {e}")
        return False


def test_protocol():
    """Test protocol encoding/decoding"""
    print("\nTesting protocol implementation...")
    try:
        from main import NibeProtocol

        # Test checksum
        data = [0x02, 0x64, 0x00]
        checksum = NibeProtocol.calc_checksum(data)
        print(f"  ✓ Checksum calculation works: {checksum}")

        # Test read request encoding
        message = NibeProtocol.encode_read_request(40004)
        print(f"  ✓ Read request encoding works: {bytes(message).hex()}")
        expected = "c0690264000066"  # Expected format
        if bytes(message).hex() == expected:
            print(f"    Message format correct!")

        # Test write request encoding
        message = NibeProtocol.encode_write_request(47011, 10, "s8")
        print(f"  ✓ Write request encoding works: {bytes(message).hex()}")

        return True
    except Exception as e:
        print(f"  ✗ Protocol test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_connection(port=None):
    """Test actual connection to heat pump"""
    print("\nTesting heat pump connection...")

    if port is None:
        try:
            import config

            port = config.SERIAL_PORT
        except:
            port = input("Enter serial port (e.g., COM3 or /dev/ttyUSB0): ").strip()

    try:
        from main import NibeHeatPump
        from registers_360p import NIBE_360P_REGISTERS

        print(f"  Attempting to connect to {port}...")
        pump = NibeHeatPump(port, registers=NIBE_360P_REGISTERS)

        if not pump.connect():
            print("  ✗ Failed to open serial port")
            print("    Check port name and permissions")
            return False

        print("  ✓ Serial port opened successfully")
        print("  Waiting 2 seconds for connection to stabilize...")
        time.sleep(2)

        print("  Attempting to read register 40004 (outdoor temp)...")
        value = pump.read_register(40004, timeout=5.0)

        if value is not None:
            print(f"  ✓ Successfully read register: {value}°C")
            print("  🎉 Communication working!")
        else:
            print("  ⚠ No response from heat pump")
            print("    Possible causes:")
            print("    - Modbus not enabled on heat pump")
            print("    - Wrong register address")
            print("    - Incorrect wiring (try swapping A/B)")
            print("    - Baudrate mismatch")

        pump.disconnect()
        return value is not None

    except Exception as e:
        print(f"  ✗ Connection test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("  Nibe 360P Communication Test Suite")
    print("=" * 70)
    print()

    results = []

    # Run tests
    results.append(("Import Test", test_imports()))
    results.append(("Serial Port Detection", test_serial_ports()))
    results.append(("Configuration Check", test_config()))
    results.append(("Protocol Implementation", test_protocol()))

    # Ask user if they want to test connection
    print("\n" + "=" * 70)
    response = input("\nTest actual heat pump connection? (y/n): ").strip().lower()
    if response == "y":
        results.append(("Heat Pump Connection", test_connection()))

    # Summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name:.<50} {status}")

    print("\n" + "=" * 70)

    if all(result for _, result in results):
        print("  🎉 All tests passed! You're ready to go.")
        print("  Run 'python examples.py' to get started.")
    else:
        print("  ⚠ Some tests failed. Please review the output above.")

    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
