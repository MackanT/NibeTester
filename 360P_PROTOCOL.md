# Nibe 360P Protocol - CORRECTED INFORMATION

## Critical Discoveries

Based on the Swedish forum [elektronikforumet.com](https://elektronikforumet.com/forum/viewtopic.php?f=4&t=13714&start=83), the Nibe 360P uses a **completely different protocol** than initially assumed:

### Key Differences from F-Series

| Aspect | F-Series (nibepi) | 360P (Actual) |
|--------|-------------------|---------------|
| **Baudrate** | 9600 | **19200** |
| **Data Bits** | 8 | **8 + parity bit (9-bit mode)** |
| **Parity** | None | **Mark/Space** |
| **Protocol** | Active polling | **Passive listening** |
| **Addressing** | Modbus-like registers | **Parameter indices** |

## The 360P Protocol

### 1. Serial Settings

```
Baudrate: 19200
Data bits: 8
Parity: MARK for receiving, SPACE for transmitting
Stop bits: 1
Format: 19200, 8, M/S, 1
```

### 2. 9-Bit Mode

The protocol uses the **parity bit as a 9th data bit**:
- **Bit 9 = 1 (MARK parity)**: Address byte
- **Bit 9 = 0 (SPACE parity)**: Data byte

### 3. Communication Flow

The 360P system has a **master** (main control board, address 0x24) that polls various nodes:

**Nodes:**
- `0x14` = RCU (Room Control Unit) - **This is what we emulate!**
- `0x24` = Main control board (Master)
- `0xF5` = Relay board
- `0xF9` = Display board

**Sequence:**

1. **Master addresses RCU:**
   ```
   *00 *14
   ```
   (Asterisk `*` means bit 9 = 1)

2. **RCU responds:**
   - `0x06` (ACK) = "I'm here, nothing to report"
   - `0x05` (ENQ) = "I have data to send"

3. **Master sends data** (if RCU sent ACK):
   ```
   C0 00 24 <len> [00 <param> <value>...]* <checksum>
   ```

4. **RCU acknowledges:**
   ```
   06
   ```

### 4. Data Packet Format

```
┌────┬────┬────────┬────────┬─────────────────────────┬──────────┐
│ C0 │ 00 │ SENDER │ LENGTH │   PARAMETER DATA        │ CHECKSUM │
└────┴────┴────────┴────────┴─────────────────────────┴──────────┘
```

**Example from forum:**
```
C0 00 24 11 00 04 01 25 00 05 01 10 00 06 01 42 00 07 01 66 01 E5
│  │  │  │  │  │  └─┴─ Value: 0x0125 = 293 / 10 = 29.3°C
│  │  │  │  │  └────── Parameter index: 0x04
│  │  │  │  └───────── Always 0x00 before parameter
│  │  │  └──────────── Length: 0x11 = 17 bytes
│  │  └─────────────── Sender: 0x24 (Master)
│  └────────────────── Always 0x00
└───────────────────── Command: 0xC0 (data for RCU)
```

### 5. Checksum

XOR of all bytes from `C0` to last data byte (excluding checksum itself).

```python
checksum = C0 ^ 00 ^ 24 ^ 11 ^ 00 ^ 04 ^ 01 ^ 25 ^ ... = E5
```

### 6. Parameter Indices (NOT Modbus Registers!)

Your "Register 2" from the Modbus documentation is actually **Parameter Index 0x01**:

| Index | Bytes | Description | Factor | Unit |
|-------|-------|-------------|--------|------|
| 0x00 | 1 | CPU ID (0x20=360P) | 1 | - |
| **0x01** | **2** | **Outdoor Temperature** | **10** | **°C** |
| 0x02 | 2 | Hot Water Temperature | 10 | °C |
| 0x03 | 2 | Exhaust Air Temp | 10 | °C |
| 0x04 | 2 | Extract Air Temp | 10 | °C |
| 0x05 | 2 | Evaporator Temp | 10 | °C |
| 0x06 | 2 | Supply Temperature | 10 | °C |
| 0x07 | 2 | Return Temperature | 10 | °C |
| 0x08 | 2 | Compressor Temp | 10 | °C |
| 0x09 | 2 | Electric Heater Temp | 10 | °C |
| 0x0B | 1 | Heat Curve Slope | 1 | - |
| 0x0C | 1 | Heat Curve Offset | 1 | °C |

## Implementation Strategy

### Passive Listening Mode (Recommended First)

**Simplest approach:**
1. Listen on the bus with MARK parity (19200, 8, M, 1)
2. Detect addressing: `0x00 0x14`
3. Send ACK with SPACE parity: `0x06`
4. Receive data packet
5. Parse parameters
6. Send ACK: `0x06`

**Advantages:**
- No need to actively poll
- Master sends all data automatically
- Less risk of disrupting system

### Active Mode (Advanced)

To write parameters or request specific data, reply with `0x05` (ENQ) instead of ACK.

## Python Implementation

See `nibe360p_corrected.py` for the correct implementation using:
- 19200 baud
- MARK/SPACE parity for 9-bit simulation
- Passive listening mode
- Parameter index addressing

## Why Previous Code Failed

1. **Wrong baudrate**: Used 9600 instead of 19200
2. **Wrong protocol**: Tried to actively poll like Modbus
3. **Wrong addressing**: Used Modbus registers instead of parameter indices
4. **Missing 9-bit handling**: Didn't use MARK/SPACE parity

## Testing the Corrected Version

```powershell
python nibe360p_corrected.py
```

The program will:
1. Listen for RCU addressing (0x00 0x14)
2. Respond with ACK
3. Receive and parse data automatically
4. Display all parameters in real-time

## Timing Considerations

- Master polls RCU regularly (every few seconds)
- Must respond to addressing quickly
- PC response time is usually fast enough
- If issues: Consider using microcontroller with auto-timing RS485

## Hardware Notes

From forum discussions:
- Can draw 5V/12V from heat pump's RS485 port
- Use proper RS485 transceiver (MAX485 or similar)
- Galvanic isolation recommended for safety

## Next Steps

1. ✅ Test corrected code at 19200 baud
2. Verify parameter index 0x01 (outdoor temp)
3. Map remaining parameters from your manual
4. Implement parameter writing if needed

## Credits

Protocol information from:
- FredRovers, cosmos, and others on elektronikforumet.com
- Thread: "PC-styrning av Bergvärmepump"
- Years of community reverse engineering!
