# Nibe 360P Heat Pump RS-485 Communication

Python implementation for communicating with Nibe 360P heat pump via RS-485 serial interface.

Based on the [nibepi project](https://github.com/anerdins/nibepi) but reimplemented in Python for the Nibe 360P model.

## Features

- ✅ Read register values (temperatures, status, etc.)
- ✅ Write register values (settings)
- ✅ Real-time monitoring
- ✅ Data logging to CSV
- ✅ Alarm monitoring
- ✅ Threaded serial communication
- ✅ Protocol checksum validation
- ✅ Automatic acknowledgment handling

## Hardware Requirements

- Nibe 360P heat pump
- RS-485 to USB/Serial adapter
- Connection to heat pump's RS-485 interface (A, B, GND, optionally 12V)

## Wiring

Connect your RS-485 adapter to the heat pump's communication port:

```
Heat Pump     RS-485 Adapter
---------     --------------
A         ->  A (or D+)
B         ->  B (or D-)
GND       ->  GND
12V       ->  VCC (optional, if adapter needs power)
```

**Important**: Check your heat pump manual for the correct pins! The 360P should have similar connections to the F-series pumps.

## Software Requirements

```bash
pip install pyserial
```

Or if using the project's `pyproject.toml`:

```bash
uv sync
# or
pip install -e .
```

## Quick Start

1. **Configure your serial port**:

   Copy `config.example.py` to `config.py` and edit:

   ```python
   SERIAL_PORT = 'COM3'  # Windows
   # or
   SERIAL_PORT = '/dev/ttyUSB0'  # Linux
   ```

2. **Update register definitions**:

   Edit `registers_360p.py` with the actual register addresses from your Nibe 360P documentation. The example registers are based on F-series pumps and may need adjustment.

3. **Run examples**:

   ```bash
   python examples.py
   ```

   Or run directly:

   ```bash
   python main.py
   ```

## Usage Examples

### Basic Reading

```python
from main import NibeHeatPump
from registers_360p import NIBE_360P_REGISTERS, IMPORTANT_REGISTERS

# Create instance
pump = NibeHeatPump('COM3', registers=NIBE_360P_REGISTERS)

# Connect
if pump.connect():
    # Read outdoor temperature
    temp = pump.read_register(IMPORTANT_REGISTERS['outdoor_temp'])
    print(f"Outdoor: {temp}°C")
    
    # Disconnect
    pump.disconnect()
```

### Continuous Monitoring

```python
# Add callback for updates
def on_data(register, name, value, unit):
    print(f"{name}: {value} {unit}")

pump.add_callback(on_data)
pump.connect()

# Poll registers every 10 seconds
while True:
    pump.read_register(40004)  # Outdoor temp
    pump.read_register(40008)  # Supply temp
    time.sleep(10)
```

### Writing Values

```python
# Change hot water setpoint to 50°C
pump.write_register(47043, 50.0)
```

### Data Logging

```python
import csv
from datetime import datetime

with open('log.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'register', 'value'])
    
    def log_data(register, name, value, unit):
        writer.writerow([datetime.now(), name, value])
    
    pump.add_callback(log_data)
    # ... continue monitoring
```

## Register Definitions

Registers are defined in `registers_360p.py`. Each register has:

- **address**: Register number (e.g., 40004)
- **name**: Human-readable name
- **size**: Data type ('s16', 'u16', 's32', etc.)
- **factor**: Division factor (10.0 means value is divided by 10)
- **unit**: Unit of measurement
- **writable**: Whether the register can be written to

**Important**: You must obtain the correct register list for your specific Nibe 360P model. The included registers are examples and may not match your system.

## Protocol Details

The Nibe protocol uses RS-485 serial communication at 9600 baud:

### Message Structure

```
[START] [CMD] [LEN] [DATA...] [CHECKSUM]
 0xC0    0x69  0x02  reg_addr   XOR
```

### Message Types

- `0x69` - Read request
- `0x6A` - Read response
- `0x6B` - Write request
- `0x6C` - Write response
- `0x68` - Data message (pump initiated)
- `0x06` - ACK
- `0x15` - NACK

### Checksum

XOR of bytes from length field to last data byte.

## Finding Your Registers

To find the correct register addresses for your Nibe 360P:

1. Check your heat pump's service manual
2. Use Nibe Uplink (if available) to see parameter IDs
3. Contact Nibe support for technical documentation
4. Check Nibe Modbus documentation
5. Use a Modbus scanner tool to probe available registers

## Troubleshooting

### Connection Issues

- **Check serial port**: Use Device Manager (Windows) or `ls /dev/tty*` (Linux)
- **Verify baud rate**: Should be 9600 for Nibe pumps
- **Check wiring**: A/B might be swapped
- **Enable Modbus**: Heat pump service menu → Settings 5.2 → Enable Modbus

### No Data Received

- Heat pump may not be sending data messages automatically
- Try reading specific registers
- Check that Modbus is enabled in the heat pump
- Some models require a "token" to be sent first

### Checksum Errors

- Electrical interference on RS-485 bus
- Wrong baud rate
- Incorrect protocol implementation
- Use shielded cable and proper termination

### Permission Denied (Linux)

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

## Safety and Warnings

⚠️ **IMPORTANT**: 

- Only modify settings if you understand their effect
- Incorrect settings can damage your heat pump
- Always test read operations before attempting writes
- Keep a record of original settings before making changes
- This software is provided as-is with no warranties

## Advanced Features (TODO)

Possible extensions:

- [ ] MQTT integration for Home Assistant
- [ ] Web dashboard with Flask/FastAPI
- [ ] InfluxDB data export
- [ ] Automatic retry and error recovery
- [ ] Configuration file validation
- [ ] Register auto-discovery
- [ ] Alarm notifications (email, webhook)
- [ ] Historical data analysis

## References

- [nibepi GitHub Repository](https://github.com/anerdins/nibepi) - Original Node.js implementation
- [Nibe Modbus Documentation](https://www.nibe.eu/en-eu/support)
- [RS-485 Protocol Basics](https://en.wikipedia.org/wiki/RS-485)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:

1. Test thoroughly with your heat pump
2. Document register addresses and their meanings
3. Include examples for new features
4. Follow existing code style

## Support

This is an independent project not affiliated with Nibe. For heat pump issues, contact Nibe support.

For code issues, please open a GitHub issue with:
- Your heat pump model
- Serial adapter details
- Error messages and logs
- Configuration used

## Acknowledgments

- Thanks to [anerdins](https://github.com/anerdins) for the original nibepi project
- Nibe heat pump community for documentation and testing
