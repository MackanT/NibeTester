# Nibe 360P Addressing Information

## Key Finding: Different Addressing Scheme!

The Nibe 360P uses a **different addressing scheme** than the F-series pumps.

### Addressing Rule

```
Register Number in Manual = Address in Code + 1
```

Or inversely:

```
Address in Code = Register Number in Manual - 1
```

### Example

From your data:
- **Register 2** = "Outdoor Temperature" (Menu M4.0)
- **Address to use in code** = 1 (because 2 - 1 = 1)

### Confirmed Working

✅ **Register 2 (Outdoor Temperature)**
- Manual: Register 2
- Code address: `1`
- Type: Signed int 16
- Factor: 0.1 (divide by 10)
- Unit: °C
- Menu: M4.0
- Access: Read-only

### How to Use

When you find a register in your 360P manual:

1. Look up the register number (e.g., Register 5)
2. Subtract 1 to get the address (5 - 1 = 4)
3. Add to `registers_360p.py`:

```python
Register(4, "Register Name", "s16", 10.0, "°C", False)
         ↑
    Address = Register Number - 1
```

### Testing

To test reading register 2 (outdoor temp):

```bash
python test_setup.py
```

The test will now attempt to read **address 1** (register 2).

### Next Steps

1. ✅ Test reading address 1 (register 2 - outdoor temp)
2. Map your other registers from the 360P manual
3. Update `registers_360p.py` with correct addresses
4. Remember: **Address = Register Number - 1**

### Examples of Mapping

| Manual Register | Description | Code Address |
|----------------|-------------|--------------|
| 1 | Register 1 | 0 |
| 2 | Outdoor Temp | 1 |
| 3 | Supply Temp | 2 |
| 4 | Return Temp | 3 |
| 5 | Hot Water | 4 |
| ... | ... | ... |
| N | Register N | N-1 |

### Important Notes

- This is **different** from Modbus 4xxxx addressing used by F-series
- The 360P uses **simple sequential addressing** starting at 0
- Always use (register_number - 1) when adding to `registers_360p.py`
- The protocol layer sends the address directly, not the register number
