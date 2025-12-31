# Nibe RS-485 Protocol Reference

## Overview

The Nibe heat pump uses a proprietary protocol over RS-485 serial communication at 9600 baud, 8 data bits, no parity, 1 stop bit (8N1).

## Physical Layer

- **Interface**: RS-485 differential signaling
- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Wiring**: A, B (differential pair) + GND

## Message Structure

All messages follow this basic structure:

```
┌────────┬──────────┬────────┬──────────────┬──────────┐
│ START  │ COMMAND  │ LENGTH │     DATA     │ CHECKSUM │
├────────┼──────────┼────────┼──────────────┼──────────┤
│ 0xC0   │  1 byte  │ 1 byte │  N bytes     │  1 byte  │
└────────┴──────────┴────────┴──────────────┴──────────┘
```

### Fields

1. **START** (1 byte): Always `0xC0` (192)
2. **COMMAND** (1 byte): Message type
3. **LENGTH** (1 byte): Number of data bytes
4. **DATA** (N bytes): Payload data
5. **CHECKSUM** (1 byte): XOR of all bytes from LENGTH through end of DATA

## Checksum Calculation

```python
def calc_checksum(data: List[int]) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum
```

Example:
```
Message: C0 69 02 64 00
Checksum = 02 ^ 64 ^ 00 = 0x66
Full message: C0 69 02 64 00 66
```

## Command Types

| Command | Value | Direction | Description |
|---------|-------|-----------|-------------|
| READ_REQ | 0x69 | → Pump | Request to read register |
| READ_RESP | 0x6A | ← Pump | Response with register value |
| WRITE_REQ | 0x6B | → Pump | Request to write register |
| WRITE_RESP | 0x6C | ← Pump | Write confirmation |
| DATA_MSG | 0x68 | ← Pump | Unsolicited data (pump initiated) |
| ACK | 0x06 | → Pump | Acknowledgment |
| NACK | 0x15 | → Pump | Negative acknowledgment |
| RMU_DATA | 0x62 | ← Pump | RMU (room unit) data |
| RMU_WRITE | 0x60 | ← Pump | RMU write request |

## Read Register (0x69)

Request to read a register value.

### Request Format

```
┌────┬────┬────┬─────────┬─────────┬──────────┐
│ C0 │ 69 │ 02 │ REG_LOW │ REG_HI  │ CHECKSUM │
└────┴────┴────┴─────────┴─────────┴──────────┘
```

**Example**: Read register 40004 (0x9C44)

```
C0 69 02 44 9C 07
     │   │  └─┴─ Register address (little-endian)
     │   └────── Length (2 bytes)
     └────────── Read command
```

### Response Format (0x6A)

```
┌────┬────┬────┬─────────┬─────────┬────────────┬──────────┐
│ C0 │ 6A │ LEN│ REG_LOW │ REG_HI  │  VALUE(s)  │ CHECKSUM │
└────┴────┴────┴─────────┴─────────┴────────────┴──────────┘
```

**Example**: Response with value 235 (0x00EB) for s16/10 = 23.5°C

```
C0 6A 04 44 9C EB 00 2E
     │   │  └─┴─ Register
     │   └─────── Value bytes (little-endian)
     └────────── Length (4 bytes: reg + value)
```

## Write Register (0x6B)

Request to write a value to a register.

### Request Format

```
┌────┬────┬────┬─────────┬─────────┬────────────┬──────────┐
│ C0 │ 6B │ LEN│ REG_LOW │ REG_HI  │  VALUE(s)  │ CHECKSUM │
└────┴────┴────┴─────────┴─────────┴────────────┴──────────┘
```

**Example**: Write value 10 to register 47011 (priority)

```
C0 6B 03 D3 B7 0A 4F
     │   │  └─┴─ Register 47011 (0xB7D3)
     │   │      └─ Value: 10
     │   └────────── Length (3 bytes)
     └────────────── Write command
```

### Response Format (0x6C)

```
┌────┬────┬────┬────────┬──────────┐
│ C0 │ 6C │ 01 │ STATUS │ CHECKSUM │
└────┴────┴────┴────────┴──────────┘
```

STATUS: `0x01` = Success, `0x00` = Failure

## Data Message (0x68)

Unsolicited data message from pump (automatic updates).

```
┌────┬────┬────┬───────────────────────┬──────────┐
│ C0 │ 68 │ LEN│  Multiple Registers   │ CHECKSUM │
└────┴────┴────┴───────────────────────┴──────────┘
```

