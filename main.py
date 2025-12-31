"""
Nibe 360P Heat Pump RS-485 Serial Communication
Based on nibepi project but adapted for Python and Nibe 360P model

Protocol uses RS-485 at 9600 baud with specific message structure:
- Start byte: 0xC0 (192)
- Command byte: 0x69 (read), 0x6B (write)
- Length byte
- Data bytes (register address, value)
- Checksum (XOR of bytes 2 to length+4)
- End byte: 0xC0 (192) implied by implementation
"""

import serial
import struct
import time
import threading
from typing import Optional, Dict, List, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types for Nibe protocol"""

    MODBUS_READ_REQ = 0x69  # Request to read data
    MODBUS_READ_RESP = 0x6A  # Response with data
    MODBUS_WRITE_REQ = 0x6B  # Request to write data
    MODBUS_WRITE_RESP = 0x6C  # Write confirmation
    MODBUS_DATA_MSG = 0x68  # Data message (pump initiated)
    MODBUS_ACK = 0x06  # Acknowledgment
    MODBUS_NACK = 0x15  # Negative acknowledgment
    RMU_DATA = 0x62  # RMU data message
    RMU_WRITE = 0x60  # RMU write message


@dataclass
class Register:
    """Register definition for Nibe heat pump"""

    address: int
    name: str
    size: str  # 's8', 'u8', 's16', 'u16', 's32', 'u32'
    factor: float = 1.0  # Division factor for value
    unit: str = ""
    writable: bool = False
    mode: str = "R"  # R for Read, RW for Read/Write


class NibeProtocol:
    """Handles Nibe protocol encoding/decoding"""

    START_BYTE = 0xC0
    ACK = [0x06]
    NACK = [0x15]

    @staticmethod
    def calc_checksum(data: List[int]) -> int:
        """Calculate XOR checksum for message"""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    @staticmethod
    def encode_read_request(register: int) -> List[int]:
        """
        Encode a read register request
        Format: [0xC0, 0x69, 0x02, reg_low, reg_high, checksum]
        """
        data = [
            NibeProtocol.START_BYTE,
            MessageType.MODBUS_READ_REQ.value,
            0x02,  # Length
            (register & 0xFF),  # Register low byte
            ((register >> 8) & 0xFF),  # Register high byte
        ]
        data.append(NibeProtocol.calc_checksum(data[2:]))
        return data

    @staticmethod
    def encode_write_request(register: int, value: int, size: str = "s16") -> List[int]:
        """
        Encode a write register request
        Format: [0xC0, 0x6B, length, reg_low, reg_high, value_bytes..., checksum]
        """
        data = [NibeProtocol.START_BYTE, MessageType.MODBUS_WRITE_REQ.value]

        reg_bytes = [(register & 0xFF), ((register >> 8) & 0xFF)]

        # Encode value based on size
        if size in ["u8", "s8"]:
            length = 0x03
            value_bytes = [(value & 0xFF)]
        elif size in ["u16", "s16"]:
            length = 0x04
            value_bytes = [(value & 0xFF), ((value >> 8) & 0xFF)]
        elif size in ["u32", "s32"]:
            length = 0x06
            value_bytes = [
                (value & 0xFF),
                ((value >> 8) & 0xFF),
                ((value >> 16) & 0xFF),
                ((value >> 24) & 0xFF),
            ]
        else:
            raise ValueError(f"Unsupported size: {size}")

        data.append(length)
        data.extend(reg_bytes)
        data.extend(value_bytes)
        data.append(NibeProtocol.calc_checksum(data[2:]))

        return data

    @staticmethod
    def decode_value(data: bytes, size: str, factor: float = 1.0) -> float:
        """Decode value from bytes based on size type"""
        if size == "u8":
            value = data[0] & 0xFF
        elif size == "s8":
            value = data[0] & 0xFF
            if value >= 128:
                value = value - 256
        elif size == "u16":
            value = (data[1] & 0xFF) << 8 | (data[0] & 0xFF)
        elif size == "s16":
            value = (data[1] & 0xFF) << 8 | (data[0] & 0xFF)
            if value >= 32768:
                value = value - 65536
        elif size == "u32":
            value = (
                (data[3] & 0xFF) << 24
                | (data[2] & 0xFF) << 16
                | (data[1] & 0xFF) << 8
                | (data[0] & 0xFF)
            )
        elif size == "s32":
            value = (
                (data[3] & 0xFF) << 24
                | (data[2] & 0xFF) << 16
                | (data[1] & 0xFF) << 8
                | (data[0] & 0xFF)
            )
            if value >= 2147483648:
                value = value - 4294967296
        else:
            raise ValueError(f"Unsupported size: {size}")

        return value / factor

    @staticmethod
    def parse_message(data: bytes) -> Optional[Dict]:
        """Parse incoming message from heat pump"""
        if len(data) < 5:
            return None

        # Validate start byte
        if data[0] != NibeProtocol.START_BYTE:
            return None

        msg_type = data[1]
        length = data[2]

        # Validate length
        if len(data) < length + 5:
            return None

        # Validate checksum
        expected_checksum = NibeProtocol.calc_checksum(data[2 : length + 4])
        actual_checksum = data[length + 4]

        if expected_checksum != actual_checksum:
            logger.warning(
                f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
            )
            return None

        result = {"type": msg_type, "length": length, "raw_data": data[: length + 5]}

        # Parse based on message type
        if msg_type == MessageType.MODBUS_READ_RESP.value:  # Read response (0x6A)
            if length >= 4:
                register = data[4] << 8 | data[3]
                value_bytes = data[5 : length + 3]
                result["register"] = register
                result["value_bytes"] = value_bytes

        elif msg_type == MessageType.MODBUS_DATA_MSG.value:  # Data message (0x68)
            # Multiple registers can be sent
            registers = []
            i = 3
            while i < length + 2:
                if i + 2 >= len(data):
                    break
                register = data[i + 1] << 8 | data[i]
                registers.append(register)
                # Skip to next register (register + value, typically 4 bytes)
                i += 4  # Adjust based on actual data size
            result["registers"] = registers

        elif msg_type == MessageType.MODBUS_WRITE_RESP.value:  # Write response (0x6C)
            result["success"] = data[3] == 0x01

        return result


class NibeHeatPump:
    """Main class for communicating with Nibe 360P heat pump"""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        registers: Optional[List[Register]] = None,
    ):
        """
        Initialize Nibe heat pump communication

        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Baud rate (default 9600)
            registers: List of Register objects to monitor
        """
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None
        self.registers: Dict[int, Register] = {}
        self.register_values: Dict[int, float] = {}
        self.callbacks: List[Callable] = []
        self.pending_requests: Dict[int, threading.Event] = {}
        self.response_data: Dict[int, any] = {}

        # Load registers if provided
        if registers:
            for reg in registers:
                self.registers[reg.address] = reg

    def add_register(self, register: Register):
        """Add a register to monitor"""
        self.registers[register.address] = register

    def add_callback(self, callback: Callable):
        """Add callback for data updates"""
        self.callbacks.append(callback)

    def connect(self) -> bool:
        """Connect to the heat pump"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            logger.info(f"Connected to {self.port} at {self.baudrate} baud")

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

        while self.running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    buffer.extend(data)

                    # Process buffer
                    self._process_buffer(buffer)

                time.sleep(0.01)  # Small delay to prevent CPU spinning

            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                time.sleep(0.1)

    def _process_buffer(self, buffer: bytearray):
        """Process incoming data buffer"""
        while len(buffer) > 0:
            # Find start byte
            if buffer[0] != NibeProtocol.START_BYTE:
                buffer.pop(0)
                continue

            # Need at least 5 bytes for minimal message
            if len(buffer) < 5:
                break

            # Get message length
            length = buffer[2]
            msg_length = length + 5  # start + type + len + data + checksum

            # Wait for complete message
            if len(buffer) < msg_length:
                break

            # Extract message
            message = bytes(buffer[:msg_length])
            buffer = buffer[msg_length:]

            # Parse and handle message
            parsed = NibeProtocol.parse_message(message)
            if parsed:
                self._handle_message(parsed, message)

            # Send ACK for most messages
            if len(message) > 1 and message[1] in [
                MessageType.MODBUS_DATA_MSG.value,
                MessageType.MODBUS_READ_RESP.value,
            ]:
                self._send_ack()

    def _handle_message(self, parsed: Dict, raw: bytes):
        """Handle parsed message"""
        msg_type = parsed["type"]

        if msg_type == MessageType.MODBUS_READ_RESP.value:
            # Read response
            register = parsed.get("register")
            value_bytes = parsed.get("value_bytes", b"")

            if register and register in self.registers:
                reg_def = self.registers[register]
                try:
                    value = NibeProtocol.decode_value(
                        value_bytes, reg_def.size, reg_def.factor
                    )
                    self.register_values[register] = value

                    logger.info(
                        f"Register {register} ({reg_def.name}): {value} {reg_def.unit}"
                    )

                    # Notify callbacks
                    for callback in self.callbacks:
                        callback(register, reg_def.name, value, reg_def.unit)

                    # Notify pending request
                    if register in self.pending_requests:
                        self.response_data[register] = value
                        self.pending_requests[register].set()
                except Exception as e:
                    logger.error(f"Error decoding register {register}: {e}")

        elif msg_type == MessageType.MODBUS_DATA_MSG.value:
            # Data message (pump initiated)
            logger.debug(f"Received data message: {raw.hex()}")

        elif msg_type == MessageType.MODBUS_WRITE_RESP.value:
            # Write response
            success = parsed.get("success", False)
            logger.info(f"Write response: {'success' if success else 'failed'}")

    def _send_ack(self):
        """Send acknowledgment"""
        if self.serial:
            self.serial.write(bytes(NibeProtocol.ACK))

    def _send_message(self, data: List[int]):
        """Send message to heat pump"""
        if self.serial:
            self.serial.write(bytes(data))
            logger.debug(f"Sent: {bytes(data).hex()}")

    def read_register(self, register: int, timeout: float = 5.0) -> Optional[float]:
        """
        Read a register value

        Args:
            register: Register address
            timeout: Timeout in seconds

        Returns:
            Register value or None if timeout
        """
        if register not in self.registers:
            logger.warning(f"Register {register} not defined")
            return None

        # Create event for this request
        event = threading.Event()
        self.pending_requests[register] = event

        # Send read request
        message = NibeProtocol.encode_read_request(register)
        self._send_message(message)

        # Wait for response
        if event.wait(timeout):
            value = self.response_data.get(register)
            del self.pending_requests[register]
            del self.response_data[register]
            return value
        else:
            logger.warning(f"Timeout reading register {register}")
            if register in self.pending_requests:
                del self.pending_requests[register]
            return None

    def write_register(self, register: int, value: float) -> bool:
        """
        Write a register value

        Args:
            register: Register address
            value: Value to write (will be multiplied by factor)

        Returns:
            True if successful
        """
        if register not in self.registers:
            logger.warning(f"Register {register} not defined")
            return False

        reg_def = self.registers[register]

        if not reg_def.writable:
            logger.warning(f"Register {register} is not writable")
            return False

        # Apply factor
        int_value = int(value * reg_def.factor)

        # Send write request
        message = NibeProtocol.encode_write_request(register, int_value, reg_def.size)
        self._send_message(message)

        # TODO: Wait for write confirmation
        time.sleep(0.5)
        return True

    def read_all_registers(self, interval: float = 1.0):
        """
        Read all defined registers sequentially

        Args:
            interval: Delay between reads in seconds
        """
        for register in self.registers.keys():
            value = self.read_register(register)
            if value is not None:
                reg_def = self.registers[register]
                print(f"{reg_def.name}: {value} {reg_def.unit}")
            time.sleep(interval)


