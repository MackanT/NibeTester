"""
Nibe 360P Heat Pump RS-485 Communication

Protocol:
- Baudrate: 19200
- Format: 9-bit mode using MARK/SPACE parity
- Custom Nibe protocol (NOT standard Modbus)

This implementation passively reads parameters by responding to the pump's polling.
"""

import serial
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
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
    menu_structure: str = ""  # Optional menu structure
    min_value: int = None  # Optional min value
    max_value: int = None  # Optional max value
    step_size: int = None  # Optional step size


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
    def parse_data_packet(
        data: bytes, param_defs: Dict[int, Register] = None
    ) -> Optional[Dict]:
        """
        Parse data packet from pump
        Format: C0 00 24 <len> [00 <idx> <val>...] <checksum>

        param_defs: Dictionary of parameter definitions to determine size (1 or 2 bytes)
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

        checksum_received = data[expected_size - 1]
        checksum_calc = Nibe360PProtocol.calc_checksum(data[0 : expected_size - 1])

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

            # Determine parameter size (1 or 2 bytes)
            param_size = 2  # Default to 2 bytes
            if param_defs and param_index in param_defs:
                param_size = param_defs[param_index].size

            # Parse value based on size
            if param_size == 1:
                # Single byte parameter
                if i + 2 < len(payload):
                    value = payload[i + 2]
                    # Handle signed byte values
                    if value >= 128:
                        value = value - 256
                    parameters[param_index] = value
                    i += 3  # 00 + index + 1 value byte
                else:
                    break
            else:
                # Two byte parameter (HIGH byte first, LOW byte second)
                if i + 3 < len(payload):
                    value_high = payload[i + 2]
                    value_low = payload[i + 3]
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
    Nibe 360P Heat Pump Interface

    Passively reads parameters by responding to the pump's addressing.
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
        logger.info(f"📡 Capturing bus traffic for {duration} seconds...")
        logger.info("Looking for patterns in the data...")

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
            print("\n📊 Analysis:")
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
            print("\n📝 First 100 bytes:")
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

                            # Parse it - pass parameter definitions for size info
                            parsed = Nibe360PProtocol.parse_data_packet(
                                packet, self.parameters
                            )
                            if parsed:
                                return parsed
                            else:
                                logger.warning("⚠️ Failed to parse packet")
                                buffer = buffer[packet_size:]  # Try next packet

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for response")
        return None

    def read_parameters_once(self) -> Dict[int, float]:
        """
        Read one complete set of parameters from the pump.

        Protocol flow:
        1. Wait for addressing: *00 *14 (bytes with 9th bit = 1)
        2. Send ACK (0x06) to accept data
        3. Receive data packet: C0 00 24 <len> [00 <param> <value>...] <csum>
        4. Send ACK (0x06) to confirm receipt
        5. Receive *03 (ETX) to end transmission
        6. Repeat until we have collected all parameters

        Returns: Dictionary of parameter_index -> value
        """
        logger.info(f"\n{'=' * 70}")
        logger.info("📖 Reading Parameters from Pump")
        logger.info(f"{'=' * 70}")
        logger.info("Collecting all parameters... This may take a few cycles.\n")

        cycles_with_new_data = 0
        max_cycles_without_new = 5  # Stop after 5 cycles with no new parameters

        while cycles_with_new_data < max_cycles_without_new:
            # Step 1: Wait for pump to address RCU
            if not self._wait_for_addressing(timeout=15.0):
                logger.warning("Timeout waiting for pump. Stopping.")
                break

            # Step 2: Send ACK (we're ready to receive data)
            logger.info("📤 Sending ACK (ready to receive)...")
            self._send_with_space_parity(bytes([Nibe360PProtocol.ACK]))

            time.sleep(0.05)  # Small delay for pump to prepare data

            # Step 3: Receive data packet
            response = self._read_response(timeout=2.0)

            if response:
                # Check if we got any new parameters
                new_params = 0
                for param_idx in response["parameters"].keys():
                    if param_idx not in self.parameter_values:
                        new_params += 1

                if new_params > 0:
                    cycles_with_new_data = 0  # Reset counter
                    logger.info(
                        f"✅ Received {len(response['parameters'])} parameters ({new_params} new)"
                    )
                else:
                    cycles_with_new_data += 1
                    logger.info(
                        f"✅ Received {len(response['parameters'])} parameters (all seen before)"
                    )

                # Store parameters
                for param_idx, raw_value in response["parameters"].items():
                    if param_idx in self.parameters:
                        param = self.parameters[param_idx]
                        actual_value = raw_value / param.factor
                        self.parameter_values[param_idx] = actual_value
                        logger.debug(
                            f"   [{param_idx:02X}] {param.name}: {actual_value:.1f} {param.unit}"
                        )

                # Step 4: Send ACK to confirm receipt
                logger.info("📤 Sending ACK (data received OK)...")
                self._send_with_space_parity(bytes([Nibe360PProtocol.ACK]))

                time.sleep(0.05)

                # Step 5: Wait for ETX
                etx_start = time.time()
                while time.time() - etx_start < 1.0:
                    if self.serial.in_waiting > 0:
                        byte = self.serial.read(1)
                        if byte[0] == Nibe360PProtocol.ETX or byte[0] == 0x03:
                            logger.debug("✅ Received ETX")
                            break
                    time.sleep(0.01)
            else:
                logger.warning("⚠️ No data received")
                cycles_with_new_data += 1

        logger.info(f"\n{'=' * 70}")
        logger.info(
            f"📊 Collection Complete: {len(self.parameter_values)} unique parameters"
        )
        logger.info(f"{'=' * 70}")

        return self.parameter_values.copy()

    def get_value(self, param_index: int) -> Optional[float]:
        """Get cached parameter value"""
        return self.parameter_values.get(param_index)

    def get_all_values(self) -> Dict[int, float]:
        """Get all cached parameter values"""
        return self.parameter_values.copy()


# Parameter definitions for Nibe 360P
NIBE_360P_PARAMETERS = [
    Register(0x00, "Produktkod", 1, 1.0, "", False, ""),
    Register(0x01, "Utetemperatur", 2, 10.0, "°C", False, "M4.0"),
    Register(0x02, "Temperatur VV-givare", 2, 10.0, "°C", False, "M1.0"),
    Register(0x03, "Avluftstemperatur", 2, 10.0, "°C", False, "M5.1"),
    Register(0x04, "Frånluftstemperatur", 2, 10.0, "°C", False, "M5.2"),
    Register(0x05, "Förångartemperatur", 2, 10.0, "°C", False, "M5.0"),
    Register(0x06, "Framledningstemp.", 2, 10.0, "°C", False, "M2.0"),
    Register(0x07, "Returtemperatur", 2, 10.0, "°C", False, "M2.6"),
    Register(0x08, "Temperatur kompressorgivare", 2, 10.0, "°C", False, "M1.1"),
    Register(0x09, "Temperatur elpatrongivare", 2, 10.0, "°C", False, "M1.2"),
    Register(0x0B, "Kurvlutning", 1, 1.0, "", True, "M2.1", -1, 15, 1),
    Register(0x0C, "Förskjutning värmekurva", 1, 1.0, "", False, "M2.2", -10, 10),
    Register(0x0D, "Beräknad framledningstemp.", 2, 1.0, "°C", False, "M2.0"),
    Register(0x13, "Kompressor", 1, 1.0, "", False, ""),  # Bitmask!
    # Register(0x13, "Cirkulationspump 1", 1, 1.0, "", False, "M9.1.4"), # Do something with bitmask!
    Register(
        0x14, "Tillsatsvärme", 1, 1.0, "", False, ""
    ),  # Do something with bitmask!
    # Register(0x14, "Driftläge säsong", 1, 1.0, "", True, ""), # Do something with bitmask!
    # Register(0x14, "Elpanna", 1, 1.0, "", True, "M9.1.1"),
    # Register(0x14, "Fläkthastighet", 1, 1.0, "", True, "", 0, 3), ##TODO menu
    # Register(0x14, "Avfrostning", 1, 1.0, "", True, ""),
    Register(0x15, "Driftläge auto", 1, 1.0, "", True, "M8.2.1"),
    # Register(0x15, "Extra varmvatten", 1, 1.0, "", True, "", 0, 4), ## Finns 5-7, men bara på låtsas
    Register(0x16, "Högtryckslarm", 1, 1.0, "", False, ""),
    # Register(0x16, "Lågtryckslarm", 1, 1.0, "", False, ""),
    # Register(0x16, "Temperaturbegränsarlarm", 1, 1.0, "", False, ""),
    # Register(0x16, "Filterlarm", 1, 1.0, "", False, ""),
    # Register(0x16, "Givarfel", 1, 1.0, "", False, ""),
    # Register(0x16, "Frånluftstemperaturslarm", 1, 1.0, "", False, ""),
    Register(0x17, "Strömförbrukning L1", 1, 10.0, "A", False, "M8.3.3"),
    Register(0x18, "Strömförbrukning L2", 1, 10.0, "A", False, "M8.3.4"),
    Register(0x19, "Strömförbrukning L3", 1, 10.0, "A", False, "M8.3.5"),
    Register(0x1A, "Fabriksinställning", 1, 1.0, "", True, "M9.1.6"),
    Register(0x1B, "Antal starter kompressor", 1, 1.0, "", False, "M5.4"),
    Register(0x1C, "Drifttid kompressor", 1, 1.0, "h", False, "M5.5"),
    Register(0x1D, "Tidfaktor elpatron", 1, 1.0, "", False, "M9.1.8"),
    Register(0x1E, "Maxtemperatur framledning", 1, 1.0, "°C", True, "M2.4", 10, 65),
    Register(0x1F, "Mintemperatur framledning", 1, 1.0, "°C", True, "M2.3", 10, 65),
    Register(0x22, "Kompensering yttre", 1, 1.0, "", True, "M2.5", -10, 10),
    Register(0x24, "Intervall per. extra VV", 1, 1.0, "dygn", True, "M1.3", 0, 90),
    Register(0x25, "Starta om FIGHTER360P", 1, 1.0, "", True, ""),
    # Register(0x25, "Extern larmsignal 1 (RCU DI 1)", 1, 1.0, "", False, ""),
    # Register(0x25, "Extern larmsignal 2 (RCU DI 2)", 1, 1.0, "", False, ""),
    Register(0x26, "RCU förskjutning 1 (Reg1)", 1, 1.0, "", True, "M2.7", -10, 10),
    Register(0x28, "Larmnivå frånluftstemperatur", 1, 1.0, "°C", True, "M5.6", 0, 20),
    Register(0x29, "Klocka: år", 1, 1.0, "", False, ""),
    Register(0x2A, "Klocka: månad", 1, 1.0, "", False, ""),
    Register(0x2B, "Klocka: dag", 1, 1.0, "", False, ""),
    Register(0x2C, "Klocka: timma", 1, 1.0, "", False, ""),
    Register(0x2D, "Klocka: minut", 1, 1.0, "", False, ""),
    Register(0x2E, "Klocka: sekund", 1, 1.0, "", False, ""),
]


def main():
    """Main program"""
    SERIAL_PORT = "/dev/ttyUSB0"

    print("\n" + "=" * 70)
    print("  Nibe 360P Heat Pump Reader")
    print("=" * 70)
    print()
    print("Options:")
    print("  1) Read parameters (normal operation)")
    print("  9) Capture bus traffic (diagnostic mode)")
    print()

    choice = input("Choose option [1/9] (default: 1): ").strip() or "1"

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
        if choice == "9":
            # Diagnostic mode
            print("\n" + "=" * 70)
            print("  BUS TRAFFIC CAPTURE")
            print("=" * 70)
            print("\nCapturing raw RS-485 bus data...")
            print("Press Ctrl+C to stop...\n")
            time.sleep(2)

            pump.capture_bus_traffic(duration=15.0)

        else:
            # Normal operation
            print("\n" + "=" * 70)
            print("  PARAMETER READING")
            print("=" * 70)
            print("\nReading parameters from heat pump...")
            print("This will collect data from multiple cycles until complete.")
            print("\nPress Ctrl+C to stop early...\n")
            time.sleep(2)

            values = pump.read_parameters_once()

            if values:
                print("\n" + "=" * 35)
                print(f"  SUCCESS! Captured {len(values)} parameters:")
                print("=" * 35)
                print()
                for idx in sorted(values.keys()):
                    param = pump.parameters[idx]
                    print(
                        f"  [{idx:02X}] {param.name:.<35} {values[idx]:>8.1f} {param.unit:<5} {param.menu_structure}"
                    )
                print()
            else:
                print("\n❌ No parameters received!")
                print("Try option 1 to diagnose the issue.")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")

        # Show what we captured so far
        values = pump.get_all_values()
        if values:
            print("\n📊 Partial Results:")
            print("=" * 70)
            for idx in sorted(values.keys()):
                if idx in pump.parameters:
                    param = pump.parameters[idx]
                    print(f"  [{idx:02X}] {param.name}: {values[idx]} {param.unit}")
    finally:
        pump.disconnect()
        print("\n✅ Disconnected\n")


if __name__ == "__main__":
    main()
