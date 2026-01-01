# Bitmask Register Configuration

## Overview
Some registers return multiple boolean values encoded in a single byte or word using bitmasks. For example, register `0x13` may contain status flags for multiple components (compressor, circulation pumps, etc.).

## YAML Configuration

### Example: Status Register with Multiple Flags

```yaml
pumps:
  nibe_360P:
    model: nibe_360P
    name: "Nibe 360P"
    baudrate: 19200
    bit_mode: 9
    parity: "MARK"
    cmd_data: 0xC0
    master_addr: 0x24
    rcu_addr: 0x14
    ack: 0x06
    enq: 0x05
    nak: 0x15
    etx: 0x03
    
    registers:
      # Regular register (numeric value)
      - index: 0x01
        name: "Utetemperatur"
        size: 2
        factor: 10.0
        unit: "°C"
        writable: false
      
      # Bitmask register (multiple flags with custom mappings)
      - index: 0x13
        name: "Status Flags"
        size: 1
        factor: 1.0
        unit: ""
        writable: false
        bit_fields:
          - name: "Kompressor"
            mask: 0x02        # Bit 1
            sort_order: 1     # Display order
            value_map:
              0: "OFF"
              1: "ON"
          
          - name: "Cirkulationspump 1"
            mask: 0x40        # Bit 6
            sort_order: 2
            value_map:
              0: "OFF"
              1: "ON"
          
          - name: "Cirkulationspump 2"
            mask: 0x01        # Bit 0
            sort_order: 3
            value_map:
              0: "OFF"
              1: "ON"
      
      # Multi-bit field example (3 bits = values 0-7)
      - index: 0x14
        name: "Operating Mode"
        size: 1
        factor: 1.0
        unit: ""
        writable: false
        bit_fields:
          - name: "Heat Mode"
            mask: 0x07        # Bits 0-2 (3 bits = 0-7)
            sort_order: 1
            value_map:
              0: "Off"
              1: "Auto"
              2: "Manual"
              3: "Economy"
              4: "Boost"
              5: "Away"
              6: "Reserved"
              7: "Error"
          
          - name: "Fan Speed"
            mask: 0x38        # Bits 3-5 (3 bits = 0-7)
            sort_order: 2
            value_map:
              0: "Off"
              1: "Low"
              2: "Medium"
              3: "High"
              4: "Auto"
```

## Required Fields for Bit Fields

Each bit field entry must have:
- `name`: Descriptive name for the flag
- `mask`: Hex value of the bitmask (e.g., `0x02`, `0x07`, `0x38`)
- `sort_order`: Integer determining display order (1, 2, 3, etc.)

Optional fields:
- `value_map`: Dictionary mapping integer values to text descriptions (e.g., `{0: "OFF", 1: "ON"}`)
  - If not provided, the raw integer value will be displayed

## How It Works

### Single-Bit Boolean Values
When register `0x13` returns value `0x43` (binary: `01000011`):

1. **Cirkulationspump 2** (mask `0x01`, sort_order 3): `0x43 & 0x01 = 0x01` → shift 0 → value `1` → **"ON"**
2. **Kompressor** (mask `0x02`, sort_order 1): `0x43 & 0x02 = 0x02` → shift 1 → value `1` → **"ON"**
3. **Cirkulationspump 1** (mask `0x40`, sort_order 2): `0x43 & 0x40 = 0x40` → shift 6 → value `1` → **"ON"**

Display is sorted by `sort_order` (1, 2, 3), not by mask value.

### Multi-Bit Integer Values
When register `0x14` returns value `0x1A` (binary: `00011010`):

1. **Heat Mode** (mask `0x07` = bits 0-2): `0x1A & 0x07 = 0x02` → shift 0 → value `2` → **"Manual"**
2. **Fan Speed** (mask `0x38` = bits 3-5): `0x1A & 0x38 = 0x18` → shift 3 → value `3` → **"High"**

The code automatically:
- Applies the mask
- Shifts right by counting trailing zeros in mask
- Looks up the value in `value_map`
- Falls back to displaying the raw integer if no mapping exists

### Code Usage

```python
# Read all parameters
pump.read_parameters_once()

# Access individual bit fields
kompressor_on = pump.get_bit_field(0x13, "Kompressor")
pump1_on = pump.get_bit_field(0x13, "Cirkulationspump 1")
pump2_on = pump.get_bit_field(0x13, "Cirkulationspump 2")

# Get all bit fields
all_bits = pump.get_all_bit_fields()
# Returns: {
#   "0x13:Kompressor": True,
#   "0x13:Cirkulationspump 1": True,
#   "0x13:Cirkulationspump 2": True
# }
```

### Output Display
```
SUCCESS! Captured 5 parameters:
===============================

[01] Utetemperatur...................    12.5 °C   
[02] Inomhustemperatur...............    21.3 °C   
[13] Status Flags
    [13.1] Kompressor.................... ON
    [13.2] Cirkulationspump 1............ ON
    [13.3] Cirkulationspump 2............ OFF
[14] Operating Mode
    [14.1] Heat Mode..................... Manual
    [14.2] Fan Speed..................... High
```

Note: Bit fields are sorted by `sort_order`, not by their position in the YAML or mask value.

## Bitmask Reference

Common bitmask values:
- Bit 0: `0x01` (0000 0001)
- Bit 1: `0x02` (0000 0010)
- Bit 2: `0x04` (0000 0100)
- Bit 3: `0x08` (0000 1000)
- Bit 4: `0x10` (0001 0000)
- Bit 5: `0x20` (0010 0000)
- Bit 6: `0x40` (0100 0000)
- Bit 7: `0x80` (1000 0000)

For 2-byte registers (size: 2), you can use masks up to `0xFFFF`.

## Important Notes

1. **Register still needs basic fields**: Even when using `bit_fields`, the register must have `size`, `factor`, `unit`, `writable` set.

2. **Factor is ignored**: For bitmask registers, the `factor` field is not used (set to `1.0`).

3. **Storage**: Bit field values are stored separately from regular parameter values using composite keys like `"0x13:Kompressor"`.

4. **Validation**: The code validates that each bit field has `name` and `mask` fields, and that the mask value is valid.