Contains multiple register-value pairs. Each pair:
```
REG_LOW REG_HI VALUE(s)
```

## Acknowledgment

After receiving most messages, the receiver should send ACK:

```
06
```

Or NACK on error:

```
15
```

## Value Encoding

Values are encoded as little-endian integers.

### Integer Types

| Type | Bytes | Range | Encoding |
|------|-------|-------|----------|
| u8 | 1 | 0 to 255 | Unsigned byte |
| s8 | 1 | -128 to 127 | Signed byte (two's complement) |
| u16 | 2 | 0 to 65535 | Unsigned word |
| s16 | 2 | -32768 to 32767 | Signed word |
| u32 | 4 | 0 to 4294967295 | Unsigned double word |
| s32 | 4 | -2147483648 to 2147483647 | Signed double word |

### Decoding Example (s16)

Raw bytes: `EB 00` (little-endian)

1. Combine: `(0x00 << 8) | 0xEB = 0x00EB = 235`
2. Check sign: 235 < 32768, so positive
3. Apply factor: 235 / 10 = 23.5

### Encoding Example (s16)

Value: -12.5°C, factor: 10

1. Multiply: -12.5 * 10 = -125
2. Two's complement: -125 → 0xFF83
3. Little-endian bytes: `83 FF`

### Negative Numbers (Two's Complement)

For signed types, if value >= threshold, subtract max:

- **s8**: if value >= 128, subtract 256
- **s16**: if value >= 32768, subtract 65536
- **s32**: if value >= 2147483648, subtract 4294967296

## Communication Flow

### Reading a Register

```
Master → Pump:  C0 69 02 44 9C 07  (Read request)
        ← Pump:  C0 6A 04 44 9C EB 00 2E  (Read response)
Master → Pump:  06  (ACK)
```

### Writing a Register

```
Master → Pump:  C0 6B 03 D3 B7 0A 4F  (Write request)
        ← Pump:  C0 6C 01 01 6D  (Write response, success)
Master → Pump:  06  (ACK)
```

### Unsolicited Data

```
        ← Pump:  C0 68 0C 44 9C EB 00 45 9C 23 01 ...  (Data message)
Master → Pump:  06  (ACK)
```

## Timing

- **Response timeout**: 5 seconds
- **Inter-message delay**: 50-100ms recommended
- **ACK delay**: Send immediately after valid message

## Error Handling

1. **Checksum mismatch**: Send NACK, ignore message
2. **Timeout**: Retry up to 3 times
3. **Invalid format**: Discard and wait for next start byte

## Example Messages

### Read Outdoor Temperature (40004)

Request:
```
C0 69 02 64 00 66
```

Response (23.5°C):
```
C0 6A 04 64 00 EB 00 8E
```
Value: `00EB` = 235, divide by 10 = 23.5°C

### Write Hot Water Setpoint (47043 = 50°C)

Request:
```
C0 6B 04 03 B8 F4 01 BC
```
- Register: `B803` = 47043
- Value: `01F4` = 500 (50.0°C * 10)

### Enable Modbus in Pump

Set register 47011 (priority) to 20 (heating):
```
C0 6B 03 D3 B7 14 5B
```

## Protocol Tips

1. **Always validate checksum** before processing
2. **Send ACK** for data messages to keep pump happy
3. **Don't poll too fast** - 0.5-1 second between reads
4. **Handle timeouts gracefully** - pump may be busy
5. **Test reads before writes** - verify communication first
6. **Keep a message queue** - process sequentially
7. **Log all traffic** during debugging

## Debugging

Enable raw message logging:

```python
def log_message(direction: str, data: bytes):
    hex_str = data.hex().upper()
    formatted = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
    print(f"{direction} {formatted}")

# Usage
log_message("TX:", bytes([0xC0, 0x69, 0x02, 0x64, 0x00, 0x66]))
log_message("RX:", bytes([0xC0, 0x6A, 0x04, 0x64, 0x00, 0xEB, 0x00, 0x8E]))
```

Output:
```
TX: C0 69 02 64 00 66
RX: C0 6A 04 64 00 EB 00 8E
```

## References

- Nibe Modbus documentation (from manufacturer)
- Original nibepi project: https://github.com/anerdins/nibepi
- RS-485 standard: EIA/TIA-485-A

## Notes for Nibe 360P

⚠️ The 360P may have some protocol variations from F-series pumps:

- Different register addresses
- Different data message format
- May require different initialization sequence

Always verify with your specific model's documentation!
