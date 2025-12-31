"""
Nibe 360P Heat Pump RS-485 Communication - ACTIVE REQUEST MODE

CRITICAL: Based on Swedish forum elektronikforumet.com findings:
- Baudrate: 19200 (NOT 9600!)
- Format: 9-bit mode using MARK/SPACE parity
- Custom Nibe protocol (NOT standard Modbus)

This version ACTIVELY REQUESTS data from the pump by sending read commands.

Protocol for reading:
1. Send request with parameter index
2. Wait for response with value
3. Parse and display result

Note: The 360P protocol is primarily master-initiated. This attempts to request data
by emulating what the RCU would do when requesting a parameter.
"""

import serial
import struct
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Register:
    """Parameter definition for Nibe 360P"""

    index: int  # Parameter index (0x01, 0x02, etc.)
    name: str
    size: int  # Bytes: 1 or 2
    factor: float = 1.0  # Division factor for value
    unit: str = ""
    writable: bool = False


class Nibe360PProtocol:
    """Handles Nibe 360P custom protocol"""

    CMD_DATA = 0xC0
    MASTER_ADDR = 0x24
    RCU_ADDR = 0x14
    ACK = 0x06
    ENQ = 0x05
    NAK = 0x15
    ETX = 0x03

    @staticmethod
    def calc_checksum(data: List[int]) -> int:
        """Calculate XOR checksum"""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    @staticmethod
    def build_read_request(param_index: int) -> bytes:
        """
        Build a read request packet
        Format: ENQ to indicate we want to send data
        """
        return bytes([Nibe360PProtocol.ENQ])

    @staticmethod
    def parse_data_packet(data: bytes) -> Optional[Dict]:
        """
        Parse data packet from pump
        Format: C0 00 24 <len> [00 <idx> <val>...] <checksum>
        """
        if len(data) < 6:
            logger.debug(f"Packet too short: {len(data)} bytes")
            return None

        if data[0] != Nibe360PProtocol.CMD_DATA:
            logger.debug(f"Wrong start byte: {data[0]:02X} (expected C0)")
            return None

        if data[1] != 0x00:
            logger.debug(f"Wrong second byte: {data[1]:02X} (expected 00)")
            return None

        sender = data[2]
        length = data[3]

        # Check if we have enough data
        expected_size = length + 5  # C0 + 00 + sender + len + data + checksum
        if len(data) < expected_size:
            logger.debug(f"Incomplete packet: {len(data)} < {expected_size}")
            return None

        # Verify checksum
        checksum_received = data[expected_size - 1]
        checksum_calc = Nibe360PProtocol.calc_checksum(data[2 : expected_size - 1])

        if checksum_received != checksum_calc:
            logger.warning(
                f"Checksum mismatch: {checksum_received:02X} != {checksum_calc:02X}"
            )
            return None

        # Parse parameters
        parameters = {}
        payload = data[4 : 4 + length - 1]  # Exclude checksum from length

        i = 0
        while i < len(payload):
            if payload[i] != 0x00:
                logger.debug(
                    f"Expected 00 separator at position {i}, got {payload[i]:02X}"
                )
                break

            if i + 1 >= len(payload):
                break

            param_index = payload[i + 1]

            # Assume 2 bytes for temperature parameters
            if i + 3 < len(payload):
                value_low = payload[i + 2]
                value_high = payload[i + 3]
                value = (value_high << 8) | value_low

                # Handle signed values
                if value >= 32768:
                    value = value - 65536

                parameters[param_index] = value
                i += 4  # 00 + index + 2 value bytes
            else:
                break

        return {"sender": sender, "parameters": parameters}


