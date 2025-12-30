# Nibe F-Series Protocol Findings

## Research Summary
Analyzed the [nibepi GitHub repository](https://github.com/anerdins/nibepi) which is a production-proven implementation for Nibe F-series heat pumps.

## Key Findings

### 1. **Pump DOES Transmit Automatically**
The Nibe Fighter 360P is NOT purely request/response. It broadcasts data continuously:

- **Announcement messages (0x6D/109)**: Pump identification on startup
- **RMU data messages (0x62/98)**: Automatic updates from connected RMU40 modules
- **Data responses (0x68/104)**: Register data messages
- **Read tokens (0x69/105)**: Pump asking "do you want to read something?"
- **Write tokens (0x6B/107)**: Pump asking "do you want to write something?"

### 2. **Confirmed Serial Settings**
From nibepi `backend.js` line 56:
```javascript
myPort = new serialport(portName, 9600);
```

**CORRECT SETTINGS:**
- **Baudrate: 9600** (NOT 57600)
- **Parity: EVEN** (8E1: 8 data bits, even parity, 1 stop bit)
- **Data bits: 8**
- **Stop bits: 1**

### 3. **Framing Protocol**
The nibepi code reveals F-series uses **0x5C** as the frame start byte, NOT 0xC0:

```javascript
// backend.js line 125-128
if(fs_start===false) {
    if(data[0]===0x5C) {  // F-series start byte
        fs_start = true;
    }
}
```

**Our mistake:** We were looking for 0xC0, which appears to be a different encoding or end marker.

### 4. **Message Types**
From backend.js `makeResponse()` function:

| Byte 3 Value | Hex | Meaning |
|-------------|-----|---------|
| 0x60 | 96 | RMU send data request |
| 0x62 | 98 | RMU data broadcast |
| 0x63 | 99 | RMU data acknowledge |
| 0x68 | 104 | Data response |
| 0x69 | 105 | Read token (pump asking if you want to read) |
| 0x6B | 107 | Write token (pump asking if you want to write) |
| 0x6D | 109 | Announcement (pump ID/model) |
| 0xEE | 238 | RMU version request |

### 5. **Expected ACK Responses**
The pump expects **0x06** (ACK) responses to its broadcasts:
```javascript
const ack = [0x06];
myPort.write(ack);
```

### 6. **Frame Structure**
```
[0x5C] [ADDR] [CMD] [LEN] [DATA...] [CHECKSUM]
  ^       ^     ^     ^      ^          ^
  |       |     |     |      |          XOR of bytes 2 to (4+LEN)
  |       |     |     |      Variable length data
  |       |     |     Data length
  |       |     Message type (0x68, 0x69, etc)
  |       Address (0x19, 0x1A, 0x1B, 0x1C for RMU systems, 0x20 for pump)
  Start byte (F-series = 0x5C)
```

## Why We Were Getting Wrong Results

1. **Wrong Baud Rate**: We tested 57600 - should have been 9600
2. **Wrong Start Byte**: We looked for 0xC0 - should look for 0x5C
3. **Wrong Parity**: We tried NONE - should be EVEN

This explains:
- Data floods at "9600": We were actually at wrong baud, receiving garbage
- Repeating patterns: Phase-locked to wrong clock rate
- Invalid checksums: Wrong framing means we're not finding real message boundaries

## Next Steps

1. **Test 9600/EVEN** with updated `passive_listen.py`
2. **Look for 0x5C** as frame start, not 0xC0
3. **Update all our code** to use correct framing
4. **Implement ACK responses** (0x06) when pump broadcasts data

## References

- [nibepi backend.js](https://github.com/anerdins/nibepi/blob/main/backend.js) - Core serial handling
- [nibepi README](https://github.com/anerdins/nibepi/blob/main/README.md) - Connection instructions
- Nibe installation manual: 031725-6.pdf (mentioned in nibepi docs)
