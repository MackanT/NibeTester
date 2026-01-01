# Nibe 360P Heat Pump RS-485 Communication

Python implementation for communicating with Nibe 360P heat pump via RS-485 serial interface.

This project was developed through trial-and-error, reverse engineering and protocol documentation found in a [Swedish forum post from 2007](https://elektronikforumet.com/forum/viewtopic.php?f=2&t=35278&start=150#p389557). The Nibe 360P uses a **custom protocol** (not Modbus) that is fundamentally different from newer F-series pumps.

## What This Does

- ✅ Passively reads parameters by responding to the pump's polling
- ✅ Decodes temperatures, settings, and status values
- ✅ Smart collection mode (reads once until complete, then stops)
- ✅ Checksum validation for data integrity
- ✅ Diagnostic mode for protocol analysis

## Hardware Requirements

- **Nibe 360P heat pump** (older model, NOT F-series)
- **RS-485 to USB adapter** supporting 9-bit mode
- Connection to heat pump's RS-485 bus

## Wiring

Connect your RS-485 adapter to the heat pump's communication port:

```
Heat Pump     RS-485 Adapter
---------     --------------
A         ->  A (or D+)
B         ->  B (or D-)
GND       ->  GND
```

⚠️ **Note**: The 360P uses a different connector than newer models. Check your specific heat pump documentation.

## Installation

```bash
# Install dependencies
pip install pyserial

# Or using uv
uv sync
```

## Quick Start

1. **Edit the serial port** in `main.py`:
   ```python
   SERIAL_PORT = "/dev/ttyUSB0"  # Linux
   # or
   SERIAL_PORT = "COM3"  # Windows
   ```

2. **Run the program**:
   ```bash
   python main.py
   ```

3. **Choose mode**:
   - Option 1: Diagnostic mode (captures raw bus traffic)
   - Option 2: Normal mode (reads all parameters once)

## How It Works

The Nibe 360P uses a **master-slave protocol** where the heat pump (master) polls the room control unit (RCU/slave):

### Protocol Flow

```
1. Pump addresses RCU:  *00 *14  (bytes with 9th bit set)
2. RCU acknowledges:     06      (ACK - "I'm ready")
3. Pump sends data:      C0 00 24 <len> [00 <param> <value>...] <checksum>
4. RCU acknowledges:     06      (ACK - "data received")
5. Pump ends:            *03     (ETX - "transmission complete")
```

The asterisk (*) denotes bytes with the 9th bit set to 1 (achieved via MARK parity).

### Key Protocol Details

- **Baudrate**: 19200 baud
- **Format**: 9-bit mode (8N1 + 9th bit via MARK/SPACE parity switching)
- **Addressing**: RCU = 0x14, Pump = 0x24
- **Packet format**: `C0 00 24 <len> [00 <param_idx> <value_bytes>]* <checksum>`
- **Checksum**: XOR of all bytes from C0 (inclusive) to last data byte
- **Byte order**: Big-endian (HIGH byte first, LOW byte second)
- **Parameter sizes**: 1-byte or 2-byte values per parameter

### Parameter Definitions

Parameters are defined with:
- **index**: Parameter identifier (0x00-0xFF)
- **name**: Human-readable name (Swedish)
- **size**: 1 or 2 bytes
- **factor**: Division factor (typically 10.0 for temperatures)
- **unit**: Unit of measurement

Example parameters:
- `0x01`: Outdoor temperature (2 bytes, ÷10 = °C)
- `0x0B`: Heat curve slope (1 byte, raw value)
- `0x02`: Hot water tank temperature (2 bytes, ÷10 = °C)

See `nibe360p_active.py` for the complete parameter list.

## Usage Examples

### Reading All Parameters Once

```bash
$ python nibe360p_active.py
Choose option [1/2] (default: 2): 2

📖 Reading Parameters from Pump
======================================================================
Collecting all parameters... This may take a few cycles.

✅ RCU addressed by pump!
📤 Sending ACK (ready to receive)...
📦 Complete packet received: C0 00 24 0F 00 01 ...
✅ Received 4 parameters (4 new)
...
📊 Collection Complete: 15 unique parameters

🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉
  SUCCESS! Captured 15 parameters:
🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉

  [01] Utetemperatur................       -2.3 °C
  [02] Temperatur VV-givare.........       48.5 °C
  [06] Framledningstemp.............       35.2 °C
  [0B] Kurvlutning..................        5.0 
  ...
```

### Diagnostic Mode

```bash
$ python nibe360p_active.py
Choose option [1/2] (default: 2): 1

📡 Capturing bus traffic for 15 seconds...

000.12s: 00 14 06 C0 00 24 0F 00 01 FF 69 00 02 01 E5 ...
...
📊 Analysis:
  - Found '00 14' pattern: 3 times
  - Found 'C0' (data start): 3 times
```

## Troubleshooting

### Connection Issues

```bash
# Check serial port exists
ls /dev/ttyUSB*  # Linux
# or Device Manager on Windows

# Fix permissions (Linux)
sudo usermod -a -G dialout $USER
# Log out and back in

# Or quick fix:
sudo chmod 666 /dev/ttyUSB0
```

### No Data Received

- Verify RS-485 wiring (swap A/B if needed)
- Check that the heat pump is powered on
- Use diagnostic mode (option 1) to see raw bus traffic
- Ensure USB-RS-485 adapter supports 9-bit mode

### Checksum Errors

- Electrical interference - use shielded cable
- Wrong baud rate - must be 19200
- Protocol mismatch - this only works with 360P, not F-series

### Wrong Values

- Check parameter size definitions (1 vs 2 bytes)
- Verify factor (temperatures use 10.0)
- Confirm byte order (big-endian for 360P)

## Protocol Differences vs F-Series

| Aspect | Nibe 360P | Nibe F-Series |
|--------|-----------|---------------|
| Baudrate | 19200 | 9600 |
| Protocol | Custom Nibe | Modbus-like |
| Addressing | Parameter index (0x00-0xFF) | Modbus registers (40xxx) |
| Byte order | Big-endian | Little-endian |
| 9th bit | Required (MARK/SPACE) | Same |

**Do NOT use F-series tools/docs for the 360P!** They are incompatible.

## Limitations

- **Read-only**: Currently only reads parameters (no writing)
- **Parameter discovery**: You must know parameter indices beforehand
- **Single RCU**: Emulates one room control unit only
- **No continuous monitoring**: Designed to read once and finish

## References

- [Swedish forum post (2007)](https://elektronikforumet.com/forum/viewtopic.php?f=2&t=35278&start=150#p389557) - Original protocol documentation
- [RS-485 Basics](https://en.wikipedia.org/wiki/RS-485)
- pyserial documentation for 9-bit mode

## License

MIT License - See LICENSE file for details

## Disclaimer

⚠️ **IMPORTANT**:
- This is unofficial reverse-engineered software
- Not affiliated with or endorsed by Nibe
- Use at your own risk
- No warranties provided
- Test thoroughly before relying on data

## Contributing

Contributions welcome! If you have:
- Additional parameter definitions
- Protocol insights for other 360P variants  
- Bug fixes or improvements

Please open an issue or pull request.

## Support

This is an independent hobby project. For official heat pump support, contact Nibe directly.

For code issues, please provide:
- Heat pump model and firmware version
- RS-485 adapter details
- Complete error logs
- Output from diagnostic mode (option 1)




# Parameter definitions for Nibe 360P
NIBE_360P_PARAMETERS = [
    Register(0x00, "Produktkod", 1, 1.0, "", False, ""),
    Register(
        0x01, "Utetemperatur", 2, 10.0, "°C", False, "M4.0"
    ),  ## Undersök, ~-5.4C. Medeltemp ute ~2.2C (M4.2)
    Register(0x02, "Temperatur VV-givare", 2, 10.0, "°C", False, "M1.0"),
    Register(0x03, "Avluftstemperatur", 2, 10.0, "°C", False, "M5.1"),
    Register(0x04, "Frånluftstemperatur", 2, 10.0, "°C", False, "M5.2"),
    Register(0x05, "Förångartemperatur", 2, 10.0, "°C", False, "M5.0"),
    Register(0x06, "Framledningstemp.", 2, 10.0, "°C", False, "M2.0"),
    Register(0x07, "Returtemperatur", 2, 10.0, "°C", False, "M2.6"),
    Register(0x08, "Temperatur kompressorgivare", 2, 10.0, "°C", False, "M1.1"),
    Register(0x09, "Temperatur elpatrongivare", 2, 10.0, "°C", False, "M1.2"),
    Register(0x0B, "Kurvlutning", 1, 1.0, "", True, "M2.1", -1, 15, 1),
    Register(0x0C, "Förskjutning värmekurva", 1, 1.0, "", False, "M2.2", -10, 10),
    Register(0x0D, "Beräknad framledningstemp.", 1, 1.0, "°C", False, "M2.0"),
    Register(0x13, "Kompressor", 1, 1.0, "", False, ""),  # Bitmask!
    # Register(0x13, "Cirkulationspump 1", 1, 1.0, "", False, "M9.1.4"),
    Register(
        0x14, "Tillsatsvärme", 2, 1.0, "", False, ""
    ),  # Do something with bitmask!
    # Register(0x14, "Driftläge säsong", 2, 1.0, "", True, ""), # Do something with bitmask!
    # Register(0x14, "Elpanna", 2, 1.0, "", True, "M9.1.1"),
    # Register(0x14, "Fläkthastighet", 2, 1.0, "", True, "", 0, 3), ##TODO menu
    # Register(0x14, "Avfrostning", 2, 1.0, "", True, ""),
    Register(
        0x15, "Driftläge auto", 2, 1.0, "", True, "M8.2.1"
    ),  ## Undersök, ska vara Ja
    Register(0x16, "Högtryckslarm", 2, 1.0, "", False, ""),
    # Register(0x16, "Lågtryckslarm", 2, 1.0, "", False, ""),
    # Register(0x16, "Temperaturbegränsarlarm", 2, 1.0, "", False, ""),
    # Register(0x16, "Filterlarm", 2, 1.0, "", False, ""),
    # Register(0x16, "Givarfel", 2, 1.0, "", False, ""),
    # Register(0x16, "Frånluftstemperaturslarm", 2, 1.0, "", False, ""),
    Register(0x17, "Strömförbrukning L1", 2, 10.0, "A", False, "M8.3.3"),
    Register(0x18, "Strömförbrukning L2", 2, 10.0, "A", False, "M8.3.4"),
    Register(0x19, "Strömförbrukning L3", 2, 10.0, "A", False, "M8.3.5"),
    Register(0x1A, "Fabriksinställning", 1, 1.0, "", True, "M9.1.6"),
    Register(0x1B, "Antal starter kompressor", 2, 1.0, "", False, "M5.4"),
    Register(0x1C, "Drifttid kompressor", 2, 1.0, "h", False, "M5.5"),
    Register(0x1D, "Tidfaktor elpatron", 2, 1.0, "", False, "M9.1.8"),
    Register(0x1E, "Maxtemperatur framledning", 1, 1.0, "°C", True, "M2.4", 10, 65),
    Register(0x1F, "Mintemperatur framledning", 1, 1.0, "°C", True, "M2.3", 10, 65),
    # Register(0x22, "Kompensering yttre", 1, 1.0, "", True, "M2.5", -10, 10), # UNUSED
    Register(
        0x24, "Intervall per. extra VV", 1, 1.0, "dygn", True, "M1.3", 0, 90
    ),  ## UNDERSÖK -> 14
    Register(0x25, "Starta om FIGHTER360P", 2, 1.0, "", True, ""),
    # Register(0x25, "Extern larmsignal 1 (RCU DI 1)", 2, 1.0, "", False, ""),
    # Register(0x25, "Extern larmsignal 2 (RCU DI 2)", 2, 1.0, "", False, ""),
    Register(0x26, "RCU förskjutning 1 (Reg1)", 1, 1.0, "", True, "M2.7", -10, 10),
    Register(0x28, "Larmnivå frånluftstemperatur", 1, 1.0, "°C", True, "M5.6", 0, 20),
    Register(0x29, "Klocka: år", 1, 1.0, "", False, "M7.1"),
    Register(0x2A, "Klocka: månad", 1, 1.0, "", False, "M7.1"),
    Register(0x2B, "Klocka: dag", 1, 1.0, "", False, "M7.1"),
    Register(0x2C, "Klocka: timma", 1, 1.0, "", False, "M7.2"),
    Register(0x2D, "Klocka: minut", 1, 1.0, "", False, "M7.2"),
    Register(0x2E, "Klocka: sekund", 1, 1.0, "", False, "M7.2"),
]




