"""
Nibe Protocol - Core Message Definitions
Based on analysis of anerdins/nibepi JavaScript implementation
"""
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Optional


class NibeCommand(IntEnum):
    """Nibe protocol command bytes"""
    # Commands FROM pump
    MODBUS_DATA_MSG = 0x68      # Data response (modbus read response)
    MODBUS_WRITE_MSG = 0x69     # Write request acknowledgment?
    MODBUS_READ_REQ = 0x6A      # Announcement/status message
    RMU_DATA_MSG = 0x62         # RMU40 data message
    RMU_WRITE_MSG = 0x60        # RMU40 write data
    
    # Commands TO pump
    MODBUS_READ_REQ = 0x69      # Read register request
    MODBUS_WRITE_REQ = 0x6B     # Write register request
    
    # Response codes
    ACK = 0x06                  # Acknowledge
    NACK = 0x15                 # Negative acknowledge


class MessageType(IntEnum):
    """Message type identifiers"""
    ANNOUNCEMENT = 0x6D         # 109 - Initial announcement
    DATA_RESPONSE = 0x68        # 104 - Data in response
    WRITE_ACK = 0x6B           # 107 - Write acknowledgment
    READ_REQUEST = 0x69         # 105 - Read request ACK
    RMU_SYSTEM = 0x62           # 98 - RMU40 system message


# Message constants
START_BYTE = 0xC0
RMU_START_LENGTHS = [0x19, 0x1A, 0x1B, 0x1C]  # System 1-4 messages


@dataclass
class NibeMessage:
    """Represents a parsed Nibe protocol message"""
    start: int
    command: int
    length: int
    data: bytes
    checksum: int
    raw: bytes
    
    @property
    def is_valid(self) -> bool:
        """Verify message checksum"""
        return calculate_checksum(self.raw[:-1]) == self.checksum
    
    @property
    def address(self) -> Optional[int]:
        """Extract register address if present"""
        if len(self.data) >= 2:
            return self.data[0] | (self.data[1] << 8)
        return None


def calculate_checksum(data: bytes) -> int:
    """
    Calculate XOR checksum for Nibe protocol
    XOR all bytes together
    """
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


def create_ack() -> bytes:
    """Create ACK message"""
    return bytes([0x06])


def create_nack() -> bytes:
    """Create NACK message"""
    return bytes([0x15])


def create_read_request(register: int) -> bytes:
    """
    Create a read register request message
    
    Args:
        register: Register address (e.g., 40004 for BT1 outdoor temp)
    
    Returns:
        Complete message bytes ready to send
    """
    data = bytearray([
        START_BYTE,              # 0xC0
        0x69,                    # Read command
        0x02,                    # Length (2 bytes for address)
        register & 0xFF,         # Address low byte
        (register >> 8) & 0xFF   # Address high byte
    ])
    data.append(calculate_checksum(data))
    return bytes(data)


def create_write_request(register: int, value: int, size: str = "s16") -> bytes:
    """
    Create a write register request message
    
    Args:
        register: Register address
        value: Value to write
        size: Data size - "s8", "u8", "s16", "u16", "s32", "u32"
    
    Returns:
        Complete message bytes ready to send
    """
    data = bytearray([
        START_BYTE,              # 0xC0
        0x6B,                    # Write command
    ])
    
    # Determine length and pack value based on size
    if size in ("s8", "u8"):
        data.append(0x03)  # Length: 3 bytes (addr low, addr high, value)
        data.append(register & 0xFF)
        data.append((register >> 8) & 0xFF)
        data.append(value & 0xFF)
    else:  # s16, u16, s32, u32
        data.append(0x06)  # Length: 6 bytes
        data.append(register & 0xFF)
        data.append((register >> 8) & 0xFF)
        data.append(value & 0xFF)
        data.append((value >> 8) & 0xFF)
        
        if size in ("s32", "u32"):
            data.append((value >> 16) & 0xFF)
            data.append((value >> 24) & 0xFF)
    
    data.append(calculate_checksum(data))
    return bytes(data)


def parse_message(buffer: bytes) -> Optional[NibeMessage]:
    """
    Parse a Nibe protocol message from buffer
    
    Args:
        buffer: Raw bytes received from serial port
    
    Returns:
        NibeMessage if valid, None otherwise
    """
    if len(buffer) < 6:  # Minimum: START + CMD + LEN + 0 data + CRC
        return None
    
    if buffer[0] != START_BYTE:
        return None
    
    start = buffer[0]
    command = buffer[1]
    length = buffer[2]
    
    # Check if we have complete message
    expected_length = 3 + length + 1  # START + CMD + LEN + DATA + CRC
    if len(buffer) < expected_length:
        return None
    
    data = buffer[3:3+length]
    checksum = buffer[3+length]
    raw = buffer[:expected_length]
    
    msg = NibeMessage(
        start=start,
        command=command,
        length=length,
        data=bytes(data),
        checksum=checksum,
        raw=raw
    )
    
    return msg if msg.is_valid else None


def decode_value(data: bytes, register_size: str) -> int:
    """
    Decode register value based on size
    
    Args:
        data: Raw data bytes from message
        register_size: "s8", "u8", "s16", "u16", "s32", "u32"
    
    Returns:
        Decoded integer value
    """
    if register_size == "s8":
        value = data[0]
        if value > 127:
            value -= 256
        return value
    
    elif register_size == "u8":
        return data[0]
    
    elif register_size == "s16":
        value = data[0] | (data[1] << 8)
        if value > 32767:
            value -= 65536
        return value
    
    elif register_size == "u16":
        return data[0] | (data[1] << 8)
    
    elif register_size == "s32":
        value = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
        if value > 2147483647:
            value -= 4294967296
        return value
    
    elif register_size == "u32":
        return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
    
    return 0


def encode_value(value: int, size: str) -> bytes:
    """
    Encode value to bytes based on size
    
    Args:
        value: Integer value to encode
        size: "s8", "u8", "s16", "u16", "s32", "u32"
    
    Returns:
        Encoded bytes
    """
    if size in ("s8", "u8"):
        if value < 0:
            value += 256
        return bytes([value & 0xFF])
    
    elif size in ("s16", "u16"):
        if value < 0 and size == "s16":
            value += 65536
        return bytes([
            value & 0xFF,
            (value >> 8) & 0xFF
        ])
    
    elif size in ("s32", "u32"):
        if value < 0 and size == "s32":
            value += 4294967296
        return bytes([
            value & 0xFF,
            (value >> 8) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 24) & 0xFF
        ])
    
    return bytes()


if __name__ == "__main__":
    # Test checksum calculation
    test_data = bytes([0xC0, 0x69, 0x02, 0x04, 0x9C])
    checksum = calculate_checksum(test_data)
    print(f"Checksum test: {checksum:02X}")
    
    # Test message creation
    read_msg = create_read_request(40004)
    print(f"Read register 40004: {read_msg.hex(' ')}")
    
    # Test ACK/NACK
    print(f"ACK: {create_ack().hex()}")
    print(f"NACK: {create_nack().hex()}")
