"""
Nibe 360P Heat Pump RS-485 Communication - CORRECTED VERSION

IMPORTANT: Based on Swedish forum elektronikforumet.com findings:
- Baudrate: 19200 (NOT 9600!)
- Format: 9-bit mode (8 data bits + parity as 9th bit)
- Custom Nibe protocol (NOT standard Modbus)
- Parameter index based addressing (NOT Modbus register addresses)

Protocol:
1. Master addresses RCU with: *00 *14 (bit 9 = 1 for addressing)
2. RCU responds: 0x06 (ACK) if passive, 0x05 (ENQ) if has data
3. Master sends data if RCU sent ACK
4. Format: C0 00 24 <len> <param_index> <value_bytes>... <checksum>
"""

import serial
import struct
import time
import threading
from typing import Optional, Dict, List, Tuple, Callable
from dataclasses import dataclass
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Register:
    """Parameter definition for Nibe 360P"""

    index: int  # Parameter index (not Modbus address!)
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
    def parse_data_packet(data: bytes) -> Optional[Dict]:
        """
        Parse data packet from master
        Format: C0 00 24 <len> [00 <idx> <val>...]  <checksum>
        """
        if len(data) < 6:
            return None

        if data[0] != Nibe360PProtocol.CMD_DATA:
            return None

        if data[1] != 0x00:
            return None

        sender = data[2]
        length = data[3]

        # Validate length
        if len(data) < length + 5:
            return None

        # Calculate and verify checksum
        checksum_calc = Nibe360PProtocol.calc_checksum(list(data[0 : length + 4]))
        checksum_recv = data[length + 4]

        if checksum_calc != checksum_recv:
            logger.warning(
                f"Checksum error: expected {checksum_calc:02X}, got {checksum_recv:02X}"
            )
            return None

        # Parse parameters
        parameters = {}
        i = 4  # Start after cmd, 00, sender, length
        while i < length + 3:
            if data[i] != 0x00:
                logger.warning(f"Expected 0x00 before param index, got {data[i]:02X}")
                break

            if i + 1 >= len(data):
                break

            param_index = data[i + 1]

            # Determine size based on index (you'll need to map this)
            # For now, assume 2 bytes for temperature params
            if i + 3 < len(data):
                value_low = data[i + 2]
                value_high = data[i + 3]
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
    Nibe 360P Heat Pump communication

    NOTE: This uses MARK/SPACE parity to simulate 9-bit mode
    - Receive with Mark parity to detect addressing (bit 9 = 1)
    - Send with Space parity for data (bit 9 = 0)
    """

    def __init__(self, port: str, parameters: Optional[List[Register]] = None):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None
        self.parameters: Dict[int, Register] = {}
        self.parameter_values: Dict[int, float] = {}
        self.callbacks: List[Callable] = []

        if parameters:
            for param in parameters:
                self.parameters[param.index] = param

    def add_parameter(self, parameter: Register):
        """Add a parameter to monitor"""
        self.parameters[parameter.index] = parameter

    def add_callback(self, callback: Callable):
        """Add callback for data updates"""
        self.callbacks.append(callback)

    def connect(self) -> bool:
        """Connect to the heat pump"""
        try:
            # Use MARK parity for receiving (detect bit 9 = 1 for addressing)
            self.serial = serial.Serial(
                port=self.port,
                baudrate=19200,  # CRITICAL: 19200, not 9600!
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_MARK,  # Mark parity = bit 9 = 1 for addressing
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            logger.info(f"Connected to {self.port} at 19200 baud (Mark parity)")

            # Start read thread
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()

            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the heat pump"""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected")

    def _read_loop(self):
        """Background thread for reading serial data"""
        buffer = bytearray()
        addressed = False

        while self.running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    buffer.extend(data)

                    # Look for addressing sequence: 0x00 0x14
                    for i in range(len(buffer) - 1):
                        if (
                            buffer[i] == 0x00
                            and buffer[i + 1] == Nibe360PProtocol.RCU_ADDR
                        ):
                            logger.debug("RCU addressed!")
                            addressed = True
                            buffer = buffer[i + 2 :]  # Remove addressing bytes

                            # Send ACK (switch to Space parity for sending)
                            self._send_ack()
                            break

                    # Process data packets
                    if len(buffer) > 0 and buffer[0] == Nibe360PProtocol.CMD_DATA:
                        self._process_data_packet(buffer)

                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                time.sleep(0.1)

    def _send_ack(self):
        """Send ACK with Space parity (bit 9 = 0)"""
        if self.serial:
            # Temporarily switch to Space parity for sending
            self.serial.parity = serial.PARITY_SPACE
            self.serial.write(bytes([Nibe360PProtocol.ACK]))
            self.serial.flush()
            # Switch back to Mark parity for receiving
            self.serial.parity = serial.PARITY_MARK
            logger.debug("Sent ACK")

    def _process_data_packet(self, buffer: bytearray):
        """Process incoming data packet"""
        parsed = Nibe360PProtocol.parse_data_packet(bytes(buffer))

        if parsed:
            logger.debug(f"Received data from {parsed['sender']:02X}")

            for param_index, value in parsed["parameters"].items():
                if param_index in self.parameters:
                    param_def = self.parameters[param_index]
                    actual_value = value / param_def.factor
                    self.parameter_values[param_index] = actual_value

                    logger.info(
                        f"Parameter {param_index} ({param_def.name}): {actual_value} {param_def.unit}"
                    )

                    # Notify callbacks
                    for callback in self.callbacks:
                        callback(
                            param_index, param_def.name, actual_value, param_def.unit
                        )

            # Clear processed data
            buffer.clear()

    def get_value(self, param_index: int) -> Optional[float]:
        """Get cached parameter value"""
        return self.parameter_values.get(param_index)

    def get_all_values(self) -> Dict[int, float]:
        """Get all cached values"""
        return self.parameter_values.copy()


# Parameter definitions for Nibe 360P
# Based on forum post by FredRovers
NIBE_360P_PARAMETERS = [
    Register(0x00, "CPU ID", 1, 1.0, "", False),
    Register(0x01, "Outdoor Temperature", 2, 10.0, "°C", False),  # Your register 2!
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
    # Add more as needed from your documentation
]


def main():
    """Example usage"""
    SERIAL_PORT = "COM3"  # Change to your port

    print("Nibe 360P Heat Pump Monitor (Corrected Protocol)")
    print("=================================================")
    print("Baudrate: 19200 (9-bit mode with MARK/SPACE parity)")
    print(f"Connecting to {SERIAL_PORT}...")
    print()

    pump = Nibe360PHeatPump(SERIAL_PORT, parameters=NIBE_360P_PARAMETERS)

    def on_data_update(param_index: int, name: str, value: float, unit: str):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {name}: {value} {unit}")

    pump.add_callback(on_data_update)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        print("Listening for data from heat pump...")
        print("The pump will send data automatically when it addresses the RCU.")
        print("Press Ctrl+C to exit\n")

        while True:
            time.sleep(1)

            # Show current values every 10 seconds
            if int(time.time()) % 10 == 0:
                values = pump.get_all_values()
                if values:
                    print(f"\n--- Current Values ({len(values)} parameters) ---")
                    for idx, val in sorted(values.items()):
                        if idx in pump.parameters:
                            param = pump.parameters[idx]
                            print(f"  {param.name}: {val} {param.unit}")
                time.sleep(1)  # Prevent multiple prints in same second

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        pump.disconnect()


if __name__ == "__main__":
    main()
