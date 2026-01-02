"""
Nibe Heat Pump RS-485 Communication

Protocol:
- Baudrate: Parametrizeable (F360P uses 19200)
- Format: 9-bit mode using MARK/SPACE parity
- Custom Nibe protocol (NOT standard Modbus)

This implementation passively reads parameters by responding to the pump's polling.
"""

import serial
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import logging
import yaml
import sys

FULL_LINE = 53
TIMEOUT = 30

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BitField:
    """Bit field definition for registers with multiple boolean or multi-bit flags"""

    name: str  # Name of the bit field (e.g., "Kompressor")
    mask: int  # Bitmask to extract the bits (e.g., 0x02, 0x07, 0x40)
    sort_order: int  # Display order (used for sorting)
    writable: bool  # Whether this bit field can be written to
    value_map: Optional[Dict[int, str]] = (
        None  # Optional mapping of integer values to text (e.g., {0: "OFF", 1: "ON"})
    )
    unit: str = ""  # Unit for the value (e.g., "°C", "%")
    min_value: Optional[int] = None  # Minimum value
    max_value: Optional[int] = None  # Maximum value
    step_size: Optional[int] = None  # Step size for incrementing
    menu_structure: str = ""  # Menu structure location (e.g., "M2.1")


@dataclass
class Register:
    """Register definition for Nibe communication"""

    index: int  # Parameter index (0x01, 0x02, etc.)
    name: str
    size: int  # Bytes: 1 or 2
    factor: float = 1.0  # Division factor for value
    unit: str = ""
    writable: bool = False
    data_type: Optional[str] = None  # Required if writable: s8, u8, s16, u16, s32, u32
    menu_structure: str = ""  # Optional menu structure
    min_value: int = None  # Optional min value
    max_value: int = None  # Optional max value
    step_size: int = None  # Optional step size
    bit_fields: Optional[List[BitField]] = (
        None  # Optional bit fields for bitmask registers
    )


@dataclass
class Pump:
    """Parameter definition for the heat pump"""

    model: str
    name: str
    baudrate: int  # 9600, 19200, etc.
    bit_mode: int  # 8 or 9
    parity: str  # "MARK" or "SPACE"
    # Protocol specific bytes (integers)
    cmd_data: int  # 0xC0
    master_addr: int  # 0x24
    rcu_addr: int  # 0x14
    ack: int  # 0x06
    enq: int  # 0x05
    nak: int  # 0x15
    etx: int  # 0x03


def _parse_byte_val(v, default: int):
    """Helper: accept int or hex-string like '0x14' or decimal string and return int."""
    if v is None:
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            if v.startswith("0x") or v.startswith("0X"):
                return int(v, 16)
            return int(v)
        except Exception:
            return default
    try:
        return int(v)
    except Exception:
        return default


class NibeProtocol:
    """Handles Nibe heat pump custom protocol"""

    @staticmethod
    def calc_checksum(data: List[int]) -> int:
        """Calculate XOR checksum"""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    @staticmethod
    def parse_data_packet(
        data: bytes,
        param_defs: Dict[int, Register] = None,
        proto: Optional[Pump] = None,
    ) -> Optional[Dict]:
        """
        Parse data packet from pump
        Format: C0 00 24 <len> [00 <idx> <val>...] <checksum>

        param_defs: Dictionary of parameter definitions to determine size (1 or 2 bytes)
        """
        if len(data) < 6:
            logger.debug(f"Packet too short: {len(data)} bytes")
            return None

        if proto is None:
            raise ValueError("Protocol configuration (proto) is required")

        cmd_data = proto.cmd_data

        if data[0] != cmd_data:
            logger.debug(f"Wrong start byte: {data[0]:02X} (expected {cmd_data:02X})")
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
        checksum_calc = NibeProtocol.calc_checksum(data[0 : expected_size - 1])

        logger.info(
            f"Checksum validation: received=0x{checksum_received:02X}, calculated=0x{checksum_calc:02X}"
        )

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