class Nibe360PHeatPump:
    """
    Nibe 360P Heat Pump - Active Request Mode

    Sends read requests to the pump and waits for responses.
    Uses 9-bit mode via MARK/SPACE parity switching.
    """

    def __init__(self, port: str, parameters: Optional[List[Register]] = None):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.parameters: Dict[int, Register] = {}
        self.parameter_values: Dict[int, float] = {}

        if parameters:
            for param in parameters:
                self.parameters[param.index] = param

    def connect(self) -> bool:
        """Connect to the heat pump"""
        try:
            # Use MARK parity for receiving (9th bit detection)
            self.serial = serial.Serial(
                port=self.port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_MARK,  # 9-bit mode: MARK parity
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,  # 2 second timeout for reads
            )
            logger.info(
                f"✅ Connected to {self.port} at 19200 baud (9-bit mode: MARK parity)"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the heat pump"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected")

    def _send_with_space_parity(self, data: bytes):
        """Send data with SPACE parity (9th bit = 0)"""
        if self.serial:
            # Switch to Space parity for sending data
            self.serial.parity = serial.PARITY_SPACE
            self.serial.write(data)
            self.serial.flush()
            # Switch back to Mark parity for receiving
            self.serial.parity = serial.PARITY_MARK
            logger.debug(f"Sent: {data.hex(' ').upper()}")

    def capture_bus_traffic(self, duration: float = 10.0):
        """
        Capture and display raw bus traffic to understand the protocol
        """
        logger.info(f"\n📡 Capturing bus traffic for {duration} seconds...")
        logger.info("Looking for patterns in the data...\n")

        start_time = time.time()
        buffer = bytearray()
        byte_count = 0

        while time.time() - start_time < duration:
            if self.serial.in_waiting > 0:
                byte = self.serial.read(1)
                buffer.extend(byte)
                byte_count += 1

                # Print bytes in rows of 16
                if byte_count % 16 == 1:
                    print(f"\n{time.time() - start_time:06.2f}s: ", end="")
                print(f"{byte[0]:02X} ", end="", flush=True)

            time.sleep(0.001)

        print("\n\n" + "=" * 70)
        print(f"  Captured {byte_count} bytes")
        print("=" * 70)

        # Analyze for patterns
        if len(buffer) > 0:
            print(f"\n📊 Analysis:")
            print(f"  - Most common byte: 0x{max(set(buffer), key=buffer.count):02X}")
            print(f"  - Unique bytes: {len(set(buffer))}")

            # Look for 0x00 0x14 pattern
            count_00_14 = sum(
                1
                for i in range(len(buffer) - 1)
                if buffer[i] == 0x00 and buffer[i + 1] == 0x14
            )
            print(f"  - Found '00 14' pattern: {count_00_14} times")

            # Look for C0 (data packet start)
            count_c0 = buffer.count(0xC0)
            print(f"  - Found 'C0' (data start): {count_c0} times")

            # Show first 100 bytes in hex
            print(f"\n📝 First 100 bytes:")
            for i in range(min(100, len(buffer))):
                if i % 16 == 0:
                    print(f"\n{i:04d}: ", end="")
                print(f"{buffer[i]:02X} ", end="")
            print("\n")

        return buffer

    def _wait_for_addressing(self, timeout: float = 5.0) -> bool:
        """
        Wait for the pump to address us (0x00 0x14)
        Returns True if addressed, False if timeout
        """
        logger.debug("⏳ Waiting for pump to address RCU (0x00 0x14)...")
        start_time = time.time()
        buffer = bytearray()

        while time.time() - start_time < timeout:
            if self.serial.in_waiting > 0:
                byte = self.serial.read(1)
                buffer.extend(byte)
                logger.debug(f"Received byte: {byte.hex().upper()}")

                # Look for addressing sequence
                if len(buffer) >= 2:
                    if buffer[-2] == 0x00 and buffer[-1] == Nibe360PProtocol.RCU_ADDR:
                        logger.info("✅ RCU addressed by pump!")
                        return True

                # Keep buffer manageable
                if len(buffer) > 100:
                    buffer = buffer[-50:]

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for addressing")
        logger.info(f"\n📋 Captured bytes: {' '.join(f'{b:02X}' for b in buffer[:50])}")
        return False

    def _read_response(self, timeout: float = 3.0) -> Optional[Dict]:
        """Read and parse response packet from pump"""
        logger.debug("📥 Reading response from pump...")
        start_time = time.time()
        buffer = bytearray()

        while time.time() - start_time < timeout:
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                buffer.extend(data)
                logger.debug(f"Buffer: {buffer.hex(' ').upper()}")

                # Look for start of data packet (C0)
                if Nibe360PProtocol.CMD_DATA in buffer:
                    # Find C0
                    idx = buffer.index(Nibe360PProtocol.CMD_DATA)
                    buffer = buffer[idx:]  # Remove everything before C0

                    # Check if we have length byte
                    if len(buffer) >= 4:
                        length = buffer[3]
                        packet_size = length + 5

                        # Wait for complete packet
                        if len(buffer) >= packet_size:
                            packet = bytes(buffer[:packet_size])
                            logger.info(
                                f"📦 Complete packet received: {packet.hex(' ').upper()}"
                            )

                            # Parse it
                            parsed = Nibe360PProtocol.parse_data_packet(packet)
                            if parsed:
                                return parsed
                            else:
                                logger.warning("⚠️ Failed to parse packet")
                                buffer = buffer[packet_size:]  # Try next packet

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for response")
        return None

    def read_parameter(self, param_index: int) -> Optional[float]:
        """
        Read a parameter from the pump

        Returns: Parameter value or None if failed
        """
        if param_index not in self.parameters:
            logger.error(f"❌ Parameter {param_index:02X} not defined")
            return None

        param = self.parameters[param_index]
        logger.info(f"\n{'=' * 70}")
        logger.info(f"📖 Reading Parameter {param_index:02X}: {param.name}")
        logger.info(f"{'=' * 70}")

        # Step 1: Wait for pump to address us
        if not self._wait_for_addressing():
            logger.error("❌ Pump did not address RCU")
            return None

        # Step 2: Send ENQ to indicate we want to send data (request parameter)
        logger.info("📤 Sending ENQ (we have data to send)...")
        self._send_with_space_parity(bytes([Nibe360PProtocol.ENQ]))

        time.sleep(0.1)  # Small delay

        # Step 3: Wait for pump's response with data
        response = self._read_response()

        if not response:
            logger.error("❌ No response received")
            return None

        # Step 4: Extract parameter value
        if param_index in response["parameters"]:
            raw_value = response["parameters"][param_index]
            actual_value = raw_value / param.factor

            logger.info(f"✅ Success!")
            logger.info(f"   Raw value: {raw_value}")
            logger.info(f"   Actual value: {actual_value} {param.unit}")

            self.parameter_values[param_index] = actual_value
            return actual_value
        else:
            logger.warning(
                f"⚠️ Parameter {param_index:02X} not in response. "
                f"Received: {list(response['parameters'].keys())}"
            )
            return None

    def get_value(self, param_index: int) -> Optional[float]:
        """Get cached parameter value"""
        return self.parameter_values.get(param_index)


