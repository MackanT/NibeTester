"""
Nibe Fighter 360P Register Definitions
Based on nibepi models and Nibe documentation
"""
from dataclasses import dataclass
from typing import Optional, Literal


RegisterSize = Literal["s8", "u8", "s16", "u16", "s32", "u32"]
RegisterMode = Literal["R", "R/W"]


@dataclass
class NibeRegister:
    """Definition of a Nibe register"""
    register: int
    title: str
    unit: str
    size: RegisterSize
    factor: float  # Divide raw value by this
    mode: RegisterMode
    min: Optional[float] = None
    max: Optional[float] = None
    info: str = ""
    
    def decode_value(self, raw_value: int) -> float:
        """Convert raw register value to actual value"""
        return raw_value / self.factor
    
    def encode_value(self, value: float) -> int:
        """Convert actual value to raw register value"""
        return int(value * self.factor)
    
    def format_value(self, raw_value: int) -> str:
        """Format value with unit"""
        value = self.decode_value(raw_value)
        return f"{value:.1f} {self.unit}"


# Nibe Fighter 360P Register Database
# Temperature registers (scaled by 10)
FIGHTER_360P_REGISTERS = {
    # BT sensors (temperatures scaled by 10)
    40004: NibeRegister(
        register=40004,
        title="BT1 Outdoor Temperature",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="External outdoor temperature sensor"
    ),
    40008: NibeRegister(
        register=40008,
        title="BT2 Supply Temperature S1",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Supply line temperature system 1"
    ),
    40012: NibeRegister(
        register=40012,
        title="BT3 Return Temperature S1",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Return line temperature system 1"
    ),
    40013: NibeRegister(
        register=40013,
        title="BT7 Hot Water Top",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Hot water tank top temperature"
    ),
    40014: NibeRegister(
        register=40014,
        title="BT6 Hot Water Load",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Hot water charging temperature"
    ),
    40015: NibeRegister(
        register=40015,
        title="BT15 Brine In Temperature",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Brine inlet temperature"
    ),
    40016: NibeRegister(
        register=40016,
        title="BT17 Brine Out Temperature",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Brine outlet temperature"
    ),
    40017: NibeRegister(
        register=40017,
        title="BT10 Brine Average Temperature",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Average brine temperature"
    ),
    40018: NibeRegister(
        register=40018,
        title="BT11 Condenser In",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Condenser inlet temperature"
    ),
    40019: NibeRegister(
        register=40019,
        title="BT12 Condenser Out",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Condenser outlet temperature"
    ),
    40022: NibeRegister(
        register=40022,
        title="BT25 External Supply",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="External supply temperature"
    ),
    40033: NibeRegister(
        register=40033,
        title="Degree Minutes",
        unit="DM",
        size="s16",
        factor=10.0,
        mode="R",
        info="Accumulated degree minutes for heating curve"
    ),
    40071: NibeRegister(
        register=40071,
        title="BT50 Room Temperature S1",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R",
        info="Room temperature sensor system 1"
    ),
    
    # Status registers (no scaling)
    43001: NibeRegister(
        register=43001,
        title="Software Version",
        unit="",
        size="u16",
        factor=1.0,
        mode="R",
        info="Heat pump software version"
    ),
    43084: NibeRegister(
        register=43084,
        title="Alarm Number",
        unit="",
        size="u16",
        factor=1.0,
        mode="R",
        info="Current alarm code (0 = no alarm)"
    ),
    43181: NibeRegister(
        register=43181,
        title="Priority",
        unit="",
        size="u8",
        factor=1.0,
        mode="R",
        info="Current operation priority"
    ),
    
    # Compressor data (scaled by 10)
    43424: NibeRegister(
        register=43424,
        title="Compressor Frequency Actual",
        unit="Hz",
        size="u8",
        factor=1.0,
        mode="R",
        info="Current compressor frequency"
    ),
    43427: NibeRegister(
        register=43427,
        title="Compressor Speed",
        unit="%",
        size="u8",
        factor=1.0,
        mode="R",
        info="Compressor speed percentage"
    ),
    
    # Control settings (Read/Write)
    47011: NibeRegister(
        register=47011,
        title="BT1 Outdoor Temp Adjustment",
        unit="°C",
        size="s16",
        factor=10.0,
        mode="R/W",
        min=-10.0,
        max=10.0,
        info="Adjustment for outdoor temperature sensor"
    ),
    47136: NibeRegister(
        register=47136,
        title="Hot Water Production",
        unit="",
        size="u8",
        factor=1.0,
        mode="R/W",
        min=0.0,
        max=1.0,
        info="Hot water production: 0=Off, 1=On"
    ),
    47138: NibeRegister(
        register=47138,
        title="Heating",
        unit="",
        size="u8",
        factor=1.0,
        mode="R/W",
        min=0.0,
        max=1.0,
        info="Heating: 0=Off, 1=On"
    ),
}


def get_register_info(address: int) -> Optional[NibeRegister]:
    """Get register definition by address"""
    return FIGHTER_360P_REGISTERS.get(address)


def get_all_temperature_registers() -> list[int]:
    """Get all temperature sensor register addresses"""
    return [
        addr for addr, reg in FIGHTER_360P_REGISTERS.items()
        if "BT" in reg.title and reg.unit == "°C"
    ]


def get_writable_registers() -> list[int]:
    """Get all writable register addresses"""
    return [
        addr for addr, reg in FIGHTER_360P_REGISTERS.items()
        if reg.mode == "R/W"
    ]


if __name__ == "__main__":
    # Display register database
    print("Nibe Fighter 360P Register Database")
    print("=" * 80)
    
    print("\nTemperature Sensors:")
    for addr in get_all_temperature_registers():
        reg = FIGHTER_360P_REGISTERS[addr]
        print(f"  {addr:5d} - {reg.title}")
    
    print("\nWritable Registers:")
    for addr in get_writable_registers():
        reg = FIGHTER_360P_REGISTERS[addr]
        print(f"  {addr:5d} - {reg.title} ({reg.min} to {reg.max})")
    
    print(f"\nTotal registers: {len(FIGHTER_360P_REGISTERS)}")
