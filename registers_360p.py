"""
Register definitions for Nibe 360P Heat Pump

NOTE: These are example registers. You will need to replace these with
the actual register addresses and definitions from your Nibe 360P documentation.

Register address format typically:
- 4xxxx = Holding registers (read/write)
- 3xxxx = Input registers (read-only)
- Some systems use other ranges

Size types:
- 'u8' = unsigned 8-bit (0-255)
- 's8' = signed 8-bit (-128 to 127)
- 'u16' = unsigned 16-bit (0-65535)
- 's16' = signed 16-bit (-32768 to 32767)
- 'u32' = unsigned 32-bit (0-4294967295)
- 's32' = signed 32-bit (-2147483648 to 2147483647)

Factor: The value is divided by this factor (e.g., factor=10 means value 235 = 23.5)
"""

from main import Register

# Temperature sensors
NIBE_360P_REGISTERS = [
    # === TEMPERATURE SENSORS ===
    # Outdoor temperature sensor
    Register(40004, "BT1 Outdoor Temperature", "s16", 10.0, "°C", False),
    # Supply/forward temperatures
    Register(40008, "BT2 Supply Temperature S1", "s16", 10.0, "°C", False),
    # Return temperature
    Register(40012, "BT3 Return Temperature", "s16", 10.0, "°C", False),
    # Hot water temperatures
    Register(40013, "BT7 Hot Water Temperature", "s16", 10.0, "°C", False),
    Register(40014, "BT6 Hot Water Charge Temperature", "s16", 10.0, "°C", False),
    # Brine/source temperatures (if applicable)
    Register(40015, "BT10 Brine In Temperature", "s16", 10.0, "°C", False),
    Register(40016, "BT11 Brine Out Temperature", "s16", 10.0, "°C", False),
    # Average outdoor temperature
    Register(40033, "BT1 Average Outdoor Temperature", "s16", 10.0, "°C", False),
    # Room temperature (if RMU connected)
    Register(40033, "BT50 Room Temperature", "s16", 10.0, "°C", False),
    # === OPERATIONAL DATA ===
    # Degree minutes (climate control parameter)
    Register(43005, "Degree Minutes", "s16", 10.0, "DM", False),
    # Calculated supply temperature
    Register(43009, "Calculated Supply Temperature S1", "s16", 10.0, "°C", False),
    # Compressor frequency
    Register(43136, "Compressor Frequency Actual", "s16", 1.0, "Hz", False),
    # Operating times
    Register(43081, "Total Hot Water Operating Time", "s32", 10.0, "h", False),
    Register(43084, "Total Compressor Operating Time", "s32", 10.0, "h", False),
    # Compressor starts
    Register(43086, "Number of Compressor Starts", "s32", 1.0, "", False),
    # === STATUS AND ALARMS ===
    # Alarm status
    Register(45001, "Alarm Number", "s16", 1.0, "", False),
    # Software version
    Register(43001, "Software Version", "s16", 1.0, "", False),
    # === SETTINGS (READ/WRITE) ===
    # Priority: 0=Off, 10=Hot water, 20=Heat, 30=Pool, 40=Transfer, 60=Cooling
    Register(47011, "Priority", "s8", 1.0, "", True),
    # Hot water settings
    Register(47041, "Hot Water Comfort Mode", "s8", 1.0, "", True),
    Register(47043, "Hot Water Setpoint Normal", "s16", 10.0, "°C", True),
    Register(47044, "Hot Water Setpoint Luxury", "s16", 10.0, "°C", True),
    # Heating curve settings
    Register(47398, "Temporary Lux", "s8", 1.0, "", True),
    Register(47007, "Heat Curve S1", "s16", 10.0, "", True),
    Register(47009, "Heat Curve Offset S1", "s16", 10.0, "°C", True),
    # Room temperature setpoint
    Register(47398, "Room Setpoint S1", "s16", 10.0, "°C", True),
    # Fan speed (if applicable)
    Register(47260, "Fan Mode", "s8", 1.0, "", True),
    # === ADDITIONAL SENSORS (model dependent) ===
    # Add more registers based on your specific 360P configuration
]

# Register groups for easy access
TEMPERATURE_REGISTERS = [40004, 40008, 40012, 40013, 40014, 40015, 40016, 40033]
OPERATIONAL_REGISTERS = [43005, 43009, 43136, 43081, 43084, 43086]
SETTINGS_REGISTERS = [47011, 47041, 47043, 47044, 47398, 47007, 47009]

# Common register addresses (you may need to adjust these)
IMPORTANT_REGISTERS = {
    "outdoor_temp": 40004,
    "supply_temp": 40008,
    "return_temp": 40012,
    "hot_water_temp": 40013,
    "degree_minutes": 43005,
    "compressor_freq": 43136,
    "priority": 47011,
    "alarm": 45001,
}


def get_register_by_name(name: str) -> int:
    """Get register address by common name"""
    return IMPORTANT_REGISTERS.get(name)


def get_temperature_registers() -> list:
    """Get all temperature sensor register addresses"""
    return TEMPERATURE_REGISTERS


def get_writable_registers() -> list:
    """Get list of writable register addresses"""
    return [reg.address for reg in NIBE_360P_REGISTERS if reg.writable]


if __name__ == "__main__":
    # Print register summary
    print("Nibe 360P Register Definitions")
    print("=" * 70)
    print(f"Total registers: {len(NIBE_360P_REGISTERS)}")
    print(f"Writable registers: {len(get_writable_registers())}")
    print("\nRegister List:")
    print("-" * 70)

    for reg in NIBE_360P_REGISTERS:
        access = "RW" if reg.writable else "R"
        print(
            f"{reg.address:5d} | {access:2s} | {reg.size:4s} | {reg.name:40s} | {reg.unit}"
        )