# Parameter definitions for Nibe 360P
NIBE_360P_PARAMETERS = [
    Register(0x00, "CPU ID", 1, 1.0, "", False),
    Register(0x01, "Outdoor Temperature", 2, 10.0, "°C", False),
    Register(0x02, "Hot Water Temperature", 2, 10.0, "°C", False),
    Register(0x03, "Exhaust Air Temperature", 2, 10.0, "°C", False),
    Register(0x04, "Extract Air Temperature", 2, 10.0, "°C", False),
    Register(0x05, "Evaporator Temperature", 2, 10.0, "°C", False),
    Register(0x06, "Supply Temperature", 2, 10.0, "°C", False),
    Register(0x07, "Return Temperature", 2, 10.0, "°C", False),
    Register(0x08, "Compressor Temperature", 2, 10.0, "°C", False),
    Register(0x09, "Electric Heater Temperature", 2, 10.0, "°C", False),
    Register(0x0B, "Heat Curve Slope", 1, 1.0, "", True),
    Register(0x0C, "Heat Curve Offset", 1, 1.0, "°C", True),
]


def main():
    """Test reading parameters"""
    import sys

    SERIAL_PORT = "/dev/ttyUSB0"  # Linux USB-RS485 adapter

    print("\n" + "=" * 70)
    print("  Nibe 360P Heat Pump - Protocol Analyzer")
    print("=" * 70)
    print()
    print("Options:")
    print("  1) Capture bus traffic (see what's happening)")
    print("  2) Try to read parameter 0x01")
    print()

    choice = input("Choose option [1/2] (default: 1): ").strip() or "1"

    print()
    print(f"Serial Port: {SERIAL_PORT}")
    print("Baudrate: 19200 baud, 9-bit mode (MARK parity)")
    print()

    # Create pump instance
    pump = Nibe360PHeatPump(SERIAL_PORT, parameters=NIBE_360P_PARAMETERS)

    if not pump.connect():
        print("❌ Failed to connect!")
        print("\nTroubleshooting:")
        print("  1. Check serial port: ls /dev/ttyUSB*")
        print("  2. Check permissions: sudo chmod 666 /dev/ttyUSB0")
        print("  3. Verify RS-485 wiring: A→A, B→B, GND→GND")
        return

    try:
        if choice == "1":
            # Capture mode - see what's on the bus
            print("\n" + "=" * 70)
            print("  BUS TRAFFIC CAPTURE MODE")
            print("=" * 70)
            print()
            print("This will show you ALL bytes on the RS-485 bus.")
            print("Look for patterns, repeated sequences, or familiar bytes.")
            print("\nPress Ctrl+C to stop early...\n")
            time.sleep(2)

            buffer = pump.capture_bus_traffic(duration=15.0)

            print("\n" + "=" * 70)
            print("  Next Steps:")
            print("=" * 70)
            print("Look at the captured data above:")
            print("  - Do you see any repeating patterns?")
            print("  - Do you see 0x00 0x14 (RCU addressing)?")
            print("  - Do you see 0xC0 packets (data frames)?")
            print("  - What are the most common bytes?")
            print()
            print("This will help us understand the actual protocol!")

        else:
            # Active read mode
            print("\n" + "=" * 70)
            print("  ACTIVE READ MODE")
            print("=" * 70)
            print("  Attempting to read Parameter 0x01 (Outdoor Temperature)")
            print("=" * 70)
            print()

            value = pump.read_parameter(0x01)

            if value is not None:
                print("\n" + "🎉" * 35)
                print(f"  SUCCESS! Outdoor Temperature = {value}°C")
                print("🎉" * 35)
            else:
                print("\n" + "❌" * 35)
                print("  FAILED to read parameter")
                print("❌" * 35)
                print("\nTry option 1 first to see what's on the bus!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        pump.disconnect()
        print("\n✅ Disconnected\n")


if __name__ == "__main__":
    main()
