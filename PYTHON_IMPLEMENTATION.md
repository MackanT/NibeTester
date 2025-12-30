# Nibe Fighter 360P - Python Implementation

Python implementation for direct RS485 serial communication with Nibe Fighter 360P heat pump.

## Files Created

### Core Protocol
- **`nibe_protocol.py`** - Protocol definitions, message parsing, checksum calculation
- **`nibe_serial.py`** - Serial communication handler with threading
- **`nibe_registers.py`** - Fighter 360P register database

### Applications
- **`test_nibe.py`** - Simple test app to read temperature sensors

## Hardware Requirements

**USB-to-RS485 Adapter:**
- Any FTDI or CH340-based USB-RS485 converter
- Examples:
  - DSD TECH SH-U11
  - Waveshare USB TO RS485
  - USR-USB-RS485

**Connections:**
```
Nibe Fighter 360P    USB-RS485 Adapter
     A         →          A (or Data+)
     B         →          B (or Data-)
    GND        →          GND
```

## Installation

```powershell
# Install required package
.venv\Scripts\pip install pyserial
```

## Usage

### 1. Find Your Serial Port

**Windows:**
```powershell
# List COM ports
Get-CimInstance -ClassName Win32_SerialPort | Select-Object Name, DeviceID

# Or use Device Manager → Ports (COM & LPT)
```

**Linux:**
```bash
# List USB serial devices
ls /dev/ttyUSB*
# Usually: /dev/ttyUSB0
```

### 2. Update Port in test_nibe.py

Edit `test_nibe.py` line 17:
```python
SERIAL_PORT = "COM3"  # Change to your port!
```

### 3. Run Test

```powershell
.venv\Scripts\python.exe test_nibe.py
```

## Expected Output

```
======================================================================
Nibe Fighter 360P - Temperature Monitor
======================================================================
Serial Port: COM3
======================================================================
✓ Connected to Nibe heat pump

Waiting for initial communication...

Requesting temperature sensors...
----------------------------------------------------------------------
  BT1 Outdoor Temperature: 5.2 °C
  BT2 Supply Temperature S1: 35.8 °C
  BT3 Return Temperature S1: 30.1 °C
  BT7 Hot Water Top: 48.3 °C
  ...

Summary - Received Values:
======================================================================
BT1 Outdoor Temperature                 :    5.2 °C
BT2 Supply Temperature S1               :   35.8 °C
...
```

## Protocol Details

### Message Format
```
[0xC0] [CMD] [LEN] [DATA...] [CRC]

0xC0    - Start byte (constant)
CMD     - Command byte
LEN     - Length of DATA
DATA    - Payload (register address, values, etc.)
CRC     - XOR checksum of all previous bytes
```

### Key Commands
- `0x69` - Read register request
- `0x68` - Data response from pump
- `0x6B` - Write register request
- `0x06` - ACK (acknowledge)
- `0x15` - NACK (negative acknowledge)

### Communication Flow
1. Pump sends periodic announcements
2. PC must respond with ACK (0x06)
3. PC can request registers between announcements
4. Pump responds with data messages
5. PC acknowledges data with ACK

## Next Steps

### Add More Features
1. **Continuous Monitoring:**
   - Loop reading registers every N seconds
   - Log to file or database

2. **Web Interface:**
   - Flask/FastAPI web dashboard
   - Real-time temperature graphs

3. **MQTT Integration:**
   - Publish to MQTT broker
   - Home Assistant integration

4. **Write Operations:**
   - Control hot water production
   - Adjust heating settings
   - Be careful - test thoroughly!

### Expand Register Database
The `nibe_registers.py` file currently has ~20 registers. The full Nibe register set has hundreds more. You can add them from:
- nibepi repository: `models/` folder
- Nibe official documentation
- Reverse engineering from RCU11

## Troubleshooting

**"Failed to connect":**
- Check COM port number
- Verify USB-RS485 adapter is plugged in
- Check Windows Device Manager for port

**No data received:**
- Verify A/B wiring (try swapping A↔B if no response)
- Check GND connection
- Ensure Modbus is enabled on Nibe (Menu 5.2)
- Baudrate must be 9600

**Invalid checksums:**
- Serial interference
- Wrong baudrate
- Wiring issues

**Pump alarm after connecting:**
- Normal if interrupting RCU communication
- Connect to different RS485 port if available
- Or use "sniffer" mode (passive listening)

## Safety Notes

⚠️ **Be Careful:**
- Don't write to registers you don't understand
- Test read-only operations first
- Keep RCU11 as backup
- Monitor pump for errors during testing

## Resources

- **nibepi source:** https://github.com/anerdins/nibepi
- **Nibe Modbus docs:** Check Nibe support site
- **Python serial docs:** https://pyserial.readthedocs.io/

---

Created: December 30, 2025
Based on: anerdins/nibepi JavaScript implementation
