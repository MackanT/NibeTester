"""
Nibe 360P Heat Pump RS-485 Communication - BUS MONITOR MODE

IMPORTANT: Based on Swedish forum elektronikforumet.com findings:
- Baudrate: 19200 (NOT 9600!)
- Format: 9-bit mode (8 data bits + parity as 9th bit)
- Custom Nibe protocol (NOT standard Modbus)

This version acts as a BUS MONITOR - passively reading all data on the RS-485 bus
WITHOUT emulating the RCU. This is the safest approach.

The pump's master controller (0x24) continuously polls all devices and sends data.
We simply listen and decode all traffic.

Protocol:
- Master (0x24) sends data packets: C0 00 24 <len> [00 <param> <value>]* <checksum>
- Various devices (RCU=0x14, Display=0xF9, etc.) respond with ACK/ENQ
- We just capture and decode everything
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
    Nibe 360P Heat Pump Bus Monitor

    Passively monitors the RS-485 bus and decodes all data packets.
    Does NOT emulate RCU - just reads everything on the bus.

    This is safer and simpler than active participation.
    """

    def __init__(
        self,
        port: str,
        parameters: Optional[List[Register]] = None,
        monitor_mode: bool = True,
    ):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None
        self.parameters: Dict[int, Register] = {}
        self.parameter_values: Dict[int, float] = {}
        self.callbacks: List[Callable] = []
        self.monitor_mode = monitor_mode  # Pure monitoring, no interaction

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
        """Connect to the heat pump bus"""
        try:
            if self.monitor_mode:
                # Pure monitoring mode - use 8N1 to capture all data
                # We'll see both addressing (with parity errors) and data
                self.serial = serial.Serial(
                    port=self.port,
                    baudrate=19200,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,  # No parity - see all bytes
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.1,
                )
                logger.info(
                    f"Connected to {self.port} at 19200 baud (Monitor mode - 8N1)"
                )
            else:
                # Interactive mode - use MARK parity to detect addressing
                self.serial = serial.Serial(
                    port=self.port,
                    baudrate=19200,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_MARK,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.1,
                )
                logger.info(
                    f"Connected to {self.port} at 19200 baud (Interactive mode - Mark parity)"
                )

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

                    if self.monitor_mode:
                        # Monitor mode - just look for data packets
                        self._scan_for_packets(buffer)
                    else:
                        # Interactive mode - look for addressing
                        for i in range(len(buffer) - 1):
                            if (
                                buffer[i] == 0x00
                                and buffer[i + 1] == Nibe360PProtocol.RCU_ADDR
                            ):
                                logger.debug("RCU addressed!")
                                buffer = buffer[i + 2 :]
                                self._send_ack()
                                break

                        # Process data packets
                        if len(buffer) > 0 and buffer[0] == Nibe360PProtocol.CMD_DATA:
                            self._process_data_packet(buffer)

                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                time.sleep(0.1)

    def _scan_for_packets(self, buffer: bytearray):
        """Scan buffer for C0 data packets (monitor mode)"""
        while True:
            # Look for start of packet (C0)
            try:
                idx = buffer.index(Nibe360PProtocol.CMD_DATA)
            except ValueError:
                # No C0 found, keep first byte in case it's part of next packet
                if len(buffer) > 100:
                    buffer[:] = buffer[-50:]  # Keep last 50 bytes
                break

            # Remove everything before C0
            if idx > 0:
                buffer[:] = buffer[idx:]

            # Check if we have enough data for header
            if len(buffer) < 5:
                break

            # Get packet length
            length = buffer[3]
            packet_size = length + 5  # C0 + 00 + sender + len + data + checksum

            # Wait for complete packet
            if len(buffer) < packet_size:
                break

            # Extract packet
            packet = bytes(buffer[:packet_size])
            buffer[:] = buffer[packet_size:]  # Remove processed packet

            # Process it
            self._process_data_packet(bytearray(packet))

            # Log raw packet for debugging
            logger.debug(f"Raw packet: {packet.hex(' ').upper()}")

    def _send_ack(self):
        """Send ACK with Space parity (bit 9 = 0) - only in interactive mode"""
        if self.serial and not self.monitor_mode:
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
    import sys

    SERIAL_PORT = "COM3"  # Change to your port (Windows: COM3, Linux: /dev/ttyUSB0)

    print("=" * 70)
    print("  Nibe 360P Heat Pump Bus Monitor")
    print("=" * 70)
    print()
    print("Mode: PASSIVE BUS MONITORING (No RCU emulation)")
    print("Baudrate: 19200 baud, 8N1")
    print("Function: Read and decode all data on RS-485 bus")
    print()
    print(f"Connecting to {SERIAL_PORT}...")
    print()

    # Use monitor mode - safest option, just reads everything
    pump = Nibe360PHeatPump(
        SERIAL_PORT, parameters=NIBE_360P_PARAMETERS, monitor_mode=True
    )

    def on_data_update(param_index: int, name: str, value: float, unit: str):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] Param {param_index:02X}: {name} = {value} {unit}")

    pump.add_callback(on_data_update)

    if not pump.connect():
        print("❌ Failed to connect!")
        print("\nTroubleshooting:")
        print("  1. Check serial port name (COM3, COM4, etc.)")
        print("  2. Ensure RS-485 adapter is connected")
        print("  3. Verify wiring: A→A, B→B, GND→GND")
        return

    try:
        print("✅ Connected successfully!")
        print("\n" + "=" * 70)
        print("  Monitoring RS-485 bus for data packets...")
        print("  The pump's master controller sends data every few seconds.")
        print("  Press Ctrl+C to exit")
        print("=" * 70)
        print()

        last_summary_time = 0

        while True:
            time.sleep(0.5)

            # Show summary every 15 seconds
            current_time = int(time.time())
            if current_time - last_summary_time >= 15 and current_time % 15 == 0:
                values = pump.get_all_values()
                if values:
                    print(f"\n{'─' * 70}")
                    print(f"  Current Values ({len(values)} parameters received)")
                    print(f"{'─' * 70}")
                    for idx, val in sorted(values.items()):
                        if idx in pump.parameters:
                            param = pump.parameters[idx]
                            print(f"  {param.name:.<40} {val:>8.1f} {param.unit}")
                    print(f"{'─' * 70}\n")
                    last_summary_time = current_time
                elif current_time > 30:
                    print("\n⚠️  No data received yet. Check:")
                    print("  - Is the heat pump powered on?")
                    print("  - Is RS-485 wiring correct?")
                    print("  - Is RCU enabled in pump menu?")
                    last_summary_time = current_time

    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("  Shutting down...")
        print("=" * 70)
    finally:
        pump.disconnect()

        # Show final summary
        values = pump.get_all_values()
        if values:
            print(f"\n📊 Session Summary: Captured {len(values)} parameters")
            print("=" * 70)
            for idx, val in sorted(values.items()):
                if idx in pump.parameters:
                    param = pump.parameters[idx]
                    print(f"  [{idx:02X}] {param.name}: {val} {param.unit}")
            print("=" * 70)
        print("\n✅ Disconnected.\n")


if __name__ == "__main__":
    main()