# Example registers for Nibe 360P (you'll need to populate with actual registers)
NIBE_360P_REGISTERS = [
    # Common registers - adjust addresses for your 360P model
    Register(40004, "BT1 Outdoor Temperature", "s16", 10.0, "°C", False),
    Register(40008, "EB100-EP14 BT2 Supply temp S1", "s16", 10.0, "°C", False),
    Register(40012, "EB100-EP14 BT3 Return temp", "s16", 10.0, "°C", False),
    Register(40013, "BT7 Hot Water Temperature", "s16", 10.0, "°C", False),
    Register(40014, "BT6 Hot Water Load", "s16", 10.0, "°C", False),
    Register(40033, "BT1 Average", "s16", 10.0, "°C", False),
    Register(43005, "Degree Minutes", "s16", 10.0, "DM", False),
    Register(43009, "Calculated Supply Temperature S1", "s16", 10.0, "°C", False),
    Register(43081, "Total HW Operation Time", "s32", 10.0, "h", False),
    Register(47011, "Priority", "s8", 1.0, "", True),
    Register(47398, "Temporary Lux", "s8", 1.0, "", True),
    # Add more registers specific to your 360P model
]


def main():
    """Example usage"""
    # Configuration - CHANGE THIS TO YOUR SERIAL PORT
    SERIAL_PORT = "COM3"  # Windows: 'COM3', Linux: '/dev/ttyUSB0', '/dev/ttyAMA0'

    print("Nibe 360P Heat Pump Monitor")
    print(f"Connecting to {SERIAL_PORT}...")

    # Create heat pump instance
    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    # Add callback for real-time updates
    def on_data_update(register: int, name: str, value: float, unit: str):
        print(f"UPDATE: {name} = {value} {unit}")

    pump.add_callback(on_data_update)

    # Connect
    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        # Wait a bit for connection to stabilize
        time.sleep(2)

        # Read all registers once
        print("\nReading all registers...")
        pump.read_all_registers(interval=0.5)

        # Keep running to receive data messages from pump
        print("\nMonitoring for data updates... (Press Ctrl+C to exit)")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        pump.disconnect()


if __name__ == "__main__":
    main()