class NibeHeatPump:
    """
    Nibe Heat Pump Interface

    Passively reads parameters by responding to the pump's addressing.
    Uses 9-bit mode via MARK/SPACE parity switching.
    """

    def __init__(
        self,
        port: str,
        parameters: Optional[List[Register]] = None,
        pump_info: Optional[Pump] = None,
    ):
        if not pump_info:
            raise ValueError("Pump configuration (pump_info) is required")

        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.parameters: Dict[int, Register] = {}
        self.parameter_values: Dict[int, float] = {}  # Regular parameter values
        self.bit_field_values: Dict[
            str, int
        ] = {}  # Bit field values (key: "0x13:Kompressor", value: integer 0-7 or boolean 0/1)
        self.pump: Pump = pump_info

        if parameters:
            for param in parameters:
                self.parameters[param.index] = param

    def connect(self) -> bool:
        """Connect to the heat pump"""
        try:
            # Require pump configuration
            if not self.pump:
                raise ValueError("Pump configuration is required")

            baud = self.pump.baudrate
            parity_cfg = self.pump.parity.upper()
            parity = serial.PARITY_MARK if parity_cfg == "MARK" else serial.PARITY_SPACE

            self.serial = serial.Serial(
                port=self.port,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=parity,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5,  # Short timeout to prevent blocking
                inter_byte_timeout=0.1,  # Prevent read() from blocking indefinitely
            )
            logger.info(
                f"✅ Connected to {self.port} at {baud} baud (parity={parity_cfg})"
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
            logger.debug(f"Sent with SPACE: {data.hex(' ').upper()}")

    def _send_with_mark_parity(self, data: bytes):
        """Send data with MARK parity (9th bit = 1)"""
        if self.serial:
            # Use Mark parity for sending data
            self.serial.parity = serial.PARITY_MARK
            self.serial.write(data)
            self.serial.flush()
            # Stay in Mark parity for receiving
            self.serial.parity = serial.PARITY_MARK
            logger.debug(f"Sent with MARK: {data.hex(' ').upper()}")

    def capture_bus_traffic(self, duration: float = 10.0):
        """
        Capture and display raw bus traffic to understand the protocol
        """
        if not self.pump:
            raise ValueError("Pump configuration is required")

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

        print("\n\n" + "=" * FULL_LINE)
        print(f"  Captured {byte_count} bytes")
        print("=" * FULL_LINE)

        # Analyze for patterns
        if len(buffer) > 0:
            print("\n📊 Analysis:")
            print(f"  - Most common byte: 0x{max(set(buffer), key=buffer.count):02X}")
            print(f"  - Unique bytes: {len(set(buffer))}")

            # Look for addressing pattern (0x00 followed by RCU address)
            count_addressing = sum(
                1
                for i in range(len(buffer) - 1)
                if buffer[i] == 0x00 and buffer[i + 1] == self.pump.rcu_addr
            )
            print(
                f"  - Found '00 {self.pump.rcu_addr:02X}' (addressing) pattern: {count_addressing} times"
            )

            # Look for CMD_DATA (data packet start)
            count_cmd = buffer.count(self.pump.cmd_data)
            print(f"  - Found '{self.pump.cmd_data:02X}' (CMD_DATA): {count_cmd} times")

            # Show first 100 bytes in hex
            print("\n📝 First 100 bytes:")
            for i in range(min(100, len(buffer))):
                if i % 16 == 0:
                    print(f"\n{i:04d}: ", end="")
                print(f"{buffer[i]:02X} ", end="")
            print("\n")

        return buffer

    def _wait_for_addressing(self, timeout: float = 5.0, verbose: bool = True) -> bool:
        """
        Wait for the pump to address us (0x00 0x14)
        Returns True if addressed, False if timeout

        Args:
            timeout: Maximum time to wait
            verbose: If False, reduce debug logging (useful during write retries)
        """
        if verbose:
            logger.debug("⏳ Waiting for pump to address RCU (0x00 0x14)...")
        start_time = time.time()
        buffer = bytearray()

        while time.time() - start_time < timeout:
            if self.serial.in_waiting > 0:
                byte = self.serial.read(1)
                buffer.extend(byte)
                if verbose:
                    logger.debug(f"Received byte: {byte.hex().upper()}")

                # Look for addressing sequence
                if len(buffer) >= 2:
                    if buffer[-2] == 0x00 and buffer[-1] == self.pump.rcu_addr:
                        logger.info("✅ RCU addressed by pump!")
                        return True

                # Keep buffer manageable
                if len(buffer) > 100:
                    buffer = buffer[-50:]

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for addressing")
        if verbose:
            logger.info(
                f"\n📋 Captured bytes: {' '.join(f'{b:02X}' for b in buffer[:50])}"
            )
        return False

    def _read_response(self, timeout: float = 3.0) -> Optional[Dict]:
        """Read and parse response packet from pump

        Args:
            timeout: Maximum time to wait for response
        """
        logger.debug("📥 Reading response from pump...")
        start_time = time.time()
        buffer = bytearray()

        while time.time() - start_time < timeout:
            # Read up to 256 bytes at a time (or whatever is available)
            # This prevents blocking on serial.read() with exact byte counts
            data = self.serial.read(256)
            if data:
                buffer.extend(data)
                logger.debug(f"Buffer: {buffer.hex(' ').upper()}")

                # Look for start of data packet (CMD_DATA)
                if self.pump.cmd_data in buffer:
                    cmd_byte = self.pump.cmd_data
                    # Find start
                    idx = buffer.index(cmd_byte)
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

                            # Parse it - pass parameter definitions for size info and pump protocol
                            parsed = NibeProtocol.parse_data_packet(
                                packet, self.parameters, proto=self.pump
                            )
                            if parsed:
                                return parsed
                            else:
                                logger.warning("⚠️ Failed to parse packet")
                                buffer = buffer[packet_size:]  # Try next packet

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for response")
        return None

    def read_parameters_once(self, timeout: int = 10) -> Dict[int, float]:
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
        print(f"\n{'=' * FULL_LINE}")
        print("📖 Reading Parameters from Pump")
        print(f"{'=' * FULL_LINE}")
        print("Collecting all parameters... This may take a few cycles.\n")

        cycles_with_new_data = 0
        max_cycles_without_new = 3  # Stop after 3 cycles with no new parameters
        start_time = time.time()

        while cycles_with_new_data < max_cycles_without_new:
            # Check if we've exceeded maximum time
            if time.time() - start_time > timeout:
                logger.warning(f"⏱️ Maximum read time ({timeout}s) exceeded. Stopping.")
                break

            # Step 1: Wait for pump to address RCU
            if not self._wait_for_addressing(timeout=15.0):
                logger.warning("Timeout waiting for pump. Stopping.")
                break

            # Step 2: Send ACK (we're ready to receive data)
            logger.info("📤 Sending ACK (ready to receive)...")
            self._send_with_space_parity(bytes([self.pump.ack]))

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

                        # Check if this is a bitmask register
                        if param.bit_fields:
                            # Extract individual bit fields
                            for bit_field in param.bit_fields:
                                # Extract the masked value
                                masked_value = raw_value & bit_field.mask
                                # Shift right to get actual value (count trailing zeros in mask)
                                shift = (
                                    bit_field.mask & -bit_field.mask
                                ).bit_length() - 1
                                actual_value = masked_value >> shift

                                key = f"0x{param_idx:02X}:{bit_field.name}"
                                self.bit_field_values[key] = actual_value

                                # Format display value
                                if (
                                    bit_field.value_map
                                    and actual_value in bit_field.value_map
                                ):
                                    display_value = bit_field.value_map[actual_value]
                                else:
                                    display_value = str(actual_value)

                                logger.debug(
                                    f"   [{param_idx:02X}] {bit_field.name}: {display_value} (mask=0x{bit_field.mask:02X}, value={actual_value})"
                                )
                        else:
                            # Regular parameter with factor
                            actual_value = raw_value / param.factor
                            self.parameter_values[param_idx] = actual_value
                            logger.debug(
                                f"   [{param_idx:02X}] {param.name}: {actual_value:.1f} {param.unit}"
                            )

                # Step 4: Send ACK to confirm receipt
                logger.info("📤 Sending ACK (data received OK)...")
                self._send_with_space_parity(bytes([self.pump.ack]))

                time.sleep(0.05)

                # Step 5: Wait for ETX
                etx_start = time.time()
                while time.time() - etx_start < 1.0:
                    if self.serial.in_waiting > 0:
                        byte = self.serial.read(1)
                        if byte[0] == self.pump.etx:
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

    def read_single_parameter(
        self, param_index: int, timeout: float = 10.0
    ) -> Optional[float]:
        """
        Read a single specific parameter from the pump.

        Args:
            param_index: The register index to read (e.g., 0x01)
            timeout: Maximum time to wait for the parameter (seconds)

        Returns:
            The parameter value if found, None if timeout
        """
        print(f"\n{'=' * FULL_LINE}")
        print(f"📖 Reading Parameter 0x{param_index:02X}")
        print(f"{'=' * FULL_LINE}")

        if param_index in self.parameters:
            param = self.parameters[param_index]
            print(f"Parameter: {param.name}")
            print(f"Waiting up to {timeout} seconds...\n")
        else:
            print(f"Warning: Register 0x{param_index:02X} not defined in YAML\n")

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Wait for pump to address RCU
            if not self._wait_for_addressing(timeout=5.0):
                continue

            # Send ACK (we're ready to receive data)
            logger.info("📤 Sending ACK (ready to receive)...")
            self._send_with_space_parity(bytes([self.pump.ack]))
            time.sleep(0.05)

            # Receive data packet
            response = self._read_response(timeout=2.0)

            if response:
                # Check if this packet contains our parameter
                if param_index in response["parameters"]:
                    raw_value = response["parameters"][param_index]

                    if param_index in self.parameters:
                        param = self.parameters[param_index]

                        # Check if this is a bitmask register
                        if param.bit_fields:
                            # Store all bit fields
                            for bit_field in param.bit_fields:
                                masked_value = raw_value & bit_field.mask
                                shift = (
                                    bit_field.mask & -bit_field.mask
                                ).bit_length() - 1
                                actual_value = masked_value >> shift
                                key = f"0x{param_index:02X}:{bit_field.name}"
                                self.bit_field_values[key] = actual_value

                            logger.info(
                                f"✅ Found parameter 0x{param_index:02X} with {len(param.bit_fields)} bit fields"
                            )

                            # Send ACK to confirm receipt
                            self._send_with_space_parity(bytes([self.pump.ack]))
                            time.sleep(0.05)

                            # Wait for ETX to complete protocol cycle
                            etx_start = time.time()
                            while time.time() - etx_start < 1.0:
                                if self.serial.in_waiting > 0:
                                    byte = self.serial.read(1)
                                    if byte[0] == self.pump.etx:
                                        logger.debug("✅ Received ETX")
                                        break
                                time.sleep(0.01)

                            return None  # Bit fields stored separately
                        else:
                            # Regular parameter
                            actual_value = raw_value / param.factor
                            self.parameter_values[param_index] = actual_value
                            logger.info(
                                f"✅ Found parameter 0x{param_index:02X}: {actual_value} {param.unit}"
                            )

                            # Send ACK to confirm receipt
                            self._send_with_space_parity(bytes([self.pump.ack]))
                            time.sleep(0.05)

                            # Wait for ETX to complete protocol cycle
                            etx_start = time.time()
                            while time.time() - etx_start < 1.0:
                                if self.serial.in_waiting > 0:
                                    byte = self.serial.read(1)
                                    if byte[0] == self.pump.etx:
                                        logger.debug("✅ Received ETX")
                                        break
                                time.sleep(0.01)

                            return actual_value
                    else:
                        # Unknown parameter, just store raw value
                        logger.info(
                            f"✅ Found parameter 0x{param_index:02X}: {raw_value} (raw)"
                        )

                        # Send ACK to confirm receipt
                        self._send_with_space_parity(bytes([self.pump.ack]))
                        time.sleep(0.05)

                        # Wait for ETX
                        etx_start = time.time()
                        while time.time() - etx_start < 1.0:
                            if self.serial.in_waiting > 0:
                                byte = self.serial.read(1)
                                if byte[0] == self.pump.etx:
                                    logger.debug("✅ Received ETX")
                                    break
                            time.sleep(0.01)

                        return float(raw_value)
                else:
                    # Parameter not in this packet - complete protocol cycle and try again
                    params_in_packet = ", ".join(
                        f"0x{p:02X}" for p in response["parameters"].keys()
                    )
                    logger.info(
                        f"⏩ Packet has [{params_in_packet}] but not 0x{param_index:02X}, completing cycle..."
                    )
                    self._send_with_space_parity(bytes([self.pump.ack]))
                    time.sleep(0.05)
                    # Don't wait for ETX - move quickly to catch next addressing
        logger.warning(
            f"⏱️ Timeout: Parameter 0x{param_index:02X} not received within {timeout}s"
        )
        return None

    def write_parameter(
        self, param_index: int, value: float, timeout: float = 30.0
    ) -> bool:
        """
        Write a value to a specific parameter.

        Protocol flow:
        1. Wait for addressing: *00 *14
        2. Send ENQ (0x05) instead of ACK to signal write intent
        3. Wait for ACK from pump
        4. Send data packet: C0 00 14 <len> 00 <param> <value> <checksum>
        5. Wait for ACK (success) or NAK (checksum error)
        6. Send ETX to complete

        Args:
            param_index: The register index to write (e.g., 0x01)
            value: The value to write (will be multiplied by factor)
            timeout: Maximum time to wait for write success (seconds)

        Returns:
            True if write successful, False otherwise
        """
        print(f"\n{'=' * FULL_LINE}")
        print(f"✍️  Writing Parameter 0x{param_index:02X}")
        print(f"{'=' * FULL_LINE}")

        # Check if parameter is writable
        if param_index in self.parameters:
            param = self.parameters[param_index]
            if not param.writable:
                logger.error(
                    f"❌ Parameter 0x{param_index:02X} ({param.name}) is not writable!"
                )
                return False

            print(f"Parameter: {param.name}")
            print(
                f"Current value: {self.parameter_values.get(param_index, 'unknown')} {param.unit}"
            )
            print(f"New value: {value} {param.unit}")

            # Convert value using factor and data type
            raw_value = int(value * param.factor)

            # Check bounds if specified
            if param.min_value is not None and raw_value < param.min_value:
                logger.error(f"❌ Value {raw_value} below minimum {param.min_value}")
                return False
            if param.max_value is not None and raw_value > param.max_value:
                logger.error(f"❌ Value {raw_value} above maximum {param.max_value}")
                return False
        else:
            print(f"Warning: Register 0x{param_index:02X} not defined in YAML")
            param = None
            raw_value = int(value)

        print(f"Raw value to write: {raw_value} (0x{raw_value:04X})\n")

        # Wait for pump to address us
        if not self._wait_for_addressing(timeout=5.0):
            logger.error("❌ Pump did not address RCU")
            return False

        # Clear buffer BEFORE sending ENQ (to remove any old data)
        self.serial.reset_input_buffer()

        # Send ENQ (0x05) to signal write intent
        logger.info("📤 Sending ENQ (write request)...")
        self._send_with_space_parity(bytes([self.pump.enq]))
        time.sleep(0.05)  # Small delay for pump to process

        # Wait for ACK from pump
        logger.debug("⏳ Waiting for pump ACK...")
        ack_start = time.time()
        pump_acked = False
        while time.time() - ack_start < 2.0:
            if self.serial.in_waiting > 0:
                byte = self.serial.read(1)
                logger.debug(
                    f"   Received byte: 0x{byte[0]:02X} (expected ACK=0x{self.pump.ack:02X})"
                )
                if byte[0] == self.pump.ack:
                    logger.info("✅ Pump acknowledged write request")
                    pump_acked = True
                    break
                else:
                    logger.warning(f"   Unexpected byte: 0x{byte[0]:02X}")
            time.sleep(0.01)

        if not pump_acked:
            logger.error("❌ Pump did not acknowledge write request")
            return False

        # Build data packet
        # Format: C0 00 14 <len> 00 <param_index> <value_bytes> <checksum>
        # Parameter MUST be defined - no defaults
        if not param:
            logger.error(
                f"❌ Parameter 0x{param_index:02X} not defined in YAML! Cannot write."
            )
            return False

        if param.data_type is None:
            logger.error(
                f"❌ Parameter 0x{param_index:02X} is missing data_type in YAML!"
            )
            return False

        data_type = param.data_type  ## TODO use this?

        # Use the parameter's size field to determine byte count on the wire
        # size=1 means send 1 byte, size=2 means send 2 bytes (matches READ format)
        if param.size == 1:
            # Single byte parameter
            value_bytes = [raw_value & 0xFF]
        else:
            # Two byte parameter (HIGH byte first, LOW byte second)
            value_high = (raw_value >> 8) & 0xFF
            value_low = raw_value & 0xFF
            value_bytes = [value_high, value_low]

        # Data payload: 00 <param_index> <value_bytes> (same format as reads)
        data_payload = [0x00, param_index] + value_bytes
        # Length field = payload size
        data_length = len(data_payload)

        # Build full packet: C0 00 14 <len> <payload>
        packet = [
            self.pump.cmd_data,  # C0
            0x00,
            self.pump.rcu_addr,  # 14 (our address as sender)
            data_length,
        ] + data_payload

        # Calculate checksum on ALL bytes built so far
        checksum = NibeProtocol.calc_checksum(packet)
        packet.append(checksum)

        # Verify packet structure before sending
        logger.info(f"Packet breakdown:")
        logger.info(f"  CMD: 0x{packet[0]:02X}")
        logger.info(f"  Fixed: 0x{packet[1]:02X}")
        logger.info(f"  Sender: 0x{packet[2]:02X}")
        logger.info(f"  Length: 0x{packet[3]:02X} ({packet[3]} bytes)")
        logger.info(f"  Payload: {' '.join(f'{b:02X}' for b in packet[4:-1])}")
        logger.info(f"  Checksum: 0x{packet[-1]:02X}")
        logger.info(f"  Total packet size: {len(packet)} bytes")

        # Send data packet with SPACE parity (9th bit = 0)
        packet_bytes = bytes(packet)
        logger.info(f"📤 Sending write packet: {packet_bytes.hex(' ').upper()}")
        logger.info(
            f"   Param: 0x{param_index:02X}, Raw value: {raw_value} (0x{raw_value:04X}), Bytes: {' '.join(f'{b:02X}' for b in value_bytes)}"
        )
        logger.info(
            f"   Checksum: 0x{checksum:02X}, Data length field: 0x{data_length:02X}"
        )
        # Send packet using same method as ENQ (switches back to MARK after sending)
        self._send_with_space_parity(packet_bytes)

        # Give pump time to process and respond
        time.sleep(0.15)

        # Wait for ACK or NAK (we're back in MARK parity now, consistent with ENQ handling)
        logger.info("⏳ Waiting for pump response (ACK/NAK)...")
        logger.info(f"   Current parity mode: {self.serial.parity}")
        logger.info(f"   Bytes in buffer: {self.serial.in_waiting}")
        response_start = time.time()
        response_bytes = []  # Track all bytes received
        while time.time() - response_start < 3.0:  # Increased timeout
            in_waiting = self.serial.in_waiting
            if in_waiting > 0:
                logger.info(f"   📥 {in_waiting} byte(s) available in buffer")
                byte = self.serial.read(1)
                response_bytes.append(byte[0])
                logger.info(
                    f"   Received byte: 0x{byte[0]:02X} (ACK=0x{self.pump.ack:02X}, NAK=0x{self.pump.nak:02X})"
                )
                if byte[0] == self.pump.ack:
                    logger.info("✅ Pump acknowledged write (ACK)")

                    # Send *ETX (with 9th bit set = MARK parity) to complete transaction
                    logger.info("📤 Sending *ETX (complete)...")
                    # ETX must be sent with MARK parity (9th bit = 1)
                    self.serial.parity = serial.PARITY_MARK
                    self.serial.write(bytes([self.pump.etx]))
                    self.serial.flush()
                    # Switch back to MARK for receiving
                    self.serial.parity = serial.PARITY_MARK
                    logger.debug(f"Sent *ETX: {self.pump.etx:02X} (with 9th bit set)")

                    # Wait for pump to complete write and restart addressing cycle
                    time.sleep(2.0)
                    # Clear any residual data from buffers
                    self.serial.reset_input_buffer()
                    self.serial.reset_output_buffer()

                    print(f"\n{'=' * FULL_LINE}")
                    print("  ✅ WRITE SUCCESSFUL!")
                    print(f"{'=' * FULL_LINE}\n")
                    return True
                elif byte[0] == self.pump.nak:
                    logger.error("❌ Pump rejected write (NAK - checksum error)")
                    return False
                else:
                    logger.error(
                        f"❌ Unexpected byte during ACK/NAK wait: 0x{byte[0]:02X}"
                    )
                    return False
            time.sleep(0.01)
            # Periodic check
            if int((time.time() - response_start) * 10) % 10 == 0:  # Every second
                logger.debug(
                    f"   Still waiting... ({int(time.time() - response_start)}s elapsed, buffer: {self.serial.in_waiting} bytes)"
                )

        # Timeout waiting for response
        if response_bytes:
            logger.error(
                f"❌ Timeout waiting for pump response. Received bytes: {' '.join(f'{b:02X}' for b in response_bytes)}"
            )
        else:
            logger.error("❌ Timeout waiting for pump response (no bytes received)")
        return False

    def get_value(self, param_index: int) -> Optional[float]:
        """Get cached parameter value"""
        return self.parameter_values.get(param_index)

    def get_all_values(self) -> Dict[int, float]:
        """Get all cached parameter values"""
        return self.parameter_values.copy()

    def get_bit_field(self, param_index: int, bit_field_name: str) -> Optional[int]:
        """Get cached bit field value"""
        key = f"0x{param_index:02X}:{bit_field_name}"
        return self.bit_field_values.get(key)

    def get_all_bit_fields(self) -> Dict[str, int]:
        """Get all cached bit field values"""
        return self.bit_field_values.copy()


def load_from_yaml(file_path: str, pump_name: str) -> Tuple[List[Register], Pump]:
    """Load register definitions from a YAML file

    Args:
        file_path: Path to the YAML file
        pump_name: Name of the pump model (default: "nibe_360P")

    Returns:
        List of Register objects for the specified pump
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Navigate to the pump-specific registers
    if "pumps" not in data:
        raise ValueError("YAML file must have a 'pumps' top-level key")

    # Support either a mapping (pumps: { name: {...} }) or a list of pump dicts
    pumps_section = data["pumps"]
    if isinstance(pumps_section, dict):
        if pump_name not in pumps_section:
            available = ", ".join(pumps_section.keys())
            raise ValueError(
                f"Pump '{pump_name}' not found. Available pumps: {available}"
            )
        pump_data = pumps_section[pump_name]
    else:
        # assume list
        pump_list = pumps_section
        pump_data = None
        for p in pump_list:
            if p.get("model") == pump_name or p.get("name") == pump_name:
                pump_data = p
                break
        if pump_data is None:
            available = ", ".join(
                str(p.get("model") or p.get("name")) for p in pump_list
            )
            raise ValueError(
                f"Pump '{pump_name}' not found. Available pumps: {available}"
            )

    # Build Pump instance with protocol bytes parsed (all required)
    required_protocol_fields = [
        "cmd_data",
        "master_addr",
        "rcu_addr",
        "ack",
        "enq",
        "nak",
        "etx",
    ]
    missing_fields = [f for f in required_protocol_fields if f not in pump_data]
    if missing_fields:
        raise ValueError(
            f"Pump '{pump_name}' missing required protocol fields: {', '.join(missing_fields)}"
        )

    cmd_data = _parse_byte_val(pump_data["cmd_data"], None)
    master_addr = _parse_byte_val(pump_data["master_addr"], None)
    rcu_addr = _parse_byte_val(pump_data["rcu_addr"], None)
    ack = _parse_byte_val(pump_data["ack"], None)
    enq = _parse_byte_val(pump_data["enq"], None)
    nak = _parse_byte_val(pump_data["nak"], None)
    etx = _parse_byte_val(pump_data["etx"], None)

    # Validate all protocol bytes were parsed successfully
    if None in [cmd_data, master_addr, rcu_addr, ack, enq, nak, etx]:
        raise ValueError(f"Failed to parse protocol bytes for pump '{pump_name}'")

    # Validate required pump fields
    required_pump_fields = ["model", "name", "baudrate", "bit_mode", "parity"]
    missing_pump_fields = [f for f in required_pump_fields if f not in pump_data]
    if missing_pump_fields:
        raise ValueError(
            f"Pump '{pump_name}' missing required fields: {', '.join(missing_pump_fields)}"
        )

    pump = Pump(
        model=pump_data["model"],
        name=pump_data["name"],
        baudrate=pump_data["baudrate"],
        bit_mode=pump_data["bit_mode"],
        parity=pump_data["parity"],
        cmd_data=cmd_data,
        master_addr=master_addr,
        rcu_addr=rcu_addr,
        ack=ack,
        enq=enq,
        nak=nak,
        etx=etx,
    )
    logger.info(f"✅ Loaded pump: {pump.name} at {pump.baudrate} baud")

    if "registers" not in pump_data:
        raise ValueError(f"Pump '{pump_name}' must have a 'registers' key")

    registers = []
    for item in pump_data["registers"]:
        if item.get("ignore", False):
            continue

        # Validate required register fields
        required_reg_fields = ["name", "size"]
        missing_reg_fields = [f for f in required_reg_fields if f not in item]
        if missing_reg_fields:
            raise ValueError(
                f"Register in pump '{pump_name}' missing required fields: {', '.join(missing_reg_fields)}"
            )

        # Validate index (accept either 'index' or 'id')
        index_val = item.get("index") or item.get("id")
        if index_val is None:
            raise ValueError(
                f"Register '{item.get('name', 'unknown')}' in pump '{pump_name}' must have 'index' or 'id' field"
            )

        # Validate factor and writable are present (can be 0 or False, but must be explicitly set)
        if "factor" not in item:
            raise ValueError(
                f"Register '{item['name']}' in pump '{pump_name}' missing required field: factor"
            )
        if "writable" not in item:
            raise ValueError(
                f"Register '{item['name']}' in pump '{pump_name}' missing required field: writable"
            )

        # If writable, data_type is required
        if item["writable"] and "data_type" not in item:
            raise ValueError(
                f"Register '{item['name']}' in pump '{pump_name}' is writable but missing required field: data_type"
            )

        # Parse bit fields if present
        bit_fields = None
        if "bit_fields" in item:
            bit_fields = []
            for bf in item["bit_fields"]:
                if "name" not in bf or "mask" not in bf or "sort_order" not in bf:
                    raise ValueError(
                        f"Bit field in register '{item['name']}' must have 'name', 'mask', and 'sort_order'"
                    )
                if "writable" not in bf:
                    raise ValueError(
                        f"Bit field '{bf.get('name', 'unknown')}' in register '{item['name']}' missing required field: writable"
                    )
                mask_val = _parse_byte_val(bf["mask"], None)
                if mask_val is None:
                    raise ValueError(
                        f"Invalid mask value '{bf['mask']}' in bit field '{bf['name']}'"
                    )

                # Parse value_map if present
                value_map = None
                if "value_map" in bf:
                    value_map = {}
                    for key, val in bf["value_map"].items():
                        # Keys in YAML are strings, convert to int
                        int_key = int(key) if isinstance(key, str) else key
                        value_map[int_key] = val

                bit_fields.append(
                    BitField(
                        name=bf["name"],
                        mask=mask_val,
                        sort_order=bf["sort_order"],
                        writable=bf["writable"],
                        value_map=value_map,
                        unit=bf.get("unit", ""),
                        min_value=bf.get("min_value"),
                        max_value=bf.get("max_value"),
                        step_size=bf.get("step_size"),
                        menu_structure=bf.get("menu_structure", ""),
                    )
                )

        reg = Register(
            index=index_val,
            name=item["name"],
            size=item["size"],
            factor=item["factor"],
            unit=item.get("unit", ""),
            writable=item["writable"],
            data_type=item.get(
                "data_type"
            ),  # None for read-only, required for writable
            menu_structure=item.get("menu_structure", ""),
            min_value=item.get("min_value"),
            max_value=item.get("max_value"),
            step_size=item.get("step_size"),
            bit_fields=bit_fields,
        )
        registers.append(reg)

    logger.info(f"✅ Loaded {len(registers)} registers for {pump_name}")
    return registers, pump


def main():
    """Main program"""

    pump_model = "nibe_360P"
    NIBE_PARAMETERS, PUMP = load_from_yaml("pumps.yaml", pump_model)

    if sys.platform.startswith("win"):
        SERIAL_PORT = "COM3"
        system_name = "Windows"
    else:
        SERIAL_PORT = "/dev/ttyUSB0"
        system_name = "Linux/Mac"

    logger.info(
        f"✅ Code detected environment: {system_name}, using {SERIAL_PORT} as default serial port."
    )

    print("")
    print("" + "=" * FULL_LINE)
    print(f"  Configured for {PUMP.name} Heat Pump Reader")
    print("=" * FULL_LINE)
    print("")
    print("Options:")
    print("  1) Read parameters (normal operation)")
    print("  2) Read single parameter")
    print("  3) Write parameter value")
    print("  4) Send custom packet (testing)")
    print("  9) Capture bus traffic (diagnostic mode)")
    print("")

    choice = input("Choose option [1/2/3/4/9] (default: 1): ").strip() or "1"
    print("")

    logger.info("")
    logger.info(f"Serial Port: {SERIAL_PORT}")
    logger.info(
        f"Baudrate: {PUMP.baudrate} baud, {PUMP.bit_mode}-bit mode ({PUMP.parity} parity)"
    )
    logger.info("")
    pump = NibeHeatPump(SERIAL_PORT, parameters=NIBE_PARAMETERS, pump_info=PUMP)

    ## Failing pump connection
    if not pump.connect():
        logger.error("❌ Failed to connect!")
        logger.error("\nTroubleshooting:")

        if sys.platform.startswith("win"):
            logger.error(
                "  1. Check Device Manager → Ports (COM & LPT) for your adapter"
            )
            logger.error("  2. Verify the correct COM port number")
            logger.error("  3. Install/update USB-RS485 driver if needed")
            logger.error("  4. Verify RS-485 wiring: A→A, B→B, GND→GND")
        else:
            logger.error("  1. Check serial port: ls /dev/ttyUSB*")
            logger.error("  2. Check permissions: sudo chmod 666 /dev/ttyUSB0")
            logger.error(
                "  3. Or add user to dialout group: sudo usermod -a -G dialout $USER"
            )
            logger.error("  4. Verify RS-485 wiring: A→A, B→B, GND→GND")

        return

    try:
        # Diagnostic mode
        if choice == "9":
            print("\n" + "=" * FULL_LINE)
            print("  BUS TRAFFIC CAPTURE")
            print("=" * FULL_LINE)
            print("\nCapturing raw RS-485 bus data...")
            print("Press Ctrl+C to stop...\n")
            time.sleep(2)

            pump.capture_bus_traffic(duration=15.0)

        # Normal operation
        if choice == "1":
            print("\n" + "=" * FULL_LINE)
            print("  PARAMETER READING")
            print("=" * FULL_LINE)
            print("\nReading parameters from heat pump...")
            print("This will collect data from multiple cycles until complete.")
            print("\nPress Ctrl+C to stop early...\n")
            time.sleep(2)

            values = pump.read_parameters_once(timeout=TIMEOUT)
            bit_fields = pump.get_all_bit_fields()

            if values or bit_fields:
                total_count = len(values) + len(bit_fields)
                print("\n" + "=" * 35)
                print(f"  SUCCESS! Captured {total_count} parameters:")
                print("=" * 35)
                print()

                # Collect all unique register indices (both regular and bit field)
                all_indices = set(values.keys())
                for key in bit_fields.keys():
                    idx_str = key.split(":")[0]  # Extract "0x13" from "0x13:Kompressor"
                    idx = int(idx_str, 16)
                    all_indices.add(idx)

                # Display in sorted order
                for idx in sorted(all_indices):
                    if idx in pump.parameters:
                        param = pump.parameters[idx]

                        if param.bit_fields:
                            # This is a bit field register - show header then bit fields
                            print(f"  [{idx:02X}] {param.name}")
                            # Sort bit fields by sort_order
                            sorted_bit_fields = sorted(
                                param.bit_fields, key=lambda bf: bf.sort_order
                            )
                            for i, bit_field in enumerate(sorted_bit_fields, 1):
                                key = f"0x{idx:02X}:{bit_field.name}"
                                if key in bit_fields:
                                    raw_value = bit_fields[key]
                                    # Format display value using value_map if available
                                    if (
                                        bit_field.value_map
                                        and raw_value in bit_field.value_map
                                    ):
                                        display_value = bit_field.value_map[raw_value]
                                    else:
                                        display_value = str(raw_value)
                                    print(
                                        f"      [{idx:02X}.{i}] {bit_field.name:.<29} {display_value:>8} {bit_field.unit:<5} {bit_field.menu_structure}"
                                    )
                        else:
                            # Regular parameter
                            if idx in values:
                                print(
                                    f"  [{idx:02X}] {param.name:.<35} {values[idx]:>8.1f} {param.unit:<5} {param.menu_structure}"
                                )

                print()
            else:
                print("\n❌ No parameters received!")
                print("Try option 1 to diagnose the issue.")

        # Single parameter read
        if choice == "2":
            print("\n" + "=" * FULL_LINE)
            print("  SINGLE PARAMETER READ")
            print("=" * FULL_LINE)
            print("\nAvailable registers:")

            # Show available registers
            for idx in sorted(pump.parameters.keys()):
                param = pump.parameters[idx]
                print(f"  0x{idx:02X} ({idx:3d}) - {param.name}")

            print("")
            param_input = input(
                "Enter register ID (hex like 0x01 or decimal like 1): "
            ).strip()

            # Parse input as hex or decimal
            try:
                if param_input.startswith("0x") or param_input.startswith("0X"):
                    param_idx = int(param_input, 16)
                else:
                    param_idx = int(param_input)
            except ValueError:
                print(f"\n❌ Invalid input: {param_input}")
                return

            print("")
            time.sleep(1)

            value = pump.read_single_parameter(param_idx, timeout=TIMEOUT)

            if value is not None:
                param = pump.parameters.get(param_idx)
                if param:
                    print("\n" + "=" * 35)
                    print("  SUCCESS!")
                    print("=" * 35)
                    print(
                        f"\n  [0x{param_idx:02X}] {param.name}: {value:.1f} {param.unit}"
                    )
                    print()
                else:
                    print(f"\n✅ Value: {value}")
            elif param_idx in pump.parameters and pump.parameters[param_idx].bit_fields:
                # This is a bit field register
                param = pump.parameters[param_idx]
                bit_fields = pump.get_all_bit_fields()

                print("\n" + "=" * 35)
                print("  SUCCESS!")
                print("=" * 35)
                print(f"\n  [0x{param_idx:02X}] {param.name}")

                sorted_bit_fields = sorted(
                    param.bit_fields, key=lambda bf: bf.sort_order
                )
                for i, bit_field in enumerate(sorted_bit_fields, 1):
                    key = f"0x{param_idx:02X}:{bit_field.name}"
                    if key in bit_fields:
                        raw_value = bit_fields[key]
                        if bit_field.value_map and raw_value in bit_field.value_map:
                            display_value = bit_field.value_map[raw_value]
                        else:
                            display_value = str(raw_value)
                        print(
                            f"      [{param_idx:02X}.{i}] {bit_field.name:.<29} {display_value:>8} {bit_field.unit:<5} {bit_field.menu_structure}"
                        )
                print()
            else:
                print(f"\n❌ Parameter 0x{param_idx:02X} not received")
                print("Try option 9 to diagnose bus traffic.")

        # Write parameter
        if choice == "3":
            print("\n" + "=" * FULL_LINE)
            print("  WRITE PARAMETER")
            print("=" * FULL_LINE)
            print("\nAvailable writable registers:")

            # Show only writable registers
            writable_params = {
                idx: param for idx, param in pump.parameters.items() if param.writable
            }

            if not writable_params:
                print("\n❌ No writable parameters defined in YAML!")
                return

            for idx in sorted(writable_params.keys()):
                param = writable_params[idx]
                min_max = ""
                if param.min_value is not None or param.max_value is not None:
                    min_max = f" [min: {param.min_value}, max: {param.max_value}]"
                print(f"  0x{idx:02X} ({idx:3d}) - {param.name} {param.unit}{min_max}")

            print("")
            param_input = input(
                "Enter register ID (hex like 0x01 or decimal like 1): "
            ).strip()

            # Parse input as hex or decimal
            try:
                if param_input.startswith("0x") or param_input.startswith("0X"):
                    param_idx = int(param_input, 16)
                else:
                    param_idx = int(param_input)
            except ValueError:
                print(f"\n❌ Invalid input: {param_input}")
                return

            # Check if parameter is writable
            if param_idx not in writable_params:
                print(f"\n❌ Parameter 0x{param_idx:02X} is not writable!")
                return

            # Get current value first
            print("\n📖 Reading current value...")
            time.sleep(1)
            current_value = pump.read_single_parameter(param_idx, timeout=TIMEOUT)

            if current_value is not None:
                param = writable_params[param_idx]
                print(f"\nCurrent value: {current_value:.1f} {param.unit}")
            else:
                print("\n⚠️  Could not read current value")

            # Get new value
            value_input = input("\nEnter new value: ").strip()
            try:
                new_value = float(value_input)
            except ValueError:
                print(f"\n❌ Invalid value: {value_input}")
                return

            # Confirm
            confirm = (
                input(
                    f"\n⚠️  Write {new_value} to register 0x{param_idx:02X}? (yes/no): "
                )
                .strip()
                .lower()
            )
            if confirm not in ["yes", "y"]:
                print("\n❌ Write cancelled")
                return

            print("")
            time.sleep(1)

            # Perform write
            success = pump.write_parameter(param_idx, new_value, timeout=10.0)

            if success:
                # Verify by reading back
                print("\n🔍 Verifying write...")
                time.sleep(1)
                verify_value = pump.read_single_parameter(param_idx, timeout=10.0)
                if verify_value is not None:
                    print(f"\nVerified value: {verify_value:.1f} {param.unit}")
                    if abs(verify_value - new_value) < 0.1:
                        print("✅ Write verified successfully!")
                    else:
                        print(
                            f"⚠️  Warning: Read value ({verify_value}) differs from written value ({new_value})"
                        )
            else:
                print("\n❌ Write failed!")

        # Send custom packet
        if choice == "4":
            print("\n" + "=" * FULL_LINE)
            print("  SEND CUSTOM PACKET - BRUTE FORCE CHECKSUM")
            print("=" * FULL_LINE)

            # Base packet WITHOUT checksum - use length=4 (padding size=1 to 2 bytes)
            # Forum example: C0 00 14 04 00 14 01 45 worked (2-byte value)
            # So for 1-byte: pad with leading 0x00 to make it 2 bytes
            base_packet = [0xC0, 0x00, 0x14, 0x04, 0x00, 0x26, 0x00, 0x01]

            # Calculate what we THINK the checksum should be
            calculated_checksum = NibeProtocol.calc_checksum(base_packet)
            print(f"\nBase packet: {bytes(base_packet).hex(' ').upper()}")
            print(f"Register 0x26 (size=1), value=1, length=4 (padded to 2 bytes)")
            print(f"Calculated checksum: 0x{calculated_checksum:02X}")
            print(f"\nTrying all 256 possible checksums until ACK...\n")
            time.sleep(1)

            # Try all possible checksums
            for test_checksum in range(0x00, 0x100):
                package_bytes = base_packet + [test_checksum]

                print(f"Try checksum 0x{test_checksum:02X}: ", end="", flush=True)

                # Wait for pump to address us
                if not pump._wait_for_addressing(timeout=5.0, verbose=False):
                    print("❌ Timeout")
                    continue

                # Clear buffer
                pump.serial.reset_input_buffer()

                # Send ENQ
                pump._send_with_space_parity(bytes([pump.pump.enq]))
                time.sleep(0.05)

                # Wait for ACK from pump
                ack_start = time.time()
                pump_acked = False
                while time.time() - ack_start < 2.0:
                    if pump.serial.in_waiting > 0:
                        byte = pump.serial.read(1)
                        if byte[0] == pump.pump.ack:
                            pump_acked = True
                            break
                    time.sleep(0.01)

                if not pump_acked:
                    print("❌ No ENQ ACK")
                    continue

                # Clear buffer before sending packet
                pump.serial.reset_input_buffer()

                # Send packet with current test checksum
                custom_packet = bytes(package_bytes)
                pump._send_with_space_parity(custom_packet)

                # Wait for pump response (ACK/NAK)
                response_timeout = time.time() + 1.0  # Increased to 1 second
                got_response = False

                while time.time() < response_timeout:
                    if pump.serial.in_waiting > 0:
                        first_byte = pump.serial.read(1)[0]

                        if first_byte == pump.pump.ack:
                            print(f"✅ ACK! Correct checksum is 0x{test_checksum:02X}")
                            print(f"   Full packet: {custom_packet.hex(' ').upper()}")
                            print(f"   Calculated was: 0x{calculated_checksum:02X}")

                            # Send ETX to complete
                            pump.serial.parity = serial.PARITY_MARK
                            pump.serial.write(bytes([pump.pump.etx]))
                            pump.serial.flush()

                            print("\n✅ SUCCESS! Write complete.\n")
                            got_response = True
                            break
                        elif first_byte == pump.pump.nak:
                            print(f"❌ NAK (bad checksum)")
                            got_response = True
                            break
                        else:
                            # Unexpected byte - log it but keep checking
                            print(f"   Got 0x{first_byte:02X}, ", end="", flush=True)
                            continue
                    time.sleep(0.001)

                if got_response and first_byte == pump.pump.ack:
                    # Success! Stop brute force
                    break

                if not got_response:
                    # Check if there were ANY bytes
                    bytes_in_buffer = pump.serial.in_waiting
                    print(f"⏱️ Timeout (buffer: {bytes_in_buffer} bytes)")

                # Small delay before next attempt
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")

        # Show what we captured so far
        values = pump.get_all_values()
        bit_fields = pump.get_all_bit_fields()

        if values or bit_fields:
            print("\n📊 Partial Results:")
            print("=" * 70)

            # Collect all unique register indices
            all_indices = set(values.keys())
            for key in bit_fields.keys():
                idx_str = key.split(":")[0]
                idx = int(idx_str, 16)
                all_indices.add(idx)

            # Display in sorted order
            for idx in sorted(all_indices):
                if idx in pump.parameters:
                    param = pump.parameters[idx]

                    if param.bit_fields:
                        # Bit field register
                        print(f"  [{idx:02X}] {param.name}")
                        sorted_bit_fields = sorted(
                            param.bit_fields, key=lambda bf: bf.sort_order
                        )
                        for i, bit_field in enumerate(sorted_bit_fields, 1):
                            key = f"0x{idx:02X}:{bit_field.name}"
                            if key in bit_fields:
                                raw_value = bit_fields[key]
                                if (
                                    bit_field.value_map
                                    and raw_value in bit_field.value_map
                                ):
                                    display_value = bit_field.value_map[raw_value]
                                else:
                                    display_value = str(raw_value)
                                print(
                                    f"      [{idx:02X}.{i}] {bit_field.name}: {display_value} {bit_field.unit}"
                                )
                    else:
                        # Regular parameter
                        if idx in values:
                            print(
                                f"  [{idx:02X}] {param.name}: {values[idx]} {param.unit}"
                            )
    finally:
        pump.disconnect()
        print("\n✅ Disconnected\n")


if __name__ == "__main__":
    main()
