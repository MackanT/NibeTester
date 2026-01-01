# Nibe 360P Write Protocol - Issues & Fixes

## Critical Issues Found & Fixed

### ✅ Issue 1: Incorrect Data Length Calculation
**Problem:** The length field was including the checksum byte  
**Forum says:** "11 är längden av datat som kommer efter ländbyten, 0x11=17. **Obs! csum ej inkluderat.**"

**Fixed:**
```python
# WRONG (before):
data_length = len(data_payload) + 1  # +1 for checksum ❌

# CORRECT (after):
data_length = len(data_payload)  # Checksum NOT included ✅
```

### ✅ Issue 2: Missing Buffer Clear After ENQ
**Problem:** Old data in the serial buffer could interfere with ACK detection  
**Fixed:** Added `serial.reset_input_buffer()` after sending ENQ and before waiting for ACK

### ✅ Issue 3: Timing Too Aggressive
**Problem:** Delays were too short (50-100ms)  
**Forum emphasizes:** "**Det gäller dock att svara i tid!!!**" (You must respond in time!)

**Fixed:**
- After ENQ: Increased to 100ms
- After write packet: Increased to 200ms

### ✅ Issue 4: YAML Configuration Error
**Problem:** Register 0x0B had contradictory settings:
- `size: 1` (1 byte)
- `data_type: "s16"` (16-bit signed) ❌

**Fixed:** Changed `data_type` to `"s8"` (8-bit signed) to match `size: 1`

### ✅ Issue 5: Insufficient Debug Logging
**Added:** More detailed logging to see exactly what bytes are being sent/received

---

## Protocol Specification (from Forum Post)

### Write Sequence
```
1. Master: *00 *14           (Addresses RCU, 9th bit set)
2. RCU:    05                (ENQ = "I want to write", 9th bit clear)
3. Master: 06                (ACK = "OK, send your data")
4. RCU:    C0 00 14 <len> <data> <xor>  (9th bit clear)
5. Master: 06 or 15          (ACK if OK, NAK if checksum error)
6. RCU:    *03               (ETX = "Done", 9th bit set)
```

### Packet Format for Write
```
C0          - CMD_DATA (always 0xC0 for RCU)
00          - Fixed second byte
14          - Sender address (RCU = 0x14)
<len>       - Length of data payload (NOT including checksum!)
00          - Separator before parameter
<param_idx> - Parameter index (e.g., 0x0B)
<value>     - Value bytes (1 or 2 bytes depending on register size)
<xor>       - XOR checksum of ALL previous bytes
```

### Example Write: Parameter 0x14 = 0x0145
```
C0 00 14 04 00 14 01 45 <XOR>
         ^^  Data length = 4 bytes (00 14 01 45)
            00 - Separator
            14 - Parameter index
            01 45 - Value (2 bytes: HIGH=0x01, LOW=0x45)
```

### Checksum Calculation
```python
checksum = 0
for byte in [C0, 00, 14, 04, 00, 14, 01, 45]:
    checksum ^= byte
# checksum is NOT included in length field!
```

---

## Testing Checklist

- [ ] Read parameters successfully (baseline test)
- [ ] Write attempt shows proper addressing (0x00 0x14)
- [ ] ENQ (0x05) is sent correctly
- [ ] Pump responds with ACK (0x06) after ENQ
- [ ] Write packet has correct length field (data only, no checksum)
- [ ] Write packet has correct checksum (XOR of all bytes from C0)
- [ ] Pump responds with ACK (0x06) after write packet
- [ ] ETX (0x03) is sent with MARK parity (9th bit = 1)
- [ ] Parameter value changes in next read cycle

---

## Common Problems & Solutions

### Pump doesn't respond to ENQ
- **Check:** Is RCU mode enabled in pump menu?
- **Check:** Are you responding too slowly to *00 *14 addressing?
- **Try:** Increase buffer size or decrease other processing

### Pump sends NAK after write packet
- **Cause:** Checksum error
- **Check:** Verify checksum includes ALL bytes from C0 to last data byte
- **Check:** Length field does NOT include checksum

### Write seems successful but value doesn't change
- **Check:** Value is within min/max bounds
- **Check:** Register is actually writable (some are read-only despite protocol support)
- **Check:** Value encoding matches register size (1 or 2 bytes)
- **Check:** Factor is applied correctly (e.g., temp sensors use factor=10.0)

### Timing issues / intermittent failures
- **Try:** Increase delays between steps
- **Try:** Clear input buffer before waiting for responses
- **Check:** Serial port settings (19200 baud, MARK parity initially)

---

## 9-Bit Mode Implementation

This protocol uses the 9th bit for framing:
- **MARK parity (9th bit = 1):** Used for addressing bytes (*00, *14, *03)
- **SPACE parity (9th bit = 0):** Used for all data bytes

Your implementation switches parity modes:
```python
# For normal data (ACK, ENQ, data packets):
serial.parity = serial.PARITY_SPACE  # 9th bit = 0

# For addressing/control bytes (*00, *14, *03):
serial.parity = serial.PARITY_MARK   # 9th bit = 1
```

---

## Next Steps

1. Test with a simple 1-byte register (like 0x0B Kurvlutning)
2. Monitor with oscilloscope or logic analyzer if issues persist
3. Enable DEBUG logging to see all bytes
4. Compare timing with a working RCU device if available

---

## References
- Forum post: 2007 Swedish heat pump forum (provided by user)
- Pump model: NIBE FIGHTER 360P
- Protocol: Custom 9-bit RS-485 (NOT Modbus)
