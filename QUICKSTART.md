# Quick Reference Guide - Nibe 360P

## Installation

```bash
# Install dependencies
pip install pyserial

# Or using uv
uv sync
```

## First Time Setup

1. **Connect RS-485 adapter** to your computer
2. **Find serial port**:
   - Windows: Check Device Manager → Ports (COM & LPT)
   - Linux: `ls /dev/tty*` or `dmesg | grep tty`
   - macOS: `ls /dev/tty.*`

3. **Create config file**:
   ```bash
   cp config.example.py config.py
   # Edit config.py with your serial port
   ```

4. **Update registers** in `registers_360p.py` with your actual 360P register list

5. **Enable Modbus on heat pump**:
   - Enter service menu (hold BACK button ~7 seconds)
   - Go to Settings 5.2
   - Enable "Modbus"

## Common Commands

### Test Connection

```python
python examples.py  # Choose option 1
```

### Read Single Register

```python
from main import NibeHeatPump
from registers_360p import NIBE_360P_REGISTERS

pump = NibeHeatPump('COM3', registers=NIBE_360P_REGISTERS)
pump.connect()
value = pump.read_register(40004)  # Outdoor temp
print(f"Value: {value}")
pump.disconnect()
```

### Monitor Temperatures

```bash
python examples.py  # Choose option 6 (Dashboard)
```

### Log Data

```bash
python examples.py  # Choose option 4 (CSV logging)
```

## Important Register Addresses (Example - Verify for 360P!)

| Address | Name | Type | Unit | R/W |
|---------|------|------|------|-----|
| 40004 | Outdoor Temperature | s16/10 | °C | R |
| 40008 | Supply Temperature | s16/10 | °C | R |
| 40012 | Return Temperature | s16/10 | °C | R |
| 40013 | Hot Water Temperature | s16/10 | °C | R |
| 43005 | Degree Minutes | s16/10 | DM | R |
| 43136 | Compressor Frequency | s16 | Hz | R |
| 45001 | Alarm Number | s16 | - | R |
| 47011 | Priority | s8 | - | RW |
| 47043 | Hot Water Setpoint | s16/10 | °C | RW |

**Note**: These addresses are examples. Verify with your 360P documentation!

## Register Size Types

- `u8` = Unsigned 8-bit (0-255)
- `s8` = Signed 8-bit (-128 to 127)
- `u16` = Unsigned 16-bit (0-65535)
- `s16` = Signed 16-bit (-32768 to 32767)
- `u32` = Unsigned 32-bit (0-4294967295)
- `s32` = Signed 32-bit (-2147483648 to 2147483647)

## Value Factors

If a register has factor=10, divide the raw value by 10:
- Raw value: 235 → Actual value: 23.5°C

## Priority Values (Register 47011)

- `0` = Off
- `10` = Hot Water
- `20` = Heat
- `30` = Pool
- `40` = Transfer
- `60` = Cooling

## Message Types

- `0x69` (105) = Read request
- `0x6A` (106) = Read response
- `0x6B` (107) = Write request
- `0x6C` (108) = Write response
- `0x68` (104) = Data message (pump initiated)
- `0x06` (6) = ACK
- `0x15` (21) = NACK

## Troubleshooting Quick Fixes

### Can't find serial port
```bash
# Windows
mode  # Lists COM ports

# Linux
ls -l /dev/ttyUSB* /dev/ttyAMA*
sudo dmesg | grep tty

# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER
```

### Permission denied (Linux)
```bash
sudo chmod 666 /dev/ttyUSB0  # Temporary
# or
sudo usermod -a -G dialout $USER  # Permanent (requires logout)
```

### No response from heat pump
1. Check Modbus is enabled in heat pump
2. Verify RS-485 wiring (A/B may be swapped)
3. Check baud rate is 9600
4. Try swapping A and B wires
5. Ensure proper grounding

### Checksum errors
1. Check electrical connections
2. Use shielded cable
3. Reduce cable length
4. Add RS-485 termination resistor (120Ω)

### Wrong values
1. Verify register address is correct for 360P
2. Check size type (s16 vs u16)
3. Verify factor (divide by 10?)

## File Structure

```
NibeTester/
├── main.py              # Main communication class
├── registers_360p.py    # Register definitions
├── examples.py          # Usage examples
├── config.py            # Your configuration (create from .example)
├── config.example.py    # Example configuration
├── README.md            # Full documentation
├── QUICKSTART.md        # This file
└── pyproject.toml       # Python project config
```

## Next Steps

1. ✅ Test basic connection with `python examples.py`
2. ✅ Verify register addresses work for your 360P
3. ✅ Update `registers_360p.py` with correct addresses
4. ✅ Set up continuous monitoring
5. ⬜ Add your specific use case (logging, automation, etc.)

## Getting Register Documentation

Contact Nibe support or check:
- Heat pump service manual
- Nibe Uplink parameter IDs
- Modbus register documentation
- Community forums (e.g., Home Assistant)

## Support

For issues:
1. Check this guide first
2. Review README.md
3. Check example code in examples.py
4. Search GitHub issues
5. Create new issue with full details

## Safety Reminder

⚠️ **Always test read operations before writing!**
⚠️ **Keep a backup of original settings**
⚠️ **Incorrect settings can damage equipment**
