"""
Nibe Heat Pump RS-485 Communication

Protocol:
- Baudrate: Parametrizeable (F360P uses 19200)
- Format: 9-bit mode using MARK/SPACE parity
- Custom Nibe protocol (NOT standard Modbus)

This implementation passively reads parameters by responding to the pump's polling.
Auto-runs on startup with 1-minute timeout, storing all collected fields in a dict.
"""

import serial
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import logging
import yaml
import sys
import json
from datetime import datetime

FULL_LINE = 53
TIMEOUT = 60  # seconds (1 minute)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class BitField:
    """Bit field definition for registers with multiple boolean or multi-bit flags"""

    name: str
    mask: int
    sort_order: int
    value_map: Optional[Dict[int, str]] = None
    unit: str = ""


@dataclass
class Register:
    """Register definition for Nibe communication"""

    index: int
    name: str
    size: int  # Bytes: 1 or 2
    factor: float = 1.0
    unit: str = ""
    bit_fields: Optional[List[BitField]] = None


@dataclass
class Pump:
    """Parameter definition for the heat pump"""

    model: str
    name: str
    baudrate: int
    bit_mode: int
    parity: str
    cmd_data: int
    master_addr: int
    rcu_addr: int
    ack: int
    enq: int
    nak: int
    etx: int


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
        expected_size = length + 5
        if len(data) < expected_size:
            logger.debug(f"Incomplete packet: {len(data)} < {expected_size}")
            return None

        checksum_received = data[expected_size - 1]
        checksum_calc = NibeProtocol.calc_checksum(data[0 : expected_size - 1])

        if checksum_received != checksum_calc:
            logger.warning(
                f"Checksum mismatch: {checksum_received:02X} != {checksum_calc:02X}"
            )
            return None

        # Parse parameters
        parameters = {}
        payload = data[4 : 4 + length - 1]

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
                if i + 2 < len(payload):
                    value = payload[i + 2]
                    if value >= 128:
                        value = value - 256
                    parameters[param_index] = value
                    i += 3
                else:
                    break
            else:
                # Two byte parameter (HIGH byte first, LOW byte second)
                if i + 3 < len(payload):
                    value_high = payload[i + 2]
                    value_low = payload[i + 3]
                    value = (value_high << 8) | value_low
                    if value >= 32768:
                        value = value - 65536
                    parameters[param_index] = value
                    i += 4
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
        self.parameter_values: Dict[int, float] = {}
        self.bit_field_values: Dict[str, int] = {}
        self.pump: Pump = pump_info

        # Combined results dict for easy export to PostgreSQL
        self.all_results: Dict[str, any] = {}

        if parameters:
            for param in parameters:
                self.parameters[param.index] = param

    def connect(self) -> bool:
        """Connect to the heat pump"""
        try:
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
                timeout=0.5,
                inter_byte_timeout=0.1,
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
            self.serial.parity = serial.PARITY_SPACE
            self.serial.write(data)
            self.serial.flush()
            logger.debug(f"Sent with SPACE: {data.hex(' ').upper()}")

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

                # Look for addressing sequence (00 14)
                if len(buffer) >= 2:
                    if buffer[-2] == 0x00 and buffer[-1] == self.pump.rcu_addr:
                        logger.info("✅ RCU addressed by pump!")
                        return True

                # Keep buffer manageable
                if len(buffer) > 100:
                    buffer = buffer[-50:]

            time.sleep(0.01)

        logger.warning("⏱️ Timeout waiting for addressing")
        return False

    def _read_response(self, timeout: float = 3.0) -> Optional[Dict]:
        """Read and parse response packet from pump"""
        logger.debug("📥 Reading response from pump...")
        start_time = time.time()
        buffer = bytearray()

        while time.time() - start_time < timeout:
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

    def read_all_parameters(self, timeout: int = TIMEOUT) -> Dict[str, any]:
        """
        Read all parameters from the pump with early exit when all fields collected.

        Returns: Dictionary with all collected data ready for database storage
        """
        print(f"\n{'=' * FULL_LINE}")
        print("📖 Reading All Parameters from Pump")
        print(f"{'=' * FULL_LINE}")
        print(f"Collecting data (timeout: {timeout}s)...\n")

        cycles_with_new_data = 0
        max_cycles_without_new = 3
        start_time = time.time()

        while cycles_with_new_data < max_cycles_without_new:
            # Check timeout
            if time.time() - start_time > timeout:
                logger.warning(f"⏱️ Maximum read time ({timeout}s) exceeded. Stopping.")
                break

            # Wait for pump to address RCU
            if not self._wait_for_addressing(timeout=15.0):
                logger.warning("Timeout waiting for pump. Stopping.")
                break

            # Send ACK (ready to receive data)
            logger.info("📤 Sending ACK (ready to receive)...")
            self._send_with_space_parity(bytes([self.pump.ack]))
            time.sleep(0.05)

            # Receive data packet
            response = self._read_response(timeout=2.0)

            if response:
                # Check if we got any new parameters
                new_params = 0
                for param_idx in response["parameters"].keys():
                    if param_idx not in self.parameter_values:
                        new_params += 1

                if new_params > 0:
                    cycles_with_new_data = 0
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
                            for bit_field in param.bit_fields:
                                masked_value = raw_value & bit_field.mask
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
                                    f"   [{param_idx:02X}] {bit_field.name}: {display_value}"
                                )
                        else:
                            # Regular parameter with factor
                            actual_value = raw_value / param.factor
                            self.parameter_values[param_idx] = actual_value
                            logger.debug(
                                f"   [{param_idx:02X}] {param.name}: {actual_value:.1f} {param.unit}"
                            )

                # Send ACK to confirm receipt
                logger.info("📤 Sending ACK (data received OK)...")
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
            else:
                logger.warning("⚠️ No data received")
                cycles_with_new_data += 1

        # Compile all results into a single dict
        self._compile_results()

        logger.info(f"\n{'=' * 70}")
        logger.info(f"📊 Collection Complete: {len(self.all_results)} total fields")
        logger.info(f"{'=' * 70}")

        return self.all_results

    def _compile_results(self):
        """Compile all collected data into a single dict for database storage"""
        self.all_results = {}

        # Add regular parameters
        for param_idx, value in self.parameter_values.items():
            if param_idx in self.parameters:
                param = self.parameters[param_idx]
                key = f"{param.name} (0x{param_idx:02X})"
                self.all_results[key] = {
                    "value": value,
                    "unit": param.unit,
                    "register": f"0x{param_idx:02X}",
                    "type": "parameter",
                }

        # Add bit fields
        for key, value in self.bit_field_values.items():
            # key format: "0x13:Kompressor"
            parts = key.split(":")
            register_hex = parts[0]
            field_name = parts[1]

            register_idx = int(register_hex, 16)
            if register_idx in self.parameters:
                param = self.parameters[register_idx]
                # Find the bit field definition
                for bit_field in param.bit_fields or []:
                    if bit_field.name == field_name:
                        # Get display value
                        if bit_field.value_map and value in bit_field.value_map:
                            display_value = bit_field.value_map[value]
                        else:
                            display_value = str(value)

                        result_key = f"{field_name} ({register_hex})"
                        self.all_results[result_key] = {
                            "value": value,
                            "display_value": display_value,
                            "unit": bit_field.unit,
                            "register": register_hex,
                            "type": "bit_field",
                        }
                        break

    def get_results(self) -> Dict[str, any]:
        """Get all collected results (for PostgreSQL export)"""
        return self.all_results

    def save_results(self, filename: str = None) -> str:
        """Save results to JSON file

        Args:
            filename: Optional filename. If not provided, uses timestamp.

        Returns:
            The filename that was written to
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pump_data_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.all_results, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Results saved to {filename}")
        return filename

    @staticmethod
    def load_results(filename: str) -> Dict[str, any]:
        """Load results from JSON file

        Args:
            filename: Path to JSON file

        Returns:
            Dictionary with pump data
        """
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"✅ Results loaded from {filename}")
        return data


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

        # Validate factor is present
        if "factor" not in item:
            item["factor"] = 1.0  # Default factor

        # Parse bit fields if present
        bit_fields = None
        if "bit_fields" in item:
            bit_fields = []
            for bf in item["bit_fields"]:
                if "name" not in bf or "mask" not in bf or "sort_order" not in bf:
                    raise ValueError(
                        f"Bit field in register '{item['name']}' must have 'name', 'mask', and 'sort_order'"
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
                        value_map=value_map,
                        unit=bf.get("unit", ""),
                    )
                )

        reg = Register(
            index=index_val,
            name=item["name"],
            size=item["size"],
            factor=item.get("factor", 1.0),
            unit=item.get("unit", ""),
            bit_fields=bit_fields,
        )
        registers.append(reg)

    logger.info(f"✅ Loaded {len(registers)} registers for {pump_name}")
    return registers, pump


def main():
    """Main program - automatically collects all data on startup"""

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
    print("=" * FULL_LINE)
    print(f"  {PUMP.name} Heat Pump Reader")
    print("=" * FULL_LINE)
    print("")
    print(f"Serial Port: {SERIAL_PORT}")
    print(
        f"Baudrate: {PUMP.baudrate} baud, {PUMP.bit_mode}-bit mode ({PUMP.parity} parity)"
    )
    print("")
    print("Starting automatic data collection...")
    print("")

    pump = NibeHeatPump(SERIAL_PORT, parameters=NIBE_PARAMETERS, pump_info=PUMP)

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
        # Automatically read all parameters
        results = pump.read_all_parameters(timeout=TIMEOUT)

        if results:
            print("\n" + "=" * 70)
            print(f"  SUCCESS! Captured {len(results)} fields:")
            print("=" * 70)
            print()

            # Display results sorted by register
            sorted_results = sorted(
                results.items(),
                key=lambda x: x[1]["register"],
            )

            for key, data in sorted_results:
                if data["type"] == "parameter":
                    print(
                        f"  [{data['register']}] {key:.<45} {data['value']:>8.1f} {data['unit']:<5}"
                    )
                elif data["type"] == "bit_field":
                    display = data.get("display_value", data["value"])
                    print(
                        f"      [{data['register']}] {key:.<41} {display:>8} {data['unit']:<5}"
                    )

            print()
            print("=" * 70)
            print("Data collection complete!")
            print("=" * 70)
            print()

            # Save results to file for later PostgreSQL import
            filename = pump.save_results()
            print(f"💾 Results saved to: {filename}")
            print("   Use NibeHeatPump.load_results(filename) to load data later.")
            print("=" * 70)
            print()

        else:
            print("\n❌ No parameters received!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")

        # Show partial results
        results = pump.get_results()
        if results:
            print(f"\n📊 Partial Results: {len(results)} fields captured")
            print("=" * 70)
            for key, data in sorted(results.items(), key=lambda x: x[1]["register"]):
                if data["type"] == "parameter":
                    print(
                        f"  [{data['register']}] {key}: {data['value']} {data['unit']}"
                    )
                elif data["type"] == "bit_field":
                    display = data.get("display_value", data["value"])
                    print(f"      [{data['register']}] {key}: {display} {data['unit']}")
    finally:
        pump.disconnect()
        print("\n✅ Disconnected\n")


if __name__ == "__main__":
    main()
