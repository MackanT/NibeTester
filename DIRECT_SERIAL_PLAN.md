# Nibe Fighter 360P - Direct Serial Communication (Python)

## Project Goal
Build a Python application to communicate directly with Nibe Fighter 360P via RS485 serial connection, replicating the nibepi functionality.

## Hardware Requirements

### Essential Components
1. **USB to RS485 Adapter**
   - Recommended: FTDI-based adapters for better driver support
   - Examples:
     - DSD TECH USB to RS485 Converter
     - Waveshare USB TO RS485
     - Any CH340/FTDI USB-RS485 adapter

2. **Connection to Nibe**
   - **4-wire cable** from Nibe to adapter
   - Connections needed:
     - **A** (RS485+)
     - **B** (RS485-)
     - **GND** (Ground)
     - **12V** (optional - power from Nibe, not needed if using USB power)

### Physical Setup
```
Nibe Fighter 360P → RS485 A/B → USB-RS485 Adapter → PC USB Port
```

## Protocol Analysis (From nibepi)

### Communication Pattern
The Nibe uses a **proprietary protocol** (NOT standard Modbus RTU), with these characteristics:

1. **Message Format:**
   ```
   [0xC0] [CMD] [LEN] [DATA...] [CRC]
   ```

2. **Key Commands:**
   - `0x69` - Read register
   - `0x6B` - Write register
   - `0x6A` - Announcement/status
   - `0x68` - Data response (read)
   - `0x6C` - Write acknowledgment

3. **Register Addressing:**
   - Temperature sensors: 40000 range
   - Status info: 43000 range
   - Settings (R/W): 47000 range
   - RMU (room units): 10000 range

4. **Flow Control:**
   - Pump sends periodic announcements
   - Must respond with ACK (`0x06`) or NACK (`0x15`)
   - Request registers during idle periods

### Example Register Read
**From Nibe docs:** `00 00 00 00 00 06 01 03 00 00 00 01`
- This is for **Modbus TCP**, not the serial protocol
- The serial protocol is different!

**Serial protocol example (from nibepi):**
```python
# Read register 40004 (BT1 Outdoor temp)
msg = [0xC0, 0x69, 0x02, 0x04, 0x9C, CRC]
# 0xC0 = Start
# 0x69 = Read command
# 0x02 = Length
# 0x04 0x9C = Register 40004 (little-endian)
# CRC = XOR checksum
```

## Python Implementation Plan

### Phase 1: Serial Communication
```python
import serial
import struct

class NibeSerial:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
    
    def calculate_crc(self, data):
        """XOR checksum"""
        crc = 0
        for byte in data:
            crc ^= byte
        return crc
    
    def send_ack(self):
        self.ser.write(bytes([0x06]))
    
    def send_nack(self):
        self.ser.write(bytes([0x15]))
```

### Phase 2: Message Parsing
```python
def parse_message(data):
    if len(data) < 6:
        return None
    
    if data[0] != 0xC0:
        return None
    
    cmd = data[1]
    length = data[2]
    payload = data[3:3+length]
    crc = data[3+length]
    
    # Verify CRC
    calc_crc = calculate_crc(data[:3+length])
    if calc_crc != crc:
        return None
    
    return {
        'cmd': cmd,
        'data': payload
    }
```

### Phase 3: Register Operations
```python
def read_register(address):
    """Read a register from Nibe"""
    msg = bytearray([
        0xC0,           # Start
        0x69,           # Read command
        0x02,           # Length
        address & 0xFF, # Address low byte
        (address >> 8) & 0xFF  # Address high byte
    ])
    msg.append(calculate_crc(msg))
    return msg

def decode_temperature(raw_value):
    """Most temps are signed 16-bit / 10"""
    if raw_value > 32767:
        raw_value -= 65536
    return raw_value / 10.0
```

## Next Steps

1. **Get Hardware:** Order USB-RS485 adapter
2. **Analyze nibepi Code:** Study `backend.js` for exact protocol details
3. **Build Python Parser:** Create serial message handler
4. **Test Reading:** Start with simple register reads
5. **Build Register Database:** Port Nibe register definitions
6. **Add MQTT/API:** Expose data to Home Assistant, etc.

## Key Differences from Modbus

| Aspect | Standard Modbus | Nibe Protocol |
|--------|----------------|---------------|
| Start byte | None | 0xC0 |
| CRC | CRC16 (Modbus) | XOR checksum |
| Function codes | Standard (0x03, 0x04, etc.) | Custom (0x69, 0x6B, etc.) |
| Flow control | Request/response | ACK required for announcements |
| Protocol | Documented standard | Proprietary Nibe |

## Advantages of Direct Serial

✅ **No RCU needed** - Direct connection to pump  
✅ **Full control** - Not limited by RCU features  
✅ **Lower latency** - Direct serial communication  
✅ **Python** - Easier to understand and modify  
✅ **Learning** - Understand the protocol deeply

## Resources

- **nibepi repository:** Study `backend.js` and `index.js` for protocol details
- **Nibe register docs:** Check models/ folder in nibepi for register definitions
- **Serial debugging:** Use a logic analyzer or serial sniffer to verify messages
- **Python libraries:**
  - `pyserial` - Serial port communication
  - `struct` - Binary data packing/unpacking
  - `asyncio` - Async message handling

## Estimated Timeline

- **Day 1-2:** Get hardware, set up serial connection
- **Day 3-5:** Implement protocol parser from nibepi analysis
- **Day 6-7:** Test register reading
- **Week 2:** Build full register database and data structures
- **Week 3+:** Add features (MQTT, web UI, logging, etc.)

Ready to start building? 🚀
