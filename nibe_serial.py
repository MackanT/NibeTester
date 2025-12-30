"""
Nibe Serial Communication Handler
Manages serial port communication with Nibe heat pump
"""

import serial
import threading
import time
from typing import Callable, Optional, Dict, List
from queue import Queue, Empty
import logging

from nibe_protocol import (
    NibeMessage,
    parse_message,
    create_ack,
    create_nack,
    create_read_request,
    START_BYTE,
    MessageType,
)


logger = logging.getLogger(__name__)


class NibeSerial:
    """
    Handles serial communication with Nibe heat pump
    Manages message sending, receiving, and acknowledgments
    """

    def __init__(
        self, port: str = "/dev/ttyUSB0", baudrate: int = 9600, timeout: float = 1.0
    ):
        """
        Initialize serial connection

        Args:
            port: Serial port path (Windows: 'COM3', Linux: '/dev/ttyUSB0')
            baudrate: Communication speed (default: 9600 for Nibe)
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.serial: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None

        # Buffers and queues
        self.read_buffer = bytearray()
        self.send_queue: Queue[bytes] = Queue()
        self.receive_queue: Queue[NibeMessage] = Queue()

        # Callbacks
        self.message_callbacks: List[Callable[[NibeMessage], None]] = []
        self.register_callbacks: Dict[int, Callable[[int, int], None]] = {}

        # State tracking
        self.last_announcement = 0
        self.connected = False
        self.pump_model = ""
        self.firmware_version = 0

    def connect(self) -> bool:
        """
        Open serial connection and start communication thread

        Returns:
            True if connected successfully
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,  # Fighter 360P uses NO parity at 57600 baud
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )

            logger.info(f"Connected to {self.port} at {self.baudrate} baud")

            # Start read thread
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()

            # Start write thread
            self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
            self.write_thread.start()

            self.connected = True
            return True

        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Close serial connection and stop threads"""
        self.running = False

        if self.read_thread:
            self.read_thread.join(timeout=2.0)

        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Serial connection closed")

        self.connected = False

    def _read_loop(self):
        """Background thread that reads from serial port"""
        logger.info("Read loop started")

        while self.running and self.serial and self.serial.is_open:
            try:
                # Read available bytes
                if self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting)
                    self.read_buffer.extend(data)

                    # Try to parse messages from buffer
                    self._process_buffer()
                else:
                    time.sleep(0.01)  # Small delay when no data

            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                break
            except Exception as e:
                logger.exception(f"Unexpected error in read loop: {e}")

        logger.info("Read loop stopped")

    def _write_loop(self):
        """Background thread that writes to serial port"""
        logger.info("Write loop started")

        while self.running and self.serial and self.serial.is_open:
            try:
                # Get message from queue (block with timeout)
                try:
                    msg = self.send_queue.get(timeout=0.1)
                    self.serial.write(msg)
                    self.serial.flush()
                    logger.debug(f"Sent: {msg.hex(' ')}")
                except Empty:
                    continue

            except serial.SerialException as e:
                logger.error(f"Serial write error: {e}")
                break
            except Exception as e:
                logger.exception(f"Unexpected error in write loop: {e}")

        logger.info("Write loop stopped")

    def _process_buffer(self):
        """Process read buffer and extract complete messages"""
        while len(self.read_buffer) > 0:
            # Look for start byte anywhere in buffer
            if START_BYTE not in self.read_buffer:
                # No start byte found, buffer is all garbage - clear it
                if len(self.read_buffer) > 100:  # Only warn if significant data
                    logger.debug(
                        f"No start byte in {len(self.read_buffer)} bytes, clearing buffer"
                    )
                self.read_buffer.clear()
                break

            # Find the start byte position
            start_idx = self.read_buffer.index(START_BYTE)

            # Discard any bytes before the start byte
            if start_idx > 0:
                discarded = bytes(self.read_buffer[:start_idx])
                logger.debug(
                    f"Discarded {start_idx} bytes before start: {discarded.hex(' ')}"
                )
                self.read_buffer = self.read_buffer[start_idx:]

            # Try to parse message starting at position 0 (which is now START_BYTE)
            msg = parse_message(self.read_buffer)

            if msg:
                # Valid message found
                logger.debug(f"Received: {msg.raw.hex(' ')}")

                # Remove message from buffer
                self.read_buffer = self.read_buffer[len(msg.raw) :]

                # Handle message
                self._handle_message(msg)
            else:
                # Not enough data or invalid message
                # Wait for more data if buffer is small
                if len(self.read_buffer) < 50:
                    break
                else:
                    # Buffer is large but no valid message, discard first byte
                    logger.warning(
                        f"Discarding byte from large buffer: 0x{self.read_buffer[0]:02X}"
                    )
                    self.read_buffer.pop(0)

    def _handle_message(self, msg: NibeMessage):
        """
        Handle received message

        Args:
            msg: Parsed Nibe message
        """
        # Respond to announcements with ACK
        if (
            msg.command == MessageType.ANNOUNCEMENT
            or msg.command == MessageType.DATA_RESPONSE
        ):
            self.send_ack()
            self.last_announcement = time.time()

        # Extract register data if present
        if msg.command == MessageType.DATA_RESPONSE and len(msg.data) >= 4:
            # Data response format: [ADDR_LOW, ADDR_HIGH, DATA...]
            self._decode_data_message(msg.data)

        # Put message in receive queue
        self.receive_queue.put(msg)

        # Call registered callbacks
        for callback in self.message_callbacks:
            try:
                callback(msg)
            except Exception as e:
                logger.exception(f"Error in message callback: {e}")

    def _decode_data_message(self, data: bytes):
        """
        Decode data response message containing register values

        Args:
            data: Message data payload
        """
        i = 0
        while i < len(data) - 3:
            # Extract register address
            address = data[i] | (data[i + 1] << 8)

            # Extract value (assume s16 for now, should lookup from register DB)
            value = data[i + 2] | (data[i + 3] << 8)
            if value > 32767:
                value -= 65536

            logger.info(f"Register {address}: {value}")

            # Call register-specific callbacks
            if address in self.register_callbacks:
                try:
                    self.register_callbacks[address](address, value)
                except Exception as e:
                    logger.exception(f"Error in register callback: {e}")

            i += 4  # Move to next register (4 bytes: addr + value)

    def send_ack(self):
        """Send ACK to pump"""
        self.send_queue.put(create_ack())

    def send_nack(self):
        """Send NACK to pump"""
        self.send_queue.put(create_nack())

    def read_register(self, address: int):
        """
        Queue a register read request

        Args:
            address: Register address to read
        """
        msg = create_read_request(address)
        self.send_queue.put(msg)
        logger.info(f"Queued read request for register {address}")

    def add_message_callback(self, callback: Callable[[NibeMessage], None]):
        """Register a callback for all received messages"""
        self.message_callbacks.append(callback)

    def add_register_callback(self, address: int, callback: Callable[[int, int], None]):
        """
        Register a callback for specific register updates

        Args:
            address: Register address to monitor
            callback: Function(address, value) to call when register is received
        """
        self.register_callbacks[address] = callback

    def wait_for_message(self, timeout: float = 5.0) -> Optional[NibeMessage]:
        """
        Wait for next message from pump

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            NibeMessage or None if timeout
        """
        try:
            return self.receive_queue.get(timeout=timeout)
        except Empty:
            return None


if __name__ == "__main__":
    # Test serial communication
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Windows: use "COM3", Linux: use "/dev/ttyUSB0"
    nibe = NibeSerial(port="COM3")  # Change to your port!

    if nibe.connect():
        print("Connected! Waiting for messages...")
        print("Press Ctrl+C to exit")

        try:
            # Request some registers
            time.sleep(2)  # Wait for initial handshake
            nibe.read_register(40004)  # BT1 Outdoor temp
            nibe.read_register(40008)  # BT2 Supply temp

            # Listen for messages
            while True:
                msg = nibe.wait_for_message(timeout=10.0)
                if msg:
                    print(f"Message: CMD=0x{msg.command:02X}, Data={msg.data.hex(' ')}")
                else:
                    print("No message received in 10 seconds")

        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            nibe.disconnect()
    else:
        print("Failed to connect!")
